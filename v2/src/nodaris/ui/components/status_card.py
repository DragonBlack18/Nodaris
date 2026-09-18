from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from nodaris.ui.theme import tokens as t
from nodaris.ui.theme.status import status_color, status_soft_color


class StatusCard(QFrame):
    def __init__(self, title: str, value: int | str = 0, parent=None) -> None:
        super().__init__(parent)
        self.title = title.upper()
        self.setObjectName("statusCard")
        self.setMinimumHeight(92)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet(f"color:{t.TEXT_MUTED};")

        self.value_label = QLabel(str(value))
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.value_label.setStyleSheet(
            f"color:{t.TEXT_PRIMARY}; font-size:24px; font-weight:800;"
        )

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

        accent = t.ACCENT if self.title == "TOTAL" else status_color(self.title)
        hover = t.BG_PANEL_ALT if self.title == "TOTAL" else status_soft_color(self.title)

        self.setStyleSheet(
            f"QFrame#statusCard{{background:{t.BG_PANEL};"
            f"border:1px solid {t.BORDER};border-top:2px solid {accent};"
            f"border-radius:{t.RADIUS_LG}px;}}"
            f"QFrame#statusCard:hover{{background:{hover};}}"
            "QLabel{background:transparent;}"
        )

    def set_value(self, value: int | str) -> None:
        self.value_label.setText(str(value))
