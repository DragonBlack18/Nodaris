import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from api.config import API_BASE_URL, API_HOST, API_PORT
from api.logging_config import get_logger
from api.paths import WATCHDOG_STATE_FILE


HEALTH_URL = f"{API_BASE_URL}/health"
CORE_TASK_NAME = "NODARIS Core"

ENGINE_ERROR_RESTART_THRESHOLD = 3
DEGRADED_CONFIRM_SECONDS = 5
DEGRADED_RESTART_COOLDOWN_SECONDS = 300
CORE_STOP_TIMEOUT_SECONDS = 10
CORE_START_VERIFY_SECONDS = 20
HEALTH_REQUEST_TIMEOUT_SECONDS = 5.0
HEALTH_TIMEOUT_GRACE_SECONDS = 60.0

CRITICAL_HEALTH_REASONS = {
    "engine_task_not_running",
    "scan_stale",
}
REPLACE_RUNNING_CORE_REASONS = {
    "engine_task_not_running",
    "scan_stale",
    "engine_errors_threshold",
    "monitor_engine_not_running",
    "health_status_not_ok",
}

logger = get_logger("watchdog", "monitorping-watchdog.log")


def evaluate_core_health(data: dict) -> tuple[bool, str]:
    if data.get("service") != "monitorping-api":
        return False, "unexpected_service"
    if data.get("monitor_engine") != "running":
        return False, "monitor_engine_not_running"
    if data.get("status") != "ok":
        return False, "health_status_not_ok"

    reasons = data.get("health_reasons", [])
    if not isinstance(reasons, list):
        reasons = []
    for reason in reasons:
        if reason in CRITICAL_HEALTH_REASONS:
            return False, str(reason)

    try:
        consecutive_errors = int(data.get("consecutive_engine_errors", 0))
    except (TypeError, ValueError):
        consecutive_errors = 0

    if consecutive_errors >= ENGINE_ERROR_RESTART_THRESHOLD:
        return False, "engine_errors_threshold"
    return True, "healthy"


def check_core_health() -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(
            HEALTH_URL,
            timeout=HEALTH_REQUEST_TIMEOUT_SECONDS,
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not isinstance(data, dict):
            return False, "invalid_health_payload"
        return evaluate_core_health(data)
    except urllib.error.HTTPError as exc:
        return False, f"health_http_error:{exc.code}"
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return False, "health_request_timeout"
        if isinstance(reason, ConnectionRefusedError):
            return False, "health_connection_refused"
        return False, f"health_request_failed: {exc}"
    except (TimeoutError, socket.timeout):
        return False, "health_request_timeout"
    except ConnectionRefusedError:
        return False, "health_connection_refused"
    except (ValueError, OSError) as exc:
        return False, f"health_request_failed: {exc}"


def core_is_healthy() -> bool:
    healthy, _ = check_core_health()
    return healthy


def recovery_mode_for_reason(reason: str) -> str:
    if reason in {"health_request_timeout", "health_connection_refused"}:
        return "start"
    if reason.startswith("health_request_failed"):
        return "start"
    if reason in REPLACE_RUNNING_CORE_REASONS:
        return "replace"
    return "manual"


def recovery_mode_for_current_state(reason: str) -> str:
    mode = recovery_mode_for_reason(reason)
    if mode != "start":
        return mode

    task_state = _get_core_task_state()
    if task_state and task_state.lower() == "running":
        return "replace"

    processes = _get_verified_core_processes()
    if processes:
        return "replace"

    if _core_port_is_open():
        return "manual"
    return "start"


def _load_watchdog_state() -> dict:
    try:
        if not WATCHDOG_STATE_FILE.exists():
            return {}
        with WATCHDOG_STATE_FILE.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, UnicodeError):
        logger.exception("Falha ao ler estado persistente do Watchdog.")
        return {}


def _save_watchdog_state(state: dict):
    try:
        WATCHDOG_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = WATCHDOG_STATE_FILE.with_suffix(".tmp")
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(state, file, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_file, WATCHDOG_STATE_FILE)
    except OSError:
        logger.exception("Falha ao persistir estado do Watchdog.")


