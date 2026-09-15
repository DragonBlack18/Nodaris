from __future__ import annotations


# =========================================================
# NODARIS — DESIGN TOKENS
# =========================================================

# ---------------------------------------------------------
# BASE
# ---------------------------------------------------------

BG_APP = "#0B1220"
BG_PANEL = "#111827"
BG_PANEL_ALT = "#172033"
BG_ELEVATED = "#1E293B"

BORDER = "#263247"
BORDER_STRONG = "#334155"


# ---------------------------------------------------------
# TEXT
# ---------------------------------------------------------

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
TEXT_MUTED = "#94A3B8"
TEXT_DISABLED = "#64748B"


# ---------------------------------------------------------
# BRAND
# ---------------------------------------------------------

ACCENT = "#38BDF8"
ACCENT_HOVER = "#0EA5E9"
ACCENT_PRESSED = "#0284C7"


# ---------------------------------------------------------
# STATUS
# ---------------------------------------------------------

SUCCESS = "#22C55E"
SUCCESS_SOFT = "#16351F"

DANGER = "#EF4444"
DANGER_SOFT = "#3A171A"

WARNING = "#F59E0B"
WARNING_SOFT = "#3B2A11"

SUSPECT = "#F97316"
SUSPECT_SOFT = "#402112"

RECOVERING = "#A78BFA"
RECOVERING_SOFT = "#2D2347"

ERROR = "#E879F9"
ERROR_SOFT = "#3A1F3D"

MAINTENANCE = "#64748B"
MAINTENANCE_SOFT = "#202936"

UNKNOWN = "#64748B"


# =========================================================
# TYPOGRAPHY
# =========================================================

FONT_FAMILY = "Segoe UI"

FONT_SIZE_XS = 10
FONT_SIZE_SM = 11
FONT_SIZE_MD = 12
FONT_SIZE_LG = 14
FONT_SIZE_XL = 18
FONT_SIZE_2XL = 24
FONT_SIZE_3XL = 32


# =========================================================
# SPACING
# =========================================================

SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24
SPACE_8 = 32


# =========================================================
# RADII
# =========================================================

RADIUS_SM = 6
RADIUS_MD = 10
RADIUS_LG = 14
RADIUS_XL = 18


# =========================================================
# COMPONENT DIMENSIONS
# =========================================================

CONTROL_HEIGHT = 36
CONTROL_HEIGHT_LG = 42

SIDEBAR_WIDTH = 220

CARD_MIN_HEIGHT = 92

TABLE_ROW_HEIGHT = 42

STATUS_DOT_SIZE = 8


# =========================================================
# STATUS HELPERS
# =========================================================

_STATUS_COLORS = {
    "ONLINE": SUCCESS,
    "OFFLINE": DANGER,
    "SUSPECT": SUSPECT,
    "RECOVERING": RECOVERING,
    "ERROR": ERROR,
    "MAINTENANCE": MAINTENANCE,
    "MANUTENÇÃO": MAINTENANCE,
    "MANUTENCAO": MAINTENANCE,
    "UNKNOWN": UNKNOWN,
}


_STATUS_SOFT_COLORS = {
    "ONLINE": SUCCESS_SOFT,
    "OFFLINE": DANGER_SOFT,
    "SUSPECT": SUSPECT_SOFT,
    "RECOVERING": RECOVERING_SOFT,
    "ERROR": ERROR_SOFT,
    "UNKNOWN": MAINTENANCE_SOFT,
    "MAINTENANCE": MAINTENANCE_SOFT,
    "MANUTENÇÃO": MAINTENANCE_SOFT,
    "MANUTENCAO": MAINTENANCE_SOFT,
}


def status_color(
    status: str | None,
) -> str:

    normalized = (
        str(status or "UNKNOWN")
        .strip()
        .upper()
    )

    return _STATUS_COLORS.get(
        normalized,
        UNKNOWN,
    )


def status_soft_color(
    status: str | None,
) -> str:

    normalized = (
        str(status or "UNKNOWN")
        .strip()
        .upper()
    )

    return _STATUS_SOFT_COLORS.get(
        normalized,
        MAINTENANCE_SOFT,
    )


def nodaris_typography_qss() -> str:
    """Tipografia e cores de texto comuns, sem tamanho global."""

    return f"""
        QWidget {{ font-family: "{FONT_FAMILY}"; }}
        QLabel {{ color: {TEXT_PRIMARY}; }}
        QLabel[secondary="true"] {{ color: {TEXT_SECONDARY}; }}
        QLabel[muted="true"] {{ color: {TEXT_MUTED}; }}
        QLabel[disabled="true"] {{ color: {TEXT_DISABLED}; }}
        QLabel[status="online"] {{ color: {SUCCESS}; }}
        QLabel[status="offline"] {{ color: {DANGER}; }}
        QLabel[status="suspect"] {{ color: {SUSPECT}; }}
        QLabel[status="recovering"] {{ color: {RECOVERING}; }}
        QLabel[status="maintenance"] {{ color: {MAINTENANCE}; }}
        QLabel[status="error"] {{ color: {ERROR}; }}
        QLabel[status="unknown"] {{ color: {UNKNOWN}; }}
    """


def nodaris_status_qss() -> str:
    """Bordas dos estados operacionais; sem alterar o fundo."""

    return f"""
        QWidget[status="online"], QFrame[status="online"] {{ border-color: {SUCCESS}; }}
        QWidget[status="offline"], QFrame[status="offline"] {{ border-color: {DANGER}; }}
        QWidget[status="suspect"], QFrame[status="suspect"] {{ border-color: {SUSPECT}; }}
        QWidget[status="recovering"], QFrame[status="recovering"] {{ border-color: {RECOVERING}; }}
        QWidget[status="maintenance"], QFrame[status="maintenance"] {{ border-color: {MAINTENANCE}; }}
        QWidget[status="error"], QFrame[status="error"] {{ border-color: {ERROR}; }}
    """


