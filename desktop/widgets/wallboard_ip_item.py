from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
)

from desktop.theme import wallboard_ip_item_qss


class WallboardIpItem(QFrame):
    """
    Item compacto utilizado exclusivamente no Wallboard.

    Apenas apresenta IP, estado, latência e tooltip recebidos da API.
    Não executa ping, calcula Health, acessa SQLite ou altera equipamento.
    """

    ITEM_HEIGHT = 32

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_ip = ""
        self.current_name = ""
        self.current_status = "UNKNOWN"

        self.setObjectName("wallboardIpItem")
        self.setProperty("status", "unknown")
        self.setFixedHeight(self.ITEM_HEIGHT)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._build_ui()

        legacy_style = self.styleSheet()
        self.setStyleSheet(
            legacy_style + wallboard_ip_item_qss()
        )

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(7)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setProperty("status", "unknown")
        self.status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_dot.setFixedWidth(16)

        self.ip_label = QLabel("--")
        self.ip_label.setObjectName("ipText")
        self.ip_label.setProperty("role", "ip")
        self.ip_label.setProperty("status", "unknown")
        self.ip_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )

        self.value_label = QLabel("--")
        self.value_label.setObjectName("ipValue")
        self.value_label.setProperty("role", "status")
        self.value_label.setProperty("status", "unknown")
        self.value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.value_label.setMinimumWidth(62)

        layout.addWidget(self.status_dot)
        layout.addWidget(self.ip_label, 1)
        layout.addWidget(self.value_label, 0)

    def update_device(self, device: dict):
        if not isinstance(device, dict):
            return

        health = device.get("health") or {}
        if not isinstance(health, dict):
            health = {}

        ip = str(device.get("ip", "")).strip()
        name = str(
            device.get("name")
            or device.get("nome")
            or ip
            or "Equipamento"
        )
        status = str(
            health.get("status")
            or health.get("effective_status")
            or device.get("effective_status")
            or device.get("status")
            or "UNKNOWN"
        ).upper()
        maintenance = bool(device.get("maintenance", False))
        display_status = "MAINTENANCE" if maintenance else status
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
        self.current_name = name
        self.current_status = display_status
        self.ip_label.setText(ip or "--")

        display_value = self._display_value(
            status=display_status,
            latency=latency,
        )
        self.value_label.setText(display_value)

        self._apply_visual_status(display_status)

        tooltip_latency = display_value if latency is not None else "--"
        tooltip_quality = str(quality or "--")
        maintenance_text = "SIM" if maintenance else "NÃO"
        self.setToolTip(
            f"{name}\n"
            f"IP: {ip or '--'}\n"
            f"Status de rede: {status}\n"
            f"Manutenção: {maintenance_text}\n"
            f"Latência: {tooltip_latency}\n"
            f"Qualidade: {tooltip_quality}"
        )

    def _apply_visual_status(self, status):
        """Projeta o estado já calculado em propriedades visuais."""

        normalized = str(status or "unknown").strip().lower()
        normalized = {
            "manutenção": "maintenance",
            "manutencao": "maintenance",
        }.get(normalized, normalized)

        if normalized not in (
            "online",
            "suspect",
            "recovering",
            "offline",
            "unknown",
            "error",
            "maintenance",
        ):
            normalized = "unknown"

        for widget in (
            self,
            self.status_dot,
            self.ip_label,
            self.value_label,
        ):
            widget.setProperty("status", normalized)
            self._refresh_style(widget)

    @staticmethod
    def _display_value(status: str, latency) -> str:
        if status == "MAINTENANCE":
            return "MANUTENÇÃO"
        if status == "OFFLINE":
            return "OFFLINE"
        if status == "SUSPECT":
            return "SUSPECT"
        if status == "RECOVERING":
            return "RECOVER"
        if status == "ERROR":
            return "ERRO"
        if status == "UNKNOWN":
            return "SEM DADOS"
        if latency is None:
            return "ONLINE"

        try:
            value = float(latency)
        except (TypeError, ValueError):
            return "ONLINE"

        if value < 1:
            return "<1 ms"
        return f"{value:.0f} ms"

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
