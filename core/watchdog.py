import json
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request

from api.logging_config import get_logger
from api.paths import WATCHDOG_STATE_FILE


# =========================================================
# CORE
# =========================================================

HEALTH_URL = "http://127.0.0.1:8765/health"

CORE_HOST = "127.0.0.1"
CORE_PORT = 8765

CORE_TASK_NAME = "NODARIS Core"


# =========================================================
# RECOVERY POLICY
# =========================================================

ENGINE_ERROR_RESTART_THRESHOLD = 3

DEGRADED_CONFIRM_SECONDS = 5

DEGRADED_RESTART_COOLDOWN_SECONDS = 300

CORE_STOP_TIMEOUT_SECONDS = 10

CORE_START_VERIFY_SECONDS = 20


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


# =========================================================
# LOGGER
# =========================================================

logger = get_logger(
    "watchdog",
    "monitorping-watchdog.log",
)


# =========================================================
# HEALTH EVALUATION
# =========================================================

def evaluate_core_health(
    data: dict,
) -> tuple[bool, str]:

    # -----------------------------------------------------
    # SERVICE IDENTITY
    # -----------------------------------------------------

    if (
        data.get("service")
        != "monitorping-api"
    ):
        return (
            False,
            "unexpected_service",
        )

    # -----------------------------------------------------
    # ENGINE
    # -----------------------------------------------------

    if (
        data.get("monitor_engine")
        != "running"
    ):
        return (
            False,
            "monitor_engine_not_running",
        )

    # -----------------------------------------------------
    # BASIC STATUS
    # -----------------------------------------------------

    if data.get("status") != "ok":

        return (
            False,
            "health_status_not_ok",
        )

    # -----------------------------------------------------
    # HEALTH REASONS
    # -----------------------------------------------------

    health_reasons = data.get(
        "health_reasons",
        [],
    )

    if not isinstance(
        health_reasons,
        list,
    ):
        health_reasons = []

    for reason in health_reasons:

        if (
            reason
            in CRITICAL_HEALTH_REASONS
        ):
            return (
                False,
                str(reason),
            )

    # -----------------------------------------------------
    # ENGINE ERRORS
    # -----------------------------------------------------

    consecutive_errors = data.get(
        "consecutive_engine_errors",
        0,
    )

    try:

        consecutive_errors = int(
            consecutive_errors
        )

    except (
        TypeError,
        ValueError,
    ):

        consecutive_errors = 0

    if (
        consecutive_errors
        >= ENGINE_ERROR_RESTART_THRESHOLD
    ):

        return (
            False,
            "engine_errors_threshold",
        )

    return (
        True,
        "healthy",
    )


def check_core_health() -> tuple[
    bool,
    str,
]:

    try:

        with urllib.request.urlopen(
            HEALTH_URL,
            timeout=2.0,
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        if not isinstance(
            data,
            dict,
        ):

            return (
                False,
                "invalid_health_payload",
            )

        return evaluate_core_health(
            data
        )

    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        json.JSONDecodeError,
        OSError,
    ) as exc:

        return (
            False,
            (
                "health_request_failed: "
                f"{exc}"
            ),
        )


def core_is_healthy() -> bool:

    healthy, _ = (
        check_core_health()
    )

    return healthy


# =========================================================
# RECOVERY MODE
# =========================================================

def recovery_mode_for_reason(
    reason: str,
) -> str:

    if reason.startswith(
        "health_request_failed"
    ):

        return "start"

    if (
        reason
        in REPLACE_RUNNING_CORE_REASONS
    ):

        return "replace"

    return "manual"


