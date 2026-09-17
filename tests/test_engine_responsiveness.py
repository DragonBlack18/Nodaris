import asyncio
import time
import unittest
from unittest.mock import patch

from api.monitor_engine import MonitorEngine


class SlowRepository:
    def __init__(self, delay: float = 0.30):
        self.delay = delay

    def get_devices(self):
        time.sleep(self.delay)
        return []

    def get_interval(self):
        time.sleep(self.delay)
        return 5


class EmptyMonitorService:
    async def probe_devices(self, devices):
        return {"devices": []}


class OneDeviceRepository:
    def get_devices(self):
        return [
            {
                "ip": "127.0.0.1",
                "name": "Loopback",
                "maintenance": False,
            }
        ]

    def get_interval(self):
        return 5


class OneDeviceMonitorService:
    async def probe_devices(self, devices):
        return {
            "devices": [
                {
                    "ip": "127.0.0.1",
                    "name": "Loopback",
                    "status": "ONLINE",
                    "latency_ms": 0.5,
                    "error": None,
                }
            ]
        }


class FakeHealthService:
    def observe(self, result):
        return {
            "probe_status": "ONLINE",
            "status": "ONLINE",
            "stable_status": "ONLINE",
            "quality": "EXCELLENT",
            "consecutive_failures": 0,
            "consecutive_successes": 2,
        }


class EngineResponsivenessTests(unittest.TestCase):
    def _make_engine(self, repository, monitor_service):
        with (
            patch("api.monitor_engine.WindowsNotifier"),
            patch("api.monitor_engine.EventRepository"),
            patch("api.monitor_engine.IncidentRepository"),
            patch("api.monitor_engine.DeviceStateRepository"),
            patch("api.monitor_engine.IPHealthService"),
            patch("api.monitor_engine.ProbeHistoryRepository"),
        ):
            return MonitorEngine(
                repository=repository,
                monitor_service=monitor_service,
            )

    def test_slow_device_catalog_does_not_block_event_loop(self):
        engine = self._make_engine(
            SlowRepository(delay=0.30),
            EmptyMonitorService(),
        )

        async def scenario():
            scan_task = asyncio.create_task(engine.scan_once())
            started = time.perf_counter()
            await asyncio.sleep(0.05)
            elapsed = time.perf_counter() - started
            await scan_task
            return elapsed

        elapsed = asyncio.run(scenario())
        self.assertLess(elapsed, 0.20)

    def test_slow_probe_persistence_does_not_block_event_loop(self):
        engine = self._make_engine(
            OneDeviceRepository(),
            OneDeviceMonitorService(),
        )
        engine.ip_health_service = FakeHealthService()
        engine.incident_repository.has_open_incident.return_value = False

        def slow_save_probe(**kwargs):
            time.sleep(0.30)

        engine.probe_history_repository.save_probe.side_effect = slow_save_probe

        async def scenario():
            scan_task = asyncio.create_task(engine.scan_once())
            started = time.perf_counter()
            await asyncio.sleep(0.05)
            elapsed = time.perf_counter() - started
            await scan_task
            return elapsed

        elapsed = asyncio.run(scenario())
        self.assertLess(elapsed, 0.20)


if __name__ == "__main__":
    unittest.main()
