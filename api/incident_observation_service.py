import json
import sqlite3
from contextlib import closing

from datetime import datetime
from pathlib import Path
from typing import Optional

from api.config import DATABASE_FILE, IPS_FILE


class IncidentObservationService:
    """
    Corrige métricas de duração de incidentes usando somente períodos
    realmente observados no probe_history. Buracos de monitoramento não
    contam como downtime.
    """

    def __init__(
        self,
        database_file: Path = DATABASE_FILE,
        ips_file: Path = IPS_FILE,
    ):
        self.database_file = Path(database_file)
        self.ips_file = Path(ips_file)

    # =====================================================
    # PUBLIC
    # =====================================================

    def enrich_incident(self, incident: dict) -> dict:
        if not isinstance(incident, dict):
            return incident

        result = dict(incident)
        ip = str(incident.get("ip", "")).strip()
        started_at = self._parse_datetime(
            incident.get("started_at")
            or incident.get("start_at")
            or incident.get("opened_at")
        )
        ended_at = self._parse_datetime(
            incident.get("ended_at")
            or incident.get("end_at")
            or incident.get("closed_at")
            or incident.get("recovered_at")
        )

        if not ip or started_at is None:
            result["duration_basis"] = "unavailable"
            return result

        # Incidente OPEN calcula até agora.
        effective_end = ended_at or datetime.now()
        if effective_end < started_at:
            effective_end = started_at

        wall_clock_seconds = max(
            0.0,
            (effective_end - started_at).total_seconds(),
        )
        interval_seconds = self._load_interval()
        max_observed_gap = max(
            interval_seconds * 2.5,
            interval_seconds + 2.0,
        )
        measurements = self._calculate_observed_duration(
            ip=ip,
            started_at=started_at,
            ended_at=effective_end,
            max_observed_gap=max_observed_gap,
        )
        monitored_seconds = measurements["monitored_seconds"]
        offline_seconds = measurements["offline_seconds"]
        sample_count = measurements["sample_count"]
        unmonitored_seconds = max(
            0.0,
            wall_clock_seconds - monitored_seconds,
        )

        if wall_clock_seconds > 0:
            coverage_percent = (
                monitored_seconds / wall_clock_seconds * 100.0
            )
        else:
            coverage_percent = 100.0 if sample_count > 0 else 0.0

        # duration_seconds mantém compatibilidade com a UI e passa a
        # representar somente o downtime efetivamente observado.
        result["wall_clock_duration_seconds"] = wall_clock_seconds
        result["observed_downtime_seconds"] = offline_seconds
        result["monitored_seconds"] = monitored_seconds
        result["unmonitored_seconds"] = unmonitored_seconds
        result["monitoring_coverage_percent"] = coverage_percent
        result["duration_seconds"] = offline_seconds
        result["duration_basis"] = "observed_probes"
        result["duration_sample_count"] = sample_count
        result["expected_interval_seconds"] = interval_seconds
        result["max_observed_gap_seconds"] = max_observed_gap
        return result

    def enrich_collection(self, data):
        """Aceita lista direta, envelopes JSON ou um incidente único."""
        if isinstance(data, list):
            return [
                self.enrich_incident(item)
                if isinstance(item, dict)
                else item
                for item in data
            ]

        if isinstance(data, dict):
            result = dict(data)
            for key in ("incidents", "items", "data", "results"):
                value = result.get(key)
                if isinstance(value, list):
                    result[key] = [
                        self.enrich_incident(item)
                        if isinstance(item, dict)
                        else item
                        for item in value
                    ]
                    return result

            if "ip" in result and (
                "started_at" in result
                or "opened_at" in result
                or "start_at" in result
            ):
                return self.enrich_incident(result)

        return data

    # =====================================================
    # CALCULATION
    # =====================================================

    def _calculate_observed_duration(
        self,
        ip: str,
        started_at: datetime,
        ended_at: datetime,
        max_observed_gap: float,
    ) -> dict:
        samples = self._load_samples(
            ip=ip,
            started_at=started_at,
            ended_at=ended_at,
        )
        monitored_seconds = 0.0
        offline_seconds = 0.0

        for index, sample in enumerate(samples):
            current_at = self._parse_datetime(sample.get("observed_at"))
            if current_at is None:
                continue

            if index + 1 < len(samples):
                next_at = self._parse_datetime(
                    samples[index + 1].get("observed_at")
                )
            else:
                next_at = ended_at

            if next_at is None:
                continue

            raw_duration = max(
                0.0,
                (next_at - current_at).total_seconds(),
            )
            duration = min(raw_duration, max_observed_gap)
            probe_status = str(
                sample.get("probe_status") or ""
            ).upper()
            effective_status = str(
                sample.get("effective_status")
                or sample.get("status")
                or probe_status
                or "UNKNOWN"
            ).upper()

            if probe_status == "ERROR" or effective_status == "ERROR":
                continue
            if effective_status == "UNKNOWN":
                continue

            monitored_seconds += duration
            if effective_status == "OFFLINE":
                offline_seconds += duration

        return {
            "monitored_seconds": monitored_seconds,
            "offline_seconds": offline_seconds,
            "sample_count": len(samples),
        }

    # =====================================================
    # DATABASE
    # =====================================================

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_file)
        connection.row_factory = sqlite3.Row
        return connection

    def _load_samples(
        self,
        ip: str,
        started_at: datetime,
        ended_at: datetime,
    ) -> list[dict]:
        start_text = started_at.isoformat(timespec="seconds")
        end_text = ended_at.isoformat(timespec="seconds")

        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    ip,
                    probe_status,
                    effective_status,
                    observed_at
                FROM probe_history
                WHERE ip = ?
                  AND datetime(observed_at) >= datetime(?)
                  AND datetime(observed_at) <= datetime(?)
                ORDER BY datetime(observed_at) ASC, id ASC
                """,
                (ip, start_text, end_text),
            ).fetchall()

        return [dict(row) for row in rows]

    # =====================================================
    # CONFIG
    # =====================================================

    def _load_interval(self) -> float:
        try:
            with self.ips_file.open("r", encoding="utf-8") as file:
                config = json.load(file)
            interval = float(config.get("intervalo", 5))
            return max(1.0, interval)
        except Exception:
            return 5.0

    # =====================================================
    # DATETIME
    # =====================================================

    @staticmethod
    def _parse_datetime(value) -> Optional[datetime]:
        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone().replace(tzinfo=None)
            return parsed
        except (TypeError, ValueError):
            return None
