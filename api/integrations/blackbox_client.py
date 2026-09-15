import re
from typing import Optional

import httpx

from api.config import (
    BLACKBOX_PROBE_TIMEOUT,
    BLACKBOX_TIMEOUT,
    BLACKBOX_URL,
)


class BlackboxError(Exception):
    """Erro de comunicação com o Blackbox Exporter."""


class BlackboxClient:
    def __init__(self, base_url: str = BLACKBOX_URL):
        self.base_url = base_url.rstrip("/")

    async def health(self) -> bool:
        """
        Verifica se o Blackbox Exporter está acessível.
        """
        try:
            async with httpx.AsyncClient(
                timeout=BLACKBOX_TIMEOUT
            ) as client:
                response = await client.get(self.base_url)

            return response.status_code == 200

        except httpx.HTTPError:
            return False

    async def ping(self, ip: str) -> dict:
        """
        Executa probe ICMP usando o Blackbox Exporter.
        """

        params = {
            "target": ip,
            "module": "icmp",
        }

        try:
            async with httpx.AsyncClient(
                timeout=BLACKBOX_TIMEOUT
            ) as client:

                response = await client.get(
                    f"{self.base_url}/probe",
                    params=params,
                    headers={
                        "X-Prometheus-Scrape-Timeout-Seconds": str(
                            BLACKBOX_PROBE_TIMEOUT
                        )
                    },
                )

                response.raise_for_status()

        except httpx.HTTPError as exc:
            raise BlackboxError(
                f"Falha ao acessar Blackbox Exporter: {exc}"
            ) from exc

        metrics = response.text

        success = self._get_metric(
            metrics,
            "probe_success",
        )

        online = success == 1.0

        latency_ms = self._extract_icmp_rtt(
            metrics
        )

        if not online:
            latency_ms = None

        if latency_ms is not None:
            latency_ms = round(
                latency_ms,
                2,
            )

        return {
            "ip": ip,
            "online": online,
            "status": "ONLINE" if online else "OFFLINE",
            "latency_ms": latency_ms,
            "latency_source": "icmp_rtt",
        }

    @staticmethod
    def _extract_icmp_rtt(
        metrics_text: str,
    ):

        pattern = re.compile(
            r'^probe_icmp_duration_seconds'
            r'\{[^}]*phase="rtt"[^}]*\}'
            r'\s+([0-9.eE+-]+)$',
            re.MULTILINE,
        )

        match = pattern.search(
            metrics_text
        )

        if not match:
            return None

        try:

            seconds = float(
                match.group(1)
            )

            return (
                seconds * 1000.0
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    @staticmethod
    def _get_metric(
        metrics: str,
        metric_name: str,
        label: Optional[str] = None,
    ) -> Optional[float]:

        for line in metrics.splitlines():

            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            parts = line.split()

            if len(parts) != 2:
                continue

            metric = parts[0]

            if not (
                metric == metric_name
                or metric.startswith(f"{metric_name}{{")
            ):
                continue

            if label and label not in metric:
                continue

            try:
                return float(parts[1])

            except ValueError:
                continue

        return None
