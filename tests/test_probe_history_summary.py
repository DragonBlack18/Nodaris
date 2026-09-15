import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from api.probe_history_repository import ProbeHistoryRepository


class ProbeHistorySummaryTests(unittest.TestCase):

    def _insert_legacy_sample(
        self,
        database_file: Path,
        *,
        probe_status: str,
        effective_status: str,
        latency_ms,
        observed_at: str,
    ):
        with closing(sqlite3.connect(database_file)) as connection:
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
                    "192.0.2.1",
                    "Device",
                    probe_status,
                    effective_status,
                    latency_ms,
                    None,
                    0,
                    0,
                    observed_at,
                ),
            )
            connection.commit()

    def test_legacy_offline_zero_does_not_contaminate_latency_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            database_file = Path(directory) / "history.db"
            repository = ProbeHistoryRepository(database_file)
            now = datetime.now()

            self._insert_legacy_sample(
                database_file,
                probe_status="ONLINE",
                effective_status="ONLINE",
                latency_ms=10,
                observed_at=(now - timedelta(seconds=2)).isoformat(
                    timespec="seconds"
                ),
            )
            self._insert_legacy_sample(
                database_file,
                probe_status="OFFLINE",
                effective_status="OFFLINE",
                latency_ms=0,
                observed_at=(now - timedelta(seconds=1)).isoformat(
                    timespec="seconds"
                ),
            )

            result = repository.get_history_window(
                "192.0.2.1",
                minutes=1,
            )

        summary = result["summary"]
        self.assertEqual(summary["average_latency_ms"], 10.0)
        self.assertEqual(summary["minimum_latency_ms"], 10.0)
        self.assertEqual(summary["maximum_latency_ms"], 10.0)
        self.assertEqual(summary["offline_samples"], 1)
        self.assertEqual(summary["loss_percent"], 50.0)

    def test_online_zero_remains_a_valid_historical_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            database_file = Path(directory) / "history.db"
            repository = ProbeHistoryRepository(database_file)
            now = datetime.now()

            for offset, latency in enumerate((0, 10), start=1):
                self._insert_legacy_sample(
                    database_file,
                    probe_status="ONLINE",
                    effective_status="ONLINE",
                    latency_ms=latency,
                    observed_at=(
                        now - timedelta(seconds=offset)
                    ).isoformat(timespec="seconds"),
                )

            result = repository.get_history_window(
                "192.0.2.1",
                minutes=1,
            )

        summary = result["summary"]
        self.assertEqual(summary["average_latency_ms"], 5.0)
        self.assertEqual(summary["minimum_latency_ms"], 0.0)
        self.assertEqual(summary["maximum_latency_ms"], 10.0)


if __name__ == "__main__":
    unittest.main()
