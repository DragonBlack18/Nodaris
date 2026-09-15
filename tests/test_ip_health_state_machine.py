import unittest

from api.config import (
    HEALTH_FAILURE_THRESHOLD,
    HEALTH_RECOVERY_THRESHOLD,
)
from api.ip_health_service import IPHealthService


class IPHealthStateMachineTests(unittest.TestCase):

    def setUp(self):
        self.service = IPHealthService()
        self.ip = "192.0.2.1"

    def _observe(self, status: str):
        return self.service.observe(
            {
                "ip": self.ip,
                "status": status,
                "latency_ms": 1.0 if status == "ONLINE" else None,
            }
        )

    def test_offline_is_confirmed_on_third_consecutive_failure(self):
        self.assertEqual(HEALTH_FAILURE_THRESHOLD, 3)

        first = self._observe("OFFLINE")
        second = self._observe("OFFLINE")
        third = self._observe("OFFLINE")

        self.assertEqual(first["status"], "SUSPECT")
        self.assertEqual(first["consecutive_failures"], 1)
        self.assertEqual(second["status"], "SUSPECT")
        self.assertEqual(second["consecutive_failures"], 2)
        self.assertEqual(third["status"], "OFFLINE")
        self.assertEqual(third["stable_status"], "OFFLINE")
        self.assertEqual(third["consecutive_failures"], 3)

    def test_recovery_still_requires_two_consecutive_successes(self):
        self.assertEqual(HEALTH_RECOVERY_THRESHOLD, 2)

        for _ in range(HEALTH_FAILURE_THRESHOLD):
            offline = self._observe("OFFLINE")

        self.assertEqual(offline["status"], "OFFLINE")

        first = self._observe("ONLINE")
        second = self._observe("ONLINE")

        self.assertEqual(first["status"], "RECOVERING")
        self.assertEqual(first["stable_status"], "OFFLINE")
        self.assertEqual(first["consecutive_successes"], 1)
        self.assertEqual(second["status"], "ONLINE")
        self.assertEqual(second["stable_status"], "ONLINE")
        self.assertEqual(second["consecutive_successes"], 2)

    def test_monitoring_error_does_not_count_as_device_failure(self):
        first = self._observe("OFFLINE")
        error = self._observe("ERROR")

        self.assertEqual(first["consecutive_failures"], 1)
        self.assertEqual(error["probe_status"], "ERROR")
        self.assertEqual(error["consecutive_failures"], 1)
        self.assertEqual(error["status"], "SUSPECT")


if __name__ == "__main__":
    unittest.main()
