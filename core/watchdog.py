import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from api.logging_config import get_logger


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
# STATE
# =========================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

WATCHDOG_STATE_FILE = (
    PROJECT_ROOT
    / "data"
    / "monitorping_watchdog_state.json"
)


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


def _wait_for_port_closed(
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

        if not _core_port_is_open():

            return True

        time.sleep(0.5)

    return not _core_port_is_open()


# =========================================================
# PROCESS DISCOVERY
# =========================================================

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

    if "core.main" not in normalized_command:

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

    if _wait_for_port_closed(
        5,
    ):

        return True

    logger.warning(
        "Porta %s permaneceu ativa após "
        "encerramento da tarefa. "
        "Verificando processo listener.",
        CORE_PORT,
    )

    if not (
        _force_kill_verified_core_listener()
    ):

        return False

    return _wait_for_port_closed(
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
            recovery_mode_for_reason(
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
                recovery_mode_for_reason(
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
