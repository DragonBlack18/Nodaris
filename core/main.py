import ctypes
import json
import logging
import os
import socket
import sys
import urllib.error
import urllib.request
from ctypes import wintypes

import uvicorn

from api.config import API_HOST, API_PORT
from api.logging_config import (
    bind_logger_handlers,
    get_logger,
)


logger = get_logger(
    "core",
    "monitorping-core.log",
)


# =========================================================
# BACKGROUND STREAM COMPATIBILITY
# =========================================================

_background_streams = []


def _ensure_background_streams():
    """
    Garante stdout/stderr válidos quando o Core é executado
    com pythonw.exe.

    pythonw.exe pode iniciar com sys.stdout e sys.stderr
    iguais a None. O Uvicorn consulta isatty() nesses
    streams durante a configuração de logging.

    Em execução normal com python.exe, nada é alterado.
    """

    global _background_streams

    if sys.stdout is None:

        stdout_stream = open(
            os.devnull,
            "w",
            encoding="utf-8",
            buffering=1,
        )

        sys.stdout = stdout_stream

        _background_streams.append(
            stdout_stream
        )

    if sys.stderr is None:

        stderr_stream = open(
            os.devnull,
            "w",
            encoding="utf-8",
            buffering=1,
        )

        sys.stderr = stderr_stream

        _background_streams.append(
            stderr_stream
        )


# =========================================================
# WINDOWS SINGLETON
# =========================================================

MUTEX_NAME = (
    "Global\\MonitorPingCoreSingleton"
)

ERROR_ALREADY_EXISTS = 183


def _acquire_singleton_mutex():
    """
    Garante uma única instância do Core no Windows.

    O próprio Windows libera o mutex quando o processo
    termina ou sofre crash, portanto não há lock antigo
    permanente para limpar manualmente.
    """

    kernel32 = ctypes.WinDLL(
        "kernel32",
        use_last_error=True,
    )

    kernel32.CreateMutexW.argtypes = [
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]

    kernel32.CreateMutexW.restype = (
        wintypes.HANDLE
    )

    handle = kernel32.CreateMutexW(
        None,
        False,
        MUTEX_NAME,
    )

    if not handle:
        raise ctypes.WinError(
            ctypes.get_last_error()
        )

    error = ctypes.get_last_error()

    if error == ERROR_ALREADY_EXISTS:

        kernel32.CloseHandle(
            handle
        )

        return None

    return handle


def _release_singleton_mutex(
    handle,
):
    if not handle:
        return

    kernel32 = ctypes.WinDLL(
        "kernel32",
        use_last_error=True,
    )

    kernel32.CloseHandle(
        handle
    )


# =========================================================
# PORT / CORE CHECK
# =========================================================

def _port_is_open(
    host: str,
    port: int,
) -> bool:

    try:

        with socket.create_connection(
            (
                host,
                port,
            ),
            timeout=0.5,
        ):
            return True

    except OSError:
        return False


def _monitorping_core_is_running() -> bool:

    url = (
        f"http://{API_HOST}:{API_PORT}"
        "/health"
    )

    try:

        with urllib.request.urlopen(
            url,
            timeout=1.5,
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        return (
            data.get("status") == "ok"
            and
            data.get("service")
            == "monitorping-api"
        )

    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        json.JSONDecodeError,
        OSError,
    ):
        return False


# =========================================================
# MAIN
# =========================================================

def main():

    _ensure_background_streams()

    logger.info(
        "Inicializando NODARIS Core."
    )

    print("=" * 56)
    print("NODARIS Core")
    print("=" * 56)

    # =====================================================
    # WINDOWS MUTEX
    # =====================================================

    mutex_handle = (
        _acquire_singleton_mutex()
    )

    if mutex_handle is None:

        print()
        print(
            "NODARIS Core já está "
            "em execução."
        )
        print()
        print(
            "Nenhuma nova instância "
            "foi iniciada."
        )

        logger.warning(
            "Inicialização ignorada: "
            "NODARIS Core já está em execução."
        )

        return

    try:

        # =================================================
        # PORT GUARD
        # =================================================

        if _port_is_open(
            API_HOST,
            API_PORT,
        ):

            if _monitorping_core_is_running():

                print()
                print(
                    "NODARIS Core já está "
                    "em execução."
                )

                print(
                    f"API: "
                    f"http://{API_HOST}:{API_PORT}"
                )

                print()

                print(
                    "Nenhuma nova instância "
                    "foi iniciada."
                )

                return

            print()

            print(
                f"ERRO: a porta {API_PORT} "
                "já está sendo utilizada "
                "por outro processo."
            )

            print()

            print(
                "O NODARIS Core não será "
                "iniciado para evitar conflito."
            )

            logger.error(
                "Não foi possível iniciar o Core: "
                "porta %s ocupada por outro processo.",
                API_PORT,
            )

            return

        # =================================================
        # START CORE
        # =================================================

        print(
            f"API: "
            f"http://{API_HOST}:{API_PORT}"
        )

        print(
            "Iniciando monitoramento..."
        )

        print()

        # =========================================================
        # UVICORN LOGGING
        # =========================================================

        bind_logger_handlers(
            "uvicorn",
            logger,
        )

        bind_logger_handlers(
            "uvicorn.error",
            logger,
        )

        bind_logger_handlers(
            "uvicorn.access",
            logger,
        )

        logger.info(
            "Iniciando API em http://%s:%s.",
            API_HOST,
            API_PORT,
        )

        try:

            uvicorn.run(
                "api.main:app",
                host=API_HOST,
                port=API_PORT,
                reload=False,
                access_log=False,
                log_config=None,
            )

        except Exception:

            logger.exception(
                "Falha fatal durante execução "
                "do NODARIS Core."
            )

            raise

        finally:

            logger.info(
                "NODARIS Core encerrado."
            )

    finally:

        _release_singleton_mutex(
            mutex_handle
        )


if __name__ == "__main__":
    main()
