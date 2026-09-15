from __future__ import annotations

from ipaddress import IPv4Address, ip_address

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from desktop import theme
from desktop.theme import (
    device_form_qss,
    nodaris_desktop_controls_qss,
    nodaris_global_visual_qss,
)


class DeviceFormDialog(QDialog):
    def __init__(
        self,
        device: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.device = device if isinstance(device, dict) else None
        self.is_editing = self.device is not None

        self.setModal(True)
        self.setWindowTitle(
            "Editar equipamento"
            if self.is_editing
            else "Adicionar equipamento"
        )
        self.setMinimumWidth(460)

        self._build_ui()
        self._apply_style()

        if self.device:
            self._load_device(self.device)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)

        title = QLabel(
            "Editar equipamento" if self.is_editing else "Novo equipamento"
        )
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        description = QLabel(
            "Os dados serão validados antes de serem enviados ao NODARIS."
        )
        description.setObjectName("dialogDescription")
        root.addWidget(description)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ex.: Rasp Sala Controle")
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("Ex.: 192.168.6.91")
        self.gateway_input = QLineEdit()
        self.gateway_input.setPlaceholderText("Opcional")

        form.addRow("Nome", self.name_input)
        form.addRow("IPv4", self.ip_input)
        form.addRow("Gateway", self.gateway_input)
        root.addLayout(form)

        # A manutenção aparece somente ao editar um cadastro existente.
        # Equipamentos novos sempre começam fora de manutenção.
        self.maintenance_checkbox = QCheckBox(
            "Equipamento em manutenção"
        )
        self.maintenance_checkbox.setObjectName(
            "maintenanceCheckbox"
        )
        self.maintenance_checkbox.setToolTip(
            "Marque esta opção quando o equipamento estiver "
            "temporariamente em manutenção."
        )
        self.maintenance_checkbox.setVisible(self.is_editing)
        root.addWidget(self.maintenance_checkbox)

        self.error_label = QLabel("")
        self.error_label.setObjectName("formError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        cancel_button = QPushButton("Cancelar")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self.reject)

        self.save_button = QPushButton(
            "Salvar alterações" if self.is_editing else "Adicionar"
        )
        self.save_button.setObjectName("primaryButton")
        self.save_button.setProperty("primary", True)
        self.save_button.clicked.connect(self._validate_and_accept)

        buttons.addWidget(cancel_button)
        buttons.addWidget(self.save_button)
        root.addLayout(buttons)

    def _load_device(self, device: dict):
        self.name_input.setText(
            str(device.get("name") or device.get("nome") or "")
        )
        self.ip_input.setText(str(device.get("ip", "")))
        self.gateway_input.setText(
            str(device.get("gateway", "") or "")
        )
        self.maintenance_checkbox.setChecked(
            bool(device.get("maintenance", False))
        )

    def payload(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "ip": self.ip_input.text().strip(),
            "gateway": self.gateway_input.text().strip(),
            "maintenance": (
                self.maintenance_checkbox.isChecked()
                if self.is_editing
                else False
            ),
        }

    def _validate_and_accept(self):
        data = self.payload()
        name = data["name"]
        ip = data["ip"]
        gateway = data["gateway"]

        if not name:
            self._show_error("Informe o nome do equipamento.")
            return
        if len(name) > 120:
            self._show_error(
                "O nome pode ter no máximo 120 caracteres."
            )
            return
        if not self._is_ipv4(ip):
            self._show_error("Informe um endereço IPv4 válido.")
            return
        if gateway and not self._is_ipv4(gateway):
            self._show_error(
                "O gateway informado não é um IPv4 válido."
            )
            return

        self.error_label.hide()
        self.accept()

    @staticmethod
    def _is_ipv4(value: str) -> bool:
        try:
            parsed = ip_address(str(value).strip())
            return isinstance(parsed, IPv4Address)
        except ValueError:
            return False

    def _show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()

    def _apply_style(self):
        legacy_qss = """
            QDialog {
                background: %(BG_APP)s;
                color: %(TEXT_PRIMARY)s;
            }
            QLabel { color: %(TEXT_SECONDARY)s; }
            QLabel#dialogTitle {
                color: %(TEXT_PRIMARY)s;
                font-size: 20px;
                font-weight: 900;
            }
            QLabel#dialogDescription {
                color: %(TEXT_MUTED)s;
                font-size: 11px;
            }
            QLabel#formError {
                color: %(DANGER)s;
                background: %(DANGER_SOFT)s;
                border: 1px solid %(DANGER)s;
                border-radius: 6px;
                padding: 8px;
            }
            QLineEdit {
                background: %(BG_PANEL)s;
                color: %(TEXT_PRIMARY)s;
                border: 1px solid %(BORDER)s;
                border-radius: 7px;
                padding: 8px 10px;
                min-height: 20px;
            }
            QLineEdit:focus { border-color: %(ACCENT)s; }
            QPushButton {
                min-height: 32px;
                padding-left: 15px;
                padding-right: 15px;
                border-radius: 7px;
                font-weight: 700;
            }
            QPushButton#primaryButton {
                background: %(ACCENT)s;
                color: %(TEXT_PRIMARY)s;
                border: 1px solid %(ACCENT)s;
            }
            QPushButton#primaryButton:hover { background: %(ACCENT_HOVER)s; }
            QPushButton#secondaryButton {
                background: %(BG_PANEL_ALT)s;
                color: %(TEXT_SECONDARY)s;
                border: 1px solid %(BORDER)s;
            }
            QPushButton#secondaryButton:hover { background: %(BG_ELEVATED)s; }
            QCheckBox#maintenanceCheckbox {
                color: %(TEXT_SECONDARY)s;
                spacing: 9px;
                font-size: 12px;
                font-weight: 700;
                padding-top: 4px;
                padding-bottom: 4px;
            }
            """
        legacy_qss = legacy_qss % vars(theme)
        self.setStyleSheet(
            legacy_qss
            + device_form_qss()
            + nodaris_global_visual_qss()
            + nodaris_desktop_controls_qss()
        )
