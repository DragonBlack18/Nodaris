import json
import tempfile
import unittest
from pathlib import Path

from api import paths


class PersistentPathTests(unittest.TestCase):

    def test_source_mode_keeps_project_root(self):
        source = Path(tempfile.gettempdir()) / "nodaris-source"

        result = paths.resolve_persistent_root(
            frozen=False,
            environment={},
            source_root=source,
        )

        self.assertEqual(
            result,
            source.resolve(),
        )

    def test_frozen_mode_uses_program_data(self):
        program_data = Path(tempfile.gettempdir()) / "ProgramData"

        result = paths.resolve_persistent_root(
            frozen=True,
            environment={
                "PROGRAMDATA": str(program_data),
            },
        )

        self.assertEqual(
            result,
            (program_data / "NODARIS").resolve(),
        )

    def test_explicit_data_root_has_priority(self):
        custom = Path(tempfile.gettempdir()) / "NodarisCustom"

        result = paths.resolve_persistent_root(
            frozen=True,
            environment={
                "PROGRAMDATA": "ignored",
                "NODARIS_DATA_ROOT": str(custom),
            },
        )

        self.assertEqual(
            result,
            custom.resolve(),
        )

    def test_layout_seeds_config_and_never_overwrites_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundled = root / "bundled-ips.json"
            bundled.write_text(
                '{"intervalo": 7, "equipamentos": {}}',
                encoding="utf-8",
            )

            config_dir = root / "persistent" / "config"
            data_dir = root / "persistent" / "data"
            log_dir = root / "persistent" / "logs"
            ips_file = config_dir / "ips.json"

            paths.ensure_persistent_layout(
                config_dir=config_dir,
                data_dir=data_dir,
                log_dir=log_dir,
                ips_file=ips_file,
                default_ips_file=bundled,
            )

            self.assertEqual(
                json.loads(ips_file.read_text(encoding="utf-8"))["intervalo"],
                7,
            )
            self.assertTrue(data_dir.is_dir())
            self.assertTrue(log_dir.is_dir())

            ips_file.write_text(
                '{"intervalo": 99, "equipamentos": {}}',
                encoding="utf-8",
            )

            paths.ensure_persistent_layout(
                config_dir=config_dir,
                data_dir=data_dir,
                log_dir=log_dir,
                ips_file=ips_file,
                default_ips_file=bundled,
            )

            self.assertEqual(
                json.loads(ips_file.read_text(encoding="utf-8"))["intervalo"],
                99,
            )


if __name__ == "__main__":
    unittest.main()
