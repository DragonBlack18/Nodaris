import json
import tempfile
import unittest
from pathlib import Path

from api import paths


class PersistentPathTests(unittest.TestCase):
    def test_source_and_frozen_share_program_data_on_windows(self):
        program_data = Path(tempfile.gettempdir()) / "ProgramData"
        environment = {"PROGRAMDATA": str(program_data)}

        source_result = paths.resolve_persistent_root(
            frozen=False,
            environment=environment,
            source_root=Path(tempfile.gettempdir()) / "source",
        )
        frozen_result = paths.resolve_persistent_root(
            frozen=True,
            environment=environment,
        )

        expected = (program_data / "NODARIS").resolve()
        self.assertEqual(source_result, expected)
        self.assertEqual(frozen_result, expected)

    def test_source_without_windows_paths_uses_isolated_runtime_directory(self):
        source = Path(tempfile.gettempdir()) / "nodaris-source"
        result = paths.resolve_persistent_root(
            frozen=False,
            environment={},
            source_root=source,
        )
        self.assertEqual(
            result,
            (source / ".nodaris-runtime").resolve(),
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
        self.assertEqual(result, custom.resolve())

    def test_layout_seeds_config_and_never_overwrites_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundled = root / "bundled-ips.json"
            bundled.write_text(
                '{"config_version": 1, "intervalo": 7, "equipamentos": {}}',
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
                '{"config_version": 1, "intervalo": 99, "equipamentos": {}}',
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

    def test_legacy_source_catalog_is_migrated_only_when_destination_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = root / "legacy" / "ips.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                json.dumps(
                    {
                        "config_version": 1,
                        "intervalo": 11,
                        "equipamentos": {
                            "192.0.2.10": {
                                "nome": "Legacy",
                                "gateway": "",
                                "manutencao": False,
                            }
                        },
                    }
                ),
                encoding="utf-8-sig",
            )
            default = root / "default.json"
            default.write_text(
                '{"config_version": 1, "intervalo": 5, "equipamentos": {}}',
                encoding="utf-8",
            )

            config_dir = root / "persistent" / "config"
            data_dir = root / "persistent" / "data"
            log_dir = root / "persistent" / "logs"
            target = config_dir / "ips.json"

            paths.ensure_persistent_layout(
                config_dir=config_dir,
                data_dir=data_dir,
                log_dir=log_dir,
                ips_file=target,
                default_ips_file=default,
                legacy_ips_file=legacy,
            )

            migrated = json.loads(target.read_text(encoding="utf-8-sig"))
            self.assertEqual(migrated["intervalo"], 11)
            self.assertIn("192.0.2.10", migrated["equipamentos"])

            target.write_text(
                '{"config_version": 1, "intervalo": 33, "equipamentos": {}}',
                encoding="utf-8",
            )
            paths.ensure_persistent_layout(
                config_dir=config_dir,
                data_dir=data_dir,
                log_dir=log_dir,
                ips_file=target,
                default_ips_file=default,
                legacy_ips_file=legacy,
            )
            kept = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(kept["intervalo"], 33)


if __name__ == "__main__":
    unittest.main()
