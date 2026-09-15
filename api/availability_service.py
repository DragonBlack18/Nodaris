from datetime import datetime, timedelta

from api.device_state_repository import (
    DeviceStateRepository,
)

from api.incident_repository import (
    IncidentRepository,
)


class AvailabilityService:

    def __init__(
        self,
        device_state_repository:
            DeviceStateRepository,

        incident_repository:
            IncidentRepository,
    ):

        self.device_state_repository = (
            device_state_repository
        )

        self.incident_repository = (
            incident_repository
        )

    def get_availability(
        self,
        hours: int | None = None,
    ) -> list[dict]:

        now = datetime.now()

        devices = (
            self.device_state_repository
            .get_devices()
        )

        results = []

        for device in devices:

            first_seen = datetime.fromisoformat(
                device["first_seen_at"]
            )

            period_start = first_seen

            if hours is not None:

                requested_start = (
                    now - timedelta(
                        hours=hours
                    )
                )

                period_start = max(
                    first_seen,
                    requested_start,
                )

            monitored_seconds = max(
                0,
                (
                    now - period_start
                ).total_seconds(),
            )

            incidents = (
                self.incident_repository
                .get_incidents_between(
                    ip=device["ip"],
                    start_at=(
                        period_start.isoformat(
                            timespec="seconds"
                        )
                    ),
                    end_at=(
                        now.isoformat(
                            timespec="seconds"
                        )
                    ),
                )
            )

            downtime_seconds = 0.0

            for incident in incidents:

                incident_start = (
                    datetime.fromisoformat(
                        incident["started_at"]
                    )
                )

                incident_end = (
                    datetime.fromisoformat(
                        incident["ended_at"]
                    )
                    if incident["ended_at"]
                    else now
                )

                overlap_start = max(
                    period_start,
                    incident_start,
                )

                overlap_end = min(
                    now,
                    incident_end,
                )

                if overlap_end > overlap_start:

                    downtime_seconds += (
                        overlap_end
                        - overlap_start
                    ).total_seconds()

            downtime_seconds = min(
                downtime_seconds,
                monitored_seconds,
            )

            uptime_seconds = max(
                0,
                monitored_seconds
                - downtime_seconds,
            )

            if monitored_seconds > 0:

                availability = (
                    uptime_seconds
                    / monitored_seconds
                    * 100
                )

            else:

                availability = 100.0

            results.append(
                {
                    "ip": device["ip"],
                    "name": device["name"],

                    "status": (
                        device["last_status"]
                    ),

                    "monitoring_since": (
                        device["first_seen_at"]
                    ),

                    "last_seen_at": (
                        device["last_seen_at"]
                    ),

                    "monitored_seconds": round(
                        monitored_seconds,
                        2,
                    ),

                    "uptime_seconds": round(
                        uptime_seconds,
                        2,
                    ),

                    "downtime_seconds": round(
                        downtime_seconds,
                        2,
                    ),

                    "availability_percent": (
                        round(
                            availability,
                            4,
                        )
                    ),

                    "incident_count": len(
                        incidents
                    ),

                    "incident_open": any(
                        incident["status"]
                        == "OPEN"

                        for incident
                        in incidents
                    ),
                }
            )

        return results