def nodaris_global_visual_qss() -> str:
    return nodaris_typography_qss() + nodaris_status_qss()


# =========================================================
# GENERIC QSS HELPERS
# =========================================================

def app_base_qss() -> str:
    """
    Estilo base futuro do NODARIS.

    Nesta etapa ele ainda não é aplicado globalmente.
    Os estilos existentes continuam controlando as janelas.

    Será utilizado progressivamente durante a modernização.
    """

    return f"""
        QWidget {{
            font-family: "{FONT_FAMILY}";
            color: {TEXT_PRIMARY};
        }}

        QToolTip {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            padding: 6px 8px;
            border-radius: {RADIUS_SM}px;
        }}
    """


def button_primary_qss() -> str:

    return f"""
        QPushButton {{
            background-color: {ACCENT};
            color: {BG_APP};

            border: none;
            border-radius: {RADIUS_MD}px;

            padding: 0 {SPACE_4}px;

            min-height: {CONTROL_HEIGHT}px;

            font-weight: 600;
        }}

        QPushButton:hover {{
            background-color: {ACCENT_HOVER};
        }}

        QPushButton:pressed {{
            background-color: {ACCENT_PRESSED};
        }}

        QPushButton:disabled {{
            background-color: {BG_ELEVATED};
            color: {TEXT_DISABLED};
        }}
    """


def panel_qss() -> str:

    return f"""
        QFrame {{
            background-color: {BG_PANEL};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_LG}px;
        }}
    """


def admin_window_qss() -> str:
    """Camada visual do Admin; não altera layouts nem comportamento."""

    return f"""
        QMainWindow {{
            background-color: {BG_APP};
        }}

        QMainWindow QWidget {{
            font-family: "{FONT_FAMILY}";
            color: {TEXT_PRIMARY};
        }}

        QLabel {{
            background: transparent;
        }}

        QLabel[muted="true"] {{
            color: {TEXT_MUTED};
        }}

        QLabel[secondary="true"] {{
            color: {TEXT_SECONDARY};
        }}

        QFrame {{
            border: none;
        }}

        QFrame[panel="true"] {{
            background-color: {BG_PANEL};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_LG}px;
        }}

        QPushButton {{
            min-height: {CONTROL_HEIGHT}px;
            padding-left: {SPACE_4}px;
            padding-right: {SPACE_4}px;
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            border-radius: {RADIUS_MD}px;
            font-size: {FONT_SIZE_MD}px;
            font-weight: 600;
        }}

        QPushButton:hover {{
            background-color: {BG_PANEL_ALT};
            border-color: {ACCENT};
        }}

        QPushButton:pressed {{
            background-color: {BORDER};
        }}

        QPushButton:disabled {{
            background-color: {BG_PANEL};
            color: {TEXT_DISABLED};
            border-color: {BORDER};
        }}

        QPushButton[primary="true"] {{
            background-color: {ACCENT};
            color: {BG_APP};
            border-color: {ACCENT};
        }}

        QPushButton[primary="true"]:hover {{
            background-color: {ACCENT_HOVER};
            border-color: {ACCENT_HOVER};
        }}

        QPushButton[primary="true"]:pressed {{
            background-color: {ACCENT_PRESSED};
            border-color: {ACCENT_PRESSED};
        }}

        /* Preserve as dimensões dos controles atuais do Admin.
           A altura mínima genérica vale só para novos botões. */
        QPushButton#managementButton,
        QPushButton#deviceButton,
        QPushButton#alertButton {{
            min-height: 0px;
        }}

        QScrollArea {{
            background-color: transparent;
            border: none;
        }}

        QScrollArea > QWidget > QWidget {{
            background-color: transparent;
        }}

        QScrollBar:vertical {{
            width: 10px;
            background: transparent;
            margin: 2px;
        }}

        QScrollBar::handle:vertical {{
            min-height: 32px;
            background-color: {BORDER_STRONG};
            border-radius: {RADIUS_SM}px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {TEXT_DISABLED};
        }}

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent;
        }}

        QScrollBar:horizontal {{
            height: 10px;
            background: transparent;
            margin: 2px;
        }}

        QScrollBar::handle:horizontal {{
            min-width: 32px;
            background-color: {BORDER_STRONG};
            border-radius: {RADIUS_SM}px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {TEXT_DISABLED};
        }}

        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        QStatusBar {{
            background-color: {BG_PANEL};
            color: {TEXT_MUTED};
            border-top: 1px solid {BORDER};
            font-size: {FONT_SIZE_SM}px;
        }}

        QStatusBar::item {{
            border: none;
        }}

        QToolTip {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            border-radius: {RADIUS_SM}px;
            padding: 6px 8px;
        }}
    """