def _cooldown_remaining_seconds() -> float:
    state = _load_watchdog_state()
    try:
        last_restart = float(state.get("last_degraded_restart_at"))
    except (TypeError, ValueError):
        return 0.0
    return max(
        0.0,
        DEGRADED_RESTART_COOLDOWN_SECONDS - (time.time() - last_restart),
    )


def _mark_degraded_restart_attempt(reason: str):
    state = _load_watchdog_state()
    state["last_degraded_restart_at"] = time.time()
    state["last_degraded_restart_reason"] = reason
    _save_watchdog_state(state)


def _record_health_timeout_failure() -> float:
    state = _load_watchdog_state()
    now = time.time()

    try:
        first_seen = float(state.get("health_timeout_first_seen_at"))
    except (TypeError, ValueError):
        first_seen = now
    try:
        last_seen = float(state.get("health_timeout_last_seen_at"))
    except (TypeError, ValueError):
        last_seen = None

    if (
        last_seen is None
        or now - last_seen > HEALTH_TIMEOUT_GRACE_SECONDS * 2
        or first_seen > now
    ):
        first_seen = now

    state["health_timeout_first_seen_at"] = first_seen
    state["health_timeout_last_seen_at"] = now
    _save_watchdog_state(state)
    return max(0.0, now - first_seen)


def _clear_health_timeout_failure():
    state = _load_watchdog_state()
    changed = False
    for key in (
        "health_timeout_first_seen_at",
        "health_timeout_last_seen_at",
    ):
        if key in state:
            state.pop(key, None)
            changed = True
    if changed:
        _save_watchdog_state(state)


def _core_port_is_open() -> bool:
    try:
        with socket.create_connection((API_HOST, API_PORT), timeout=0.5):
            return True
    except OSError:
        return False


def _is_verified_core_command(command_line: str) -> bool:
    command_line = str(command_line).strip()

    if re.search(
        r"(?:^|\s)-m\s+core\.main(?:\s|$)",
        command_line,
        flags=re.IGNORECASE,
    ):
        return True

    if not getattr(sys, "frozen", False):
        return False

    match = re.match(
        r'^\s*"([^"]+\.exe)"\s*(.*)$',
        command_line,
        flags=re.IGNORECASE,
    ) or re.match(
        r"^\s*(.+?\.exe)\s*(.*)$",
        command_line,
        flags=re.IGNORECASE,
    )
    if match is None:
        return False

    executable = os.path.normcase(os.path.abspath(match.group(1)))
    expected = os.path.normcase(os.path.abspath(sys.executable))
    arguments = match.group(2).strip().lower()
    return executable == expected and arguments in ("", "--core")


