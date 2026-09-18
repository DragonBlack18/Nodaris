from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from nodaris.ui.theme import tokens as t


_STATUS_COLORS = {
    "TOTAL": t.ACCENT,
    "ONLINE": t.SUCCESS,
    "SUSPECT": t.SUSPECT,
    "OFFLINE": t.DANGER,
    "RECOVERING": t.RECOVERING,
    "MAINTENANCE": t.MAINTENANCE,
}


class StatusCard(QFrame):
    def __init__(self, title: str, value: int | str = 0, parent=None) -> None:
        super().__init__(parent)
        self.title = title.upper()
        self.setProperty("panel", True)
        self.setMinimumHeight(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet(
            f"color:{t.TEXT_MUTED}; font-size:10px; font-weight:800;"
        )

        self.value_label = QLabel(str(value))
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.value_label.setStyleSheet(
            f"color:{_STATUS_COLORS.get(self.title, t.TEXT_PRIMARY)};"
            "font-size:28px; font-weight:900;"
        )

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: int | str) -> None:
        self.value_label.setText(str(value))