def admin_action_buttons_qss(
    min_height: int = 30,
    horizontal_padding: int = SPACE_3,
) -> str:
    """Botões de ação reutilizáveis nas janelas auxiliares."""

    return f"""
        QPushButton {{
            min-height: {min_height}px;
            padding-left: {horizontal_padding}px;
            padding-right: {horizontal_padding}px;
            border-radius: {RADIUS_SM}px;
            font-weight: 700;
        }}

        QPushButton#primaryButton {{
            background-color: {ACCENT};
            color: {BG_APP};
            border: 1px solid {ACCENT};
        }}
        QPushButton#primaryButton:hover {{
            background-color: {ACCENT_HOVER};
            border-color: {ACCENT_HOVER};
        }}
        QPushButton#primaryButton:pressed {{
            background-color: {ACCENT_PRESSED};
            border-color: {ACCENT_PRESSED};
        }}

        QPushButton#secondaryButton,
        QPushButton#tableButton {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
        }}
        QPushButton#secondaryButton:hover,
        QPushButton#tableButton:hover {{
            background-color: {BG_PANEL_ALT};
        }}
        QPushButton#secondaryButton:pressed,
        QPushButton#tableButton:pressed {{
            background-color: {BORDER};
        }}
        QPushButton#secondaryButton:focus,
        QPushButton#tableButton:focus {{
            border-color: {ACCENT};
        }}

        QPushButton#dangerButton {{
            background-color: {DANGER_SOFT};
            color: {DANGER};
            border: 1px solid {DANGER};
        }}
        QPushButton#dangerButton:hover {{
            background-color: {DANGER};
            color: {TEXT_PRIMARY};
        }}
        QPushButton#dangerButton:pressed {{
            background-color: {DANGER_SOFT};
        }}

        QPushButton#primaryButton:disabled,
        QPushButton#secondaryButton:disabled,
        QPushButton#tableButton:disabled,
        QPushButton#dangerButton:disabled {{
            background-color: {BG_PANEL};
            color: {TEXT_DISABLED};
            border-color: {BORDER};
        }}
    """


def device_management_qss() -> str:
    """Tema da janela Equipamentos, sem alterar sua estrutura."""

    return f"""
        QMainWindow,
        QWidget#deviceManagementCentral {{
            background-color: {BG_APP};
            color: {TEXT_PRIMARY};
            font-family: "{FONT_FAMILY}";
        }}

        QLabel#pageTitle {{
            color: {TEXT_PRIMARY};
            font-size: 22px;
            font-weight: 900;
        }}
        QLabel#pageDescription {{
            color: {TEXT_MUTED};
            font-size: {FONT_SIZE_SM}px;
        }}
        QLabel#statusText {{
            color: {TEXT_MUTED};
            font-size: {FONT_SIZE_XS}px;
        }}

        QLineEdit,
        QComboBox {{
            min-height: {CONTROL_HEIGHT}px;
            background-color: {BG_PANEL};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD}px;
            padding-left: {SPACE_3}px;
            padding-right: {SPACE_3}px;
        }}
        QLineEdit:hover,
        QComboBox:hover {{
            border-color: {BORDER_STRONG};
        }}
        QLineEdit:focus {{
            border-color: {ACCENT};
            background-color: {BG_PANEL_ALT};
        }}
        QComboBox:focus {{
            border-color: {ACCENT};
        }}
        QLineEdit:disabled,
        QComboBox:disabled {{
            color: {TEXT_DISABLED};
            background-color: {BG_PANEL};
        }}
        QLineEdit {{
            selection-background-color: {ACCENT};
        }}
        QComboBox QAbstractItemView {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            selection-background-color: {BG_PANEL_ALT};
            selection-color: {TEXT_PRIMARY};
            outline: none;
        }}

        QTableWidget#deviceTable {{
            background-color: {BG_PANEL};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD}px;
            selection-background-color: {BG_PANEL_ALT};
            font-size: {FONT_SIZE_MD}px;
        }}
        QTableWidget#deviceTable::item {{
            border-bottom: 1px solid {BORDER};
            padding: {SPACE_2}px;
        }}
        QTableWidget#deviceTable::item:hover {{
            background-color: {BG_PANEL_ALT};
        }}
        QHeaderView::section {{
            background-color: {BG_ELEVATED};
            color: {TEXT_MUTED};
            border: none;
            border-bottom: 1px solid {BORDER};
            padding: {SPACE_2}px;
            font-size: {FONT_SIZE_XS}px;
            font-weight: 800;
        }}
        QHeaderView::section:hover {{
            background-color: {BG_PANEL_ALT};
        }}

        QTableView {{
            background-color: {BG_PANEL};
            alternate-background-color: {BG_PANEL_ALT};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_LG}px;
            gridline-color: {BORDER};
            selection-background-color: {BG_ELEVATED};
            selection-color: {TEXT_PRIMARY};
            outline: none;
        }}
        QTableView::item {{
            padding: {SPACE_2}px;
            border-bottom: 1px solid {BORDER};
        }}
        QTableView::item:hover {{
            background-color: {BG_PANEL_ALT};
        }}

        QListWidget,
        QTreeWidget {{
            background-color: {BG_PANEL};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_LG}px;
            outline: none;
        }}
        QListWidget::item,
        QTreeWidget::item {{
            padding: {SPACE_3}px;
            border-bottom: 1px solid {BORDER};
        }}
        QListWidget::item:hover,
        QTreeWidget::item:hover {{
            background-color: {BG_PANEL_ALT};
        }}
        QListWidget::item:selected,
        QTreeWidget::item:selected {{
            background-color: {BG_ELEVATED};
        }}

        QCheckBox {{
            color: {TEXT_SECONDARY};
            spacing: {SPACE_2}px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            background-color: {BG_PANEL};
            border: 1px solid {BORDER_STRONG};
            border-radius: {SPACE_1}px;
        }}
        QCheckBox::indicator:hover {{
            border-color: {ACCENT};
        }}
        QCheckBox::indicator:checked {{
            background-color: {ACCENT};
            border-color: {ACCENT};
        }}

        QScrollArea {{
            background: transparent;
            border: none;
        }}
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}
        QScrollBar:vertical {{
            width: 10px;
            background: transparent;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            min-height: 30px;
            background-color: {BORDER_STRONG};
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {TEXT_DISABLED};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent;
        }}

        QToolTip {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            border-radius: {RADIUS_SM}px;
            padding: 6px 8px;
        }}
    """ + admin_action_buttons_qss()


