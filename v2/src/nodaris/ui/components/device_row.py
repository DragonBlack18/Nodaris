from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from nodaris.ui.theme import tokens as t
from nodaris.ui.theme.status import normalize_status, status_color, status_soft_color


class DeviceRow(QFrame):
    details_requested = Signal(str)

    def __init__(self, device: dict, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("deviceRow")
        self.setProperty("panel", True)
        self._build_ui()
        self.set_device(device)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(14)

        identity = QVBoxLayout()
        identity.setSpacing(3)

        self.name_label = QLabel("Sem nome")
        self.name_label.setStyleSheet(
            f"color:{t.TEXT_PRIMARY}; font-size:13px; font-weight:800;"
        )
        self.ip_label = QLabel("--")
        self.ip_label.setStyleSheet(f"color:{t.TEXT_MUTED}; font-size:11px;")

        identity.addWidget(self.name_label)
        identity.addWidget(self.ip_label)

        layout.addLayout(identity)
        layout.addStretch(1)

        self.status_label = QLabel("UNKNOWN")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumWidth(108)

        self.latency_label = QLabel("--")
        self.latency_label.setMinimumWidth(100)
        self.latency_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.latency_label.setStyleSheet(f"color:{t.TEXT_SECONDARY};")

        self.details_button = QPushButton("Detalhes")
        self.details_button.clicked.connect(self._emit_details)

        layout.addWidget(self.status_label)
        layout.addWidget(self.latency_label)
        layout.addWidget(self.details_button)

    def set_device(self, device: dict) -> None:
        self.device = dict(device)
        self.ip = str(device.get("ip", "")).strip()
        self.name_label.setText(
            str(device.get("name") or device.get("nome") or "Sem nome")
        )
        self.ip_label.setText(self.ip or "--")

        raw_status = "MAINTENANCE" if device.get("maintenance") else (
            (device.get("health") or {}).get("status")
            or device.get("effective_status")
            or device.get("status")
            or "UNKNOWN"
        )
        status = normalize_status(raw_status)
        display = "MANUTENÇÃO" if status == "MAINTENANCE" else status

        self.status_label.setText(display)
        self.status_label.setStyleSheet(
            f"color:{status_color(status)};"
            f"background:{status_soft_color(status)};"
            f"border:1px solid {status_color(status)};"
            f"border-radius:{t.RADIUS_SM}px;"
            "padding:5px 10px; font-size:10px; font-weight:800;"
        )

        latency = device.get("latency_ms")
        if latency is None:
            self.latency_label.setText("--")
        else:
            try:
                self.latency_label.setText(f"{float(latency):.2f} ms")
            except (TypeError, ValueError):
                self.latency_label.setText("--")

    def _emit_details(self) -> None:
        if self.ip:
            self.details_requested.emit(self.ip)
