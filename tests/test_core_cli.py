import unittest
from unittest.mock import patch

from core import main as core_main


class CoreCliTests(unittest.TestCase):

    @patch.object(core_main, "main")
    def test_default_mode_starts_core(self, start_core):
        self.assertEqual(core_main.cli_main([]), 0)
        start_core.assert_called_once_with()

    @patch.object(core_main, "main")
    def test_explicit_core_mode_starts_core(self, start_core):
        self.assertEqual(
            core_main.cli_main(["--core"]),
            0,
        )
        start_core.assert_called_once_with()

    @patch("core.watchdog.main")
    def test_watchdog_mode_runs_watchdog_only(self, run_watchdog):
        self.assertEqual(
            core_main.cli_main(["--watchdog"]),
            0,
        )
        run_watchdog.assert_called_once_with()

    @patch.object(core_main, "main")
    def test_unknown_mode_is_rejected(self, start_core):
        self.assertEqual(
            core_main.cli_main(["--unknown"]),
            2,
        )
        start_core.assert_not_called()


if __name__ == "__main__":
    unittest.main()