def device_form_qss() -> str:
    """Acabamento do formulário, preservando as dimensões atuais."""

    return f"""
        QDialog {{
            background-color: {BG_APP};
            color: {TEXT_PRIMARY};
        }}
        QWidget {{
            font-family: "{FONT_FAMILY}";
            color: {TEXT_PRIMARY};
        }}
        QLabel {{
            background: transparent;
            color: {TEXT_SECONDARY};
        }}
        QLabel#dialogTitle {{
            color: {TEXT_PRIMARY};
            font-size: 20px;
            font-weight: 900;
        }}
        QLabel#dialogDescription {{
            color: {TEXT_MUTED};
            font-size: {FONT_SIZE_SM}px;
        }}
        QLabel#formError {{
            color: {DANGER};
            background-color: {DANGER_SOFT};
            border: 1px solid {DANGER};
            border-radius: {RADIUS_SM}px;
            padding: {SPACE_2}px;
        }}
        QLabel[error="true"] {{
            color: {DANGER};
            font-size: {FONT_SIZE_XS}px;
        }}

        QLineEdit,
        QSpinBox,
        QDoubleSpinBox,
        QTextEdit,
        QPlainTextEdit {{
            min-height: {CONTROL_HEIGHT}px;
            background-color: {BG_PANEL};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD}px;
            padding-left: {SPACE_3}px;
            padding-right: {SPACE_3}px;
            padding-top: 0px;
            padding-bottom: 0px;
            selection-background-color: {ACCENT};
            selection-color: {BG_APP};
        }}
        QLineEdit:hover,
        QSpinBox:hover,
        QDoubleSpinBox:hover,
        QTextEdit:hover,
        QPlainTextEdit:hover {{
            border-color: {BORDER_STRONG};
        }}
        QLineEdit:focus,
        QSpinBox:focus,
        QDoubleSpinBox:focus,
        QTextEdit:focus,
        QPlainTextEdit:focus {{
            background-color: {BG_PANEL_ALT};
            border-color: {ACCENT};
        }}
        QLineEdit:disabled,
        QSpinBox:disabled,
        QDoubleSpinBox:disabled {{
            background-color: {BG_PANEL};
            color: {TEXT_DISABLED};
            border-color: {BORDER};
        }}
        QLineEdit[error="true"],
        QComboBox[error="true"] {{
            border-color: {DANGER};
        }}
        QLineEdit {{
            placeholder-text-color: {TEXT_DISABLED};
        }}

        QComboBox {{
            min-height: {CONTROL_HEIGHT}px;
            background-color: {BG_PANEL};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD}px;
            padding-left: {SPACE_3}px;
            padding-right: {SPACE_3}px;
        }}
        QComboBox:hover {{
            border-color: {BORDER_STRONG};
        }}
        QComboBox:focus {{
            background-color: {BG_PANEL_ALT};
            border-color: {ACCENT};
        }}
        QComboBox QAbstractItemView {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            selection-background-color: {BG_PANEL_ALT};
            selection-color: {TEXT_PRIMARY};
            outline: none;
        }}

        QCheckBox {{
            color: {TEXT_SECONDARY};
            spacing: {SPACE_2}px;
        }}
        QCheckBox#maintenanceCheckbox {{
            color: {TEXT_SECONDARY};
            spacing: 9px;
            font-size: {FONT_SIZE_MD}px;
            font-weight: 700;
            padding-top: {SPACE_1}px;
            padding-bottom: {SPACE_1}px;
        }}
        /* O estado marcado permanece nativo para preservar o check. */
        QCheckBox#maintenanceCheckbox::indicator:unchecked {{
            background-color: {BG_PANEL};
            border: 1px solid {BORDER_STRONG};
            border-radius: {RADIUS_SM}px;
        }}
        QCheckBox#maintenanceCheckbox::indicator:unchecked:hover {{
            border-color: {ACCENT};
        }}
        QCheckBox#maintenanceCheckbox:disabled {{
            color: {TEXT_DISABLED};
        }}

        QPushButton[primary="true"] {{
            background-color: {ACCENT};
            color: {BG_APP};
            border-color: {ACCENT};
        }}
        QPushButton[primary="true"]:hover {{
            background-color: {ACCENT_HOVER};
            border-color: {ACCENT_HOVER};
        }}
        QPushButton[primary="true"]:pressed {{
            background-color: {ACCENT_PRESSED};
            border-color: {ACCENT_PRESSED};
        }}

        QFrame[frameShape="4"],
        QFrame[frameShape="5"] {{
            color: {BORDER};
        }}
        QToolTip {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            border-radius: {RADIUS_SM}px;
            padding: 6px 8px;
        }}
    """ + admin_action_buttons_qss(
        min_height=32,
        horizontal_padding=15,
    )


