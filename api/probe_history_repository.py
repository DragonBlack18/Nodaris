import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from api.config import (
    DATABASE_FILE,
    PROBE_HISTORY_RETENTION_DAYS,
)


class ProbeHistoryRepository:

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

    # =====================================================
    # DATABASE
    # =====================================================

    def _initialize(self):

        with closing(self._connect()) as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS probe_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    ip TEXT NOT NULL,
                    name TEXT,

                    probe_status TEXT NOT NULL,
                    effective_status TEXT NOT NULL,

                    latency_ms REAL,

                    quality TEXT,

                    consecutive_failures INTEGER
                        DEFAULT 0,

                    consecutive_successes INTEGER
                        DEFAULT 0,

                    observed_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_probe_history_ip
                ON probe_history(ip)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_probe_history_time
                ON probe_history(observed_at)
                """
            )

            connection.commit()

    # =====================================================
    # WRITE
    # =====================================================

    def save_probe(
        self,
        *,
        ip: str,
        name: str,
        probe_status: str,
        effective_status: str,
        latency_ms: float | None,
        quality: str | None,
        consecutive_failures: int,
        consecutive_successes: int,
        observed_at: str,
    ):

        with closing(self._connect()) as connection:

            connection.execute(
                """
                INSERT INTO probe_history (
                    ip,
                    name,
                    probe_status,
                    effective_status,
                    latency_ms,
                    quality,
                    consecutive_failures,
                    consecutive_successes,
                    observed_at
                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ip,
                    name,
                    probe_status,
                    effective_status,
                    latency_ms,
                    quality,
                    consecutive_failures,
                    consecutive_successes,
                    observed_at,
                ),
            )

            connection.commit()

    # =====================================================
    # READ
    # =====================================================

    def get_history(
        self,
        ip: str,
        limit: int = 100,
    ) -> list[dict]:

        limit = max(
            1,
            min(limit, 5000),
        )

        with closing(self._connect()) as connection:

            rows = connection.execute(
                """
                SELECT
                    id,
                    ip,
                    name,
                    probe_status,
                    effective_status,
                    latency_ms,
                    quality,
                    consecutive_failures,
                    consecutive_successes,
                    observed_at

                FROM probe_history

                WHERE ip = ?

                ORDER BY id DESC

                LIMIT ?
                """,
                (
                    ip,
                    limit,
                ),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "ip": row["ip"],
                "name": row["name"],
                "probe_status": (
                    row["probe_status"]
                ),
                "status": (
                    row["effective_status"]
                ),
                "latency_ms": (
                    row["latency_ms"]
                ),
                "quality": row["quality"],
                "consecutive_failures": (
                    row["consecutive_failures"]
                ),
                "consecutive_successes": (
                    row["consecutive_successes"]
                ),
                "observed_at": (
                    row["observed_at"]
                ),
            }
            for row in rows
        ]

    def get_history_window(
        self,
        ip: str,
        minutes: int = 60,
        max_points: int = 1500,
    ):
        """
        Retorna histórico de um IP dentro de uma
        janela de tempo.

        A consulta trabalha somente com dados já
        gravados no SQLite.
        """

        minutes = max(
            1,
            min(
                int(minutes),
                10080,  # máximo 7 dias
            ),
        )

        max_points = max(
            100,
            min(
                int(max_points),
                5000,
            ),
        )

        start_at = (
            datetime.now()
            - timedelta(
                minutes=minutes
            )
        )

        start_text = start_at.isoformat(
            timespec="seconds"
        )

        with closing(self._connect()) as connection:

            rows = connection.execute(
                """
                SELECT
                    id,
                    ip,
                    name,
                    probe_status,
                    effective_status,
                    latency_ms,
                    quality,
                    consecutive_failures,
                    consecutive_successes,
                    observed_at
                FROM probe_history
                WHERE ip = ?
                  AND datetime(observed_at) >= datetime(?)
                ORDER BY datetime(observed_at) ASC
                """,
                (
                    ip,
                    start_text,
                ),
            ).fetchall()

        history = []

        for row in rows:

            history.append(
                {
                    "id": row["id"],
                    "ip": row["ip"],
                    "name": row["name"],
                    "probe_status": (
                        row["probe_status"]
                    ),
                    "status": (
                        row[
                            "effective_status"
                        ]
                    ),
                    "latency_ms": (
                        row["latency_ms"]
                    ),
                    "quality": (
                        row["quality"]
                    ),
                    "consecutive_failures": (
                        row[
                            "consecutive_failures"
                        ]
                    ),
                    "consecutive_successes": (
                        row[
                            "consecutive_successes"
                        ]
                    ),
                    "observed_at": (
                        row["observed_at"]
                    ),
                }
            )

        total_count = len(
            history
        )

        # =====================================================
        # RESUMO REAL DO PERÍODO
        # =====================================================

        latencies = [
            float(
                item["latency_ms"]
            )
            for item in history
            if item["latency_ms"] is not None
            and item["status"] != "ERROR"
        ]

        offline_count = sum(
            1
            for item in history
            if str(
                item["status"]
            ).upper() == "OFFLINE"
        )

        considered_count = sum(
            1
            for item in history
            if str(
                item["status"]
            ).upper() != "ERROR"
        )

        if latencies:

            average_latency = (
                sum(latencies)
                / len(latencies)
            )

            minimum_latency = min(
                latencies
            )

            maximum_latency = max(
                latencies
            )

        else:

            average_latency = None
            minimum_latency = None
            maximum_latency = None

        if considered_count:

            loss_percent = (
                offline_count
                / considered_count
                * 100.0
            )

        else:

            loss_percent = None

        # =====================================================
        # DOWNSAMPLING SOMENTE PARA O GRÁFICO
        # =====================================================

        returned_history = history

        if (
            total_count
            > max_points
        ):

            step = (
                total_count
                / max_points
            )

            sampled = []

            index = 0.0

            while (
                int(index)
                < total_count
            ):

                sampled.append(
                    history[
                        int(index)
                    ]
                )

                index += step

            # Garante o último ponto.
            if (
                sampled
                and
                sampled[-1]["id"]
                != history[-1]["id"]
            ):

                sampled.append(
                    history[-1]
                )

            returned_history = (
                sampled
            )

        return {
            "ip": ip,
            "minutes": minutes,
            "total_samples": (
                total_count
            ),
            "returned_samples": (
                len(
                    returned_history
                )
            ),
            "summary": {
                "average_latency_ms": (
                    average_latency
                ),
                "minimum_latency_ms": (
                    minimum_latency
                ),
                "maximum_latency_ms": (
                    maximum_latency
                ),
                "loss_percent": (
                    loss_percent
                ),
                "offline_samples": (
                    offline_count
                ),
            },
            "history": (
                returned_history
            ),
        }

    # =====================================================
    # RETENTION
    # =====================================================

    def cleanup_old_records(self) -> int:

        cutoff = (
            datetime.now()
            - timedelta(
                days=PROBE_HISTORY_RETENTION_DAYS
            )
        ).isoformat(
            timespec="seconds"
        )

        with closing(self._connect()) as connection:

            cursor = connection.execute(
                """
                DELETE FROM probe_history
                WHERE observed_at < ?
                """,
                (cutoff,),
            )

            connection.commit()

            return cursor.rowcount
