from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtGui import QIcon


# =========================================================
# RESOURCE ROOT
# =========================================================

def resource_root() -> Path:
    """
    Retorna a raiz onde os recursos da aplicação estão.

    Desenvolvimento:
        raiz do projeto

    PyInstaller:
        sys._MEIPASS
    """

    bundle_root = getattr(
        sys,
        "_MEIPASS",
        None,
    )

    if bundle_root:

        return Path(
            bundle_root
        )

    return (
        Path(__file__)
        .resolve()
        .parents[1]
    )


# =========================================================
# BRANDING PATHS
# =========================================================

def branding_path(
    filename: str,
) -> Path:

    return (
        resource_root()
        / "assets"
        / "branding"
        / filename
    )


def nodaris_icon_path() -> Path:

    return branding_path(
        "nodaris_icon.ico"
    )


def nodaris_png_path() -> Path:

    return branding_path(
        "nodaris_icon_256.png"
    )


# =========================================================
# QT ICON
# =========================================================

def get_nodaris_icon() -> QIcon:

    icon_path = (
        nodaris_icon_path()
    )

    if not icon_path.exists():

        return QIcon()

    return QIcon(
        str(icon_path)
    )


# =========================================================
# WINDOWS TASKBAR ID
# =========================================================

def configure_windows_app_id(
    app_id: str,
) -> None:
    """
    Define um AppUserModelID próprio no Windows.

    Isso ajuda o Windows a associar corretamente
    ícone, janela e barra de tarefas ao NODARIS,
    em vez de mostrar apenas o ícone do python.exe.
    """

    if sys.platform != "win32":

        return

    try:

        ctypes.windll.shell32 \
            .SetCurrentProcessExplicitAppUserModelID(
                app_id
            )

    except Exception:

        # Branding nunca deve impedir
        # a aplicação de iniciar.
        pass
