import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from api.device_state_repository import DeviceStateRepository
from api.event_repository import EventRepository
from api.incident_observation_service import IncidentObservationService
from api.incident_repository import IncidentRepository
from api.probe_availability_service import ProbeAvailabilityService
from api.probe_history_repository import ProbeHistoryRepository


class SQLiteConnectionLifecycleTests(unittest.TestCase):

    def _database_path(self, directory: str) -> Path:
        return Path(directory) / "lifecycle.db"

    def _assert_immediately_releasable(self, database_file: Path):
        renamed_file = database_file.with_name("renamed.db")

        # No gc.collect() is allowed here. On Windows these operations fail
        # immediately when any SQLite connection still owns the file.
        os.replace(database_file, renamed_file)
        renamed_file.unlink()

        self.assertFalse(database_file.exists())
        self.assertFalse(renamed_file.exists())

    def test_device_state_repository_releases_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database_file = self._database_path(directory)
            repository = DeviceStateRepository(database_file)

            repository.update_status(
                ip="127.0.0.1",
                name="Local",
                status="ONLINE",
                timestamp="2026-09-15T12:00:00",
            )
            repository.get_devices()

            self._assert_immediately_releasable(database_file)

    def test_event_repository_releases_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database_file = self._database_path(directory)
            repository = EventRepository(database_file)

            repository.save_event(
                {
                    "type": "TEST",
                    "ip": "127.0.0.1",
                    "name": "Local",
                    "message": "Lifecycle test",
                    "timestamp": "2026-09-15T12:00:00",
                }
            )
            repository.get_events()
            repository.count_events()

            self._assert_immediately_releasable(database_file)

    def test_incident_repository_releases_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database_file = self._database_path(directory)
            repository = IncidentRepository(database_file)

            repository.open_incident(
                ip="127.0.0.1",
                name="Local",
                started_at="2026-09-15T12:00:00",
            )
            repository.has_open_incident("127.0.0.1")
            repository.get_incidents()
            repository.get_summary()

            self._assert_immediately_releasable(database_file)

    def test_probe_history_repository_releases_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database_file = self._database_path(directory)
            repository = ProbeHistoryRepository(database_file)

            repository.save_probe(
                ip="127.0.0.1",
                name="Local",
                probe_status="ONLINE",
                effective_status="ONLINE",
                latency_ms=0.5,
                quality="EXCELLENT",
                consecutive_failures=0,
                consecutive_successes=1,
                observed_at="2026-09-15T12:00:00",
            )
            repository.get_history("127.0.0.1")
            repository.get_history_window("127.0.0.1")

            self._assert_immediately_releasable(database_file)

    def test_probe_availability_service_releases_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database_file = self._database_path(directory)
            ProbeHistoryRepository(database_file)
            service = ProbeAvailabilityService(database_file=database_file)
            end_at = datetime.now()

            service._load_samples(
                ip="127.0.0.1",
                start_at=end_at - timedelta(minutes=1),
                end_at=end_at,
            )
            service._load_previous_sample("127.0.0.1", end_at)

            self._assert_immediately_releasable(database_file)

    def test_incident_observation_service_releases_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database_file = self._database_path(directory)
            ProbeHistoryRepository(database_file)
            service = IncidentObservationService(database_file=database_file)
            end_at = datetime.now()

            service._load_samples(
                ip="127.0.0.1",
                started_at=end_at - timedelta(minutes=1),
                ended_at=end_at,
            )

            self._assert_immediately_releasable(database_file)


if __name__ == "__main__":
    unittest.main()
