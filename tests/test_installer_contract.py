import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class InstallerContractTests(unittest.TestCase):

    def test_default_config_contains_no_development_devices(self):
        config = json.loads(
            (
                PROJECT_ROOT
                / "defaults"
                / "ips.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(config["config_version"], 1)
        self.assertEqual(config["equipamentos"], {})

    def test_installer_preserves_program_data(self):
        text = (PROJECT_ROOT / "NODARIS.iss").read_text(
            encoding="utf-8"
        )

        self.assertIn("{commonappdata}\\NODARIS\\config", text)
        self.assertIn("{commonappdata}\\NODARIS\\data", text)
        self.assertIn("{commonappdata}\\NODARIS\\logs", text)
        self.assertIn("onlyifdoesntexist", text)
        self.assertIn(
            'Source: "defaults\\ips.json"',
            text,
        )
        self.assertNotIn(
            'Source: "ips.json"',
            text,
        )
        self.assertNotIn(
            'Type: filesandordirs; Name: "{commonappdata}',
            text,
        )

    def test_installer_uses_three_independent_builds(self):
        text = (PROJECT_ROOT / "NODARIS.iss").read_text(
            encoding="utf-8"
        )

        for application in (
            "NODARIS Core",
            "NODARIS Admin",
            "NODARIS TV",
        ):
            self.assertIn(
                f'Source: "dist\\{application}\\*"',
                text,
            )

    def test_task_scripts_use_frozen_core_modes(self):
        install_script = (
            PROJECT_ROOT
            / "installer"
            / "install_tasks.ps1"
        ).read_text(encoding="utf-8")
        uninstall_script = (
            PROJECT_ROOT
            / "installer"
            / "uninstall_tasks.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn('"NODARIS Core.exe"', install_script)
        self.assertIn('-Argument "--core"', install_script)
        self.assertIn('-Argument "--watchdog"', install_script)
        self.assertIn('"NODARIS Core"', uninstall_script)
        self.assertIn('"NODARIS Watchdog"', uninstall_script)


if __name__ == "__main__":
    unittest.main()
