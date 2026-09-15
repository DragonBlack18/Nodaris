from collections import deque

from api.config import (
    HEALTH_FAILURE_THRESHOLD,
    HEALTH_LATENCY_WINDOW,
    HEALTH_RECOVERY_THRESHOLD,
    HEALTH_RESULT_WINDOW,
    LATENCY_EXCELLENT_MAX,
    LATENCY_GOOD_MAX,
    LATENCY_POOR_MAX,
    LATENCY_WARNING_MAX,
)
from api.latency import normalize_probe_latency_ms


class IPHealthService:
    """
    Mantém em memória o estado de saúde de cada IP.

    Responsabilidades:
    - eliminar falso OFFLINE causado por uma falha isolada;
    - confirmar recuperação;
    - calcular estabilidade recente;
    - calcular estatísticas de latência;
    - classificar qualidade do IP.
    """

    def __init__(self):

        self._states: dict[str, dict] = {}

    # =====================================================
    # PUBLIC
    # =====================================================

    def observe(
        self,
        result: dict,
    ) -> dict:

        ip = result["ip"]

        probe_status = result.get(
            "status",
            "ERROR",
        )

        current_latency = (
            normalize_probe_latency_ms(
                probe_status,
                result.get("latency_ms"),
            )
        )

        state = self._get_or_create_state(
            ip
        )

        # =================================================
        # RAW ONLINE
        # =================================================

        if probe_status == "ONLINE":

            self._process_online(
                state=state,
                latency_ms=current_latency,
            )

        # =================================================
        # RAW OFFLINE
        # =================================================

        elif probe_status == "OFFLINE":

            self._process_offline(
                state
            )

        # =================================================
        # MONITORING ERROR
        # =================================================

        else:

            state["last_probe_status"] = (
                "ERROR"
            )

        return self._build_result(
            ip=ip,
            state=state,
            current_latency=current_latency,
        )

    # =====================================================
    # STATE
    # =====================================================

    def _get_or_create_state(
        self,
        ip: str,
    ) -> dict:

        if ip not in self._states:

            self._states[ip] = {
                "status": "UNKNOWN",
                "stable_status": "UNKNOWN",

                "consecutive_failures": 0,
                "consecutive_successes": 0,

                "last_probe_status": None,

                "latencies": deque(
                    maxlen=HEALTH_LATENCY_WINDOW
                ),

                "recent_results": deque(
                    maxlen=HEALTH_RESULT_WINDOW
                ),
            }

        return self._states[ip]

    # =====================================================
    # ONLINE
    # =====================================================

    def _process_online(
        self,
        state: dict,
        latency_ms: float | None,
    ):

        state["last_probe_status"] = "ONLINE"

        state["consecutive_successes"] += 1

        state["consecutive_failures"] = 0

        state["recent_results"].append(
            True
        )

        if latency_ms is not None:

            state["latencies"].append(
                float(latency_ms)
            )

        stable_status = state[
            "stable_status"
        ]

        # Estava confirmado como OFFLINE.
        if stable_status == "OFFLINE":

            if (
                state["consecutive_successes"]
                >=
                HEALTH_RECOVERY_THRESHOLD
            ):

                state["status"] = "ONLINE"

                state[
                    "stable_status"
                ] = "ONLINE"

            else:

                state["status"] = (
                    "RECOVERING"
                )

            return

        # UNKNOWN/SUSPECT/ONLINE:
        # um sucesso válido confirma que está ONLINE.
        state["status"] = "ONLINE"

        state["stable_status"] = "ONLINE"

    # =====================================================
    # OFFLINE
    # =====================================================

    def _process_offline(
        self,
        state: dict,
    ):

        state["last_probe_status"] = (
            "OFFLINE"
        )

        state["consecutive_failures"] += 1

        state["consecutive_successes"] = 0

        state["recent_results"].append(
            False
        )

        # Se já estava confirmado offline,
        # continua offline.
        if (
            state["stable_status"]
            == "OFFLINE"
        ):

            state["status"] = "OFFLINE"

            return

        # Só declara OFFLINE após atingir
        # o número configurado de falhas.
        if (
            state["consecutive_failures"]
            >=
            HEALTH_FAILURE_THRESHOLD
        ):

            state["status"] = "OFFLINE"

            state[
                "stable_status"
            ] = "OFFLINE"

        else:

            state["status"] = "SUSPECT"

    # =====================================================
    # RESULT
    # =====================================================

    def _build_result(
        self,
        ip: str,
        state: dict,
        current_latency: float | None,
    ) -> dict:

        latencies = list(
            state["latencies"]
        )

        recent = list(
            state["recent_results"]
        )

        latency_min = None
        latency_max = None
        latency_average = None

        if latencies:

            latency_min = round(
                min(latencies),
                2,
            )

            latency_max = round(
                max(latencies),
                2,
            )

            latency_average = round(
                sum(latencies)
                / len(latencies),
                2,
            )

        recent_failures = sum(
            1
            for result in recent
            if result is False
        )

        recent_successes = sum(
            1
            for result in recent
            if result is True
        )

        loss_percent = 0.0

        if recent:

            loss_percent = round(
                (
                    recent_failures
                    / len(recent)
                )
                * 100,
                2,
            )

        quality = self._classify_quality(
            status=state["status"],
            probe_status=state[
                "last_probe_status"
            ],
            average_latency=(
                latency_average
            ),
        )

        return {
            "ip": ip,

            "status": state["status"],

            "stable_status": state[
                "stable_status"
            ],

            "probe_status": state[
                "last_probe_status"
            ],

            "quality": quality,

            "consecutive_failures": state[
                "consecutive_failures"
            ],

            "consecutive_successes": state[
                "consecutive_successes"
            ],

            "recent_failures": (
                recent_failures
            ),

            "recent_successes": (
                recent_successes
            ),

            "recent_samples": len(
                recent
            ),

            "recent_loss_percent": (
                loss_percent
            ),

            "latency": {
                "current_ms": (
                    round(
                        current_latency,
                        2,
                    )
                    if current_latency
                    is not None
                    else None
                ),

                "average_ms": (
                    latency_average
                ),

                "min_ms": latency_min,

                "max_ms": latency_max,

                "samples": len(
                    latencies
                ),
            },
        }

    # =====================================================
    # QUALITY
    # =====================================================

    @staticmethod
    def _classify_quality(
        status: str,
        probe_status: str | None,
        average_latency: float | None,
    ) -> str:

        if status == "OFFLINE":
            return "CRITICAL"

        if status in {
            "SUSPECT",
            "RECOVERING",
        }:
            return "WARNING"

        if (
            probe_status == "ERROR"
            and
            status == "UNKNOWN"
        ):
            return "UNKNOWN"

        if average_latency is None:
            return "UNKNOWN"

        if (
            average_latency
            <= LATENCY_EXCELLENT_MAX
        ):
            return "EXCELLENT"

        if (
            average_latency
            <= LATENCY_GOOD_MAX
        ):
            return "GOOD"

        if (
            average_latency
            <= LATENCY_WARNING_MAX
        ):
            return "WARNING"

        if (
            average_latency
            <= LATENCY_POOR_MAX
        ):
            return "POOR"

        return "CRITICAL"
