import socket
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from api.config import PROBE_PROVIDER


class ProcessManager(QObject):

    services_ready = Signal()

    startup_status = Signal(str)

    startup_error = Signal(str)

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(parent)

        # ================================================
        # PATHS
        # ================================================

        self.project_root = (
            Path(__file__)
            .resolve()
            .parent
            .parent
        )

        self.blackbox_path = (
            self.project_root
            / "external"
            / "blackbox_exporter"
            / "blackbox_exporter.exe"
        )

        self.blackbox_config = (
            self.project_root
            / "external"
            / "blackbox_exporter"
            / "blackbox.yml"
        )

        # ================================================
        # PROCESSES
        # ================================================

        self.blackbox_process = QProcess(
            self
        )

        self.api_process = QProcess(
            self
        )

        # Indica se fomos nós que iniciamos
        # o serviço.
        self.started_blackbox = False
        self.started_api = False

        # ================================================
        # STARTUP TIMER
        # ================================================

        self._timer = QTimer(
            self
        )

        self._timer.setInterval(
            500
        )

        self._timer.timeout.connect(
            self._check_startup
        )

        self._startup_stage = (
            "IDLE"
        )

        self._attempts = 0

        self._max_attempts = 40

    # ====================================================
    # PUBLIC
    # ====================================================

    def start_services(self):

        provider = (
            str(
                PROBE_PROVIDER
            )
            .strip()
            .lower()
        )

        # =====================================================
        # NATIVE WINDOWS PING
        # =====================================================

        if provider == "native":

            self.startup_status.emit(
                "Motor ICMP: Windows Ping"
            )

            self._start_api()

            return

        # =====================================================
        # BLACKBOX
        # =====================================================

        self.startup_status.emit(
            "Verificando Blackbox..."
        )

        # Blackbox já está rodando.
        if self._is_port_open(
            "127.0.0.1",
            9115,
        ):

            self.startup_status.emit(
                "Blackbox já está ativo."
            )

            self._start_api()

            return

        self._start_blackbox()

    # ====================================================
    # BLACKBOX
    # ====================================================

    def _start_blackbox(self):

        if not self.blackbox_path.exists():

            self.startup_error.emit(
                "blackbox_exporter.exe "
                "não foi encontrado em: "
                f"{self.blackbox_path}"
            )

            return

        if not self.blackbox_config.exists():

            self.startup_error.emit(
                "blackbox.yml "
                "não foi encontrado em: "
                f"{self.blackbox_config}"
            )

            return

        self.startup_status.emit(
            "Iniciando Blackbox Exporter..."
        )

        self.blackbox_process.setWorkingDirectory(
            str(
                self.project_root
            )
        )

        arguments = [
            (
                "--config.file="
                f"{self.blackbox_config}"
            ),
            (
                "--web.listen-address="
                "127.0.0.1:9115"
            ),
        ]

        self.blackbox_process.start(
            str(
                self.blackbox_path
            ),
            arguments,
        )

        self.started_blackbox = True

        self._startup_stage = (
            "WAIT_BLACKBOX"
        )

        self._attempts = 0

        self._timer.start()

    # ====================================================
    # API
    # ====================================================

    def _start_api(self):

        # API já está rodando.
        if self._is_port_open(
            "127.0.0.1",
            8765,
        ):

            self.startup_status.emit(
                "MonitorPing API já está ativa."
            )

            self.services_ready.emit()

            return

        self.startup_status.emit(
            "Iniciando MonitorPing API..."
        )

        self.api_process.setWorkingDirectory(
            str(
                self.project_root
            )
        )

        arguments = [
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ]

        self.api_process.start(
            sys.executable,
            arguments,
        )

        self.started_api = True

        self._startup_stage = (
            "WAIT_API"
        )

        self._attempts = 0

        self._timer.start()

    # ====================================================
    # STARTUP CHECK
    # ====================================================

    def _check_startup(self):

        self._attempts += 1

        if (
            self._startup_stage
            == "WAIT_BLACKBOX"
        ):

            if self._is_port_open(
                "127.0.0.1",
                9115,
            ):

                self._timer.stop()

                self.startup_status.emit(
                    "Blackbox iniciado."
                )

                self._start_api()

                return

        elif (
            self._startup_stage
            == "WAIT_API"
        ):

            if self._is_port_open(
                "127.0.0.1",
                8765,
            ):

                self._timer.stop()

                self._startup_stage = (
                    "READY"
                )

                self.startup_status.emit(
                    "Monitoramento operacional."
                )

                self.services_ready.emit()

                return

        if (
            self._attempts
            >= self._max_attempts
        ):

            self._timer.stop()

            self.startup_error.emit(
                "Tempo limite excedido "
                "ao iniciar os serviços."
            )

    # ====================================================
    # PORT CHECK
    # ====================================================

    @staticmethod
    def _is_port_open(
        host: str,
        port: int,
    ) -> bool:

        try:

            with socket.create_connection(
                (host, port),
                timeout=0.2,
            ):

                return True

        except OSError:

            return False

    # ====================================================
    # STOP
    # ====================================================

    def stop_services(self):

        self._timer.stop()

        # Só encerra processos que
        # o próprio MonitorPing iniciou.

        if (
            self.started_api
            and
            self.api_process.state()
            != QProcess.ProcessState.NotRunning
        ):

            self.api_process.terminate()

            if not self.api_process.waitForFinished(
                3000
            ):

                self.api_process.kill()

                self.api_process.waitForFinished(
                    1000
                )

        if (
            self.started_blackbox
            and
            self.blackbox_process.state()
            != QProcess.ProcessState.NotRunning
        ):

            self.blackbox_process.terminate()

            if not (
                self.blackbox_process
                .waitForFinished(
                    3000
                )
            ):

                self.blackbox_process.kill()

                self.blackbox_process.waitForFinished(
                    1000
                )
