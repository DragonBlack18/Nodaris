import json
import tempfile
import unittest
from pathlib import Path

from api.device_management_service import (
    DeviceManagementService,
    InvalidDeviceError,
)
from api.devices_repository import DevicesRepository


class DeviceConfigResilienceTests(unittest.TestCase):
    def test_repository_accepts_utf8_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ips.json"
            path.write_text(
                json.dumps(
                    {
                        "config_version": 1,
                        "intervalo": 5,
                        "equipamentos": {
                            "192.0.2.10": {
                                "nome": "BOM device",
                                "gateway": "",
                                "manutencao": False,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8-sig",
            )

            devices = DevicesRepository(path).get_devices()

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["ip"], "192.0.2.10")
        self.assertEqual(devices[0]["name"], "BOM device")

    def test_crud_preserves_catalog_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ips.json"
            path.write_text(
                json.dumps(
                    {
                        "config_version": 1,
                        "intervalo": 7,
                        "custom_key": "keep-me",
                        "equipamentos": {},
                    }
                ),
                encoding="utf-8",
            )

            service = DeviceManagementService(path)
            service.create_device(
                ip="192.0.2.11",
                name="Device",
                gateway="192.0.2.1",
            )

            current = json.loads(path.read_text(encoding="utf-8"))
            backup = json.loads(
                service.backup_file.read_text(encoding="utf-8")
            )

        self.assertEqual(current["intervalo"], 7)
        self.assertEqual(current["custom_key"], "keep-me")
        self.assertIn("192.0.2.11", current["equipamentos"])
        self.assertEqual(backup["equipamentos"], {})

    def test_invalid_existing_json_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ips.json"
            original = "{invalid-json"
            path.write_text(original, encoding="utf-8")
            service = DeviceManagementService(path)

            with self.assertRaises(InvalidDeviceError):
                service.create_device(
                    ip="192.0.2.12",
                    name="Must not be written",
                )

            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
