import time
from datetime import datetime

from PySide6.QtCore import (
    Qt,
    QTimer,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from desktop.api_client import ApiClient
from desktop import theme
from desktop.theme import (
    DANGER,
    FONT_SIZE_LG,
    RADIUS_MD,
    SUCCESS,
    TEXT_MUTED,
    device_detail_qss,
    nodaris_desktop_controls_qss,
    nodaris_global_visual_qss,
    status_color,
    status_soft_color,
)
from desktop.widgets.latency_chart import (
    LatencyChartWidget,
    normalize_latency_ms,
)
from desktop.widgets.metric_card import MetricCard


class DeviceDetailWindow(QMainWindow):
    """
    Janela de detalhes de um equipamento monitorado.
    """

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(parent)

        self.current_device = {}

        self.current_incident = {}
        self.latest_incident = {}

        self.current_ip = None

        self._last_availability_request_at = 0.0

        self._last_probe_history_request_at = 0.0

        self._history_request_generation = 0
        self._active_history_request_token = None

        self.api = ApiClient(
            parent=self
        )

        self.api.device_availability_received.connect(
            self._availability_received
        )

        self.api.device_incidents_received.connect(
            self._incidents_received
        )

        self.api.probe_history_context_received.connect(
            self._probe_history_context_received
        )

        self.incident_timer = QTimer(
            self
        )

        self.incident_timer.setInterval(
            1000
        )

        self.incident_timer.timeout.connect(
            self._refresh_incident_duration
        )

        self.setWindowTitle(
            "NODARIS — Detalhes do Equipamento"
        )

        self.resize(
            1100,
            850,
        )

        self.setMinimumSize(
            680,
            600,
        )

        self._current_columns = None

        self._build_ui()

        self.latency_chart.period_requested.connect(
            self._chart_period_requested
        )

        self._apply_style()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):

        scroll = QScrollArea()

        scroll.setObjectName(
            "detailScroll"
        )

        scroll.setWidgetResizable(
            True
        )

        scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.setCentralWidget(
            scroll
        )

        viewport = QWidget()

        viewport.setObjectName(
            "detailViewport"
        )

        viewport_layout = QHBoxLayout(
            viewport
        )

        viewport_layout.setContentsMargins(
            24,
            0,
            24,
            40,
        )

        viewport_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop
            | Qt.AlignmentFlag.AlignHCenter
        )

        scroll.setWidget(
            viewport
        )

        self.content = QWidget()

        self.content.setObjectName(
            "detailContent"
        )

        self.content.setMaximumWidth(
            1280
        )

        self.content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        viewport_layout.addWidget(
            self.content
        )

        root = QVBoxLayout(
            self.content
        )

        root.setContentsMargins(
            0,
            28,
            0,
            28,
        )

        root.setSpacing(
            24
        )

        # =================================================
        # HEADER
        # =================================================

        header = QHBoxLayout()

        identity = QVBoxLayout()

        self.name_label = QLabel(
            "Equipamento"
        )

        self.name_label.setObjectName(
            "deviceTitle"
        )

        self.name_label.setWordWrap(True)
        self.name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.ip_label = QLabel(
            "--"
        )

        self.ip_label.setObjectName(
            "deviceIp"
        )

        identity.addWidget(
            self.name_label
        )

        identity.addWidget(
            self.ip_label
        )

        header.addLayout(
            identity
        )

        header.addStretch()

        self.status_label = QLabel(
            "UNKNOWN"
        )

        self.status_label.setObjectName(
            "deviceStatus"
        )

        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )

        header.addWidget(
            self.status_label,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        root.addLayout(
            header
        )

        # =================================================
        # HEALTH
        # =================================================

        health_title = QLabel(
            "SAÚDE ATUAL"
        )

        health_title.setObjectName(
            "sectionTitle"
        )

        root.addWidget(
            health_title
        )

        self.health_grid = QGridLayout()

        self.health_grid.setHorizontalSpacing(
            12
        )

        self.health_grid.setVerticalSpacing(
            12
        )

        self.quality_card = MetricCard(
            "QUALIDADE"
        )

        self.current_latency_card = MetricCard(
            "LATÊNCIA ATUAL"
        )

        self.average_latency_card = MetricCard(
            "LATÊNCIA MÉDIA"
        )

        self.loss_card = MetricCard(
            "PERDA RECENTE"
        )

        self.min_latency_card = MetricCard(
            "LATÊNCIA MÍNIMA"
        )

        self.max_latency_card = MetricCard(
            "LATÊNCIA MÁXIMA"
        )

        self.failures_card = MetricCard(
            "FALHAS CONSECUTIVAS"
        )

        self.successes_card = MetricCard(
            "SUCESSOS CONSECUTIVOS"
        )

        self.health_cards = [
            self.quality_card,
            self.current_latency_card,
            self.average_latency_card,
            self.loss_card,
            self.min_latency_card,
            self.max_latency_card,
            self.failures_card,
            self.successes_card,
        ]

        self.health_grid.addWidget(
            self.quality_card,
            0,
            0,
        )

        self.health_grid.addWidget(
            self.current_latency_card,
            0,
            1,
        )

        self.health_grid.addWidget(
            self.average_latency_card,
            0,
            2,
        )

        self.health_grid.addWidget(
            self.loss_card,
            0,
            3,
        )

        self.health_grid.addWidget(
            self.min_latency_card,
            1,
            0,
        )

        self.health_grid.addWidget(
            self.max_latency_card,
            1,
            1,
        )

        self.health_grid.addWidget(
            self.failures_card,
            1,
            2,
        )

        self.health_grid.addWidget(
            self.successes_card,
            1,
            3,
        )

        root.addLayout(
            self.health_grid
        )

        # =================================================
        # LATENCY HISTORY
        # =================================================

        self.latency_chart = LatencyChartWidget()

        self.latency_chart.setMinimumHeight(
            350
        )

        root.addWidget(
            self.latency_chart
        )

        # =================================================
        # AVAILABILITY
        # =================================================

        availability_title = QLabel(
            "ESTABILIDADE — ÚLTIMAS 24H"
        )

        availability_title.setObjectName(
            "sectionTitle"
        )

        root.addWidget(
            availability_title
        )

        self.availability_grid = QGridLayout()

        self.availability_grid.setHorizontalSpacing(
            12
        )

        self.availability_grid.setVerticalSpacing(
            12
        )

        self.availability_card = MetricCard(
            "DISPONIBILIDADE"
        )

        self.monitored_time_card = MetricCard(
            "TEMPO MONITORADO"
        )

        self.downtime_card = MetricCard(
            "TEMPO OFFLINE"
        )

        self.incident_count_card = MetricCard(
            "QUEDAS"
        )

        self.availability_cards = [
            self.availability_card,
            self.monitored_time_card,
            self.downtime_card,
            self.incident_count_card,
        ]

        self.availability_grid.addWidget(
            self.availability_card,
            0,
            0,
        )

        self.availability_grid.addWidget(
            self.monitored_time_card,
            0,
            1,
        )

        self.availability_grid.addWidget(
            self.downtime_card,
            0,
            2,
        )

        self.availability_grid.addWidget(
            self.incident_count_card,
            0,
            3,
        )

        root.addLayout(
            self.availability_grid
        )

        # =================================================
        # INCIDENT
        # =================================================

        incident_title = QLabel(
            "INCIDENTE"
        )

        incident_title.setObjectName(
            "sectionTitle"
        )

        root.addWidget(
            incident_title
        )

        self.incident_panel = QFrame()

        self.incident_panel.setObjectName(
            "incidentPanel"
        )

        incident_layout = QGridLayout(
            self.incident_panel
        )

        incident_layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        incident_layout.setHorizontalSpacing(
            30
        )

        incident_layout.setVerticalSpacing(
            10
        )

        # =================================================
        # STATUS DO INCIDENTE
        # =================================================

        self.incident_mode_label = QLabel(
            "Nenhum incidente"
        )

        self.incident_mode_label.setObjectName(
            "incidentMode"
        )

        incident_layout.addWidget(
            self.incident_mode_label,
            0,
            0,
            1,
            2,
        )

        # =================================================
        # INÍCIO
        # =================================================

        started_title = QLabel(
            "Início"
        )

        started_title.setObjectName(
            "infoTitle"
        )

        self.incident_started_label = QLabel(
            "--"
        )

        self.incident_started_label.setObjectName(
            "infoValue"
        )

        incident_layout.addWidget(
            started_title,
            1,
            0,
        )

        incident_layout.addWidget(
            self.incident_started_label,
            1,
            1,
        )

        # =================================================
        # FIM
        # =================================================

        ended_title = QLabel(
            "Recuperação"
        )

        ended_title.setObjectName(
            "infoTitle"
        )

        self.incident_ended_label = QLabel(
            "--"
        )

        self.incident_ended_label.setObjectName(
            "infoValue"
        )

        incident_layout.addWidget(
            ended_title,
            2,
            0,
        )

        incident_layout.addWidget(
            self.incident_ended_label,
            2,
            1,
        )

        # =================================================
        # DURAÇÃO
        # =================================================

        duration_title = QLabel(
            "Duração"
        )

        duration_title.setObjectName(
            "infoTitle"
        )

        self.incident_duration_label = QLabel(
            "--"
        )

        self.incident_duration_label.setObjectName(
            "infoValue"
        )

        incident_layout.addWidget(
            duration_title,
            3,
            0,
        )

        incident_layout.addWidget(
            self.incident_duration_label,
            3,
            1,
        )

        root.addWidget(
            self.incident_panel
        )

        # =================================================
        # COMMUNICATION
        # =================================================

        communication_title = QLabel(
            "COMUNICAÇÃO"
        )

        communication_title.setObjectName(
            "sectionTitle"
        )

        root.addWidget(
            communication_title
        )

        communication_panel = QFrame()

        communication_panel.setObjectName(
            "communicationPanel"
        )

        communication_layout = QGridLayout(
            communication_panel
        )

        communication_layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        communication_layout.setHorizontalSpacing(
            30
        )

        communication_layout.setVerticalSpacing(
            10
        )

        confirmed_title = QLabel(
            "Estado confirmado"
        )

        confirmed_title.setObjectName(
            "infoTitle"
        )

        self.confirmed_status_label = QLabel(
            "--"
        )

        self.confirmed_status_label.setObjectName(
            "infoValue"
        )

        probe_title = QLabel(
            "Última tentativa ICMP"
        )

        probe_title.setObjectName(
            "infoTitle"
        )

        self.probe_status_label = QLabel(
            "--"
        )

        self.probe_status_label.setObjectName(
            "infoValue"
        )

        communication_layout.addWidget(
            confirmed_title,
            0,
            0,
        )

        communication_layout.addWidget(
            self.confirmed_status_label,
            0,
            1,
        )

        communication_layout.addWidget(
            probe_title,
            1,
            0,
        )

        communication_layout.addWidget(
            self.probe_status_label,
            1,
            1,
        )

        root.addWidget(
            communication_panel
        )

        root.addStretch()

        self._apply_responsive_layout(
            force=True
        )

    def _clear_grid(
        self,
        layout,
    ):

        while layout.count():

            item = layout.takeAt(
                0
            )

            widget = item.widget()

            if widget:

                layout.removeWidget(
                    widget
                )

    def _fill_grid(
        self,
        layout,
        widgets,
        columns: int,
    ):

        self._clear_grid(
            layout
        )

        for index, widget in enumerate(
            widgets
        ):

            row = (
                index // columns
            )

            column = (
                index % columns
            )

            layout.addWidget(
                widget,
                row,
                column,
            )

        for column in range(
            columns
        ):

            layout.setColumnStretch(
                column,
                1,
            )

    def _apply_responsive_layout(
        self,
        force: bool = False,
    ):

        width = self.width()

        if width >= 1180:

            columns = 4

        elif width >= 760:

            columns = 2

        else:

            columns = 1

        if (
            not force
            and columns
            == self._current_columns
        ):

            return

        self._current_columns = (
            columns
        )

        self._fill_grid(
            self.health_grid,
            self.health_cards,
            columns,
        )

        self._fill_grid(
            self.availability_grid,
            self.availability_cards,
            columns,
        )

    def resizeEvent(
        self,
        event,
    ):

        super().resizeEvent(
            event
        )

        self._apply_responsive_layout()

    # =====================================================
    # DEVICE DATA
    # =====================================================

    def set_device(
        self,
        device: dict,
    ):
        """
        Atualiza a janela utilizando os dados
        atuais do equipamento recebidos do /status.
        """

        self.current_device = (
            device or {}
        )

        name = (
            self.current_device.get(
                "name"
            )
            or "Equipamento"
        )

        ip = (
            self.current_device.get(
                "ip"
            )
            or "--"
        )

        previous_ip = (
            self.current_ip
        )

        self.current_ip = str(
            ip
        )

        ip_changed = previous_ip != self.current_ip

        if ip_changed:
            self._history_request_generation += 1
            self._active_history_request_token = None
            self._last_probe_history_request_at = 0.0
            self._reset_history_view()

        status = (
            self.current_device.get(
                "status"
            )
            or "UNKNOWN"
        )

        probe_status = (
            self.current_device.get(
                "probe_status"
            )
            or self.current_device.get(
                "raw_status"
            )
            or "--"
        )

        health = (
            self.current_device.get(
                "health"
            )
            or {}
        )

        # =================================================
        # IDENTITY
        # =================================================

        self.name_label.setText(
            str(name)
        )

        self.ip_label.setText(
            str(ip)
        )

        self.status_label.setText(
            str(status)
        )

        self.confirmed_status_label.setText(
            str(status)
        )

        self.probe_status_label.setText(
            str(probe_status)
        )

        self._update_status_style(
            str(status)
        )

        # =================================================
        # QUALITY
        # =================================================

        quality = self._first_value(
            health,
            "quality",
            "latency_quality",
        )

        self.quality_card.set_value(
            quality or "--"
        )

        # =================================================
        # CURRENT LATENCY
        # =================================================

        current_latency = (
            self.current_device.get(
                "latency_ms"
            )
        )

        if current_latency is None:

            current_latency = (
                self._first_value(
                    health,
                    "current_latency_ms",
                    "latency_ms",
                )
            )

        # =================================================
        # HISTORICAL LATENCY IN HEALTH WINDOW
        # =================================================

        average_latency = (
            self._first_value(
                health,
                "average_latency_ms",
                "avg_latency_ms",
                "latency_avg_ms",
            )
        )

        min_latency = (
            self._first_value(
                health,
                "minimum_latency_ms",
                "min_latency_ms",
                "latency_min_ms",
            )
        )

        max_latency = (
            self._first_value(
                health,
                "maximum_latency_ms",
                "max_latency_ms",
                "latency_max_ms",
            )
        )

        self.current_latency_card.set_value(
            self._format_latency(
                current_latency
            )
        )

        # =================================================
        # HISTORICAL LATENCY
        # =================================================
        #
        # Esses valores podem não existir no /status.
        #
        # Quando não existirem, NÃO devemos substituir
        # os valores calculados pelo probe_history por "--".
        #

        if average_latency is not None:

            self.average_latency_card.set_value(
                self._format_latency(
                    average_latency
                )
            )

        if min_latency is not None:

            self.min_latency_card.set_value(
                self._format_latency(
                    min_latency
                )
            )

        if max_latency is not None:

            self.max_latency_card.set_value(
                self._format_latency(
                    max_latency
                )
            )

        # =================================================
        # LOSS
        # =================================================

        loss = self._first_value(
            health,
            "loss_percent",
            "packet_loss_percent",
            "recent_loss_percent",
        )

        if loss is not None:

            self.loss_card.set_value(
                self._format_percent(
                    loss
                )
            )

        # =================================================
        # CONSECUTIVE RESULTS
        # =================================================

        failures = self._first_value(
            health,
            "consecutive_failures",
            "failures",
        )

        successes = self._first_value(
            health,
            "consecutive_successes",
            "successes",
        )

        self.failures_card.set_value(
            failures
            if failures is not None
            else 0
        )

        self.successes_card.set_value(
            successes
            if successes is not None
            else 0
        )

        # =================================================
        # AVAILABILITY REFRESH
        # =================================================

        now = time.monotonic()

        refresh_due = (
            now
            - self._last_availability_request_at
            >= 10.0
        )

        if (
            self.current_ip
            and
            self.current_ip != "--"
            and
            (
                ip_changed
                or refresh_due
            )
        ):

            self._last_availability_request_at = (
                now
            )

            self.api.get_device_availability(
                self.current_ip,
                hours=24,
            )

            self.api.get_device_incidents(
                self.current_ip
            )

        # =================================================
        # PROBE HISTORY REFRESH
        # =================================================

        probe_refresh_due = (
            now
            - self._last_probe_history_request_at
            >= 30.0
        )

        if (
            self.current_ip
            and
            self.current_ip != "--"
            and
            (
                ip_changed
                or probe_refresh_due
            )
        ):

            self._request_probe_history(
                self.latency_chart.current_period_minutes()
            )

    def _reset_history_view(self):
        """Remove telemetria de histórico sem apagar o estado atual do IP."""

        self.latency_chart.clear()
        for card in (
            self.average_latency_card,
            self.min_latency_card,
            self.max_latency_card,
            self.loss_card,
        ):
            card.set_value(None)

        health = self.current_device.get("health") or {}
        if not isinstance(health, dict):
            health = {}

        quality = self._first_value(health, "quality", "latency_quality")
        failures = self._first_value(health, "consecutive_failures", "failures")
        successes = self._first_value(health, "consecutive_successes", "successes")
        self.quality_card.set_value(quality if quality is not None else "--")
        self.failures_card.set_value(failures if failures is not None else 0)
        self.successes_card.set_value(successes if successes is not None else 0)

    def _request_probe_history(self, minutes: int):
        if not self.current_ip or self.current_ip == "--":
            return

        self._history_request_generation += 1
        token = (
            self._history_request_generation,
            self.current_ip,
            int(minutes),
        )
        self._active_history_request_token = token
        self._last_probe_history_request_at = time.monotonic()
        self.api.get_probe_history(
            self.current_ip,
            minutes=minutes,
            request_token=token,
        )

    def showEvent(self, event):
        super().showEvent(event)
        self.incident_timer.start()

    def hideEvent(self, event):
        self.incident_timer.stop()
        self._history_request_generation += 1
        self._active_history_request_token = None
        self._last_probe_history_request_at = 0.0
        self._last_availability_request_at = 0.0
        self._reset_history_view()
        # Invalida também respostas de disponibilidade/incidentes que ainda
        # estejam em trânsito. set_device() restaura o IP ao reabrir.
        self.current_ip = None
        super().hideEvent(event)

    # =====================================================
    # INCIDENTS
    # =====================================================

    def _incidents_received(
        self,
        ip: str,
        data,
    ):

        if (
            str(ip)
            != str(self.current_ip)
        ):

            return

        if not isinstance(
            data,
            dict,
        ):

            data = {}

        self.current_incident = data.get(
            "current",
            {},
        ) or {}

        self.latest_incident = data.get(
            "latest",
            {},
        ) or {}

        if self.current_incident:

            incident = (
                self.current_incident
            )

            self.incident_mode_label.setText(
                "● INCIDENTE ATIVO"
            )

            self.incident_mode_label.setStyleSheet(
                f"color: {DANGER}; font-weight: 800;"
            )

            self.incident_started_label.setText(
                self._format_datetime(
                    incident.get(
                        "started_at"
                    )
                )
            )

            self.incident_ended_label.setText(
                "Ainda offline"
            )

        elif self.latest_incident:

            incident = (
                self.latest_incident
            )

            self.incident_mode_label.setText(
                "ÚLTIMO INCIDENTE"
            )

            self.incident_mode_label.setStyleSheet(
                f"color: {TEXT_MUTED}; font-weight: 800;"
            )

            self.incident_started_label.setText(
                self._format_datetime(
                    incident.get(
                        "started_at"
                    )
                )
            )

            self.incident_ended_label.setText(
                self._format_datetime(
                    incident.get(
                        "ended_at"
                    )
                )
            )

        else:

            self.incident_mode_label.setText(
                "Nenhum incidente registrado"
            )

            self.incident_mode_label.setStyleSheet(
                f"color: {SUCCESS}; font-weight: 700;"
            )

            self.incident_started_label.setText(
                "--"
            )

            self.incident_ended_label.setText(
                "--"
            )

            self.incident_duration_label.setText(
                "--"
            )

        self._refresh_incident_duration()

    def _chart_period_requested(
        self,
        minutes: int,
    ):

        if (
            not self.current_ip
            or self.current_ip == "--"
        ):

            return

        self._reset_history_view()
        self._request_probe_history(minutes)

    def _probe_history_context_received(self, ip: str, token, data):
        if (
            str(ip) != str(self.current_ip)
            or token != self._active_history_request_token
        ):
            return

        if not isinstance(data, dict):
            self._reset_history_view()
            self._active_history_request_token = None
            self._last_probe_history_request_at = 0.0
            return

        self._probe_history_received(ip, data)

    def _probe_history_received(
        self,
        ip: str,
        data,
    ):

        if (
            str(ip)
            != str(self.current_ip)
        ):

            return

        if not isinstance(
            data,
            dict,
        ):

            return

        samples = data.get(
            "history",
            [],
        )

        summary = data.get(
            "summary",
            {},
        )

        if not isinstance(
            samples,
            list,
        ):

            samples = []

        if not isinstance(
            summary,
            dict,
        ):

            summary = {}

        # =====================================================
        # GRÁFICO
        # =====================================================

        self._reset_history_view()
        self.latency_chart.set_samples(samples)

        # O gráfico já filtrou status, timestamps e latências inválidas.
        # Os cards usam a mesma regra, sem converter ausência em 0 ms.
        valid_latencies = self.latency_chart.valid_latencies

        if not valid_latencies:
            self.latency_chart.clear()
            return

        # =====================================================
        # ESTATÍSTICAS
        # =====================================================

        try:
            total_samples = int(data.get("total_samples", len(samples)))
        except (TypeError, ValueError, OverflowError):
            total_samples = len(samples)

        rejected_measurement = any(
            isinstance(item, dict)
            and item.get("latency_ms") is not None
            and (
                normalize_latency_ms(item["latency_ms"]) is None
                or LatencyChartWidget._sample_status(item) in ("OFFLINE", "ERROR")
            )
            for item in samples
        )

        # O backend resume o período completo antes do downsampling.
        # Se houve redução e nenhum dado ruim, mantemos essa precisão.
        use_full_summary = total_samples > len(samples) and not rejected_measurement
        if use_full_summary:
            average_latency = normalize_latency_ms(summary.get("average_latency_ms"))
            minimum_latency = normalize_latency_ms(summary.get("minimum_latency_ms"))
            maximum_latency = normalize_latency_ms(summary.get("maximum_latency_ms"))
            use_full_summary = all(
                value is not None
                for value in (average_latency, minimum_latency, maximum_latency)
            )

        if not use_full_summary:
            average_latency = sum(
                value / len(valid_latencies) for value in valid_latencies
            )
            minimum_latency = min(valid_latencies)
            maximum_latency = max(valid_latencies)

        self.average_latency_card.set_value(self._format_latency(average_latency))
        self.min_latency_card.set_value(self._format_latency(minimum_latency))
        self.max_latency_card.set_value(self._format_latency(maximum_latency))

        loss_percent = normalize_latency_ms(summary.get("loss_percent"))
        if loss_percent is not None and loss_percent <= 100.0:
            self.loss_card.set_value(self._format_percent(loss_percent))

        # =====================================================
        # MOST RECENT SAMPLE
        # =====================================================

        if samples:

            latest_sample = max(
                (
                    item
                    for item in samples
                    if isinstance(
                        item,
                        dict,
                    )
                ),
                key=lambda item:
                str(
                    item.get(
                        "observed_at",
                        "",
                    )
                ),
                default=None,
            )

            if latest_sample:

                quality = latest_sample.get(
                    "quality"
                )

                if quality:

                    self.quality_card.set_value(
                        quality
                    )

                failures = latest_sample.get(
                    "consecutive_failures"
                )

                successes = latest_sample.get(
                    "consecutive_successes"
                )

                if failures is not None:

                    self.failures_card.set_value(
                        failures
                    )

                if successes is not None:

                    self.successes_card.set_value(
                        successes
                    )

        # =====================================================
        # RECENT LOSS
        # =====================================================

    def _refresh_incident_duration(self):

        incident = None

        if self.current_incident:

            incident = (
                self.current_incident
            )

            started_at = (
                incident.get(
                    "started_at"
                )
            )

            seconds = (
                self._seconds_since(
                    started_at
                )
            )

        elif self.latest_incident:

            incident = (
                self.latest_incident
            )

            seconds = incident.get(
                "duration_seconds"
            )

            if seconds is None:

                seconds = (
                    self._seconds_between(
                        incident.get(
                            "started_at"
                        ),
                        incident.get(
                            "ended_at"
                        ),
                    )
                )

        else:

            self.incident_duration_label.setText(
                "--"
            )

            return

        self.incident_duration_label.setText(
            self._format_duration(
                seconds
            )
        )

    # =====================================================
    # HELPERS
    # =====================================================

    # =====================================================
    # AVAILABILITY
    # =====================================================

    def _availability_received(
        self,
        ip: str,
        data,
    ):

        # Ignora resposta antiga caso
        # o usuário já tenha aberto outro IP.

        if (
            str(ip)
            != str(self.current_ip)
        ):

            return

        if not isinstance(
            data,
            dict,
        ):

            data = {}

        availability = self._first_value(
            data,
            "availability_percent",
            "availability",
            "uptime_percent",
        )

        monitored_seconds = self._first_value(
            data,
            "monitored_seconds",
            "monitoring_seconds",
        )

        downtime_seconds = self._first_value(
            data,
            "downtime_seconds",
            "offline_seconds",
        )

        incident_count = self._first_value(
            data,
            "incident_count",
            "incidents",
            "down_count",
        )

        # ================================================
        # AVAILABILITY %
        # ================================================

        if availability is None:

            availability_text = "--"

        else:

            try:

                availability_text = (
                    f"{float(availability):.2f}%"
                )

            except (
                TypeError,
                ValueError,
            ):

                availability_text = str(
                    availability
                )

        self.availability_card.set_value(
            availability_text
        )

        # ================================================
        # MONITORED TIME
        # ================================================

        self.monitored_time_card.set_value(
            self._format_duration(
                monitored_seconds
            )
        )

        # ================================================
        # DOWNTIME
        # ================================================

        self.downtime_card.set_value(
            self._format_duration(
                downtime_seconds
            )
        )

        # ================================================
        # INCIDENT COUNT
        # ================================================

        self.incident_count_card.set_value(
            incident_count
            if incident_count is not None
            else 0
        )

    @staticmethod
    def _first_value(
        data: dict,
        *keys,
    ):
        """
        Retorna o primeiro valor existente
        entre as chaves informadas.
        """

        for key in keys:

            value = data.get(
                key
            )

            if value is not None:

                return value

        return None

    @staticmethod
    def _format_latency(
        value,
    ) -> str:

        if value is None:

            return "--"

        try:

            return (
                f"{float(value):.2f} ms"
            )

        except (
            TypeError,
            ValueError,
        ):

            return str(value)

    @staticmethod
    def _format_percent(
        value,
    ) -> str:

        if value is None:

            return "--"

        try:

            return (
                f"{float(value):.1f}%"
            )

        except (
            TypeError,
            ValueError,
        ):

            return str(value)

    @staticmethod
    def _parse_datetime(
        value,
    ):

        if not value:
            return None

        try:

            return datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    @classmethod
    def _format_datetime(
        cls,
        value,
    ):

        parsed = cls._parse_datetime(
            value
        )

        if parsed is None:

            return "--"

        try:

            if parsed.tzinfo is not None:

                parsed = (
                    parsed.astimezone()
                )

        except Exception:

            pass

        return parsed.strftime(
            "%d/%m/%Y %H:%M:%S"
        )

    @classmethod
    def _seconds_since(
        cls,
        value,
    ):

        start = cls._parse_datetime(
            value
        )

        if start is None:

            return None

        if start.tzinfo:

            now = datetime.now(
                start.tzinfo
            )

        else:

            now = datetime.now()

        return max(
            0,
            int(
                (
                    now - start
                ).total_seconds()
            ),
        )

    @classmethod
    def _seconds_between(
        cls,
        start_value,
        end_value,
    ):

        start = cls._parse_datetime(
            start_value
        )

        end = cls._parse_datetime(
            end_value
        )

        if (
            start is None
            or end is None
        ):

            return None

        return max(
            0,
            int(
                (
                    end - start
                ).total_seconds()
            ),
        )

    @staticmethod
    def _format_duration(
        seconds,
    ) -> str:

        if seconds is None:

            return "--"

        try:

            total_seconds = max(
                0,
                int(
                    float(seconds)
                ),
            )

        except (
            TypeError,
            ValueError,
        ):

            return str(seconds)

        days, remainder = divmod(
            total_seconds,
            86400,
        )

        hours, remainder = divmod(
            remainder,
            3600,
        )

        minutes, seconds = divmod(
            remainder,
            60,
        )

        if days > 0:

            return (
                f"{days}d "
                f"{hours}h "
                f"{minutes}m"
            )

        if hours > 0:

            return (
                f"{hours}h "
                f"{minutes}m"
            )

        if minutes > 0:

            return (
                f"{minutes}m "
                f"{seconds}s"
            )

        return (
            f"{seconds}s"
        )

    # =====================================================
    # STATUS STYLE
    # =====================================================

    def _update_status_style(
        self,
        status: str,
    ):

        status = status.upper()

        color = status_color(status)
        soft_color = status_soft_color(status)

        self.status_label.setStyleSheet(
            f"""
            QLabel {{
                color: {color};
                background: {soft_color};
                border: 1px solid {color};
                border-radius: {RADIUS_MD}px;
                padding: 8px 14px;
                font-size: {FONT_SIZE_LG}px;
                font-weight: 800;
            }}
            """
        )

    # =====================================================
    # STYLE
    # =====================================================

    def _apply_style(
        self,
    ):

        legacy_qss = """
            QMainWindow {
                background: %(BG_APP)s;
            }

            QScrollArea#detailScroll {
                background: %(BG_APP)s;
                border: none;
            }

            QScrollArea#detailScroll > QWidget > QWidget {
                background: %(BG_APP)s;
            }

            QWidget#detailViewport {
                background: %(BG_APP)s;
            }

            QWidget#detailContent {
                background: %(BG_APP)s;
                color: %(TEXT_PRIMARY)s;
            }

            QLabel#deviceTitle {
                color: %(TEXT_PRIMARY)s;
                font-size: 26px;
                font-weight: 800;
            }

            QLabel#deviceIp {
                color: %(TEXT_MUTED)s;
                font-size: 13px;
            }

            QLabel#sectionTitle {
                color: %(TEXT_MUTED)s;
                font-size: 11px;
                font-weight: 800;
            }

            QFrame#metricCard {
                background: %(BG_PANEL)s;
                border: 1px solid %(BORDER)s;
                border-radius: 10px;
            }

            QFrame#metricCard:hover {
                border-color: %(BORDER_STRONG)s;
            }

            QLabel#metricTitle {
                color: %(TEXT_MUTED)s;
                font-size: 10px;
                font-weight: 700;
            }

            QLabel#metricValue {
                color: %(TEXT_PRIMARY)s;
                font-size: 20px;
                font-weight: 800;
            }

            QFrame#incidentPanel,
            QFrame#communicationPanel {
                background: %(BG_PANEL)s;
                border: 1px solid %(BORDER)s;
                border-radius: 10px;
            }

            QFrame#latencyChartPanel {
                background: %(BG_PANEL)s;
                border: 1px solid %(BORDER)s;
                border-radius: 10px;
            }

            QLabel#chartTitle {
                color: %(TEXT_SECONDARY)s;
                font-size: 11px;
                font-weight: 800;
            }

            QLabel#chartSummary {
                color: %(TEXT_MUTED)s;
                font-size: 11px;
            }

            QComboBox#chartPeriod {
                background: %(BG_PANEL_ALT)s;
                color: %(TEXT_PRIMARY)s;
                border: 1px solid %(BORDER)s;
                border-radius: 6px;
                padding: 6px 10px;
            }

            QComboBox#chartPeriod:hover {
                border-color: %(ACCENT)s;
            }

            QComboBox#chartPeriod QAbstractItemView {
                background: %(BG_PANEL)s;
                color: %(TEXT_PRIMARY)s;
                border: 1px solid %(BORDER)s;
                selection-background-color: %(BG_PANEL_ALT)s;
            }

            QLabel#incidentMode {
                font-size: 12px;
                font-weight: 800;
            }

            QLabel#infoTitle {
                color: %(TEXT_MUTED)s;
                font-size: 12px;
            }

            QLabel#infoValue {
                color: %(TEXT_PRIMARY)s;
                font-size: 13px;
                font-weight: 700;
            }

            QScrollBar:vertical {
                background: %(BG_APP)s;
                width: 10px;
            }

            QScrollBar::handle:vertical {
                background: %(BORDER_STRONG)s;
                border-radius: 5px;
                min-height: 40px;
            }

            QScrollBar::handle:vertical:hover {
                background: %(BORDER_STRONG)s;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QStatusBar {
                background: %(BG_PANEL)s;
                color: %(TEXT_MUTED)s;
            }
            """
        legacy_qss = legacy_qss % vars(theme)
        self.setStyleSheet(
            legacy_qss
            + device_detail_qss()
            + nodaris_global_visual_qss()
            + nodaris_desktop_controls_qss()
        )
