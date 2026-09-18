from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from nodaris.ui.components.status_card import StatusCard
from nodaris.ui.theme import tokens as t
from nodaris.ui.theme.styles import app_stylesheet


class WallboardWindow(QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("NODARIS TV")
        self.resize(1500, 880)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(app_stylesheet())
        self._cards: dict[str, StatusCard] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(22, 16, 22, 14)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("NODARIS")
        title.setObjectName("pageTitle")
        self.health_label = QLabel("● AGUARDANDO MONITORAMENTO")
        self.health_label.setStyleSheet(f"color:{t.WARNING}; font-weight:800;")

        title_box.addWidget(title)
        title_box.addWidget(self.health_label)
        header.addLayout(title_box)
        header.addStretch(1)

        clock_box = QVBoxLayout()
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
        for key in ("TOTAL", "ONLINE", "SUSPECT", "OFFLINE", "RECOVERING"):
            card = StatusCard(key)
            self._cards[key] = card
            summary.addWidget(card)
        root.addLayout(summary)

        matrix_panel = QFrame()
        matrix_panel.setProperty("panel", True)
        matrix_layout = QVBoxLayout(matrix_panel)
        matrix_layout.setContentsMargins(16, 14, 16, 14)

        matrix_title = QLabel("EQUIPAMENTOS")
        matrix_title.setObjectName("sectionTitle")
        matrix_layout.addWidget(matrix_title)

        self.device_grid = QGridLayout()
        self.device_grid.setHorizontalSpacing(10)
        self.device_grid.setVerticalSpacing(6)
        matrix_layout.addLayout(self.device_grid, 1)

        root.addWidget(matrix_panel, 1)

    def set_summary(self, **values: int) -> None:
        for key, value in values.items():
            card = self._cards.get(key.upper())
            if card:
                card.set_value(value)