def recovery_mode_for_current_state(
    reason: str,
) -> str:
    """
    Refina a decisao usando o estado real do Windows.

    Uma falha de /health normalmente significa que o Core deve ser
    iniciado. Porem, se a tarefa ainda estiver marcada como Running ou
    existir um processo core.main sem API funcional, solicitar apenas
    /Run sera ignorado pelo Task Scheduler. Nesse caso precisamos
    substituir a instancia presa.
    """

    mode = recovery_mode_for_reason(
        reason
    )

    if mode != "start":
        return mode

    task_state = _get_core_task_state()

    if (
        task_state
        and task_state.lower() == "running"
    ):
        return "replace"

    core_processes = (
        _get_verified_core_processes()
    )

    if core_processes:
        return "replace"

    # Uma porta ocupada sem processo core.main reconhecido nao deve ser
    # encerrada automaticamente.
    if _core_port_is_open():
        return "manual"

    return "start"


# =========================================================
# WATCHDOG STATE / COOLDOWN
# =========================================================

def _load_watchdog_state() -> dict:

    try:

        if not WATCHDOG_STATE_FILE.exists():

            return {}

        with WATCHDOG_STATE_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(
                file
            )

        if isinstance(
            data,
            dict,
        ):

            return data

    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ):

        logger.exception(
            "Falha ao ler estado "
            "persistente do Watchdog."
        )

    return {}


def _save_watchdog_state(
    state: dict,
):

    try:

        WATCHDOG_STATE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_file = (
            WATCHDOG_STATE_FILE
            .with_suffix(".tmp")
        )

        with temporary_file.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                state,
                file,
                indent=2,
            )

        temporary_file.replace(
            WATCHDOG_STATE_FILE
        )

    except OSError:

        logger.exception(
            "Falha ao persistir estado "
            "do Watchdog."
        )


def _cooldown_remaining_seconds() -> float:

    state = (
        _load_watchdog_state()
    )

    last_restart = state.get(
        "last_degraded_restart_at"
    )

    try:

        last_restart = float(
            last_restart
        )

    except (
        TypeError,
        ValueError,
    ):

        return 0.0

    elapsed = (
        time.time()
        - last_restart
    )

    return max(
        0.0,
        (
            DEGRADED_RESTART_COOLDOWN_SECONDS
            - elapsed
        ),
    )


def _mark_degraded_restart_attempt(
    reason: str,
):

    state = (
        _load_watchdog_state()
    )

    state[
        "last_degraded_restart_at"
    ] = time.time()

    state[
        "last_degraded_restart_reason"
    ] = reason

    _save_watchdog_state(
        state
    )


# =========================================================
# PORT
# =========================================================

def _core_port_is_open() -> bool:

    try:

        with socket.create_connection(
            (
                CORE_HOST,
                CORE_PORT,
            ),
            timeout=0.5,
        ):

            return True

    except OSError:

        return False


# =========================================================
# PROCESS DISCOVERY
# =========================================================

def _is_verified_core_command(
    command_line: str,
) -> bool:

    return bool(
        re.search(
            r"(?:^|\s)-m\s+core\.main(?:\s|$)",
            str(command_line),
            flags=re.IGNORECASE,
        )
    )


def _get_core_task_state() -> str | None:

    creation_flags = getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        0,
    )

    command = (
        "$task = Get-ScheduledTask "
        f"-TaskName '{CORE_TASK_NAME}' "
        "-ErrorAction SilentlyContinue; "
        "if ($null -ne $task) { "
        "$task.State.ToString() "
        "}"
    )

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

    except (
        OSError,
        subprocess.SubprocessError,
    ):

        logger.exception(
            "Falha ao consultar estado da tarefa '%s'.",
            CORE_TASK_NAME,
        )

        return None

    if result.returncode != 0:
        return None

    state = (
        result.stdout or ""
    ).strip()

    return state or None


