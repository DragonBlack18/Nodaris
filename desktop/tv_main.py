import sys

from PySide6.QtWidgets import QApplication

from desktop.api_client import ApiClient
from desktop.branding import (
    configure_windows_app_id,
    get_nodaris_icon,
)
from desktop.windows.wallboard_window import WallboardWindow


def main():
    configure_windows_app_id(
        "NODARIS.TV"
    )

    app = QApplication(sys.argv)
    app.setApplicationName("NODARIS TV")
    app.setOrganizationName("NODARIS")
    app.setWindowIcon(
        get_nodaris_icon()
    )

    # =====================================================
    # START MODE
    # =====================================================

    windowed_mode = "--windowed" in sys.argv

    api_client = ApiClient()
    window = WallboardWindow(api_client=api_client)

    if windowed_mode:
        window.show()
    else:
        window.showFullScreen()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