def device_detail_qss() -> str:
    """Tema da janela de detalhes, sem alterar seus widgets ou dados."""

    return f"""
        QMainWindow,
        QDialog {{
            background-color: {BG_APP};
        }}
        QWidget {{
            font-family: "{FONT_FAMILY}";
            color: {TEXT_PRIMARY};
        }}
        QLabel {{
            background: transparent;
        }}
        QLabel[secondary="true"] {{
            color: {TEXT_SECONDARY};
        }}
        QLabel[muted="true"] {{
            color: {TEXT_MUTED};
        }}

        QScrollArea#detailScroll,
        QScrollArea#detailScroll > QWidget > QWidget,
        QWidget#detailViewport,
        QWidget#detailContent {{
            background-color: {BG_APP};
        }}
        QScrollArea#detailScroll {{
            border: none;
        }}
        QFrame[panel="true"] {{
            background-color: {BG_PANEL};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_LG}px;
        }}
        QFrame#incidentPanel,
        QFrame#communicationPanel,
        QFrame#latencyChartPanel {{
            background-color: {BG_PANEL};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD}px;
        }}

        QLabel#deviceTitle {{
            color: {TEXT_PRIMARY};
            font-size: 26px;
            font-weight: 800;
        }}
        QLabel#deviceIp {{
            color: {TEXT_MUTED};
            font-size: 13px;
        }}
        QLabel#sectionTitle {{
            color: {TEXT_MUTED};
            font-size: {FONT_SIZE_SM}px;
            font-weight: 800;
        }}
        QLabel#chartTitle {{
            color: {TEXT_SECONDARY};
            font-size: {FONT_SIZE_SM}px;
            font-weight: 800;
        }}
        QLabel#chartSummary {{
            color: {TEXT_MUTED};
            font-size: {FONT_SIZE_SM}px;
        }}
        QLabel#infoTitle {{
            color: {TEXT_MUTED};
            font-size: {FONT_SIZE_MD}px;
        }}
        QLabel#infoValue {{
            color: {TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 700;
        }}

        QComboBox#chartPeriod {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_SM}px;
            padding: 6px 10px;
        }}
        QComboBox#chartPeriod:hover,
        QComboBox#chartPeriod:focus {{
            border-color: {ACCENT};
        }}
        QComboBox#chartPeriod QAbstractItemView {{
            background-color: {BG_PANEL};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            selection-background-color: {BG_PANEL_ALT};
        }}

        QGroupBox {{
            background-color: {BG_PANEL};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_LG}px;
            margin-top: {SPACE_3}px;
            padding-top: {SPACE_3}px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {SPACE_3}px;
            padding-left: 6px;
            padding-right: 6px;
            color: {TEXT_SECONDARY};
        }}
        QPushButton {{
            min-height: {CONTROL_HEIGHT}px;
            padding-left: {SPACE_4}px;
            padding-right: {SPACE_4}px;
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            border-radius: {RADIUS_MD}px;
            font-size: {FONT_SIZE_MD}px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {BG_PANEL_ALT};
            border-color: {ACCENT};
        }}
        QPushButton:pressed {{
            background-color: {BORDER};
        }}
        QPushButton:disabled {{
            background-color: {BG_PANEL};
            color: {TEXT_DISABLED};
            border-color: {BORDER};
        }}
        QPushButton[primary="true"] {{
            background-color: {ACCENT};
            color: {BG_APP};
            border-color: {ACCENT};
        }}
        QPushButton[primary="true"]:hover {{
            background-color: {ACCENT_HOVER};
            border-color: {ACCENT_HOVER};
        }}
        QPushButton[danger="true"] {{
            background-color: {DANGER_SOFT};
            color: {DANGER};
            border-color: {DANGER};
        }}

        QTableWidget,
        QTableView {{
            background-color: {BG_PANEL};
            alternate-background-color: {BG_PANEL_ALT};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_LG}px;
            gridline-color: {BORDER};
            selection-background-color: {BG_ELEVATED};
            selection-color: {TEXT_PRIMARY};
            outline: none;
        }}
        QTableWidget::item,
        QTableView::item {{
            padding: {SPACE_2}px;
            border-bottom: 1px solid {BORDER};
        }}
        QTableWidget::item:hover,
        QTableView::item:hover {{
            background-color: {BG_PANEL_ALT};
        }}
        QHeaderView::section {{
            background-color: {BG_ELEVATED};
            color: {TEXT_SECONDARY};
            border: none;
            border-bottom: 1px solid {BORDER};
            border-right: 1px solid {BORDER};
            padding: {SPACE_3}px;
            font-weight: 600;
        }}
        QListWidget,
        QTreeWidget {{
            background-color: {BG_PANEL};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_LG}px;
            outline: none;
        }}
        QListWidget::item,
        QTreeWidget::item {{
            padding: {SPACE_3}px;
            border-bottom: 1px solid {BORDER};
        }}
        QListWidget::item:hover,
        QTreeWidget::item:hover {{
            background-color: {BG_PANEL_ALT};
        }}
        QListWidget::item:selected,
        QTreeWidget::item:selected {{
            background-color: {BG_ELEVATED};
        }}
        QProgressBar {{
            min-height: 8px;
            background-color: {BG_ELEVATED};
            border: none;
            border-radius: {SPACE_1}px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: {ACCENT};
            border-radius: {SPACE_1}px;
        }}

        QScrollBar:vertical {{
            width: 10px;
            background: transparent;
        }}
        QScrollBar::handle:vertical {{
            min-height: 40px;
            background-color: {BORDER_STRONG};
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {TEXT_DISABLED};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        QStatusBar {{
            background-color: {BG_PANEL};
            color: {TEXT_MUTED};
        }}
        QToolTip {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            border-radius: {RADIUS_SM}px;
            padding: 6px 8px;
        }}
    """


