import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from api.config import DATABASE_FILE, IPS_FILE
from api.logging_config import get_logger


logger = get_logger("availability", "monitorping-availability.log")


class ProbeAvailabilityService:
    """Calcula disponibilidade somente sobre períodos realmente observados."""

    def __init__(
        self,
        database_file: Path = DATABASE_FILE,
        ips_file: Path = IPS_FILE,
    ):
        self.database_file = Path(database_file)
        self.ips_file = Path(ips_file)

    def get_availability(self, hours: int = 24) -> dict:
        hours = max(1, min(int(hours), 24 * 30))
        end_at = datetime.now()
        start_at = end_at - timedelta(hours=hours)
        config = self._load_config()

        try:
            interval_seconds = max(1.0, float(config.get("intervalo", 5)))
        except (TypeError, ValueError):
            interval_seconds = 5.0

        equipments = config.get("equipamentos", {})
        if not isinstance(equipments, dict):
            equipments = {}

        devices = []
        for ip, config_data in equipments.items():
            if not isinstance(config_data, dict):
                config_data = {}
            devices.append(
                self._calculate_device(
                    ip=str(ip),
                    name=str(config_data.get("nome") or ip),
                    start_at=start_at,
                    end_at=end_at,
                    expected_interval=interval_seconds,
                )
            )

        valid = [
            device["availability_percent"]
            for device in devices
            if device["availability_percent"] is not None
        ]
        average = sum(valid) / len(valid) if valid else None

        return {
            "hours": hours,
            "generated_at": end_at.isoformat(timespec="seconds"),
            "summary": {
                "total_devices": len(devices),
                "devices_with_data": len(valid),
                "average_availability_percent": average,
            },
            "devices": devices,
        }

    def _calculate_device(
        self,
        ip: str,
        name: str,
        start_at: datetime,
        end_at: datetime,
        expected_interval: float,
    ) -> dict:
        samples = self._load_samples(ip, start_at, end_at)
        previous_sample = self._load_previous_sample(ip, start_at)
        window_seconds = max(0.0, (end_at - start_at).total_seconds())
        max_observed_gap = max(
            expected_interval * 2.5,
            expected_interval + 2.0,
        )

        monitored_seconds = 0.0
        uptime_seconds = 0.0
        downtime_seconds = 0.0
        incident_count = 0
        previous_status = (
            self._effective_status(previous_sample)
            if previous_sample
            else None
        )

        for index, sample in enumerate(samples):
            observed_at = self._parse_datetime(sample.get("observed_at"))
            if observed_at is None:
                continue

            if index + 1 < len(samples):
                next_at = self._parse_datetime(
                    samples[index + 1].get("observed_at")
                )
            else:
                next_at = end_at
            if next_at is None:
                continue

            duration = min(
                max(0.0, (next_at - observed_at).total_seconds()),
                max_observed_gap,
            )
            status = self._effective_status(sample)
            probe_status = str(sample.get("probe_status", "")).upper()

            if status == "ERROR" or probe_status == "ERROR":
                previous_status = status
                continue

            monitored_seconds += duration
            if status == "OFFLINE":
                downtime_seconds += duration
            else:
                uptime_seconds += duration

            if status == "OFFLINE" and previous_status != "OFFLINE":
                incident_count += 1
            previous_status = status

        availability_percent = (
            uptime_seconds / monitored_seconds * 100.0
            if monitored_seconds > 0
            else None
        )
        unmonitored_seconds = max(0.0, window_seconds - monitored_seconds)
        coverage_percent = (
            monitored_seconds / window_seconds * 100.0
            if window_seconds > 0
            else 0.0
        )

        first_observed_at = None
        last_observed_at = None
        current_status = "UNKNOWN"
        if samples:
            first_observed_at = samples[0].get("observed_at")
            last_observed_at = samples[-1].get("observed_at")
            current_status = self._effective_status(samples[-1])

        return {
            "ip": ip,
            "name": name,
            "availability_percent": availability_percent,
            "coverage_percent": coverage_percent,
            "monitored_seconds": monitored_seconds,
            "uptime_seconds": uptime_seconds,
            "downtime_seconds": downtime_seconds,
            "unmonitored_seconds": unmonitored_seconds,
            "incident_count": incident_count,
            "sample_count": len(samples),
            "current_status": current_status,
            "first_observed_at": first_observed_at,
            "last_observed_at": last_observed_at,
            "expected_interval_seconds": expected_interval,
            "max_observed_gap_seconds": max_observed_gap,
            "data_status": "OK" if monitored_seconds > 0 else "NO_DATA",
        }

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_file, timeout=10.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _load_samples(
        self,
        ip: str,
        start_at: datetime,
        end_at: datetime,
    ) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, ip, name, probe_status, effective_status,
                       latency_ms, quality, consecutive_failures,
                       consecutive_successes, observed_at
                FROM probe_history
                WHERE ip = ?
                  AND datetime(observed_at) >= datetime(?)
                  AND datetime(observed_at) <= datetime(?)
                ORDER BY datetime(observed_at) ASC, id ASC
                """,
                (
                    ip,
                    start_at.isoformat(timespec="seconds"),
                    end_at.isoformat(timespec="seconds"),
                ),
            ).fetchall()
        return [dict(row) for row in rows]

    def _load_previous_sample(
        self,
        ip: str,
        before: datetime,
    ) -> Optional[dict]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT id, ip, name, probe_status, effective_status,
                       latency_ms, quality, consecutive_failures,
                       consecutive_successes, observed_at
                FROM probe_history
                WHERE ip = ? AND datetime(observed_at) < datetime(?)
                ORDER BY datetime(observed_at) DESC, id DESC
                LIMIT 1
                """,
                (ip, before.isoformat(timespec="seconds")),
            ).fetchone()
        return dict(row) if row is not None else None

    def _load_config(self) -> dict:
        try:
            with self.ips_file.open("r", encoding="utf-8-sig") as file:
                data = json.load(file)
            if isinstance(data, dict):
                return data
            logger.error("Configuração de disponibilidade não é um objeto JSON.")
        except Exception as exc:
            logger.exception(
                "Falha ao carregar configuração para disponibilidade: %s",
                exc,
            )

        return {"intervalo": 5, "equipamentos": {}}

    @staticmethod
    def _effective_status(sample) -> str:
        if not isinstance(sample, dict):
            return "UNKNOWN"
        value = (
            sample.get("effective_status")
            or sample.get("status")
            or sample.get("probe_status")
            or "UNKNOWN"
        )
        return str(value).upper()

    @staticmethod
    def _parse_datetime(value) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except (TypeError, ValueError):
            return None
