import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from api.device_management_service import DeviceManagementService
from api.incident_repository import IncidentRepository
from api.main import delete_device
from api.monitor_engine import MonitorEngine
from api.probe_history_repository import ProbeHistoryRepository


class DeviceRemovalRetentionTests(unittest.TestCase):
    def test_runtime_reconciliation_closes_incident_for_direct_removal(self):
        engine = MonitorEngine.__new__(MonitorEngine)
        engine._current_status = {"192.0.2.21": {"status": "OFFLINE"}}
        engine._last_stable_status = {"192.0.2.21": "OFFLINE"}
        engine.incident_repository = Mock()
        engine.ip_health_service = Mock()
        engine.ip_health_service._states = {"192.0.2.21": {}}

        asyncio.run(engine._reconcile_runtime_devices([]))

        self.assertEqual(engine._current_status, {})
        self.assertEqual(engine._last_stable_status, {})
        self.assertEqual(engine.ip_health_service._states, {})
        engine.incident_repository.close_incident.assert_called_once()
        call = engine.incident_repository.close_incident.call_args
        self.assertEqual(call.kwargs["ip"], "192.0.2.21")
        self.assertTrue(call.kwargs["ended_at"])

    def test_removal_closes_incident_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_file = root / "ips.json"
            database_file = root / "monitor_api.db"
            config_file.write_text(
                json.dumps(
                    {
                        "config_version": 1,
                        "intervalo": 5,
                        "equipamentos": {
                            "192.0.2.20": {
                                "nome": "Removed device",
                                "gateway": "",
                                "queda": "",
                                "retorno": "",
                                "manutencao": False,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            management = DeviceManagementService(config_file)
            incidents = IncidentRepository(database_file)
            history = ProbeHistoryRepository(database_file)
            incidents.open_incident(
                ip="192.0.2.20",
                name="Removed device",
                started_at="2026-09-15T12:00:00",
            )
            history.save_probe(
                ip="192.0.2.20",
                name="Removed device",
                probe_status="OFFLINE",
                effective_status="OFFLINE",
                latency_ms=None,
                quality="CRITICAL",
                consecutive_failures=3,
                consecutive_successes=0,
                observed_at="2026-09-15T12:00:00",
            )

            with (
                patch("api.main.device_management_service", management),
                patch("api.main.incident_repository", incidents),
            ):
                response = delete_device("192.0.2.20")

            remaining_devices = management.list_devices()
            saved_incidents = incidents.get_incidents()
            saved_history = history.get_history("192.0.2.20")

        self.assertTrue(response["ok"])
        self.assertEqual(remaining_devices, [])
        self.assertEqual(len(saved_incidents), 1)
        self.assertEqual(saved_incidents[0]["status"], "CLOSED")
        self.assertIsNotNone(saved_incidents[0]["ended_at"])
        self.assertEqual(len(saved_history), 1)
        self.assertEqual(saved_history[0]["ip"], "192.0.2.20")


if __name__ == "__main__":
    unittest.main()
