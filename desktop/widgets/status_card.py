from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
)

from desktop.theme import (
    ACCENT,
    BG_PANEL,
    BG_PANEL_ALT,
    BORDER,
    CARD_MIN_HEIGHT,
    RADIUS_LG,
    SPACE_1,
    SPACE_3,
    SPACE_4,
    TEXT_MUTED,
    TEXT_PRIMARY,
    status_color,
    status_soft_color,
)

class StatusCard(QFrame):

    def __init__(
        self,
        title: str,
        value: int = 0,
        parent=None,
    ):
        super().__init__(parent)

        self.setObjectName("statusCard")

        self.setMinimumHeight(
            CARD_MIN_HEIGHT
        )

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            SPACE_4,
            SPACE_3,
            SPACE_4,
            SPACE_3,
        )

        layout.setSpacing(
            SPACE_1
        )

        self.title_label = QLabel(title)

        self.title_label.setObjectName(
            "statusCardTitle"
        )

        self.value_label = QLabel(
            str(value)
        )

        self.value_label.setObjectName(
            "statusCardValue"
        )

        self.value_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.value_label
        )

        # O resumo mantém os mesmos widgets e dimensões;
        # apenas o acabamento acompanha o estado exibido.
        accent = (
            ACCENT
            if title.upper() == "TOTAL"
            else status_color(title)
        )
        hover_background = (
            BG_PANEL_ALT
            if title.upper() == "TOTAL"
            else status_soft_color(title)
        )

        self.setStyleSheet(
            f"QFrame#statusCard {{"
            f"background-color: {BG_PANEL};"
            f"border: 1px solid {BORDER};"
            f"border-top: 2px solid {accent};"
            f"border-radius: {RADIUS_LG}px;"
            f"}}"
            f"QFrame#statusCard:hover {{"
            f"background-color: {hover_background};"
            f"}}"
            f"QLabel#statusCardTitle {{"
            f"color: {TEXT_MUTED};"
            f"}}"
            f"QLabel#statusCardValue {{"
            f"color: {TEXT_PRIMARY};"
            f"}}"
        )

    def set_value(
        self,
        value: int,
    ):

        self.value_label.setText(
            str(value)
        )
