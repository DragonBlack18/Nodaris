import json
import sqlite3

from datetime import (
    datetime,
    timedelta,
)
from pathlib import Path
from typing import Optional

from api.config import (
    DATABASE_FILE,
    IPS_FILE,
)


class ProbeAvailabilityService:
    """
    Calcula disponibilidade utilizando somente
    períodos realmente observados pelo MonitorPing.

    Tempo sem probes não é considerado downtime.
    """

    def __init__(
        self,
        database_file: Path = DATABASE_FILE,
        ips_file: Path = IPS_FILE,
    ):
        self.database_file = Path(
            database_file
        )

        self.ips_file = Path(
            ips_file
        )

    # =====================================================
    # PUBLIC
    # =====================================================

    def get_availability(
        self,
        hours: int = 24,
    ) -> dict:

        hours = max(
            1,
            min(
                int(hours),
                24 * 30,
            ),
        )

        end_at = datetime.now()

        start_at = (
            end_at
            - timedelta(
                hours=hours
            )
        )

        config = (
            self._load_config()
        )

        interval_seconds = max(
            1.0,
            float(
                config.get(
                    "intervalo",
                    5,
                )
            ),
        )

        equipments = (
            config.get(
                "equipamentos",
                {}
            )
        )

        if not isinstance(
            equipments,
            dict,
        ):
            equipments = {}

        devices = []

        for ip, config_data in equipments.items():

            if not isinstance(
                config_data,
                dict,
            ):
                config_data = {}

            name = (
                config_data.get(
                    "nome"
                )
                or ip
            )

            device = (
                self._calculate_device(
                    ip=str(ip),
                    name=str(name),
                    start_at=start_at,
                    end_at=end_at,
                    expected_interval=(
                        interval_seconds
                    ),
                )
            )

            devices.append(
                device
            )

        # =================================================
        # GLOBAL SUMMARY
        # =================================================

        valid_availability = [
            device[
                "availability_percent"
            ]
            for device in devices
            if (
                device[
                    "availability_percent"
                ]
                is not None
            )
        ]

        if valid_availability:

            average_availability = (
                sum(
                    valid_availability
                )
                / len(
                    valid_availability
                )
            )

        else:

            average_availability = None

        return {
            "hours": hours,

            "generated_at": (
                end_at.isoformat(
                    timespec="seconds"
                )
            ),

            "summary": {
                "total_devices": (
                    len(devices)
                ),

                "devices_with_data": (
                    len(
                        valid_availability
                    )
                ),

                "average_availability_percent": (
                    average_availability
                ),
            },

            "devices": devices,
        }

    # =====================================================
    # DEVICE
    # =====================================================

    def _calculate_device(
        self,
        ip: str,
        name: str,
        start_at: datetime,
        end_at: datetime,
        expected_interval: float,
    ) -> dict:

        samples = (
            self._load_samples(
                ip=ip,
                start_at=start_at,
                end_at=end_at,
            )
        )

        previous_sample = (
            self._load_previous_sample(
                ip=ip,
                before=start_at,
            )
        )

        window_seconds = max(
            0.0,
            (
                end_at
                - start_at
            ).total_seconds(),
        )

        # Permite alguma variação natural
        # entre ciclos.
        #
        # Exemplo:
        # intervalo = 5s
        # gap máximo observado = 12.5s
        #
        # Se houver um buraco de 3 horas,
        # só 12.5s serão considerados
        # monitorados.

        max_observed_gap = max(
            expected_interval * 2.5,
            expected_interval + 2.0,
        )

        monitored_seconds = 0.0
        uptime_seconds = 0.0
        downtime_seconds = 0.0

        incident_count = 0

        previous_status = (
            self._effective_status(
                previous_sample
            )
            if previous_sample
            else None
        )

        # =================================================
        # SAMPLE WINDOWS
        # =================================================

        for index, sample in enumerate(
            samples
        ):

            observed_at = (
                self._parse_datetime(
                    sample.get(
                        "observed_at"
                    )
                )
            )

            if observed_at is None:
                continue

            if (
                index + 1
                < len(samples)
            ):

                next_at = (
                    self._parse_datetime(
                        samples[
                            index + 1
                        ].get(
                            "observed_at"
                        )
                    )
                )

            else:

                next_at = end_at

            if next_at is None:
                continue

            raw_duration = max(
                0.0,
                (
                    next_at
                    - observed_at
                ).total_seconds(),
            )

            duration = min(
                raw_duration,
                max_observed_gap,
            )

            status = (
                self._effective_status(
                    sample
                )
            )

            probe_status = str(
                sample.get(
                    "probe_status",
                    "",
                )
            ).upper()

            # =============================================
            # ERROR
            # =============================================
            #
            # Um erro do mecanismo de monitoramento
            # não representa estado do equipamento.
            #
            # Portanto esse intervalo não entra
            # nem em uptime nem em downtime.

            if (
                status == "ERROR"
                or probe_status == "ERROR"
            ):

                previous_status = (
                    status
                )

                continue

            monitored_seconds += (
                duration
            )

            # =============================================
            # CONFIRMED OFFLINE
            # =============================================

            if status == "OFFLINE":

                downtime_seconds += (
                    duration
                )

            else:

                # ONLINE
                # SUSPECT
                # RECOVERING
                #
                # Não representam queda confirmada.

                uptime_seconds += (
                    duration
                )

            # =============================================
            # FALL COUNT
            # =============================================

            if (
                status == "OFFLINE"
                and
                previous_status
                != "OFFLINE"
            ):

                incident_count += 1

            previous_status = (
                status
            )

        # =================================================
        # AVAILABILITY
        # =================================================

        if monitored_seconds > 0:

            availability_percent = (
                uptime_seconds
                / monitored_seconds
                * 100.0
            )

        else:

            availability_percent = (
                None
            )

        unmonitored_seconds = max(
            0.0,
            window_seconds
            - monitored_seconds,
        )

        if window_seconds > 0:

            coverage_percent = (
                monitored_seconds
                / window_seconds
                * 100.0
            )

        else:

            coverage_percent = 0.0

        # =================================================
        # FIRST / LAST
        # =================================================

        first_observed_at = None
        last_observed_at = None
        current_status = "UNKNOWN"

        if samples:

            first_observed_at = (
                samples[0].get(
                    "observed_at"
                )
            )

            last_observed_at = (
                samples[-1].get(
                    "observed_at"
                )
            )

            current_status = (
                self._effective_status(
                    samples[-1]
                )
            )

        return {
            "ip": ip,
            "name": name,

            "availability_percent": (
                availability_percent
            ),

            "coverage_percent": (
                coverage_percent
            ),

            "monitored_seconds": (
                monitored_seconds
            ),

            "uptime_seconds": (
                uptime_seconds
            ),

            "downtime_seconds": (
                downtime_seconds
            ),

            "unmonitored_seconds": (
                unmonitored_seconds
            ),

            "incident_count": (
                incident_count
            ),

            "sample_count": (
                len(samples)
            ),

            "current_status": (
                current_status
            ),

            "first_observed_at": (
                first_observed_at
            ),

            "last_observed_at": (
                last_observed_at
            ),

            "expected_interval_seconds": (
                expected_interval
            ),

            "max_observed_gap_seconds": (
                max_observed_gap
            ),

            "data_status": (
                "OK"
                if monitored_seconds > 0
                else "NO_DATA"
            ),
        }

    # =====================================================
    # DATABASE
    # =====================================================

    def _connect(
        self,
    ) -> sqlite3.Connection:

        connection = sqlite3.connect(
            self.database_file
        )

        connection.row_factory = (
            sqlite3.Row
        )

        return connection

    def _load_samples(
        self,
        ip: str,
        start_at: datetime,
        end_at: datetime,
    ) -> list[dict]:

        start_text = (
            start_at.isoformat(
                timespec="seconds"
            )
        )

        end_text = (
            end_at.isoformat(
                timespec="seconds"
            )
        )

        with self._connect() as conn:

            rows = conn.execute(
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
                  AND datetime(observed_at)
                      >= datetime(?)
                  AND datetime(observed_at)
                      <= datetime(?)
                ORDER BY
                    datetime(observed_at) ASC,
                    id ASC
                """,
                (
                    ip,
                    start_text,
                    end_text,
                ),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def _load_previous_sample(
        self,
        ip: str,
        before: datetime,
    ) -> Optional[dict]:

        before_text = (
            before.isoformat(
                timespec="seconds"
            )
        )

        with self._connect() as conn:

            row = conn.execute(
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
                  AND datetime(observed_at)
                      < datetime(?)
                ORDER BY
                    datetime(observed_at) DESC,
                    id DESC
                LIMIT 1
                """,
                (
                    ip,
                    before_text,
                ),
            ).fetchone()

        if row is None:

            return None

        return dict(
            row
        )

    # =====================================================
    # CONFIG
    # =====================================================

    def _load_config(
        self,
    ) -> dict:

        try:

            with self.ips_file.open(
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(
                    file
                )

            if isinstance(
                data,
                dict,
            ):

                return data

        except Exception:

            pass

        return {
            "intervalo": 5,
            "equipamentos": {},
        }

    # =====================================================
    # HELPERS
    # =====================================================

    @staticmethod
    def _effective_status(
        sample,
    ) -> str:

        if not isinstance(
            sample,
            dict,
        ):

            return "UNKNOWN"

        value = (
            sample.get(
                "effective_status"
            )
            or sample.get(
                "status"
            )
            or sample.get(
                "probe_status"
            )
            or "UNKNOWN"
        )

        return str(
            value
        ).upper()

    @staticmethod
    def _parse_datetime(
        value,
    ) -> Optional[datetime]:

        if not value:

            return None

        try:

            return datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            ).replace(
                tzinfo=None
            )

        except (
            TypeError,
            ValueError,
        ):

            return None