import subprocess
import sys
import unittest
from unittest.mock import patch

from core import watchdog


class WatchdogRecoveryDecisionTests(unittest.TestCase):
    @patch.object(watchdog, "_core_port_is_open", return_value=False)
    @patch.object(watchdog, "_get_verified_core_processes", return_value=[])
    @patch.object(watchdog, "_get_core_task_state", return_value="Ready")
    def test_unavailable_core_without_running_task_starts(
        self,
        _task_state,
        _processes,
        _port,
    ):
        self.assertEqual(
            watchdog.recovery_mode_for_current_state(
                "health_connection_refused"
            ),
            "start",
        )

    @patch.object(watchdog, "_get_core_task_state", return_value="Running")
    def test_unavailable_core_with_running_task_is_replaced(self, _task_state):
        self.assertEqual(
            watchdog.recovery_mode_for_current_state(
                "health_connection_refused"
            ),
            "replace",
        )

    @patch.object(watchdog, "_get_core_task_state", return_value="Ready")
    @patch.object(
        watchdog,
        "_get_verified_core_processes",
        return_value=[
            {
                "pid": 123,
                "parent_pid": 1,
                "command_line": "pythonw.exe -m core.main",
            }
        ],
    )
    def test_unavailable_core_with_orphan_process_is_replaced(
        self,
        _processes,
        _task_state,
    ):
        self.assertEqual(
            watchdog.recovery_mode_for_current_state(
                "health_connection_refused"
            ),
            "replace",
        )

    @patch.object(watchdog, "_core_port_is_open", return_value=True)
    @patch.object(watchdog, "_get_verified_core_processes", return_value=[])
    @patch.object(watchdog, "_get_core_task_state", return_value="Ready")
    def test_unknown_listener_is_never_killed(
        self,
        _task_state,
        _processes,
        _port,
    ):
        self.assertEqual(
            watchdog.recovery_mode_for_current_state(
                "health_request_failed: unexpected response"
            ),
            "manual",
        )


class WatchdogProcessSafetyTests(unittest.TestCase):
    def test_command_verification_requires_module_execution(self):
        self.assertTrue(
            watchdog._is_verified_core_command(
                '"pythonw.exe" -m core.main'
            )
        )
        self.assertFalse(
            watchdog._is_verified_core_command(
                'powershell.exe -Command "search core.main"'
            )
        )
        self.assertFalse(
            watchdog._is_verified_core_command(
                "python.exe -m core.main.fake"
            )
        )

    def test_frozen_core_command_is_exact_and_excludes_watchdog(self):
        executable = r"C:\Program Files\NODARIS\Core\NODARIS Core.exe"
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "executable", executable),
        ):
            self.assertTrue(
                watchdog._is_verified_core_command(
                    f'"{executable}" --core'
                )
            )
            self.assertTrue(
                watchdog._is_verified_core_command(f'"{executable}"')
            )
            self.assertFalse(
                watchdog._is_verified_core_command(
                    f'"{executable}" --watchdog'
                )
            )
            self.assertFalse(
                watchdog._is_verified_core_command(
                    '"C:\\Temp\\NODARIS Core.exe" --core'
                )
            )

    @patch.object(watchdog, "_wait_for_core_stopped", side_effect=[False, True])
    @patch.object(watchdog, "_force_kill_verified_core_listener")
    @patch.object(watchdog, "_force_kill_verified_core_processes", return_value=True)
    @patch.object(
        watchdog,
        "_get_verified_core_processes",
        return_value=[
            {
                "pid": 123,
                "parent_pid": 1,
                "command_line": "pythonw.exe -m core.main",
            }
        ],
    )
    @patch.object(watchdog, "_core_port_is_open", return_value=False)
    @patch.object(
        watchdog,
        "_run_schtasks",
        return_value=subprocess.CompletedProcess([], 0),
    )
    def test_stop_kills_verified_orphan_even_without_listener(
        self,
        _schtasks,
        _port,
        _processes,
        kill_processes,
        kill_listener,
        wait_stopped,
    ):
        self.assertTrue(watchdog.stop_running_core())
        kill_processes.assert_called_once_with()
        kill_listener.assert_not_called()
        self.assertEqual(wait_stopped.call_count, 2)


class WatchdogMainFlowTests(unittest.TestCase):
    @patch.object(watchdog, "replace_degraded_core")
    @patch.object(watchdog, "_core_appears_alive_for_timeout", return_value=True)
    @patch.object(watchdog, "_record_health_timeout_failure", return_value=0.0)
    @patch.object(
        watchdog,
        "check_core_health",
        return_value=(False, "health_request_timeout"),
    )
    def test_live_core_timeout_is_not_restarted_immediately(
        self,
        _health,
        _record,
        _alive,
        replace,
    ):
        watchdog.main()
        replace.assert_not_called()

    @patch.object(watchdog, "replace_degraded_core")
    @patch.object(watchdog.time, "sleep")
    @patch.object(watchdog, "_get_core_task_state", return_value="Running")
    @patch.object(watchdog, "_clear_health_timeout_failure")
    @patch.object(watchdog, "_core_appears_alive_for_timeout", return_value=True)
    @patch.object(watchdog, "_record_health_timeout_failure", return_value=61.0)
    @patch.object(
        watchdog,
        "check_core_health",
        side_effect=[
            (False, "health_request_timeout"),
            (False, "health_request_timeout"),
        ],
    )
    def test_persistent_timeout_can_be_replaced_after_grace(
        self,
        _health,
        _record,
        _alive,
        _clear,
        _task_state,
        _sleep,
        replace,
    ):
        watchdog.main()
        replace.assert_called_once_with("health_request_timeout")

    @patch.object(watchdog, "_clear_health_timeout_failure")
    @patch.object(watchdog, "check_core_health", return_value=(True, "healthy"))
    def test_healthy_core_clears_timeout_sequence(self, _health, clear):
        watchdog.main()
        clear.assert_called_once_with()

    @patch.object(watchdog, "replace_degraded_core")
    @patch.object(watchdog.time, "sleep")
    @patch.object(watchdog, "_get_core_task_state", return_value="Running")
    @patch.object(watchdog, "_clear_health_timeout_failure")
    @patch.object(
        watchdog,
        "check_core_health",
        side_effect=[
            (False, "health_connection_refused"),
            (False, "health_connection_refused"),
        ],
    )
    def test_connection_refused_running_core_is_replaced(
        self,
        _health,
        _clear,
        _task_state,
        _sleep,
        replace,
    ):
        watchdog.main()
        replace.assert_called_once_with("health_connection_refused")


if __name__ == "__main__":
    unittest.main()
