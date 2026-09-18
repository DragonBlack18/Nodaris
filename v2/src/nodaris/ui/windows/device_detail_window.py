from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nodaris.ui.components.status_card import StatusCard
from nodaris.ui.theme import tokens as t
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
        self.setCentralWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(28, 28, 28, 32)
        root.setSpacing(22)

        header = QHBoxLayout()
        identity = QVBoxLayout()

        self.name_label = QLabel("Equipamento")
        self.name_label.setObjectName("pageTitle")
        self.ip_label = QLabel("--")
        self.ip_label.setObjectName("pageSubtitle")

        identity.addWidget(self.name_label)
        identity.addWidget(self.ip_label)
        header.addLayout(identity)
        header.addStretch(1)

        self.status_label = QLabel("UNKNOWN")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            f"background:{t.BG_ELEVATED}; border:1px solid {t.BORDER};"
            f"border-radius:{t.RADIUS_MD}px; padding:8px 14px; font-weight:900;"
        )
        header.addWidget(self.status_label)
        root.addLayout(header)

        health_title = QLabel("SAÚDE ATUAL")
        health_title.setObjectName("sectionTitle")
        root.addWidget(health_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.quality_card = StatusCard("QUALIDADE", "--")
        self.latency_card = StatusCard("LATÊNCIA", "--")
        self.failures_card = StatusCard("FALHAS", 0)
        self.successes_card = StatusCard("SUCESSOS", 0)

        for index, card in enumerate(
            (
                self.quality_card,
                self.latency_card,
                self.failures_card,
                self.successes_card,
            )
        ):
            grid.addWidget(card, index // 2, index % 2)

        root.addLayout(grid)

        chart_panel = QFrame()
        chart_panel.setProperty("panel", True)
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(18, 16, 18, 16)

        chart_title = QLabel("LATÊNCIA")
        chart_title.setObjectName("sectionTitle")
        self.chart_placeholder = QLabel("Gráfico será conectado ao histórico agregado da V2.")
        self.chart_placeholder.setMinimumHeight(220)
        self.chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_placeholder.setStyleSheet(f"color:{t.TEXT_MUTED};")

        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(self.chart_placeholder)
        root.addWidget(chart_panel)

        incident_panel = QFrame()
        incident_panel.setProperty("panel", True)
        incident_layout = QVBoxLayout(incident_panel)
        incident_layout.setContentsMargins(18, 16, 18, 16)

        incident_title = QLabel("INCIDENTE")
        incident_title.setObjectName("sectionTitle")
        self.incident_label = QLabel("Nenhum incidente ativo.")
        self.incident_label.setStyleSheet(f"color:{t.TEXT_MUTED};")

        incident_layout.addWidget(incident_title)
        incident_layout.addWidget(self.incident_label)
        root.addWidget(incident_panel)

    def set_identity(self, name: str, ip: str, status: str) -> None:
        self.name_label.setText(name)
        self.ip_label.setText(ip)
        self.status_label.setText(status.upper())
