from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from nodaris.ui.components.device_row import DeviceRow
from nodaris.ui.components.status_card import StatusCard
from nodaris.ui.theme import tokens as t
from nodaris.ui.theme.styles import app_stylesheet


class AdminWindow(QMainWindow):
    devices_requested = Signal()
    device_selected = Signal(str)
    alerts_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("NODARIS Admin")
        self.resize(1250, 780)
        self.setMinimumSize(950, 650)
        self.setStyleSheet(app_stylesheet())

        self._cards: dict[str, StatusCard] = {}
        self._device_rows: dict[str, DeviceRow] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(20)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel("NODARIS")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Network Availability Monitor")
        subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header.addLayout(title_box)
        header.addStretch(1)

        self.alert_button = QToolButton()
        self.alert_button.setText("⚠")
        self.alert_button.setToolTip("Nenhum alerta ativo")
        self.alert_button.setFixedHeight(t.CONTROL_HEIGHT_LG)
        self.alert_button.clicked.connect(self.alerts_requested.emit)

        devices_button = QPushButton("Equipamentos")
        devices_button.setFixedHeight(t.CONTROL_HEIGHT_LG)
        devices_button.clicked.connect(self.devices_requested.emit)

        self.connection_label = QLabel("● CONECTANDO...")
        self.connection_label.setFixedHeight(t.CONTROL_HEIGHT_LG)
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_label.setStyleSheet(
            f"color:{t.WARNING}; background:#3B2A11;"
            f"border:1px solid {t.WARNING}; border-radius:{t.RADIUS_SM}px;"
            "padding:5px 10px; font-size:10px; font-weight:700;"
        )

        header.addWidget(self.alert_button)
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

        devices_title = QLabel("EQUIPAMENTOS MONITORADOS")
        devices_title.setObjectName("sectionTitle")
        root.addWidget(devices_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.devices_container = QWidget()
        self.devices_layout = QVBoxLayout(self.devices_container)
        self.devices_layout.setContentsMargins(0, 0, 0, 0)
        self.devices_layout.setSpacing(8)
        self.devices_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.devices_container)
        root.addWidget(scroll, 1)

        self.statusBar().showMessage("Aguardando conexão com o Core.")

    def set_connection_state(self, connected: bool) -> None:
        if connected:
            self.connection_label.setText("● MONITORANDO")
            self.connection_label.setStyleSheet(
                f"color:{t.SUCCESS}; background:#16351F;"
                f"border:1px solid {t.SUCCESS}; border-radius:{t.RADIUS_SM}px;"
                "padding:5px 10px; font-size:10px; font-weight:700;"
            )
            self.statusBar().showMessage("Monitoramento operacional.")
        else:
            self.connection_label.setText("● API INDISPONÍVEL")
            self.connection_label.setStyleSheet(
                f"color:{t.DANGER}; background:#3A171A;"
                f"border:1px solid {t.DANGER}; border-radius:{t.RADIUS_SM}px;"
                "padding:5px 10px; font-size:10px; font-weight:700;"
            )

    def set_summary(self, **values: int) -> None:
        for key, value in values.items():
            card = self._cards.get(key.upper())
            if card:
                card.set_value(value)

    def set_devices(self, devices: list[dict]) -> None:
        while self.devices_layout.count():
            item = self.devices_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._device_rows.clear()
        counts = {"ONLINE": 0, "SUSPECT": 0, "OFFLINE": 0, "RECOVERING": 0}

        for device in devices:
            if not isinstance(device, dict):
                continue
            ip = str(device.get("ip", "")).strip()
            row = DeviceRow(device)
            row.details_requested.connect(self.device_selected.emit)
            self.devices_layout.addWidget(row)
            if ip:
                self._device_rows[ip] = row

            status = str(
                (device.get("health") or {}).get("status")
                or device.get("status")
                or "UNKNOWN"
            ).upper()
            if status in counts and not device.get("maintenance"):
                counts[status] += 1

        self.set_summary(
            total=len(self._device_rows),
            online=counts["ONLINE"],
            suspect=counts["SUSPECT"],
            offline=counts["OFFLINE"],
            recovering=counts["RECOVERING"],
        )

    def set_alert_count(self, count: int) -> None:
        count = max(0, int(count))
        self.alert_button.setText("⚠" if count == 0 else f"⚠ {count}")
        self.alert_button.setToolTip(
            "Nenhum alerta ativo"
            if count == 0
            else f"{count} alerta(s) ativo(s)"
        )
