import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from desktop.api_client import ApiClient
from desktop.branding import (
    configure_windows_app_id,
    get_nodaris_icon,
)
from desktop.tray import TrayManager
from desktop.windows.main_window import (
    MainWindow,
)


def main():

    # =====================================================
    # APPLICATION
    # =====================================================

    configure_windows_app_id(
        "NODARIS.Admin"
    )

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "NODARIS Admin"
    )

    app.setOrganizationName(
        "NODARIS"
    )

    app.setWindowIcon(
        get_nodaris_icon()
    )

    app.setQuitOnLastWindowClosed(
        False
    )

    # =====================================================
    # WINDOW
    # =====================================================

    window = MainWindow()

    # =====================================================
    # API CLIENT
    # =====================================================
    #
    # O Admin não inicia mais o backend.
    #
    # Ele é apenas cliente do NODARIS Core.

    api = ApiClient()

    # =====================================================
    # TRAY
    # =====================================================

    tray = TrayManager(
        main_window=window
    )

    # =====================================================
    # API SIGNALS
    # =====================================================

    api.status_received.connect(
        window.update_status
    )

    api.status_received.connect(
        tray.update_status
    )

    api.incidents_received.connect(
        window.update_incidents
    )

    api.connection_error.connect(
        window.set_connection_error
    )

    api.connection_error.connect(
        lambda _: tray.set_unknown()
    )

    # =====================================================
    # UI REFRESH TIMER
    # =====================================================
    #
    # O timer permanece ativo mesmo se o Core estiver
    # temporariamente indisponível.
    #
    # Dessa forma, se o Core iniciar depois, o Admin
    # reconecta automaticamente sem precisar reiniciar.

    refresh_timer = QTimer()

    refresh_timer.setInterval(
        2000
    )

    def refresh():

        api.get_status()

        api.get_open_incidents()

    refresh_timer.timeout.connect(
        refresh
    )

    refresh_timer.start()

    # Primeira tentativa assim que o event loop iniciar.
    QTimer.singleShot(
        0,
        refresh
    )

    # =====================================================
    # INITIAL STATUS
    # =====================================================

    window.statusBar().showMessage(
        "Conectando ao NODARIS Core..."
    )

    # =====================================================
    # SHOW WINDOW
    # =====================================================

    window.show()

    window.raise_()

    window.activateWindow()

    # =====================================================
    # EVENT LOOP
    # =====================================================

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
