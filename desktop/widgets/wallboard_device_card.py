from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)


class WallboardDeviceCard(QFrame):
    """
    Card visual de um equipamento no Wallboard.

    Não executa ping, não calcula estado e não acessa banco. Apenas
    apresenta o estado recebido pela API.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_ip = ""
        self.current_status = "UNKNOWN"

        self.setObjectName("wallboardDeviceCard")
        self.setProperty("status", "unknown")
        self.setMinimumWidth(220)
        self.setMinimumHeight(145)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(7)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        self.name_label = QLabel("Equipamento")
        self.name_label.setObjectName("deviceName")
        self.name_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )
        self.name_label.setWordWrap(False)

        self.status_label = QLabel("UNKNOWN")
        self.status_label.setObjectName("deviceStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumWidth(88)

        header.addWidget(self.name_label, 1)
        header.addWidget(self.status_label, 0)
        root.addLayout(header)

        self.ip_label = QLabel("--")
        self.ip_label.setObjectName("deviceIp")
        root.addWidget(self.ip_label)
        root.addStretch(1)

        value_row = QHBoxLayout()
        value_row.setContentsMargins(0, 0, 0, 0)
        value_row.setSpacing(12)

        self.value_label = QLabel("--")
        self.value_label.setObjectName("deviceValue")

        self.secondary_label = QLabel("")
        self.secondary_label.setObjectName("deviceSecondary")
        self.secondary_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        value_row.addWidget(self.value_label, 1)
        value_row.addWidget(self.secondary_label, 0)
        root.addLayout(value_row)

    def update_device(self, device: dict):
        if not isinstance(device, dict):
            return

        ip = str(device.get("ip", ""))
        name = str(
            device.get("name")
            or device.get("nome")
            or ip
            or "Equipamento"
        )
        health = device.get("health") or {}
        if not isinstance(health, dict):
            health = {}

        status = str(
            health.get("status")
            or health.get("effective_status")
            or device.get("effective_status")
            or device.get("status")
            or "UNKNOWN"
        ).upper()
        latency = self._first_value(
            device,
            health,
            ("latency_ms", "current_latency_ms", "current_ms"),
        )
        quality = self._first_value(
            device,
            health,
            ("quality", "latency_quality"),
        )

        self.current_ip = ip
        self.current_status = status
        self.name_label.setText(name)
        self.ip_label.setText(ip or "--")
        self.status_label.setText(status)

        if status == "OFFLINE":
            self.value_label.setText("SEM COMUNICAÇÃO")
        elif latency is not None:
            try:
                self.value_label.setText(f"{float(latency):.0f} ms")
            except (TypeError, ValueError):
                self.value_label.setText("--")
        else:
            self.value_label.setText("--")

        self.secondary_label.setText(str(quality or ""))

        status_property = status.lower()
        if status_property not in (
            "online",
            "suspect",
            "offline",
            "recovering",
        ):
            status_property = "unknown"

        self.setProperty("status", status_property)
        self.status_label.setProperty("status", status_property)
        self._refresh_style(self)
        self._refresh_style(self.status_label)

    @staticmethod
    def _first_value(device: dict, health: dict, keys):
        for source in (health, device):
            for key in keys:
                value = source.get(key)
                if value is not None:
                    return value
        return None

    @staticmethod
    def _refresh_style(widget):
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()
