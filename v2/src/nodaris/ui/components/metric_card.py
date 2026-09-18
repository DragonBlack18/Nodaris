from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

from nodaris.ui.theme import tokens as t


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "--", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setProperty("panel", True)
        self.setMinimumHeight(105)
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(7)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            f"color:{t.TEXT_MUTED}; font-size:10px; font-weight:800;"
        )

        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet(
            f"color:{t.TEXT_PRIMARY}; font-size:22px; font-weight:900;"
        )

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addStretch(1)

    def set_value(self, value) -> None:
        self.value_label.setText("--" if value is None else str(value))

    def set_title(self, title: str) -> None:
        self.title_label.setText(str(title))
