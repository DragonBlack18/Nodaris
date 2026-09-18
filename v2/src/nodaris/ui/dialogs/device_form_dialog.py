from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from nodaris.ui.theme.styles import app_stylesheet


class DeviceFormDialog(QDialog):
    def __init__(self, device: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.device = device or {}
        self.setWindowTitle("Equipamento")
        self.setMinimumWidth(420)
        self.setStyleSheet(app_stylesheet())
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit(str(self.device.get("name", "")))
        self.ip_input = QLineEdit(str(self.device.get("ip", "")))
        self.gateway_input = QLineEdit(str(self.device.get("gateway", "")))
        self.maintenance_input = QCheckBox("Em manutenção")
        self.maintenance_input.setChecked(bool(self.device.get("maintenance", False)))

        form.addRow("Nome", self.name_input)
        form.addRow("IPv4", self.ip_input)
        form.addRow("Gateway", self.gateway_input)
        form.addRow("", self.maintenance_input)

        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def payload(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "ip": self.ip_input.text().strip(),
            "gateway": self.gateway_input.text().strip(),
            "maintenance": self.maintenance_input.isChecked(),
        }
