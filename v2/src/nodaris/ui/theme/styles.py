from __future__ import annotations

from nodaris.ui.theme import tokens as t


def app_stylesheet() -> str:
    return f"""
    QWidget {{
        background: {t.BG_APP};
        color: {t.TEXT_PRIMARY};
        font-family: "{t.FONT_FAMILY}";
        font-size: 12px;
    }}

    QMainWindow {{
        background: {t.BG_APP};
    }}

    QLabel#pageTitle {{
        font-size: 24px;
        font-weight: 800;
    }}

    QLabel#pageSubtitle {{
        color: {t.TEXT_MUTED};
        font-size: 11px;
    }}

    QLabel#sectionTitle {{
        color: {t.TEXT_SECONDARY};
        font-size: 11px;
        font-weight: 800;
    }}

    QFrame[panel="true"] {{
        background: {t.BG_PANEL};
        border: 1px solid {t.BORDER};
        border-radius: {t.RADIUS_LG}px;
    }}

    QPushButton {{
        min-height: {t.CONTROL_HEIGHT}px;
        padding: 0 14px;
        background: {t.BG_ELEVATED};
        border: 1px solid {t.BORDER_STRONG};
        border-radius: {t.RADIUS_MD}px;
        font-weight: 700;
    }}

    QPushButton:hover {{
        border-color: {t.ACCENT};
        background: {t.BG_PANEL_ALT};
    }}

    QPushButton[primary="true"] {{
        background: {t.ACCENT};
        color: {t.BG_APP};
        border-color: {t.ACCENT};
    }}

    QPushButton[danger="true"] {{
        color: {t.DANGER};
        border-color: {t.DANGER};
    }}

    QLineEdit, QComboBox {{
        min-height: {t.CONTROL_HEIGHT}px;
        background: {t.BG_PANEL};
        border: 1px solid {t.BORDER};
        border-radius: {t.RADIUS_MD}px;
        padding: 0 10px;
    }}

    QLineEdit:focus, QComboBox:focus {{
        border-color: {t.ACCENT};
    }}

    QTableWidget {{
        background: {t.BG_PANEL};
        border: 1px solid {t.BORDER};
        border-radius: {t.RADIUS_MD}px;
        gridline-color: {t.BORDER};
        selection-background-color: {t.BG_ELEVATED};
    }}

    QHeaderView::section {{
        background: {t.BG_ELEVATED};
        color: {t.TEXT_MUTED};
        border: none;
        border-bottom: 1px solid {t.BORDER};
        padding: 8px;
        font-weight: 800;
    }}
    """
