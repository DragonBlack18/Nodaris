from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from nodaris.ui.components.status_card import StatusCard
from nodaris.ui.components.wallboard_ip_item import WallboardIpItem
from nodaris.ui.theme import tokens as t
from nodaris.ui.theme.styles import app_stylesheet


class WallboardWindow(QMainWindow):
    MIN_ITEM_WIDTH = 175
    HORIZONTAL_GAP = 10
    MAX_COLUMNS = 8

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("NODARIS TV")
        self.resize(1500, 880)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(app_stylesheet())

        self._cards: dict[str, StatusCard] = {}
        self._devices: list[dict] = []
        self._items: list[WallboardIpItem] = []
        self._build_ui()

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._tick_clock)
        self.clock_timer.start(1000)
        self._tick_clock()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(22, 16, 22, 14)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(1)

        title = QLabel("NODARIS")
        title.setObjectName("pageTitle")
        self.health_label = QLabel("● AGUARDANDO MONITORAMENTO")
        self.health_label.setStyleSheet(f"color:{t.WARNING}; font-weight:800;")
        title_box.addWidget(title)
        title_box.addWidget(self.health_label)

        header.addLayout(title_box)
        header.addStretch(1)

        clock_box = QVBoxLayout()
        clock_box.setSpacing(1)
        self.clock_label = QLabel("--:--:--")
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.clock_label.setStyleSheet("font-size:24px; font-weight:900;")
        self.last_update_label = QLabel("Última atualização: aguardando...")
        self.last_update_label.setObjectName("pageSubtitle")
        self.last_update_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        clock_box.addWidget(self.clock_label)
        clock_box.addWidget(self.last_update_label)
        header.addLayout(clock_box)
        root.addLayout(header)

        summary = QHBoxLayout()
        summary.setSpacing(6)
        for key in ("TOTAL", "ONLINE", "SUSPECT", "OFFLINE", "RECOVERING"):
            card = StatusCard(key)
            self._cards[key] = card
            summary.addWidget(card)
        root.addLayout(summary)

        self.matrix_panel = QFrame()
        self.matrix_panel.setProperty("panel", True)
        matrix_layout = QVBoxLayout(self.matrix_panel)
        matrix_layout.setContentsMargins(10, 8, 10, 8)
        matrix_layout.setSpacing(8)

        matrix_title = QLabel("EQUIPAMENTOS")
        matrix_title.setObjectName("sectionTitle")
        matrix_layout.addWidget(matrix_title)

        self.device_grid = QGridLayout()
        self.device_grid.setHorizontalSpacing(self.HORIZONTAL_GAP)
        self.device_grid.setVerticalSpacing(4)
        matrix_layout.addLayout(self.device_grid, 1)
        root.addWidget(self.matrix_panel, 1)

    def set_monitoring_state(self, healthy: bool) -> None:
        self.health_label.setText(
            "● MONITORAMENTO OPERACIONAL"
            if healthy
            else "● MONITORAMENTO INDISPONÍVEL"
        )
        self.health_label.setStyleSheet(
            f"color:{t.SUCCESS if healthy else t.DANGER}; font-weight:800;"
        )

    def set_devices(self, devices: list[dict]) -> None:
        self._devices = [item for item in devices if isinstance(item, dict)]
        counts = {"ONLINE": 0, "SUSPECT": 0, "OFFLINE": 0, "RECOVERING": 0}

        for device in self._devices:
            status = str(
                (device.get("health") or {}).get("status")
                or device.get("status")
                or "UNKNOWN"
            ).upper()
            if status in counts and not device.get("maintenance"):
                counts[status] += 1

        self.set_summary(
            total=len(self._devices),
            online=counts["ONLINE"],
            suspect=counts["SUSPECT"],
            offline=counts["OFFLINE"],
            recovering=counts["RECOVERING"],
        )
        self.last_update_label.setText(
            f"Última atualização: {datetime.now().strftime('%H:%M:%S')}"
        )
        self._render_devices()

    def _render_devices(self) -> None:
        while self.device_grid.count():
            item = self.device_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._items.clear()
        available_width = max(1, self.width() - 64)
        columns = max(
            1,
            min(
                self.MAX_COLUMNS,
                available_width // (self.MIN_ITEM_WIDTH + self.HORIZONTAL_GAP),
            ),
        )

        ordered = sorted(
            self._devices,
            key=lambda item: (
                _status_priority(item),
                str(item.get("ip", "")),
            ),
        )

        for index, device in enumerate(ordered):
            item = WallboardIpItem()
            item.update_device(device)
            self._items.append(item)
            self.device_grid.addWidget(item, index // columns, index % columns)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._devices:
            self._render_devices()

    def set_summary(self, **values: int) -> None:
        for key, value in values.items():
            card = self._cards.get(key.upper())
            if card:
                card.set_value(value)

    def _tick_clock(self) -> None:
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S"))


def _status_priority(device: dict) -> int:
    if device.get("maintenance"):
        return 6
    status = str(
        (device.get("health") or {}).get("status")
        or device.get("status")
        or "UNKNOWN"
    ).upper()
    return {
        "OFFLINE": 0,
        "SUSPECT": 1,
        "RECOVERING": 2,
        "ERROR": 3,
        "UNKNOWN": 4,
        "ONLINE": 5,
    }.get(status, 4)