def _get_verified_core_processes() -> (
    list[dict] | None
):
    """Retorna somente processos Python cuja acao seja -m core.main."""

    creation_flags = getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        0,
    )

    command = (
        "$processes = @(Get-CimInstance Win32_Process "
        "-ErrorAction SilentlyContinue | Where-Object { "
        "$_.Name -match '^pythonw?\\.exe$' -and "
        "$_.CommandLine -match "
        "'(?i)(?:^|\\s)-m\\s+core\\.main(?:\\s|$)' "
        "} | ForEach-Object { "
        "[PSCustomObject]@{ "
        "pid = $_.ProcessId; "
        "parent_pid = $_.ParentProcessId; "
        "command_line = $_.CommandLine "
        "} }); "
        "$processes | ConvertTo-Json -Compress"
    )

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

    except (
        OSError,
        subprocess.SubprocessError,
    ):

        logger.exception(
            "Falha ao localizar processos do Core."
        )

        return None

    if result.returncode != 0:
        return None

    output = (
        result.stdout or ""
    ).strip()

    if not output:
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        logger.error(
            "Resposta invalida ao localizar processos do Core."
        )
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
            parent_pid = int(
                item.get("parent_pid") or 0
            )
        except (KeyError, TypeError, ValueError):
            continue

        command_line = str(
            item.get("command_line") or ""
        )

        if not _is_verified_core_command(
            command_line
        ):
            continue

        processes.append(
            {
                "pid": pid,
                "parent_pid": parent_pid,
                "command_line": command_line,
            }
        )

    return processes

def _get_listener_process() -> (
    tuple[int, str] | None
):

    creation_flags = getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        0,
    )

    command = (
        "$connection = "
        "Get-NetTCPConnection "
        "-LocalAddress '127.0.0.1' "
        "-LocalPort 8765 "
        "-State Listen "
        "-ErrorAction SilentlyContinue "
        "| Select-Object -First 1; "
        "if ($null -ne $connection) { "
        "$process = Get-CimInstance "
        "Win32_Process "
        "-Filter "
        "\"ProcessId = "
        "$($connection.OwningProcess)\"; "
        "[PSCustomObject]@{ "
        "pid = $connection.OwningProcess; "
        "command_line = "
        "$process.CommandLine "
        "} | ConvertTo-Json -Compress "
        "}"
    )

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

    except (
        OSError,
        subprocess.SubprocessError,
    ):

        logger.exception(
            "Falha ao localizar processo "
            "listener do Core."
        )

        return None

    output = (
        result.stdout or ""
    ).strip()

    if not output:

        return None

    try:

        data = json.loads(
            output
        )

        pid = int(
            data["pid"]
        )

        command_line = str(
            data.get(
                "command_line"
            )
            or ""
        )

        return (
            pid,
            command_line,
        )

    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
    ):

        logger.error(
            "Resposta inválida ao localizar "
            "processo listener do Core."
        )

        return None


# =========================================================
# TASK CONTROL
# =========================================================

def _run_schtasks(
    *arguments: str,
) -> subprocess.CompletedProcess:

    creation_flags = getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        0,
    )

    return subprocess.run(
        [
            "schtasks",
            *arguments,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
        check=False,
        timeout=10,
    )


def _force_kill_verified_core_listener() -> bool:

    listener = (
        _get_listener_process()
    )

    if listener is None:

        return not (
            _core_port_is_open()
        )

    pid, command_line = listener

    normalized_command = (
        command_line.lower()
    )

    if not _is_verified_core_command(
        normalized_command
    ):

        logger.error(
            "Processo na porta %s não foi "
            "reconhecido como MonitorPing Core. "
            "PID=%s. Encerramento abortado.",
            CORE_PORT,
            pid,
        )

        return False

    creation_flags = getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        0,
    )

    try:

        result = subprocess.run(
            [
                "taskkill",
                "/PID",
                str(pid),
                "/F",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            check=False,
            timeout=10,
        )

    except (
        OSError,
        subprocess.SubprocessError,
    ):

        logger.exception(
            "Falha ao encerrar processo "
            "degradado do Core."
        )

        return False

    if result.returncode != 0:

        logger.error(
            "taskkill falhou ao encerrar "
            "Core degradado. PID=%s, código=%s.",
            pid,
            result.returncode,
        )

        return False

    logger.warning(
        "Processo degradado do Core "
        "encerrado. PID=%s.",
        pid,
    )

    return True


def _force_kill_verified_core_processes() -> bool:
    """Encerra arvores core.main remanescentes, nunca processos arbitrarios."""

    processes = (
        _get_verified_core_processes()
    )

    if processes is None:
        return False

    if not processes:
        return True

    process_ids = {
        process["pid"]
        for process in processes
    }

    root_processes = [
        process
        for process in processes
        if process["parent_pid"]
        not in process_ids
    ]

    if not root_processes:
        root_processes = processes

    creation_flags = getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        0,
    )

    for process in root_processes:

        pid = process["pid"]

        try:
            result = subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(pid),
                    "/T",
                    "/F",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
                check=False,
                timeout=10,
            )
        except (
            OSError,
            subprocess.SubprocessError,
        ):
            logger.exception(
                "Falha ao encerrar arvore remanescente "
                "do Core. PID=%s.",
                pid,
            )
            return False

        if result.returncode != 0:
            remaining = (
                _get_verified_core_processes()
            )
            if remaining is None or any(
                item["pid"] == pid
                for item in remaining
            ):
                logger.error(
                    "taskkill falhou ao encerrar arvore "
                    "do Core. PID=%s, codigo=%s.",
                    pid,
                    result.returncode,
                )
                return False

        logger.warning(
            "Arvore remanescente do Core encerrada. PID=%s.",
            pid,
        )

    return True


