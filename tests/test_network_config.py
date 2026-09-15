import inspect
import unittest

from api.config import (
    API_BASE_URL,
    API_HOST,
    API_PORT,
    BLACKBOX_ADDRESS,
    BLACKBOX_HOST,
    BLACKBOX_PORT,
    BLACKBOX_URL,
)
from core import watchdog
from desktop.api_client import ApiClient
from desktop.device_admin_client import DeviceAdminClient


class NetworkConfigTests(unittest.TestCase):

    def test_default_addresses_preserve_current_contract(self):
        self.assertEqual(API_HOST, "127.0.0.1")
        self.assertEqual(API_PORT, 8765)
        self.assertEqual(API_BASE_URL, "http://127.0.0.1:8765")
        self.assertEqual(BLACKBOX_HOST, "127.0.0.1")
        self.assertEqual(BLACKBOX_PORT, 9115)
        self.assertEqual(BLACKBOX_ADDRESS, "127.0.0.1:9115")
        self.assertEqual(BLACKBOX_URL, "http://127.0.0.1:9115")

    def test_watchdog_health_uses_central_base_url(self):
        self.assertEqual(watchdog.HEALTH_URL, f"{API_BASE_URL}/health")

    def test_desktop_clients_use_central_default_url(self):
        api_default = inspect.signature(ApiClient).parameters[
            "base_url"
        ].default
        admin_default = inspect.signature(DeviceAdminClient).parameters[
            "base_url"
        ].default

        self.assertEqual(api_default, API_BASE_URL)
        self.assertEqual(admin_default, API_BASE_URL)


if __name__ == "__main__":
    unittest.main()