def _powershell_json(command: str):
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=creation_flags,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None
    output = (result.stdout or "").strip()
    if not output:
        return []
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def _get_core_task_state() -> str | None:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    command = (
        "$task = Get-ScheduledTask "
        f"-TaskName '{CORE_TASK_NAME}' -ErrorAction SilentlyContinue; "
        "if ($null -ne $task) { $task.State.ToString() }"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=creation_flags,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        logger.exception("Falha ao consultar estado da tarefa '%s'.", CORE_TASK_NAME)
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def _get_verified_core_processes() -> list[dict] | None:
    command = (
        "$processes = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
        "Where-Object { "
        "($_.Name -match '^pythonw?\\.exe$' -and $_.CommandLine -match "
        "'(?i)(?:^|\\s)-m\\s+core\\.main(?:\\s|$)') -or "
        "$_.Name -ieq 'NODARIS Core.exe' } | ForEach-Object { "
        "[PSCustomObject]@{ pid = $_.ProcessId; parent_pid = $_.ParentProcessId; "
        "command_line = $_.CommandLine } }); "
        "$processes | ConvertTo-Json -Compress"
    )
    data = _powershell_json(command)
    if data is None:
        logger.error("Falha ao localizar processos do Core.")
        return None
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return None

    processes = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            pid = int(item["pid"])
            parent_pid = int(item.get("parent_pid") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        command_line = str(item.get("command_line") or "")
        if _is_verified_core_command(command_line):
            processes.append(
                {
                    "pid": pid,
                    "parent_pid": parent_pid,
                    "command_line": command_line,
                }
            )
    return processes


def _get_listener_process() -> tuple[int, str] | None:
    command = (
        "$connection = Get-NetTCPConnection "
        f"-LocalAddress '{API_HOST}' -LocalPort {API_PORT} -State Listen "
        "-ErrorAction SilentlyContinue | Select-Object -First 1; "
        "if ($null -ne $connection) { "
        "$process = Get-CimInstance Win32_Process -Filter "
        "\"ProcessId = $($connection.OwningProcess)\"; "
        "[PSCustomObject]@{ pid = $connection.OwningProcess; "
        "command_line = $process.CommandLine } | ConvertTo-Json -Compress }"
    )
    data = _powershell_json(command)
    if not isinstance(data, dict):
        return None
    try:
        return int(data["pid"]), str(data.get("command_line") or "")
    except (KeyError, TypeError, ValueError):
        return None


def _verified_core_listener_is_open() -> bool:
    listener = _get_listener_process()
    return bool(listener and _is_verified_core_command(listener[1]))


def _core_appears_alive_for_timeout() -> bool:
    if _verified_core_listener_is_open():
        return True
    task_state = _get_core_task_state()
    if task_state and task_state.lower() == "running":
        return True
    processes = _get_verified_core_processes()
    return bool(processes)


def _run_schtasks(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["schtasks", *arguments],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
        timeout=10,
    )


def _taskkill(pid: int, *, tree: bool = False) -> bool:
    command = ["taskkill", "/PID", str(pid)]
    if tree:
        command.append("/T")
    command.append("/F")
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
            timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _force_kill_verified_core_listener() -> bool:
    listener = _get_listener_process()
    if listener is None:
        return not _core_port_is_open()

    pid, command_line = listener
    if not _is_verified_core_command(command_line):
        logger.error(
            "Processo na porta %s não foi reconhecido como NODARIS Core. "
            "PID=%s. Encerramento abortado.",
            API_PORT,
            pid,
        )
        return False

    if not _taskkill(pid):
        logger.error("taskkill falhou ao encerrar Core degradado. PID=%s.", pid)
        return False
    logger.warning("Processo degradado do Core encerrado. PID=%s.", pid)
    return True


def _force_kill_verified_core_processes() -> bool:
    processes = _get_verified_core_processes()
    if processes is None:
        return False
    if not processes:
        return True

    process_ids = {item["pid"] for item in processes}
    roots = [item for item in processes if item["parent_pid"] not in process_ids]
    for process in roots or processes:
        if not _taskkill(process["pid"], tree=True):
            remaining = _get_verified_core_processes()
            if remaining is None or any(
                item["pid"] == process["pid"] for item in remaining
            ):
                return False
        logger.warning(
            "Árvore remanescente do Core encerrada. PID=%s.",
            process["pid"],
        )
    return True


def _wait_for_core_stopped(timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        processes = _get_verified_core_processes()
        if processes == [] and not _core_port_is_open():
            return True
        time.sleep(0.5)
    return _get_verified_core_processes() == [] and not _core_port_is_open()


def stop_running_core() -> bool:
    try:
        result = _run_schtasks("/End", "/TN", CORE_TASK_NAME)
    except (OSError, subprocess.SubprocessError):
        logger.exception("Falha ao solicitar encerramento da tarefa '%s'.", CORE_TASK_NAME)
        result = None

    if result is not None and result.returncode == 0:
        logger.info("Encerramento da tarefa '%s' solicitado.", CORE_TASK_NAME)

    if _wait_for_core_stopped(CORE_STOP_TIMEOUT_SECONDS):
        return True

    processes = _get_verified_core_processes()
    if processes and not _force_kill_verified_core_processes():
        return False

    if _core_port_is_open() and not _force_kill_verified_core_listener():
        return False

    return _wait_for_core_stopped(5)


def _wait_for_core_healthy(timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        healthy, _ = check_core_health()
        if healthy:
            return True
        time.sleep(1.0)
    return False


def start_core_task(*, verify: bool = True) -> bool:
    try:
        result = _run_schtasks("/Run", "/TN", CORE_TASK_NAME)
    except (OSError, subprocess.SubprocessError):
        logger.exception("Falha ao executar a tarefa de recuperação do Core.")
        return False

    if result.returncode != 0:
        logger.error(
            "Falha ao solicitar inicialização do Core. schtasks retornou código %s.",
            result.returncode,
        )
        return False

    logger.info("Solicitação de inicialização da tarefa '%s' enviada.", CORE_TASK_NAME)
    if not verify:
        return True
    if _wait_for_core_healthy(CORE_START_VERIFY_SECONDS):
        logger.info("Core iniciado e validado pelo health check.")
        return True

    logger.error(
        "A tarefa '%s' foi acionada, mas o Core não ficou saudável dentro de %s segundos.",
        CORE_TASK_NAME,
        CORE_START_VERIFY_SECONDS,
    )
    return False


def replace_degraded_core(reason: str) -> tuple[bool, str]:
    remaining = _cooldown_remaining_seconds()
    if remaining > 0:
        logger.warning(
            "Substituição do Core suprimida pelo cooldown. Motivo=%s, restante=%.0fs.",
            reason,
            remaining,
        )
        return False, "cooldown"

    _mark_degraded_restart_attempt(reason)
    logger.warning("Iniciando substituição segura do Core. Motivo: %s.", reason)

    if not stop_running_core():
        logger.error("Não foi possível encerrar com segurança o Core degradado.")
        return False, "stop_failed"
    if not start_core_task(verify=True):
        logger.error("Nova instância do Core não ficou saudável.")
        return False, "restart_failed"

    logger.info("Core degradado substituído com sucesso. Motivo: %s.", reason)
    return True, "recovered"


def main():
    try:
        healthy, reason = check_core_health()
        if healthy:
            _clear_health_timeout_failure()
            return

        if reason == "health_request_timeout" and _core_appears_alive_for_timeout():
            elapsed = _record_health_timeout_failure()
            if elapsed < HEALTH_TIMEOUT_GRACE_SECONDS:
                logger.warning(
                    "Health do Core excedeu o timeout, mas o processo aparenta "
                    "estar vivo. Reinicialização adiada. Persistência=%.1fs/%.0fs.",
                    elapsed,
                    HEALTH_TIMEOUT_GRACE_SECONDS,
                )
                return
            logger.warning(
                "Timeout do health persistiu por %.1fs. Recuperação será permitida.",
                elapsed,
            )
            _clear_health_timeout_failure()
        else:
            _clear_health_timeout_failure()

        mode = recovery_mode_for_current_state(reason)
        if mode == "start":
            logger.warning("Core indisponível. Motivo: %s. Solicitando inicialização.", reason)
            if not start_core_task(verify=True):
                logger.error("Watchdog não conseguiu recuperar o Core.")
            return

        if mode == "replace":
            logger.warning(
                "Core degradado detectado. Motivo inicial: %s. Confirmando condição.",
                reason,
            )
            time.sleep(DEGRADED_CONFIRM_SECONDS)
            healthy, confirmed_reason = check_core_health()
            if healthy:
                _clear_health_timeout_failure()
                logger.info("Condição degradada desapareceu. Nenhum restart necessário.")
                return

            confirmed_mode = recovery_mode_for_current_state(confirmed_reason)
            if confirmed_mode != "replace":
                logger.warning(
                    "Condição mudou durante confirmação. Motivo atual: %s. "
                    "Substituição cancelada.",
                    confirmed_reason,
                )
                return
            replace_degraded_core(confirmed_reason)
            return

        logger.error(
            "Health inválido detectado, mas recuperação automática foi bloqueada "
            "por segurança. Motivo: %s.",
            reason,
        )
    except Exception:
        logger.exception("Falha inesperada durante execução do Watchdog.")
        raise


if __name__ == "__main__":
    main()