def _wait_for_core_stopped(
    timeout_seconds: float,
) -> bool:

    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while time.monotonic() < deadline:

        processes = (
            _get_verified_core_processes()
        )

        if (
            processes == []
            and not _core_port_is_open()
        ):
            return True

        time.sleep(0.5)

    processes = (
        _get_verified_core_processes()
    )

    return (
        processes == []
        and not _core_port_is_open()
    )


def stop_running_core() -> bool:

    try:

        result = _run_schtasks(
            "/End",
            "/TN",
            CORE_TASK_NAME,
        )

    except (
        OSError,
        subprocess.SubprocessError,
    ):

        logger.exception(
            "Falha ao solicitar encerramento "
            "da tarefa '%s'.",
            CORE_TASK_NAME,
        )

        result = None

    if (
        result is not None
        and result.returncode == 0
    ):

        logger.info(
            "Encerramento da tarefa '%s' "
            "solicitado.",
            CORE_TASK_NAME,
        )

    if _wait_for_core_stopped(
        CORE_STOP_TIMEOUT_SECONDS,
    ):

        return True

    core_processes = (
        _get_verified_core_processes()
    )

    if core_processes:

        logger.warning(
            "Processos core.main permaneceram ativos apos "
            "encerramento da tarefa. Encerrando somente "
            "as arvores verificadas."
        )

        if not _force_kill_verified_core_processes():
            return False

    if _core_port_is_open():

        logger.warning(
            "Porta %s permaneceu ativa apos "
            "encerramento da tarefa. "
            "Verificando processo listener.",
            CORE_PORT,
        )

        if not (
            _force_kill_verified_core_listener()
        ):

            return False

    return _wait_for_core_stopped(
        5,
    )


# =========================================================
# START / VERIFY
# =========================================================

def _wait_for_core_healthy(
    timeout_seconds: float,
) -> bool:

    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while (
        time.monotonic()
        < deadline
    ):

        healthy, _ = (
            check_core_health()
        )

        if healthy:

            return True

        time.sleep(1.0)

    return False


def start_core_task(
    *,
    verify: bool = True,
) -> bool:

    try:

        result = _run_schtasks(
            "/Run",
            "/TN",
            CORE_TASK_NAME,
        )

    except (
        OSError,
        subprocess.SubprocessError,
    ):

        logger.exception(
            "Falha ao executar a tarefa "
            "de recuperação do Core."
        )

        return False

    if result.returncode != 0:

        logger.error(
            "Falha ao solicitar inicialização "
            "do Core. schtasks retornou "
            "código %s.",
            result.returncode,
        )

        return False

    logger.info(
        "Solicitação de inicialização da "
        "tarefa '%s' enviada.",
        CORE_TASK_NAME,
    )

    if not verify:

        return True

    if _wait_for_core_healthy(
        CORE_START_VERIFY_SECONDS,
    ):

        logger.info(
            "Core iniciado e validado "
            "pelo health check."
        )

        return True

    logger.error(
        "A tarefa '%s' foi acionada, "
        "mas o Core não ficou saudável "
        "dentro de %s segundos.",
        CORE_TASK_NAME,
        CORE_START_VERIFY_SECONDS,
    )

    return False


