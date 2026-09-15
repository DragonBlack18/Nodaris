import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from api.migrations import (
    CURRENT_CONFIG_VERSION,
    CURRENT_DATABASE_SCHEMA_VERSION,
    MigrationError,
    migrate_config,
    migrate_database,
    run_startup_migrations,
)


class MigrationTests(unittest.TestCase):

    def test_legacy_config_is_versioned_without_losing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "ips.json"
            original = {
                "intervalo": 17,
                "custom": {"preserve": True},
                "equipamentos": {
                    "192.0.2.10": {
                        "nome": "Roteador",
                        "manutencao": True,
                    }
                },
            }
            config_file.write_text(
                json.dumps(original),
                encoding="utf-8",
            )

            self.assertTrue(
                migrate_config(config_file)
            )

            migrated = json.loads(
                config_file.read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                migrated["config_version"],
                CURRENT_CONFIG_VERSION,
            )
            for key, value in original.items():
                self.assertEqual(
                    migrated[key],
                    value,
                )

            first_bytes = config_file.read_bytes()
            self.assertFalse(
                migrate_config(config_file)
            )
            self.assertEqual(
                config_file.read_bytes(),
                first_bytes,
            )

    def test_future_config_is_rejected_without_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "ips.json"
            config_file.write_text(
                json.dumps(
                    {
                        "config_version": 999,
                        "equipamentos": {},
                    }
                ),
                encoding="utf-8",
            )
            original_bytes = config_file.read_bytes()

            with self.assertRaises(MigrationError):
                migrate_config(config_file)

            self.assertEqual(
                config_file.read_bytes(),
                original_bytes,
            )

    def test_legacy_database_data_survives_idempotent_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            database_file = Path(directory) / "monitor_api.db"

            with closing(sqlite3.connect(database_file)) as connection:
                connection.execute(
                    """
                    CREATE TABLE events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        ip TEXT,
                        name TEXT,
                        message TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO events (
                        event_type, ip, name, message, timestamp
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "OFFLINE",
                        "192.0.2.10",
                        "Roteador",
                        "evento preservado",
                        "2026-01-01T00:00:00",
                    ),
                )
                connection.commit()

            self.assertTrue(
                migrate_database(database_file)
            )
            self.assertFalse(
                migrate_database(database_file)
            )

            with closing(sqlite3.connect(database_file)) as connection:
                version = connection.execute(
                    "PRAGMA user_version"
                ).fetchone()[0]
                event = connection.execute(
                    "SELECT ip, message FROM events"
                ).fetchone()
                tables = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type = 'table'
                        """
                    )
                }

            self.assertEqual(
                version,
                CURRENT_DATABASE_SCHEMA_VERSION,
            )
            self.assertEqual(
                event,
                ("192.0.2.10", "evento preservado"),
            )
            self.assertTrue(
                {
                    "events",
                    "incidents",
                    "device_state",
                    "probe_history",
                }.issubset(tables)
            )

    def test_future_database_is_rejected_without_downgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            database_file = Path(directory) / "monitor_api.db"
            with closing(sqlite3.connect(database_file)) as connection:
                connection.execute(
                    "PRAGMA user_version = 999"
                )
                connection.commit()

            with self.assertRaises(MigrationError):
                migrate_database(database_file)

            with closing(sqlite3.connect(database_file)) as connection:
                version = connection.execute(
                    "PRAGMA user_version"
                ).fetchone()[0]

            self.assertEqual(version, 999)

    def test_database_migration_rolls_back_all_partial_ddl(self):
        with tempfile.TemporaryDirectory() as directory:
            database_file = Path(directory) / "monitor_api.db"
            with closing(sqlite3.connect(database_file)) as connection:
                connection.execute(
                    """
                    CREATE TABLE incidents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip TEXT NOT NULL,
                        name TEXT,
                        status TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        ended_at TEXT,
                        duration_seconds REAL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                for name in ("primeiro", "duplicado"):
                    connection.execute(
                        """
                        INSERT INTO incidents (
                            ip, name, status, started_at
                        ) VALUES (?, ?, 'OPEN', ?)
                        """,
                        (
                            "192.0.2.20",
                            name,
                            "2026-01-01T00:00:00",
                        ),
                    )
                connection.commit()

            with self.assertRaises(sqlite3.IntegrityError):
                migrate_database(database_file)

            with closing(sqlite3.connect(database_file)) as connection:
                version = connection.execute(
                    "PRAGMA user_version"
                ).fetchone()[0]
                events_table = connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name = 'events'
                    """
                ).fetchone()
                incident_count = connection.execute(
                    "SELECT COUNT(*) FROM incidents"
                ).fetchone()[0]

            self.assertEqual(version, 0)
            self.assertIsNone(events_table)
            self.assertEqual(incident_count, 2)

    def test_startup_migrates_config_and_database_together(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_file = root / "config" / "ips.json"
            database_file = root / "data" / "monitor_api.db"
            config_file.parent.mkdir(parents=True)
            config_file.write_text(
                '{"intervalo": 5, "equipamentos": {}}',
                encoding="utf-8",
            )

            self.assertEqual(
                run_startup_migrations(
                    config_file=config_file,
                    database_file=database_file,
                ),
                (True, True),
            )
            self.assertEqual(
                run_startup_migrations(
                    config_file=config_file,
                    database_file=database_file,
                ),
                (False, False),
            )


if __name__ == "__main__":
    unittest.main()
