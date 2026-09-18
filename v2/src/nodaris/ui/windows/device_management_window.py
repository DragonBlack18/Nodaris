from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nodaris.ui.theme.styles import app_stylesheet


class DeviceManagementWindow(QMainWindow):
    add_requested = Signal()
    edit_requested = Signal(str)
    remove_requested = Signal(str)
    refresh_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("NODARIS — Equipamentos")
        self.resize(900, 620)
        self.setMinimumSize(820, 480)
        self.setStyleSheet(app_stylesheet())
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("EQUIPAMENTOS")
        title.setObjectName("pageTitle")
        self.count_label = QLabel("0 equipamentos cadastrados")
        self.count_label.setObjectName("pageSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(self.count_label)
        header.addLayout(title_box)
        header.addStretch(1)

        refresh = QPushButton("Atualizar")
        refresh.clicked.connect(self.refresh_requested.emit)

        add = QPushButton("+ Adicionar equipamento")
        add.setProperty("primary", True)
        add.clicked.connect(self.add_requested.emit)

        header.addWidget(refresh)
        header.addWidget(add)
        root.addLayout(header)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nome", "IPv4", "Gateway", "Ações"])
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)

        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 250)

        root.addWidget(self.table, 1)

    def set_devices(self, devices: list[dict]) -> None:
        self.table.setRowCount(0)
        ordered = sorted(
            devices,
            key=lambda item: (
                str(item.get("name", "")).lower(),
                str(item.get("ip", "")),
            ),
        )

        for device in ordered:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 46)

            ip = str(device.get("ip", ""))
            self.table.setItem(row, 0, QTableWidgetItem(str(device.get("name", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(ip))
            self.table.setItem(row, 2, QTableWidgetItem(str(device.get("gateway") or "-")))

            actions_widget = QWidget()
            actions = QHBoxLayout(actions_widget)
            actions.setContentsMargins(4, 4, 4, 4)
            actions.setSpacing(6)

            edit = QPushButton("Editar")
            edit.clicked.connect(lambda checked=False, value=ip: self.edit_requested.emit(value))

            remove = QPushButton("Remover")
            remove.setProperty("danger", True)
            remove.clicked.connect(
                lambda checked=False, value=ip: self.remove_requested.emit(value)
            )

            actions.addWidget(edit)
            actions.addWidget(remove)
            self.table.setCellWidget(row, 3, actions_widget)

        self.count_label.setText(f"{len(ordered)} equipamentos cadastrados")