# =========================================================
# DEGRADED CORE REPLACEMENT
# =========================================================

def replace_degraded_core(
    reason: str,
) -> tuple[bool, str]:

    remaining = (
        _cooldown_remaining_seconds()
    )

    if remaining > 0:

        logger.warning(
            "Substituição do Core suprimida "
            "pelo cooldown. Motivo=%s, "
            "restante=%.0fs.",
            reason,
            remaining,
        )

        return (
            False,
            "cooldown",
        )

    _mark_degraded_restart_attempt(
        reason
    )

    logger.warning(
        "Iniciando substituição segura "
        "do Core degradado. Motivo: %s.",
        reason,
    )

    if not stop_running_core():

        logger.error(
            "Não foi possível encerrar "
            "com segurança o Core degradado."
        )

        return (
            False,
            "stop_failed",
        )

    if not start_core_task(
        verify=True,
    ):

        logger.error(
            "Core degradado foi encerrado, "
            "mas a nova instância não ficou "
            "saudável."
        )

        return (
            False,
            "restart_failed",
        )

    logger.info(
        "Core degradado substituído "
        "com sucesso. Motivo original: %s.",
        reason,
    )

    return (
        True,
        "recovered",
    )


# =========================================================
# MAIN
# =========================================================

def main():

    try:

        healthy, reason = (
            check_core_health()
        )

        if healthy:

            logger.debug(
                "Core saudável."
            )

            return

        recovery_mode = (
            recovery_mode_for_current_state(
                reason
            )
        )

        # -------------------------------------------------
        # CORE COMPLETAMENTE INDISPONÍVEL
        # -------------------------------------------------

        if recovery_mode == "start":

            logger.warning(
                "Core indisponível. "
                "Motivo: %s. "
                "Solicitando inicialização.",
                reason,
            )

            if not start_core_task(
                verify=True,
            ):

                logger.error(
                    "Watchdog não conseguiu "
                    "recuperar o Core."
                )

            return

        # -------------------------------------------------
        # CORE VIVO, PORÉM DEGRADADO
        # -------------------------------------------------

        if recovery_mode == "replace":

            logger.warning(
                "Core degradado detectado. "
                "Motivo inicial: %s. "
                "Confirmando condição.",
                reason,
            )

            time.sleep(
                DEGRADED_CONFIRM_SECONDS
            )

            healthy, confirmed_reason = (
                check_core_health()
            )

            if healthy:

                logger.info(
                    "Condição degradada desapareceu "
                    "antes da recuperação. "
                    "Nenhum restart necessário."
                )

                return

            confirmed_mode = (
                recovery_mode_for_current_state(
                    confirmed_reason
                )
            )

            if confirmed_mode != "replace":

                logger.warning(
                    "Condição mudou durante "
                    "confirmação. Motivo atual: %s. "
                    "Substituição cancelada.",
                    confirmed_reason,
                )

                return

            replace_degraded_core(
                confirmed_reason
            )

            return

        # -------------------------------------------------
        # NÃO É SEGURO REINICIAR AUTOMATICAMENTE
        # -------------------------------------------------

        logger.error(
            "Health inválido detectado, "
            "mas recuperação automática foi "
            "bloqueada por segurança. "
            "Motivo: %s.",
            reason,
        )

    except Exception:

        logger.exception(
            "Falha inesperada durante "
            "execução do Watchdog."
        )

        raise


if __name__ == "__main__":
    main()
