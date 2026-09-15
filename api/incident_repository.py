import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from api.config import DATABASE_FILE


class IncidentRepository:

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
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    ip TEXT NOT NULL,
                    name TEXT,

                    status TEXT NOT NULL,

                    started_at TEXT NOT NULL,
                    ended_at TEXT,

                    duration_seconds REAL,

                    created_at TEXT
                        DEFAULT CURRENT_TIMESTAMP,

                    updated_at TEXT
                        DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_incidents_ip
                ON incidents(ip)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_incidents_status
                ON incidents(status)
                """
            )

            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_incidents_one_open_per_ip
                ON incidents(ip)
                WHERE status = 'OPEN'
                """
            )

            connection.commit()

    # =====================================================
    # OPEN
    # =====================================================

    def open_incident(
        self,
        ip: str,
        name: str,
        started_at: str,
    ) -> int | None:

        with closing(self._connect()) as connection:

            existing = connection.execute(
                """
                SELECT id
                FROM incidents
                WHERE ip = ?
                AND status = 'OPEN'
                LIMIT 1
                """,
                (ip,),
            ).fetchone()

            if existing:
                return int(existing[0])

            cursor = connection.execute(
                """
                INSERT INTO incidents (
                    ip,
                    name,
                    status,
                    started_at
                )
                VALUES (?, ?, 'OPEN', ?)
                """,
                (
                    ip,
                    name,
                    started_at,
                ),
            )

            connection.commit()

            return cursor.lastrowid

    # =====================================================
    # CLOSE
    # =====================================================

    def close_incident(
        self,
        ip: str,
        ended_at: str,
    ) -> dict | None:

        with closing(self._connect()) as connection:

            connection.row_factory = sqlite3.Row

            incident = connection.execute(
                """
                SELECT
                    id,
                    ip,
                    name,
                    started_at
                FROM incidents
                WHERE ip = ?
                AND status = 'OPEN'
                ORDER BY id DESC
                LIMIT 1
                """,
                (ip,),
            ).fetchone()

            if incident is None:
                return None

            started = datetime.fromisoformat(
                incident["started_at"]
            )

            ended = datetime.fromisoformat(
                ended_at
            )

            duration = max(
                0,
                (ended - started).total_seconds(),
            )

            connection.execute(
                """
                UPDATE incidents

                SET
                    status = 'CLOSED',
                    ended_at = ?,
                    duration_seconds = ?,
                    updated_at = CURRENT_TIMESTAMP

                WHERE id = ?
                """,
                (
                    ended_at,
                    duration,
                    incident["id"],
                ),
            )

            connection.commit()

            return {
                "id": incident["id"],
                "ip": incident["ip"],
                "name": incident["name"],
                "started_at": incident["started_at"],
                "ended_at": ended_at,
                "duration_seconds": duration,
                "status": "CLOSED",
            }

    # =====================================================
    # READ
    # =====================================================

    def has_open_incident(
        self,
        ip: str,
    ) -> bool:

        with closing(self._connect()) as connection:

            result = connection.execute(
                """
                SELECT 1

                FROM incidents

                WHERE ip = ?
                AND status = 'OPEN'

                LIMIT 1
                """,
                (ip,),
            ).fetchone()

        return result is not None

    def get_incidents_between(
        self,
        ip: str,
        start_at: str,
        end_at: str,
    ) -> list[dict]:

        with closing(self._connect()) as connection:

            connection.row_factory = sqlite3.Row

            rows = connection.execute(
                """
                SELECT
                    id,
                    ip,
                    name,
                    status,
                    started_at,
                    ended_at,
                    duration_seconds

                FROM incidents

                WHERE ip = ?

                AND started_at <= ?

                AND (
                    ended_at IS NULL
                    OR ended_at >= ?
                )

                ORDER BY started_at
                """,
                (
                    ip,
                    end_at,
                    start_at,
                ),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "ip": row["ip"],
                "name": row["name"],
                "status": row["status"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "duration_seconds": (
                    row["duration_seconds"]
                ),
            }
            for row in rows
        ]

    def get_incidents(
        self,
        limit: int = 100,
        status: str | None = None,
    ) -> list[dict]:

        limit = max(
            1,
            min(limit, 1000),
        )

        params = []

        query = """
            SELECT
                id,
                ip,
                name,
                status,
                started_at,
                ended_at,
                duration_seconds
            FROM incidents
        """

        if status:

            status = status.upper()

            if status not in {
                "OPEN",
                "CLOSED",
            }:
                raise ValueError(
                    "Status precisa ser OPEN ou CLOSED."
                )

            query += """
                WHERE status = ?
            """

            params.append(status)

        query += """
            ORDER BY id DESC
            LIMIT ?
        """

        params.append(limit)

        with closing(self._connect()) as connection:

            connection.row_factory = sqlite3.Row

            rows = connection.execute(
                query,
                params,
            ).fetchall()

        return [
            {
                "id": row["id"],
                "ip": row["ip"],
                "name": row["name"],
                "status": row["status"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "duration_seconds": row[
                    "duration_seconds"
                ],
            }
            for row in rows
        ]

    def get_summary(self) -> dict:

        with closing(self._connect()) as connection:

            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total,

                    SUM(
                        CASE
                            WHEN status = 'OPEN'
                            THEN 1
                            ELSE 0
                        END
                    ) AS open_count,

                    SUM(
                        CASE
                            WHEN status = 'CLOSED'
                            THEN 1
                            ELSE 0
                        END
                    ) AS closed_count

                FROM incidents
                """
            ).fetchone()

        return {
            "total": int(row[0] or 0),
            "open": int(row[1] or 0),
            "closed": int(row[2] or 0),
        }
