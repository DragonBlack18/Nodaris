from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from api.logging_config import get_logger
from api.paths import DATABASE_FILE, IPS_FILE


CURRENT_CONFIG_VERSION = 1
CURRENT_DATABASE_SCHEMA_VERSION = 1

logger = get_logger(
    "migration",
    "monitorping-core.log",
)


class MigrationError(RuntimeError):
    """Indica que dados persistentes nao podem ser migrados com seguranca."""


def _read_version(value, *, label: str) -> int:
    if value is None:
        return 0

    if isinstance(value, bool) or not isinstance(value, int):
        raise MigrationError(
            f"{label} invalida: {value!r}."
        )

    if value < 0:
        raise MigrationError(
            f"{label} invalida: {value}."
        )

    return value


def _write_json_atomically(
    file_path: Path,
    data: dict,
) -> None:
    file_path = Path(file_path)
    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=file_path.parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            json.dump(
                data,
                temporary,
                ensure_ascii=False,
                indent=2,
            )
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(
                temporary.name
            )

        os.replace(
            temporary_path,
            file_path,
        )
        temporary_path = None
    finally:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            try:
                temporary_path.unlink()
            except OSError:
                pass


def migrate_config(
    config_file: Path = IPS_FILE,
) -> bool:
    """Atualiza ips.json sem descartar campos ou equipamentos existentes."""

    config_file = Path(config_file)

    try:
        with config_file.open(
            "r",
            encoding="utf-8-sig",
        ) as file:
            config = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationError(
            f"Nao foi possivel ler a configuracao: {config_file}"
        ) from exc

    if not isinstance(config, dict):
        raise MigrationError(
            "A raiz da configuracao precisa ser um objeto JSON."
        )

    version = _read_version(
        config.get("config_version"),
        label="Versao da configuracao",
    )

    if version > CURRENT_CONFIG_VERSION:
        raise MigrationError(
            "A configuracao foi criada por uma versao mais nova "
            f"do NODARIS ({version} > {CURRENT_CONFIG_VERSION})."
        )

    changed = False

    if version < 1:
        config["config_version"] = 1
        version = 1
        changed = True

    if version != CURRENT_CONFIG_VERSION:
        raise MigrationError(
            f"Nao existe migracao de configuracao para a versao {version}."
        )

    if changed:
        _write_json_atomically(
            config_file,
            config,
        )
        logger.info(
            "Configuracao migrada para a versao %s.",
            CURRENT_CONFIG_VERSION,
        )

    return changed


def _create_schema_version_1(
    connection: sqlite3.Connection,
) -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            ip TEXT,
            name TEXT,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_events_ip
        ON events(ip)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_events_type
        ON events(event_type)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_events_timestamp
        ON events(timestamp)
        """,
        """
        CREATE TABLE IF NOT EXISTS incidents (
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
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_incidents_ip
        ON incidents(ip)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_incidents_status
        ON incidents(status)
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_incidents_one_open_per_ip
        ON incidents(ip)
        WHERE status = 'OPEN'
        """,
        """
        CREATE TABLE IF NOT EXISTS device_state (
            ip TEXT PRIMARY KEY,
            name TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            last_status TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS probe_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            name TEXT,
            probe_status TEXT NOT NULL,
            effective_status TEXT NOT NULL,
            latency_ms REAL,
            quality TEXT,
            consecutive_failures INTEGER DEFAULT 0,
            consecutive_successes INTEGER DEFAULT 0,
            observed_at TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_probe_history_ip
        ON probe_history(ip)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_probe_history_time
        ON probe_history(observed_at)
        """,
    )

    for statement in statements:
        connection.execute(statement)


def migrate_database(
    database_file: Path = DATABASE_FILE,
) -> bool:
    """Migra o SQLite de forma transacional e preserva todas as linhas."""

    database_file = Path(database_file)
    database_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with closing(
        sqlite3.connect(
            database_file,
            timeout=10,
        )
    ) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "PRAGMA user_version"
            ).fetchone()
            version = _read_version(
                row[0] if row else 0,
                label="Versao do banco",
            )

            if version > CURRENT_DATABASE_SCHEMA_VERSION:
                raise MigrationError(
                    "O banco foi criado por uma versao mais nova "
                    "do NODARIS "
                    f"({version} > {CURRENT_DATABASE_SCHEMA_VERSION})."
                )

            changed = False

            if version < 1:
                _create_schema_version_1(
                    connection
                )
                connection.execute(
                    "PRAGMA user_version = 1"
                )
                version = 1
                changed = True

            if version != CURRENT_DATABASE_SCHEMA_VERSION:
                raise MigrationError(
                    f"Nao existe migracao de banco para a versao {version}."
                )

            connection.commit()
        except Exception:
            connection.rollback()
            raise

    if changed:
        logger.info(
            "Banco migrado para o schema %s.",
            CURRENT_DATABASE_SCHEMA_VERSION,
        )

    return changed


def run_startup_migrations(
    *,
    config_file: Path = IPS_FILE,
    database_file: Path = DATABASE_FILE,
) -> tuple[bool, bool]:
    config_changed = migrate_config(
        config_file
    )
    database_changed = migrate_database(
        database_file
    )
    return config_changed, database_changed
