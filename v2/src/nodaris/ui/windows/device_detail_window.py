from __future__ import annotations

from PySide6.QtCore import Qt
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

from nodaris.ui.components.latency_chart import LatencyChart
from nodaris.ui.components.metric_card import MetricCard
from nodaris.ui.theme import tokens as t
from nodaris.ui.theme.status import normalize_status, status_color, status_soft_color
from nodaris.ui.theme.styles import app_stylesheet


class DeviceDetailWindow(QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("NODARIS — Detalhes do Equipamento")
        self.resize(1100, 850)
        self.setMinimumSize(680, 600)
        self.setStyleSheet(app_stylesheet())
        self._build_ui()

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll)

        viewport = QWidget()
        scroll.setWidget(viewport)
        viewport_layout = QHBoxLayout(viewport)
        viewport_layout.setContentsMargins(24, 0, 24, 40)
        viewport_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        content = QWidget()
        content.setMaximumWidth(1280)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        viewport_layout.addWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(0, 28, 0, 28)
        root.setSpacing(24)

        header = QHBoxLayout()
        identity = QVBoxLayout()

        self.name_label = QLabel("Equipamento")
        self.name_label.setObjectName("pageTitle")
        self.name_label.setWordWrap(True)
        self.ip_label = QLabel("--")
        self.ip_label.setObjectName("pageSubtitle")

        identity.addWidget(self.name_label)
        identity.addWidget(self.ip_label)
        header.addLayout(identity)
        header.addStretch(1)

        self.status_label = QLabel("UNKNOWN")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        health_title = QLabel("SAÚDE ATUAL")
        health_title.setObjectName("sectionTitle")
        root.addWidget(health_title)

        self.health_grid = QGridLayout()
        self.health_grid.setHorizontalSpacing(12)
        self.health_grid.setVerticalSpacing(12)

        cards = [
            ("quality_card", "QUALIDADE"),
            ("current_latency_card", "LATÊNCIA ATUAL"),
            ("average_latency_card", "LATÊNCIA MÉDIA"),
            ("loss_card", "PERDA RECENTE"),
            ("min_latency_card", "LATÊNCIA MÍNIMA"),
            ("max_latency_card", "LATÊNCIA MÁXIMA"),
            ("failures_card", "FALHAS CONSECUTIVAS"),
            ("successes_card", "SUCESSOS CONSECUTIVOS"),
        ]
        for index, (attribute, title) in enumerate(cards):
            card = MetricCard(title)
            setattr(self, attribute, card)
            self.health_grid.addWidget(card, index // 4, index % 4)
        root.addLayout(self.health_grid)

        self.latency_chart = LatencyChart()
        root.addWidget(self.latency_chart)

        availability_title = QLabel("ESTABILIDADE — ÚLTIMAS 24H")
        availability_title.setObjectName("sectionTitle")
        root.addWidget(availability_title)

        availability_grid = QGridLayout()
        availability_grid.setHorizontalSpacing(12)
        availability_grid.setVerticalSpacing(12)
        availability = [
            ("availability_card", "DISPONIBILIDADE"),
            ("monitored_time_card", "TEMPO MONITORADO"),
            ("downtime_card", "TEMPO OFFLINE"),
            ("incident_count_card", "QUEDAS"),
        ]
        for index, (attribute, title) in enumerate(availability):
            card = MetricCard(title)
            setattr(self, attribute, card)
            availability_grid.addWidget(card, 0, index)
        root.addLayout(availability_grid)

        incident_title = QLabel("INCIDENTE")
        incident_title.setObjectName("sectionTitle")
        root.addWidget(incident_title)

        self.incident_panel = QFrame()
        self.incident_panel.setProperty("panel", True)
        incident_layout = QGridLayout(self.incident_panel)
        incident_layout.setContentsMargins(18, 16, 18, 16)
        incident_layout.setHorizontalSpacing(30)
        incident_layout.setVerticalSpacing(10)

        self.incident_mode_label = QLabel("Nenhum incidente")
        self.incident_mode_label.setStyleSheet("font-weight:800;")
        self.incident_started_label = QLabel("--")
        self.incident_ended_label = QLabel("--")
        self.incident_duration_label = QLabel("--")

        incident_layout.addWidget(self.incident_mode_label, 0, 0, 1, 2)
        for row, (label, widget) in enumerate(
            (
                ("Início", self.incident_started_label),
                ("Recuperação", self.incident_ended_label),
                ("Duração", self.incident_duration_label),
            ),
            start=1,
        ):
            title = QLabel(label)
            title.setStyleSheet(f"color:{t.TEXT_MUTED};")
            incident_layout.addWidget(title, row, 0)
            incident_layout.addWidget(widget, row, 1)
        root.addWidget(self.incident_panel)

        communication_title = QLabel("COMUNICAÇÃO")
        communication_title.setObjectName("sectionTitle")
        root.addWidget(communication_title)

        communication_panel = QFrame()
        communication_panel.setProperty("panel", True)
        communication_layout = QGridLayout(communication_panel)
        communication_layout.setContentsMargins(18, 16, 18, 16)
        communication_layout.setHorizontalSpacing(30)
        communication_layout.setVerticalSpacing(10)

        self.confirmed_status_label = QLabel("--")
        self.probe_status_label = QLabel("--")
        for row, (label, widget) in enumerate(
            (
                ("Estado confirmado", self.confirmed_status_label),
                ("Última tentativa ICMP", self.probe_status_label),
            )
        ):
            title = QLabel(label)
            title.setStyleSheet(f"color:{t.TEXT_MUTED};")
            communication_layout.addWidget(title, row, 0)
            communication_layout.addWidget(widget, row, 1)
        root.addWidget(communication_panel)

    def set_identity(self, name: str, ip: str, status: str) -> None:
        normalized = normalize_status(status)
        self.name_label.setText(name)
        self.ip_label.setText(ip)
        self.status_label.setText(
            "MANUTENÇÃO" if normalized == "MAINTENANCE" else normalized
        )
        self.status_label.setStyleSheet(
            f"color:{status_color(normalized)};"
            f"background:{status_soft_color(normalized)};"
            f"border:1px solid {status_color(normalized)};"
            f"border-radius:{t.RADIUS_MD}px;"
            "padding:8px 14px; font-weight:900;"
        )

    def set_health(self, health: dict) -> None:
        latency = health.get("latency") if isinstance(health.get("latency"), dict) else {}
        self.quality_card.set_value(health.get("quality"))
        self.current_latency_card.set_value(_format_ms(latency.get("current_ms")))
        self.average_latency_card.set_value(_format_ms(latency.get("average_ms")))
        self.loss_card.set_value(_format_percent(health.get("loss_percent")))
        self.min_latency_card.set_value(_format_ms(latency.get("min_ms")))
        self.max_latency_card.set_value(_format_ms(latency.get("max_ms")))
        self.failures_card.set_value(health.get("consecutive_failures", 0))
        self.successes_card.set_value(health.get("consecutive_successes", 0))


def _format_ms(value) -> str:
    if value is None:
        return "--"
    try:
        return f"{float(value):.2f} ms"
    except (TypeError, ValueError):
        return "--"


def _format_percent(value) -> str:
    if value is None:
        return "--"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "--"
