import unittest

from api.monitor_service import MonitorService


class MonitorServiceIsolationTests(unittest.IsolatedAsyncioTestCase):

    async def test_one_unexpected_probe_error_does_not_abort_batch(self):
        service = MonitorService(concurrency=4)
        processed = []

        async def probe_device(device):
            ip = device["ip"]
            processed.append(ip)

            if ip == "192.0.2.2":
                raise RuntimeError("controlled probe failure")

            return {
                "ip": ip,
                "name": device["name"],
                "gateway": "",
                "online": True,
                "status": "ONLINE",
                "latency_ms": 1.0,
                "latency_source": "test",
                "probe_engine": "test",
                "error": None,
            }

        service.probe_device = probe_device
        devices = [
            {"ip": "192.0.2.1", "name": "A"},
            {"ip": "192.0.2.2", "name": "B"},
            {"ip": "192.0.2.3", "name": "C"},
            {"ip": "192.0.2.4", "name": "D"},
        ]

        batch = await service.probe_devices(devices)

        self.assertEqual(
            processed,
            [device["ip"] for device in devices],
        )
        self.assertEqual(batch["summary"]["total"], 4)
        self.assertEqual(batch["summary"]["online"], 3)
        self.assertEqual(batch["summary"]["offline"], 0)
        self.assertEqual(batch["summary"]["errors"], 1)
        self.assertEqual(
            [item["ip"] for item in batch["devices"]],
            [device["ip"] for device in devices],
        )

        failed = batch["devices"][1]
        self.assertEqual(failed["status"], "ERROR")
        self.assertFalse(failed["online"])
        self.assertIsNone(failed["latency_ms"])
        self.assertIn("controlled probe failure", failed["error"])


if __name__ == "__main__":
    unittest.main()
