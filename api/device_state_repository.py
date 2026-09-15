import sqlite3
from pathlib import Path

from api.config import DATABASE_FILE


class DeviceStateRepository:

    def __init__(
        self,
        database_file: Path = DATABASE_FILE,
    ):
        self.database_file = database_file
        self._initialize()

    def _connect(self):

        connection = sqlite3.connect(
            self.database_file,
            timeout=10,
        )

        connection.row_factory = sqlite3.Row

        return connection

    def _initialize(self):

        with self._connect() as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS device_state (
                    ip TEXT PRIMARY KEY,

                    name TEXT,

                    first_seen_at TEXT NOT NULL,

                    last_seen_at TEXT NOT NULL,

                    last_status TEXT NOT NULL
                )
                """
            )

            connection.commit()

    def update_status(
        self,
        ip: str,
        name: str,
        status: str,
        timestamp: str,
    ):

        with self._connect() as connection:

            connection.execute(
                """
                INSERT INTO device_state (
                    ip,
                    name,
                    first_seen_at,
                    last_seen_at,
                    last_status
                )

                VALUES (?, ?, ?, ?, ?)

                ON CONFLICT(ip)
                DO UPDATE SET

                    name = excluded.name,

                    last_seen_at =
                        excluded.last_seen_at,

                    last_status =
                        excluded.last_status
                """,
                (
                    ip,
                    name,
                    timestamp,
                    timestamp,
                    status,
                ),
            )

            connection.commit()

    def get_devices(self):

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    ip,
                    name,
                    first_seen_at,
                    last_seen_at,
                    last_status

                FROM device_state

                ORDER BY name
                """
            ).fetchall()

        return [
            {
                "ip": row["ip"],
                "name": row["name"],
                "first_seen_at": (
                    row["first_seen_at"]
                ),
                "last_seen_at": (
                    row["last_seen_at"]
                ),
                "last_status": (
                    row["last_status"]
                ),
            }
            for row in rows
        ]