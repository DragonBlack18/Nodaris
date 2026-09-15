from PySide6.QtCore import QObject
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QSystemTrayIcon,
)

from desktop.branding import (
    get_nodaris_icon,
)


class TrayManager(QObject):

    def __init__(
        self,
        main_window,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.main_window = (
            main_window
        )

        self.tray = QSystemTrayIcon(
            self
        )

        self.application_icon = (
            get_nodaris_icon()
        )

        if self.application_icon.isNull():

            self.application_icon = (
                self._create_icon(
                    "#777777"
                )
            )

        self.tray.setIcon(
            self.application_icon
        )

        self.menu = QMenu()

        self.open_action = (
            self.menu.addAction(
                "Abrir NODARIS"
            )
        )

        self.menu.addSeparator()

        self.status_action = (
            self.menu.addAction(
                "Carregando status..."
            )
        )

        self.status_action.setEnabled(
            False
        )

        self.menu.addSeparator()

        self.exit_action = (
            self.menu.addAction(
                "Sair do NODARIS"
            )
        )

        self.tray.setContextMenu(
            self.menu
        )

        self.open_action.triggered.connect(
            self.show_window
        )

        self.exit_action.triggered.connect(
            self.exit_application
        )

        self.tray.activated.connect(
            self._tray_activated
        )

        self.set_unknown()

        self.tray.show()

    # =====================================================
    # ICON
    # =====================================================

    @staticmethod
    def _create_icon(
        color: str,
    ) -> QIcon:

        pixmap = QPixmap(
            64,
            64,
        )

        pixmap.fill(
            QColor(
                "transparent"
            )
        )

        painter = QPainter(
            pixmap
        )

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        painter.setBrush(
            QColor(color)
        )

        painter.setPen(
            QColor(color)
        )

        painter.drawEllipse(
            8,
            8,
            48,
            48,
        )

        painter.end()

        return QIcon(
            pixmap
        )

    # =====================================================
    # STATUS
    # =====================================================

    def update_status(
        self,
        data: dict,
    ):

        summary = data.get(
            "summary",
            {},
        )

        total = summary.get(
            "total",
            0,
        )

        online = summary.get(
            "online",
            0,
        )

        suspect = summary.get(
            "suspect",
            0,
        )

        offline = summary.get(
            "offline",
            0,
        )

        text = (
            f"{online}/{total} online | "
            f"{suspect} suspect | "
            f"{offline} offline"
        )

        self.status_action.setText(
            text
        )

        self.tray.setToolTip(
            "NODARIS\n"
            f"{text}"
        )

    def set_unknown(self):

        self.tray.setToolTip(
            "NODARIS\n"
            "Conectando..."
        )

        self.status_action.setText(
            "API indisponível"
        )

    # =====================================================
    # ACTIONS
    # =====================================================

    def show_window(self):

        self.main_window.show()

        self.main_window.raise_()

        self.main_window.activateWindow()

    def exit_application(self):

        self.tray.hide()

        QApplication.quit()

    def _tray_activated(
        self,
        reason,
    ):

        if (
            reason
            == QSystemTrayIcon.ActivationReason.DoubleClick
        ):

            self.show_window()