def metric_card_qss() -> str:
    """Aparência neutra dos cartões de métricas do NODARIS."""

    return f"""
        QFrame#metricCard {{
            background-color: {BG_PANEL};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_LG}px;
        }}
        QFrame#metricCard:hover {{
            background-color: {BG_PANEL_ALT};
            border-color: {BORDER_STRONG};
        }}
        QLabel {{
            background: transparent;
            border: none;
            color: {TEXT_PRIMARY};
            font-family: "{FONT_FAMILY}";
        }}
        QLabel#metricTitle,
        QLabel[metricTitle="true"] {{
            color: {TEXT_MUTED};
            font-size: {FONT_SIZE_XS}px;
            font-weight: 600;
        }}
        QLabel#metricValue,
        QLabel[metricValue="true"] {{
            color: {TEXT_PRIMARY};
            font-size: {FONT_SIZE_XL}px;
            font-weight: 700;
        }}
        QLabel[metricInfo="true"] {{
            color: {TEXT_SECONDARY};
            font-size: {FONT_SIZE_XS}px;
        }}
    """


def latency_chart_palette() -> dict[str, str]:
    """Cores do gráfico; séries, eixos e cálculos continuam no widget."""

    return {
        "background": BG_PANEL,
        "plot_background": BG_PANEL,
        "border": BORDER,
        "grid": BORDER,
        "axis": TEXT_MUTED,
        "text": TEXT_SECONDARY,
        "line": ACCENT,
        "point": ACCENT,
        "selection": ACCENT_HOVER,
        "danger": DANGER,
    }


def wallboard_window_qss() -> str:
    """Camada visual da TV; não altera matriz, paginação ou geometria."""

    return f"""
        QMainWindow {{
            background-color: {BG_APP};
        }}

        QWidget {{
            font-family: "{FONT_FAMILY}";
            color: {TEXT_PRIMARY};
        }}

        QLabel {{
            background: transparent;
            color: {TEXT_PRIMARY};
        }}

        QLabel[secondary="true"] {{ color: {TEXT_SECONDARY}; }}
        QLabel[muted="true"] {{ color: {TEXT_MUTED}; }}

        QFrame {{ border: none; }}
        QFrame[panel="true"] {{
            background-color: {BG_PANEL};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_LG}px;
        }}

        QLabel[health="healthy"] {{ color: {SUCCESS}; font-weight: 700; }}
        QLabel[health="degraded"] {{ color: {WARNING}; font-weight: 700; }}
        QLabel[health="offline"] {{ color: {DANGER}; font-weight: 700; }}

        /* Shell existente: mesma estrutura, apenas paleta NODARIS. */
        QWidget#wallboardCentral {{ background-color: {BG_APP}; }}
        QLabel#wallboardTitle,
        QLabel#wallboardClock {{ color: {TEXT_PRIMARY}; }}
        QLabel#lastUpdate {{ color: {TEXT_SECONDARY}; }}
        QLabel#lastScan {{ color: {TEXT_MUTED}; }}
        QLabel#monitorHealth[state="waiting"] {{ color: {TEXT_MUTED}; }}
        QLabel#monitorHealth[state="healthy"] {{ color: {SUCCESS}; }}
        QLabel#monitorHealth[state="warning"] {{ color: {WARNING}; }}
        QLabel#monitorHealth[state="critical"] {{ color: {DANGER}; }}

        QFrame#summaryFrame {{
            background-color: {BG_PANEL};
            border-color: {BORDER};
            border-radius: {RADIUS_LG}px;
        }}
        QLabel#summaryValue {{ color: {TEXT_PRIMARY}; }}
        QLabel#summaryTitle {{ color: {TEXT_MUTED}; }}
        QLabel#sectionTitle {{ color: {TEXT_SECONDARY}; }}
        QLabel#sectionInfo,
        QLabel#matrixInfo {{ color: {TEXT_MUTED}; }}
        QLabel#pageInfo {{ color: {TEXT_PRIMARY}; }}
        QWidget#matrixHost {{ background: transparent; }}

        QPushButton {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            border-radius: {RADIUS_MD}px;
            padding-left: {SPACE_3}px;
            padding-right: {SPACE_3}px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {BG_PANEL_ALT};
            border-color: {ACCENT};
        }}
        QPushButton:pressed {{ background-color: {BORDER}; }}

        QScrollArea,
        QScrollArea > QWidget > QWidget {{
            background: transparent;
            border: none;
        }}
        QScrollBar:vertical {{ width: 9px; background: transparent; }}
        QScrollBar::handle:vertical {{
            min-height: 30px;
            background-color: {BORDER_STRONG};
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {TEXT_DISABLED};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{ height: 0px; }}

        /* WALLBOARD FINAL POLISH */
        QLabel#wallboardTitle {{
            color: {TEXT_PRIMARY};
            font-weight: 800;
        }}
        QFrame#statusLegend {{
            background: transparent;
            border: none;
        }}
        QLabel#legendItem {{
            background: transparent;
            border: none;
            color: {TEXT_SECONDARY};
            font-size: {FONT_SIZE_SM}px;
            font-weight: 700;
        }}
        QLabel#legendItem[status="online"] {{ color: {SUCCESS}; }}
        QLabel#legendItem[status="suspect"] {{ color: {SUSPECT}; }}
        QLabel#legendItem[status="recovering"] {{ color: {RECOVERING}; }}
        QLabel#legendItem[status="offline"] {{ color: {DANGER}; }}
        QLabel#legendItem[status="maintenance"] {{ color: {MAINTENANCE}; }}

        QToolTip {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            border-radius: {RADIUS_SM}px;
            padding: 6px 8px;
        }}
    """


