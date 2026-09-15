from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.device_admin_client import DeviceAdminClient
from desktop.theme import (
    device_management_qss,
    nodaris_desktop_controls_qss,
    nodaris_global_visual_qss,
)
from desktop.windows.device_form_dialog import DeviceFormDialog


class DeviceManagementWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.devices = []
        self.client = DeviceAdminClient(parent=self)
        self.client.devices_received.connect(self._devices_received)
        self.client.operation_succeeded.connect(
            self._operation_succeeded
        )
        self.client.operation_failed.connect(self._operation_failed)

        self.setWindowTitle("NODARIS — Equipamentos")
        self.resize(900, 620)
        self.setMinimumSize(720, 480)

        self._build_ui()
        self._apply_style()
        self.refresh_devices()

    # =====================================================
    # UI / DATA
    # =====================================================

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("deviceManagementCentral")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("EQUIPAMENTOS")
        title.setObjectName("pageTitle")
        self.count_label = QLabel("Carregando...")
        self.count_label.setObjectName("pageDescription")

        title_box.addWidget(title)
        title_box.addWidget(self.count_label)
        header.addLayout(title_box)
        header.addStretch(1)

        refresh_button = QPushButton("Atualizar")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh_devices)

        add_button = QPushButton("+ Adicionar equipamento")
        add_button.setObjectName("primaryButton")
        add_button.setProperty("primary", True)
        add_button.clicked.connect(self._add_device)

        header.addWidget(refresh_button)
        header.addWidget(add_button)
        root.addLayout(header)

        self.table = QTableWidget(0, 4)
        self.table.setObjectName("deviceTable")
        self.table.setHorizontalHeaderLabels(
            ["Nome", "IPv4", "Gateway", "Ações"]
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)

        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        header_view.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header_view.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header_view.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Fixed,
        )
        self.table.setColumnWidth(3, 190)
        root.addWidget(self.table, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusText")
        root.addWidget(self.status_label)

    def refresh_devices(self):
        self.status_label.setText("Atualizando equipamentos...")
        self.client.get_devices()

    def _devices_received(self, devices):
        if not isinstance(devices, list):
            devices = []

        self.devices = devices
        self._render_table()
        self.count_label.setText(
            f"{len(devices)} equipamentos cadastrados"
        )
        self.status_label.setText("Dados atualizados.")

    # =====================================================
    # RENDER
    # =====================================================

    def _render_table(self):
        self.table.setRowCount(0)
        devices = sorted(
            self.devices,
            key=lambda device: (
                str(device.get("name", "")).lower(),
                str(device.get("ip", "")),
            ),
        )

        for device in devices:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 46)

            name = str(
                device.get("name") or device.get("nome") or ""
            )
            ip = str(device.get("ip", ""))
            gateway = str(device.get("gateway", "") or "-")

            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(ip))
            self.table.setItem(row, 2, QTableWidgetItem(gateway))

            actions_widget = QWidget()
            actions = QHBoxLayout(actions_widget)
            actions.setContentsMargins(4, 4, 4, 4)
            actions.setSpacing(6)

            edit_button = QPushButton("Editar")
            edit_button.setObjectName("tableButton")
            edit_button.clicked.connect(
                lambda checked=False, item=device: self._edit_device(item)
            )

            remove_button = QPushButton("Remover")
            remove_button.setObjectName("dangerButton")
            remove_button.setProperty("danger", True)
            remove_button.clicked.connect(
                lambda checked=False, item=device: self._remove_device(item)
            )

            actions.addWidget(edit_button)
            actions.addWidget(remove_button)
            self.table.setCellWidget(row, 3, actions_widget)

    # =====================================================
    # CRUD ACTIONS
    # =====================================================

    def _add_device(self):
        dialog = DeviceFormDialog(parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        data = dialog.payload()
        self.status_label.setText("Adicionando equipamento...")
        self.client.create_device(
            ip=data["ip"],
            name=data["name"],
            gateway=data["gateway"],
        )

    def _edit_device(self, device: dict):
        dialog = DeviceFormDialog(device=device, parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        data = dialog.payload()
        current_ip = str(device.get("ip", ""))
        self.status_label.setText("Salvando alterações...")
        self.client.update_device(
            current_ip=current_ip,
            new_ip=data["ip"],
            name=data["name"],
            gateway=data["gateway"],
            maintenance=data["maintenance"],
        )

    def _remove_device(self, device: dict):
        ip = str(device.get("ip", ""))
        name = str(device.get("name") or ip)
        answer = QMessageBox.question(
            self,
            "Remover equipamento",
            (
                f"Remover '{name}'?\n\n"
                f"IP: {ip}\n\n"
                "O equipamento deixará de ser monitorado."
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.status_label.setText("Removendo equipamento...")
        self.client.delete_device(ip)

    def _operation_succeeded(self, operation: str, data):
        labels = {
            "create": "Equipamento adicionado.",
            "update": "Equipamento atualizado.",
            "delete": "Equipamento removido.",
        }
        self.status_label.setText(
            labels.get(operation, "Operação concluída.")
        )
        self.refresh_devices()

    def _operation_failed(self, message: str):
        self.status_label.setText(
            "Não foi possível concluir a operação."
        )
        QMessageBox.warning(self, "NODARIS", str(message))

    # =====================================================
    # STYLE
    # =====================================================

    def _apply_style(self):
        self.setStyleSheet(
            device_management_qss()
            + nodaris_global_visual_qss()
            + nodaris_desktop_controls_qss()
        )
