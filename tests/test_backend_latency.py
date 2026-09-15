import math
import tempfile
import unittest
from pathlib import Path

from api.ip_health_service import IPHealthService
from api.latency import normalize_latency_ms, normalize_probe_latency_ms
from api.monitor_service import MonitorService
from api.probe_history_repository import ProbeHistoryRepository


class LatencyNormalizationTests(unittest.TestCase):

    def test_rejects_invalid_measurements_and_accepts_real_zero(self):
        invalid_values = [
            None,
            True,
            False,
            -1,
            float("nan"),
            float("inf"),
            float("-inf"),
            "invalid",
        ]

        for value in invalid_values:
            with self.subTest(value=value):
                self.assertIsNone(normalize_latency_ms(value))

        self.assertEqual(normalize_latency_ms(0), 0.0)
        self.assertEqual(normalize_latency_ms("0.5"), 0.5)

    def test_only_online_probe_can_have_latency(self):
        self.assertEqual(
            normalize_probe_latency_ms("ONLINE", 0),
            0.0,
        )
        self.assertIsNone(
            normalize_probe_latency_ms("OFFLINE", 0)
        )
        self.assertIsNone(
            normalize_probe_latency_ms("ERROR", 10)
        )


class IPHealthLatencyTests(unittest.TestCase):

    def test_invalid_online_latency_does_not_contaminate_metrics(self):
        for value in (-1, float("nan"), float("inf"), True):
            with self.subTest(value=value):
                health = IPHealthService().observe(
                    {
                        "ip": "192.0.2.1",
                        "status": "ONLINE",
                        "latency_ms": value,
                    }
                )

                self.assertIsNone(health["latency"]["current_ms"])
                self.assertIsNone(health["latency"]["average_ms"])
                self.assertEqual(health["latency"]["samples"], 0)

    def test_real_zero_is_kept_for_online_probe(self):
        health = IPHealthService().observe(
            {
                "ip": "192.0.2.1",
                "status": "ONLINE",
                "latency_ms": 0,
            }
        )

        self.assertEqual(health["latency"]["current_ms"], 0.0)
        self.assertEqual(health["latency"]["average_ms"], 0.0)
        self.assertEqual(health["latency"]["samples"], 1)

    def test_offline_probe_never_exposes_latency(self):
        health = IPHealthService().observe(
            {
                "ip": "192.0.2.1",
                "status": "OFFLINE",
                "latency_ms": 0,
            }
        )

        self.assertIsNone(health["latency"]["current_ms"])
        self.assertEqual(health["latency"]["samples"], 0)


class MonitorServiceLatencyTests(unittest.IsolatedAsyncioTestCase):

    async def test_probe_result_is_normalized_before_leaving_service(self):
        service = MonitorService(concurrency=1)

        async def invalid_probe(_ip):
            return {
                "status": "ONLINE",
                "online": True,
                "latency_ms": float("nan"),
            }

        service._probe = invalid_probe
        result = await service.probe_device(
            {"ip": "192.0.2.1", "name": "Device"}
        )

        self.assertIsNone(result["latency_ms"])


class ProbeHistoryLatencyTests(unittest.TestCase):

    def test_repository_normalizes_measurements_before_persisting(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = ProbeHistoryRepository(
                Path(directory) / "latency.db"
            )

            repository.save_probe(
                ip="192.0.2.1",
                name="Device",
                probe_status="OFFLINE",
                effective_status="OFFLINE",
                latency_ms=0,
                quality="CRITICAL",
                consecutive_failures=1,
                consecutive_successes=0,
                observed_at="2026-09-15T12:00:00",
            )
            repository.save_probe(
                ip="192.0.2.1",
                name="Device",
                probe_status="ONLINE",
                effective_status="ONLINE",
                latency_ms=0,
                quality="EXCELLENT",
                consecutive_failures=0,
                consecutive_successes=1,
                observed_at="2026-09-15T12:00:01",
            )
            repository.save_probe(
                ip="192.0.2.1",
                name="Device",
                probe_status="ONLINE",
                effective_status="ONLINE",
                latency_ms=math.inf,
                quality="UNKNOWN",
                consecutive_failures=0,
                consecutive_successes=2,
                observed_at="2026-09-15T12:00:02",
            )

            history = repository.get_history("192.0.2.1")

        by_timestamp = {
            item["observed_at"]: item["latency_ms"]
            for item in history
        }
        self.assertIsNone(by_timestamp["2026-09-15T12:00:00"])
        self.assertEqual(by_timestamp["2026-09-15T12:00:01"], 0.0)
        self.assertIsNone(by_timestamp["2026-09-15T12:00:02"])


if __name__ == "__main__":
    unittest.main()