def wallboard_ip_item_qss() -> str:
    """Aparência dos itens da matriz da TV, sem alterar sua geometria."""

    return f"""
        QFrame#wallboardIpItem {{
            background-color: {BG_PANEL};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD}px;
        }}

        QFrame#wallboardIpItem:hover {{
            background-color: {BG_PANEL_ALT};
            border-color: {BORDER_STRONG};
        }}

        QFrame#wallboardIpItem[status="online"] {{
            background-color: {BG_PANEL};
            border-color: {BORDER};
            border-left: 3px solid {SUCCESS};
        }}
        QFrame#wallboardIpItem[status="offline"] {{
            background-color: {BG_PANEL};
            border-color: {BORDER};
            border-left: 3px solid {DANGER};
        }}
        QFrame#wallboardIpItem[status="suspect"] {{
            background-color: {BG_PANEL};
            border-color: {BORDER};
            border-left: 3px solid {SUSPECT};
        }}
        QFrame#wallboardIpItem[status="recovering"] {{
            background-color: {BG_PANEL};
            border-color: {BORDER};
            border-left: 3px solid {RECOVERING};
        }}
        QFrame#wallboardIpItem[status="maintenance"] {{
            background-color: {BG_PANEL};
            border-color: {BORDER};
            border-left: 3px solid {MAINTENANCE};
        }}
        QFrame#wallboardIpItem[status="error"] {{
            background-color: {BG_PANEL};
            border-color: {BORDER};
            border-left: 3px solid {ERROR};
        }}
        QFrame#wallboardIpItem[status="unknown"] {{
            background-color: {BG_PANEL};
            border-color: {BORDER};
            border-left: 3px solid {UNKNOWN};
        }}

        QFrame#wallboardIpItem[status="online"]:hover,
        QFrame#wallboardIpItem[status="offline"]:hover,
        QFrame#wallboardIpItem[status="suspect"]:hover,
        QFrame#wallboardIpItem[status="recovering"]:hover,
        QFrame#wallboardIpItem[status="maintenance"]:hover,
        QFrame#wallboardIpItem[status="error"]:hover,
        QFrame#wallboardIpItem[status="unknown"]:hover {{
            background-color: {BG_PANEL_ALT};
        }}

        QLabel {{
            background: transparent;
            border: none;
        }}
        QLabel#ipText[role="ip"] {{ color: {TEXT_PRIMARY}; }}
        QLabel#ipValue[role="status"] {{
            color: {TEXT_SECONDARY};
            font-weight: 700;
        }}

        QLabel#statusDot[status="online"],
        QLabel#ipValue[status="online"] {{ color: {SUCCESS}; }}
        QLabel#statusDot[status="offline"],
        QLabel#ipValue[status="offline"] {{ color: {DANGER}; }}
        QLabel#statusDot[status="suspect"],
        QLabel#ipValue[status="suspect"] {{ color: {SUSPECT}; }}
        QLabel#statusDot[status="recovering"],
        QLabel#ipValue[status="recovering"] {{ color: {RECOVERING}; }}
        QLabel#statusDot[status="maintenance"],
        QLabel#ipValue[status="maintenance"] {{ color: {MAINTENANCE}; }}
        QLabel#statusDot[status="error"],
        QLabel#ipValue[status="error"] {{ color: {ERROR}; }}
        QLabel#statusDot[status="unknown"],
        QLabel#ipValue[status="unknown"] {{ color: {UNKNOWN}; }}

        /* FINAL TV READABILITY: mantém 32 px e os espaçamentos do item. */
        QLabel#statusDot {{
            background: transparent;
            border: none;
            font-size: {FONT_SIZE_XL}px;
            font-weight: 900;
        }}
        QLabel#ipText {{
            background: transparent;
            border: none;
            color: {TEXT_PRIMARY};
            font-size: {FONT_SIZE_MD}px;
            font-weight: 700;
        }}
        QLabel#ipText[status="offline"] {{
            color: {DANGER};
            font-weight: 800;
        }}
        QLabel#ipText[status="suspect"] {{ color: {SUSPECT}; }}
        QLabel#ipText[status="recovering"] {{ color: {RECOVERING}; }}
        QLabel#ipText[status="maintenance"] {{ color: {MAINTENANCE}; }}
        QLabel#ipValue {{
            background: transparent;
            border: none;
            color: {TEXT_MUTED};
            font-size: {FONT_SIZE_SM}px;
            font-weight: 700;
        }}
        QLabel#ipValue[status="offline"] {{
            color: {DANGER};
            font-weight: 800;
        }}
        QLabel#ipValue[status="suspect"] {{ color: {SUSPECT}; }}
        QLabel#ipValue[status="recovering"] {{ color: {RECOVERING}; }}
        QLabel#ipValue[status="maintenance"] {{ color: {MAINTENANCE}; }}
    """


def wallboard_incident_alert_qss() -> str:
    """Aparência do alerta da TV, sem alterar fila ou duração."""

    return f"""
        QFrame#wallboardIncidentAlert {{
            background-color: {BG_ELEVATED};
            border: 1px solid {DANGER};
            border-radius: {RADIUS_LG}px;
        }}

        QLabel#alertDot {{
            background: transparent;
            color: {DANGER};
            border: none;
            font-size: {FONT_SIZE_LG}px;
            font-weight: 800;
        }}

        QLabel#alertTitle {{
            background: transparent;
            color: {DANGER};
            border: none;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 800;
        }}

        QLabel#alertDevice {{
            background: transparent;
            color: {TEXT_PRIMARY};
            border: none;
            font-size: {FONT_SIZE_LG}px;
            font-weight: 700;
        }}

        QLabel#alertIp {{
            background: transparent;
            color: {TEXT_MUTED};
            border: none;
            font-size: {FONT_SIZE_SM}px;
        }}

        QLabel#alertStatus {{
            background-color: {DANGER_SOFT};
            color: {DANGER};
            border: 1px solid {DANGER};
            border-radius: {RADIUS_SM}px;
            padding: 3px 8px;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 700;
        }}

        QLabel#alertTime {{
            background: transparent;
            color: {TEXT_MUTED};
            border: none;
            font-size: {FONT_SIZE_XS}px;
        }}
    """


