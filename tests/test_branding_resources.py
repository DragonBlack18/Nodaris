import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.paths import resource_root
from desktop.branding import branding_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class BrandingResourceTests(unittest.TestCase):

    def test_all_official_branding_assets_exist_and_are_not_empty(self):
        branding_dir = PROJECT_ROOT / "assets" / "branding"
        expected = {
            "nodaris_icon.ico",
            "nodaris_icon.png",
            "nodaris_icon_256.png",
            "nodaris_logo_reference.jpg",
        }

        found = {
            path.name
            for path in branding_dir.iterdir()
            if path.is_file()
        }

        self.assertEqual(found, expected)
        for filename in expected:
            self.assertGreater((branding_dir / filename).stat().st_size, 0)

    def test_branding_uses_pyinstaller_resource_root(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle_root = Path(directory)

            with patch.object(
                sys,
                "_MEIPASS",
                str(bundle_root),
                create=True,
            ):
                self.assertTrue(
                    resource_root().samefile(bundle_root)
                )

                resolved_icon = branding_path(
                    "nodaris_icon.ico"
                )
                expected_icon = (
                    bundle_root
                    / "assets"
                    / "branding"
                    / "nodaris_icon.ico"
                )

                self.assertEqual(
                    resolved_icon.resolve(),
                    expected_icon.resolve(),
                )


if __name__ == "__main__":
    unittest.main()
