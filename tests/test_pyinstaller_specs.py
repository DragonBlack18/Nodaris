import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PyInstallerSpecTests(unittest.TestCase):

    def _spec_text(self, filename: str) -> str:
        return (PROJECT_ROOT / filename).read_text(encoding="utf-8")

    def test_core_spec_has_independent_entrypoint_and_config_seed(self):
        text = self._spec_text("NODARIS-Core.spec")

        self.assertIn('"core" / "main.py"', text)
        self.assertIn('hiddenimports=["api.main"]', text)
        self.assertIn('project_root / "ips.json"', text)
        self.assertIn('name="NODARIS Core"', text)
        self.assertIn("console=False", text)

    def test_admin_spec_has_independent_entrypoint_and_branding(self):
        text = self._spec_text("NODARIS-Admin.spec")

        self.assertIn('"desktop" / "main.py"', text)
        self.assertIn('"assets/branding"', text)
        self.assertIn('name="NODARIS Admin"', text)
        self.assertIn("console=False", text)

    def test_tv_spec_has_independent_entrypoint_and_branding(self):
        text = self._spec_text("NODARIS-TV.spec")

        self.assertIn('"desktop" / "tv_main.py"', text)
        self.assertIn('"assets/branding"', text)
        self.assertIn('name="NODARIS TV"', text)
        self.assertIn("console=False", text)

    def test_legacy_monolithic_entrypoint_is_not_used(self):
        for filename in (
            "NODARIS-Core.spec",
            "NODARIS-Admin.spec",
            "NODARIS-TV.spec",
        ):
            with self.subTest(filename=filename):
                self.assertNotIn(
                    '["monitorping.py"]',
                    self._spec_text(filename),
                )


if __name__ == "__main__":
    unittest.main()
