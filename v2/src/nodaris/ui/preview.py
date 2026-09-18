from __future__ import annotations

import sys
from datetime import datetime, timedelta

from PySide6.QtWidgets import QApplication

from nodaris.ui.windows.admin_window import AdminWindow
from nodaris.ui.windows.device_detail_window import DeviceDetailWindow
from nodaris.ui.windows.device_management_window import DeviceManagementWindow
from nodaris.ui.windows.wallboard_window import WallboardWindow


DEVICES = [
    {
        "name": "Servidor Principal",
        "ip": "192.168.1.10",
        "gateway": "192.168.1.1",
        "status": "ONLINE",
        "latency_ms": 3.4,
        "health": {
            "status": "ONLINE",
            "quality": "EXCELLENT",
            "consecutive_failures": 0,
            "consecutive_successes": 12,
            "latency": {
                "current_ms": 3.4,
                "average_ms": 4.2,
                "min_ms": 2.8,
                "max_ms": 8.1,
            },
            "loss_percent": 0.0,
        },
    },
    {
        "name": "Balança Produção 01",
        "ip": "192.168.1.31",
        "gateway": "192.168.1.1",
        "status": "SUSPECT",
        "latency_ms": 94.7,
        "health": {"status": "SUSPECT"},
    },
    {
        "name": "Impressora Expedição",
        "ip": "192.168.1.44",
        "gateway": "192.168.1.1",
        "status": "OFFLINE",
        "latency_ms": None,
        "health": {"status": "OFFLINE"},
    },
    {
        "name": "Mini PC Sala de Controle",
        "ip": "192.168.1.52",
        "gateway": "192.168.1.1",
        "status": "RECOVERING",
        "latency_ms": 21.2,
        "health": {"status": "RECOVERING"},
    },
    {
        "name": "Equipamento em manutenção",
        "ip": "192.168.1.80",
        "gateway": "192.168.1.1",
        "status": "ONLINE",
        "latency_ms": None,
        "maintenance": True,
    },
]


class PreviewController:
    def __init__(self) -> None:
        self.admin = AdminWindow()
        self.management = DeviceManagementWindow()
        self.detail = DeviceDetailWindow()
        self.wallboard = WallboardWindow()

        self.admin.devices_requested.connect(self.show_management)
        self.admin.device_selected.connect(self.show_detail)

        self.admin.set_connection_state(True)
        self.admin.set_devices(DEVICES)
        self.admin.set_alert_count(1)

        self.management.set_devices(DEVICES)
        self.wallboard.set_monitoring_state(True)
        self.wallboard.set_devices(DEVICES)

    def show_management(self) -> None:
        self.management.show()
        self.management.raise_()
        self.management.activateWindow()

    def show_detail(self, ip: str) -> None:
        device = next((item for item in DEVICES if item["ip"] == ip), None)
        if not device:
            return

        health = device.get("health") or {}
        status = (
            "MAINTENANCE"
            if device.get("maintenance")
            else health.get("status") or device.get("status") or "UNKNOWN"
        )

        self.detail.set_identity(device["name"], device["ip"], status)
        self.detail.set_health(health)
        self.detail.latency_chart.set_samples(_latency_samples())
        self.detail.availability_card.set_value("99.94%")
        self.detail.monitored_time_card.set_value("24h")
        self.detail.downtime_card.set_value("52s")
        self.detail.incident_count_card.set_value("1")
        self.detail.confirmed_status_label.setText(status)
        self.detail.probe_status_label.setText(str(device.get("status", "--")))

        self.detail.show()
        self.detail.raise_()
        self.detail.activateWindow()


def _latency_samples() -> list[dict]:
    now = datetime.now()
    values = [4.1, 3.8, 5.0, 4.5, 7.2, 3.9, 4.4, 3.5, 6.1, 4.0]
    return [
        {
            "observed_at": (now - timedelta(minutes=(len(values) - index) * 5)).isoformat(),
            "latency_ms": value,
        }
        for index, value in enumerate(values)
    ]


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("NODARIS V2 — Visual Preview")

    controller = PreviewController()
    controller.admin.show()
    controller.wallboard.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
