import sqlite3
from contextlib import closing
from pathlib import Path

from api.config import DATABASE_FILE


class EventRepository:

    def __init__(
        self,
        database_file: Path = DATABASE_FILE,
    ):
        self.database_file = database_file

        self.database_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize()

    # =====================================================
    # DATABASE
    # =====================================================

    def _connect(self):
        return sqlite3.connect(
            self.database_file,
            timeout=10,
        )

    def _initialize(self):

        with closing(self._connect()) as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    event_type TEXT NOT NULL,

                    ip TEXT,
                    name TEXT,

                    message TEXT NOT NULL,

                    timestamp TEXT NOT NULL,

                    created_at TEXT
                        DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_events_ip
                ON events(ip)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_events_type
                ON events(event_type)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_events_timestamp
                ON events(timestamp)
                """
            )

            connection.commit()

    # =====================================================
    # WRITE
    # =====================================================

    def save_event(
        self,
        event: dict,
    ) -> int:

        with closing(self._connect()) as connection:

            cursor = connection.execute(
                """
                INSERT INTO events (
                    event_type,
                    ip,
                    name,
                    message,
                    timestamp
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event["type"],
                    event.get("ip"),
                    event.get("name"),
                    event["message"],
                    event["timestamp"],
                ),
            )

            connection.commit()

            return cursor.lastrowid

    # =====================================================
    # READ
    # =====================================================

    def get_events(
        self,
        limit: int = 100,
    ) -> list[dict]:

        limit = max(
            1,
            min(limit, 1000),
        )

        with closing(self._connect()) as connection:

            connection.row_factory = sqlite3.Row

            rows = connection.execute(
                """
                SELECT
                    id,
                    event_type,
                    ip,
                    name,
                    message,
                    timestamp
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "type": row["event_type"],
                "ip": row["ip"],
                "name": row["name"],
                "message": row["message"],
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def count_events(self) -> int:

        with closing(self._connect()) as connection:

            result = connection.execute(
                """
                SELECT COUNT(*)
                FROM events
                """
            ).fetchone()

        return int(result[0])
