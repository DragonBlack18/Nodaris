import logging
import os
import threading
from logging.handlers import RotatingFileHandler

from api.paths import LOG_DIR

if os.name == "nt":
    import msvcrt


# =========================================================
# PATHS
# =========================================================

LOCK_FILE = (
    LOG_DIR / ".monitorping-log.lock"
)


# =========================================================
# ROTATION
# =========================================================

DEFAULT_MAX_BYTES = (
    5 * 1024 * 1024
)

DEFAULT_BACKUP_COUNT = 5

ERROR_MAX_BYTES = (
    5 * 1024 * 1024
)

ERROR_BACKUP_COUNT = 10


# =========================================================
# FORMAT
# =========================================================

LOG_FORMAT = (
    "%(asctime)s | "
    "%(levelname)-8s | "
    "%(name)s | "
    "%(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# =========================================================
# SAFE ROTATING HANDLER
# =========================================================

class SafeRotatingFileHandler(
    RotatingFileHandler
):
    """
    RotatingFileHandler protegido para uso por
    múltiplos processos no Windows.

    O MonitorPing possui processos independentes
    como Core e Watchdog que podem escrever no
    mesmo monitorping-error.log.

    A trava evita que dois processos tentem
    executar rollover simultaneamente.
    """

    _thread_lock = threading.RLock()

    def __init__(
        self,
        filename,
        max_bytes,
        backup_count,
    ):
        LOG_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        super().__init__(
            filename=filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            delay=True,
        )

    def _acquire_process_lock(self):
        if os.name != "nt":
            return None

        lock_file = open(
            LOCK_FILE,
            "a+b",
        )

        lock_file.seek(
            0,
            os.SEEK_END,
        )

        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()

        lock_file.seek(0)

        msvcrt.locking(
            lock_file.fileno(),
            msvcrt.LK_LOCK,
            1,
        )

        return lock_file

    @staticmethod
    def _release_process_lock(
        lock_file,
    ):
        if (
            os.name != "nt"
            or lock_file is None
        ):
            return

        try:
            lock_file.seek(0)

            msvcrt.locking(
                lock_file.fileno(),
                msvcrt.LK_UNLCK,
                1,
            )

        finally:
            lock_file.close()

    def emit(
        self,
        record,
    ):
        lock_file = None

        with self._thread_lock:

            try:
                lock_file = (
                    self._acquire_process_lock()
                )

                super().emit(record)

            except Exception:
                self.handleError(record)

            finally:

                # Fecha o arquivo depois de cada escrita.
                #
                # Isso é necessário para permitir que outro
                # processo faça rename durante o rollover
                # no Windows.
                if self.stream is not None:

                    try:
                        self.stream.flush()

                    finally:
                        self.stream.close()
                        self.stream = None

                self._release_process_lock(
                    lock_file
                )


# =========================================================
# LOGGER FACTORY
# =========================================================

def get_logger(
    component: str,
    filename: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> logging.Logger:

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger_name = (
        f"monitorping.{component}"
    )

    logger = logging.getLogger(
        logger_name
    )

    logger.setLevel(
        logging.INFO
    )

    logger.propagate = False

    # Impede handlers duplicados caso get_logger()
    # seja chamado novamente para o mesmo componente.
    if getattr(
        logger,
        "_monitorping_configured",
        False,
    ):
        return logger

    formatter = logging.Formatter(
        LOG_FORMAT,
        datefmt=DATE_FORMAT,
    )

    # =====================================================
    # COMPONENT LOG
    # =====================================================

    component_handler = (
        SafeRotatingFileHandler(
            LOG_DIR / filename,
            max_bytes=max_bytes,
            backup_count=backup_count,
        )
    )

    component_handler.setLevel(
        logging.INFO
    )

    component_handler.setFormatter(
        formatter
    )

    logger.addHandler(
        component_handler
    )

    # =====================================================
    # GLOBAL ERROR LOG
    # =====================================================

    error_handler = (
        SafeRotatingFileHandler(
            LOG_DIR
            / "monitorping-error.log",
            max_bytes=ERROR_MAX_BYTES,
            backup_count=ERROR_BACKUP_COUNT,
        )
    )

    error_handler.setLevel(
        logging.ERROR
    )

    error_handler.setFormatter(
        formatter
    )

    logger.addHandler(
        error_handler
    )

    logger._monitorping_configured = True

    return logger


# =========================================================
# EXTERNAL LOGGER BINDING
# =========================================================

def bind_logger_handlers(
    target_name: str,
    source_logger: logging.Logger,
    level: int = logging.INFO,
) -> logging.Logger:

    target_logger = logging.getLogger(
        target_name
    )

    target_logger.handlers.clear()

    for handler in source_logger.handlers:
        target_logger.addHandler(
            handler
        )

    target_logger.setLevel(
        level
    )

    target_logger.propagate = False

    return target_logger
