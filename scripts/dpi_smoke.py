from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _sample_devices() -> list[dict]:
    states = (
        "ONLINE",
        "SUSPECT",
        "OFFLINE",
        "RECOVERING",
        "MAINTENANCE",
        "ONLINE",
        "OFFLINE",
        "ONLINE",
    )
    devices = []

    for index, state in enumerate(states, start=1):
        devices.append(
            {
                "ip": f"192.0.2.{index}",
                "name": (
                    "Equipamento corporativo de infraestrutura "
                    f"numero {index}"
                ),
                "gateway": "192.0.2.254",
                "maintenance": state == "MAINTENANCE",
                "status": state,
                "latency_ms": 0.0 if index == 1 else 12.5 + index,
                "health": {
                    "status": state,
                    "quality": "EXCELLENT",
                    "consecutive_failures": 0,
                    "consecutive_successes": 3,
                    "latency": {
                        "current_ms": 12.5 + index,
                        "average_ms": 14.0 + index,
                    },
                },
            }
        )

    return devices


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", required=True)
    parser.add_argument(
        "--platform",
        default="offscreen",
    )
    parser.add_argument("--output-dir")
    arguments = parser.parse_args()

    output_dir = (
        Path(arguments.output_dir).resolve()
        if arguments.output_dir
        else None
    )
    if output_dir is not None:
        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    os.environ["QT_QPA_PLATFORM"] = arguments.platform
    os.environ["QT_SCALE_FACTOR"] = str(arguments.scale)

    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication, QPushButton

    from desktop.windows import device_management_window as management_module
    from desktop.windows import main_window as main_module
    from desktop.windows import wallboard_window as wallboard_module
    from desktop.windows.device_detail_window import DeviceDetailWindow
    from desktop.windows.device_form_dialog import DeviceFormDialog

    class FakeApiClient(QObject):
        status_received = Signal(dict)
        incidents_received = Signal(object)
        connection_error = Signal(str)

        def get_status(self):
            return None

        def get_open_incidents(self):
            return None

    class FakeDeviceAdminClient(QObject):
        devices_received = Signal(object)
        operation_succeeded = Signal(str, object)
        operation_failed = Signal(str)

        def get_devices(self):
            return None

        def create_device(self, *args, **kwargs):
            return None

        def update_device(self, *args, **kwargs):
            return None

        def delete_device(self, *args, **kwargs):
            return None

    main_module.DeviceAdminClient = FakeDeviceAdminClient
    management_module.DeviceAdminClient = FakeDeviceAdminClient
    wallboard_module.DeviceAdminClient = FakeDeviceAdminClient

    MainWindow = main_module.MainWindow
    DeviceManagementWindow = management_module.DeviceManagementWindow
    WallboardWindow = wallboard_module.WallboardWindow

    app = QApplication.instance() or QApplication([])
    devices = _sample_devices()
    status_payload = {
        "devices": devices,
        "last_scan_at": datetime.now().isoformat(timespec="seconds"),
        "intervalo": 5,
    }

    admin = MainWindow()
    admin._catalog_devices_received(devices)
    admin.update_status(status_payload)

    management = DeviceManagementWindow()
    management._devices_received(devices)

    form = DeviceFormDialog(device=devices[0])
    form.name_input.setText(devices[0]["name"])
    form.ip_input.setText(devices[0]["ip"])
    form.gateway_input.setText(devices[0]["gateway"])

    detail = DeviceDetailWindow()
    detail.api.get_probe_history = lambda *args, **kwargs: None
    detail.api.get_device_availability = lambda *args, **kwargs: None
    detail.api.get_device_incidents = lambda *args, **kwargs: None
    detail.set_device(devices[0])

    wallboard = WallboardWindow(FakeApiClient())
    wallboard._catalog_devices_received(devices)
    wallboard._status_received(status_payload)

    windows = {
        "admin": admin,
        "management": management,
        "form": form,
        "detail": detail,
        "wallboard": wallboard,
    }

    for window in windows.values():
        window.show()

    for _ in range(5):
        app.processEvents()

    failures = []
    diagnostics = {}

    def validate_window(name, window, size_name):
        screenshot = window.grab()
        if output_dir is not None:
            screenshot.save(
                str(
                    output_dir
                    / f"{name}_{size_name}.png"
                )
            )
        diagnostics[f"{name}_{size_name}"] = {
            "width": window.width(),
            "height": window.height(),
            "pixel_ratio": screenshot.devicePixelRatio(),
            "screenshot_width": screenshot.width(),
            "screenshot_height": screenshot.height(),
        }

        if screenshot.isNull():
            failures.append(
                f"{name}/{size_name}: captura Qt vazia"
            )

        if window.width() < window.minimumWidth():
            failures.append(
                f"{name}/{size_name}: largura abaixo do minimo"
            )

        if window.height() < window.minimumHeight():
            failures.append(
                f"{name}/{size_name}: altura abaixo do minimo"
            )

        for button in window.findChildren(QPushButton):
            if not button.isVisible() or not button.text().strip():
                continue
            if button.width() < button.sizeHint().width():
                failures.append(
                    f"{name}/{size_name}: botao cortado: {button.text()} "
                    f"({button.width()} < {button.sizeHint().width()})"
                )

    for name, window in windows.items():
        validate_window(
            name,
            window,
            "default",
        )

    for window in windows.values():
        window.resize(
            max(window.minimumWidth(), 320),
            max(window.minimumHeight(), 240),
        )

    for _ in range(5):
        app.processEvents()

    for name, window in windows.items():
        validate_window(
            name,
            window,
            "minimum",
        )

    cards = (
        admin.total_card,
        admin.online_card,
        admin.suspect_card,
        admin.offline_card,
        admin.recovering_card,
    )
    card_widths = [card.width() for card in cards]
    if len(set(card_widths)) > 2:
        failures.append(
            f"admin: cards desalinhados: {card_widths}"
        )

    if management.table.rowCount() != len(devices):
        failures.append("management: quantidade de linhas incorreta")

    if len(wallboard.devices) != len(devices):
        failures.append("wallboard: quantidade de equipamentos incorreta")

    diagnostics["admin_card_widths"] = card_widths
    diagnostics["management_rows"] = management.table.rowCount()
    diagnostics["wallboard_devices"] = len(wallboard.devices)

    for window in windows.values():
        window.close()

    app.processEvents()

    print(
        json.dumps(
            {
                "scale": arguments.scale,
                "ok": not failures,
                "failures": failures,
                "diagnostics": diagnostics,
            },
            ensure_ascii=False,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
