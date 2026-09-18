from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from nodaris.ui.windows.admin_window import AdminWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("NODARIS V2")

    window = AdminWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
