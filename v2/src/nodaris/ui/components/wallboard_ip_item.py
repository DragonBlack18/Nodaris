from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy

from nodaris.ui.theme import tokens as t
from nodaris.ui.theme.status import normalize_status, status_color, status_soft_color


class WallboardIpItem(QFrame):
    ITEM_HEIGHT = 32

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self.ITEM_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(7)

        self.status_dot = QLabel("●")
        self.status_dot.setFixedWidth(16)
        self.status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.ip_label = QLabel("--")
        self.value_label = QLabel("--")
        self.value_label.setMinimumWidth(72)
        self.value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        layout.addWidget(self.status_dot)
        layout.addWidget(self.ip_label, 1)
        layout.addWidget(self.value_label)

    def update_device(self, device: dict) -> None:
        health = device.get("health") if isinstance(device.get("health"), dict) else {}
        ip = str(device.get("ip", "")).strip()
        name = str(device.get("name") or device.get("nome") or ip or "Equipamento")
        status = normalize_status(
            "MAINTENANCE"
            if device.get("maintenance")
            else (
                health.get("status")
                or device.get("effective_status")
                or device.get("status")
            )
        )
        latency = device.get("latency_ms")
        color = status_color(status)
        soft = status_soft_color(status)

        self.ip_label.setText(ip or "--")
        self.status_dot.setStyleSheet(f"color:{color};")
        self.setStyleSheet(
            f"QFrame{{background:{soft}; border:1px solid {t.BORDER};"
            f"border-radius:{t.RADIUS_SM}px;}}"
            f"QLabel{{background:transparent;}}"
        )

        if status == "MAINTENANCE":
            value = "MANUTENÇÃO"
        elif status in {"OFFLINE", "SUSPECT", "ERROR", "UNKNOWN"}:
            value = status
        elif status == "RECOVERING":
            value = "RECOVER"
        elif latency is None:
            value = "ONLINE"
        else:
            try:
                number = float(latency)
                value = "<1 ms" if number < 1 else f"{number:.0f} ms"
            except (TypeError, ValueError):
                value = "ONLINE"

        self.value_label.setText(value)
        self.setToolTip(
            f"{name}\nIP: {ip or '--'}\nStatus: {status}\nLatência: {value}"
        )