def nodaris_interactive_qss() -> str:
    """Controles desktop comuns, sem alturas ou espaçamentos estruturais."""

    return f"""
        QPushButton, QToolButton {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            border-radius: {RADIUS_MD}px;
            font-family: "{FONT_FAMILY}";
            font-weight: 600;
        }}
        QPushButton:hover, QToolButton:hover {{
            background-color: {BG_PANEL_ALT};
            border-color: {ACCENT};
        }}
        QPushButton:pressed, QToolButton:pressed {{
            background-color: {BORDER};
            border-color: {ACCENT_PRESSED};
        }}
        QPushButton:disabled, QToolButton:disabled {{
            background-color: {BG_PANEL};
            color: {TEXT_DISABLED};
            border-color: {BORDER};
        }}

        QPushButton[primary="true"], QToolButton[primary="true"] {{
            background-color: {ACCENT};
            color: {BG_APP};
            border-color: {ACCENT};
        }}
        QPushButton[primary="true"]:hover, QToolButton[primary="true"]:hover {{
            background-color: {ACCENT_HOVER};
            border-color: {ACCENT_HOVER};
        }}
        QPushButton[primary="true"]:pressed, QToolButton[primary="true"]:pressed {{
            background-color: {ACCENT_PRESSED};
            border-color: {ACCENT_PRESSED};
        }}

        QPushButton[danger="true"], QToolButton[danger="true"] {{
            background-color: {DANGER_SOFT};
            color: {DANGER};
            border-color: {DANGER};
        }}
        QPushButton[danger="true"]:hover, QToolButton[danger="true"]:hover {{
            background-color: {DANGER};
            color: {TEXT_PRIMARY};
        }}
        QPushButton[primary="true"]:disabled,
        QToolButton[primary="true"]:disabled,
        QPushButton[danger="true"]:disabled,
        QToolButton[danger="true"]:disabled {{
            background-color: {BG_PANEL};
            color: {TEXT_DISABLED};
            border-color: {BORDER};
        }}

        QLineEdit, QTextEdit, QPlainTextEdit,
        QSpinBox, QDoubleSpinBox, QComboBox {{
            background-color: {BG_PANEL};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD}px;
            selection-background-color: {ACCENT};
            selection-color: {BG_APP};
        }}
        QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover,
        QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
            border-color: {BORDER_STRONG};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
        QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border-color: {ACCENT};
        }}
        QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
        QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
            background-color: {BG_PANEL_ALT};
            color: {TEXT_DISABLED};
            border-color: {BORDER};
        }}
        QComboBox QAbstractItemView {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_STRONG};
            selection-background-color: {BG_PANEL_ALT};
            selection-color: {TEXT_PRIMARY};
        }}

        QCheckBox {{ color: {TEXT_SECONDARY}; background: transparent; }}

        QTableView, QTableWidget {{
            background-color: {BG_PANEL};
            alternate-background-color: {BG_PANEL_ALT};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD}px;
            gridline-color: {BORDER};
            selection-background-color: {BG_ELEVATED};
            selection-color: {TEXT_PRIMARY};
        }}
        QTableView::item, QTableWidget::item {{ border: none; }}
        QTableView::item:selected, QTableWidget::item:selected {{
            background-color: {BG_ELEVATED};
        }}
        QHeaderView::section {{
            background-color: {BG_ELEVATED};
            color: {TEXT_SECONDARY};
            border: none;
            border-bottom: 1px solid {BORDER_STRONG};
            font-weight: 700;
        }}
    """


def nodaris_scrollbar_qss() -> str:
    """Scrollbars discretas, verticais e horizontais."""

    return f"""
        QScrollBar:vertical {{
            width: 8px;
            background: transparent;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            min-height: 28px;
            background-color: {BORDER_STRONG};
            border: none;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {TEXT_DISABLED};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{ background: transparent; }}

        QScrollBar:horizontal {{
            height: 8px;
            background: transparent;
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            min-width: 28px;
            background-color: {BORDER_STRONG};
            border: none;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {TEXT_DISABLED};
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{ width: 0px; }}
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {{ background: transparent; }}
    """


def nodaris_desktop_controls_qss() -> str:
    return nodaris_interactive_qss() + nodaris_scrollbar_qss()


def admin_alert_notification_qss() -> str:
    """Estado do botão de alertas, após os controles genéricos."""

    return f"""
        QToolButton#alertNotificationButton {{
            min-width: 38px;
            background-color: {BG_PANEL};
            color: {TEXT_MUTED};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_MD}px;
            padding: 4px 10px;
            font-size: {FONT_SIZE_MD}px;
            font-weight: 700;
        }}
        QToolButton#alertNotificationButton:hover {{
            background-color: {BG_PANEL_ALT};
            color: {TEXT_PRIMARY};
            border-color: {BORDER_STRONG};
        }}
        QToolButton#alertNotificationButton[active="true"] {{
            background-color: {DANGER_SOFT};
            color: {DANGER};
            border-color: {DANGER};
        }}
        QToolButton#alertNotificationButton[active="true"]:hover {{
            background-color: {DANGER};
            color: {TEXT_PRIMARY};
        }}
    """
