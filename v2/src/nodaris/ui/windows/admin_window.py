from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nodaris.ui.components.status_card import StatusCard
from nodaris.ui.theme import tokens as t
from nodaris.ui.theme.styles import app_stylesheet


class AdminWindow(QMainWindow):
    devices_requested = Signal()
    device_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("NODARIS Admin")
        self.resize(1250, 780)
        self.setMinimumSize(950, 650)
        self.setStyleSheet(app_stylesheet())

        self._cards: dict[str, StatusCard] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(20)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("NODARIS")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Network Availability Monitor")
        subtitle.setObjectName("pageSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)

        devices_button = QPushButton("Equipamentos")
        devices_button.clicked.connect(self.devices_requested.emit)

        self.connection_label = QLabel("● CONECTANDO...")
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_label.setStyleSheet(
            f"color:{t.WARNING}; font-weight:800; padding:0 10px;"
        )

        header.addWidget(devices_button)
        header.addWidget(self.connection_label)
        root.addLayout(header)

        summary = QHBoxLayout()
        summary.setSpacing(12)

        for key in ("TOTAL", "ONLINE", "SUSPECT", "OFFLINE", "RECOVERING"):
            card = StatusCard(key)
            self._cards[key] = card
            summary.addWidget(card)

        root.addLayout(summary)

        body = QHBoxLayout()
        body.setSpacing(16)

        devices_panel = QFrame()
        devices_panel.setProperty("panel", True)
        devices_layout = QVBoxLayout(devices_panel)
        devices_layout.setContentsMargins(18, 16, 18, 16)

        devices_title = QLabel("MONITORAMENTO")
        devices_title.setObjectName("sectionTitle")
        devices_layout.addWidget(devices_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.device_container = QWidget()
        self.device_grid = QGridLayout(self.device_container)
        self.device_grid.setContentsMargins(0, 6, 0, 0)
        self.device_grid.setHorizontalSpacing(10)
        self.device_grid.setVerticalSpacing(10)
        scroll.setWidget(self.device_container)
        devices_layout.addWidget(scroll, 1)

        alerts_panel = QFrame()
        alerts_panel.setProperty("panel", True)
        alerts_panel.setMinimumWidth(290)
        alerts_panel.setMaximumWidth(360)
        alerts_layout = QVBoxLayout(alerts_panel)
        alerts_layout.setContentsMargins(18, 16, 18, 16)

        alerts_title = QLabel("INCIDENTES RECENTES")
        alerts_title.setObjectName("sectionTitle")
        self.alerts_label = QLabel("Nenhum incidente carregado.")
        self.alerts_label.setWordWrap(True)
        self.alerts_label.setStyleSheet(f"color:{t.TEXT_MUTED};")

        alerts_layout.addWidget(alerts_title)
        alerts_layout.addWidget(self.alerts_label)
        alerts_layout.addStretch(1)

        body.addWidget(devices_panel, 1)
        body.addWidget(alerts_panel)
        root.addLayout(body, 1)

    def set_connection_state(self, connected: bool) -> None:
        if connected:
            self.connection_label.setText("● CONECTADO")
            self.connection_label.setStyleSheet(
                f"color:{t.SUCCESS}; font-weight:800; padding:0 10px;"
            )
        else:
            self.connection_label.setText("● DESCONECTADO")
            self.connection_label.setStyleSheet(
                f"color:{t.DANGER}; font-weight:800; padding:0 10px;"
            )

    def set_summary(self, **values: int) -> None:
        for key, value in values.items():
            card = self._cards.get(key.upper())
            if card:
                card.set_value(value)
