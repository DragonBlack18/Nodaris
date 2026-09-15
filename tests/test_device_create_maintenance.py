import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.device_management_service import DeviceManagementService
from api.devices_repository import DevicesRepository
from api.main import DeviceCreateRequest, create_device


class DeviceCreateMaintenanceTests(unittest.TestCase):

    def _config_file(self, directory: str) -> Path:
        config_file = Path(directory) / "ips.json"
        config_file.write_text(
            json.dumps(
                {
                    "intervalo": 5,
                    "equipamentos": {},
                }
            ),
            encoding="utf-8",
        )
        return config_file

    def test_service_persists_maintenance_during_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = self._config_file(directory)
            service = DeviceManagementService(config_file)

            created = service.create_device(
                ip="192.0.2.10",
                name="Maintenance device",
                maintenance=True,
            )

            stored = json.loads(
                config_file.read_text(encoding="utf-8")
            )["equipamentos"]["192.0.2.10"]
            catalog = DevicesRepository(config_file).get_devices()

        self.assertTrue(created["maintenance"])
        self.assertTrue(stored["manutencao"])
        self.assertTrue(catalog[0]["maintenance"])

    def test_api_route_forwards_maintenance_to_service(self):
        with tempfile.TemporaryDirectory() as directory:
            service = DeviceManagementService(
                self._config_file(directory)
            )
            request = DeviceCreateRequest(
                ip="192.0.2.11",
                name="API maintenance device",
                maintenance=True,
            )

            with patch(
                "api.main.device_management_service",
                service,
            ):
                response = create_device(request)

        self.assertTrue(response["ok"])
        self.assertTrue(response["device"]["maintenance"])


if __name__ == "__main__":
    unittest.main()
