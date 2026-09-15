import json

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)

from api.config import API_BASE_URL

class ApiClient(QObject):

    status_received = Signal(dict)

    incidents_received = Signal(object)

    device_availability_received = Signal(
        str,
        object,
    )

    device_incidents_received = Signal(
        str,
        object,
    )

    probe_history_received = Signal(
        str,
        object,
    )

    # Signal adicional: preserva o contrato legado acima e correlaciona
    # respostas de histórico com a requisição que as originou.
    probe_history_context_received = Signal(
        str,
        object,
        object,
    )

    connection_error = Signal(str)

    def __init__(
        self,
        base_url: str = API_BASE_URL,
        parent=None,
    ):
        super().__init__(parent)

        self.base_url = base_url.rstrip("/")

        self.network = QNetworkAccessManager(
            self
        )

    # =====================================================
    # STATUS
    # =====================================================

    def get_status(self):

        self._get(
            "/api/v1/status",
            self._handle_status,
        )

    # =====================================================
    # INCIDENTS
    # =====================================================

    def get_open_incidents(self):

        self._get(
            "/api/v1/incidents?status=OPEN",
            self._handle_incidents,
        )

    # =====================================================
    # DEVICE AVAILABILITY
    # =====================================================

    def get_device_availability(
        self,
        ip: str,
        hours: int = 24,
    ):

        if not ip:
            return

        path = (
            f"/api/v1/availability"
            f"?hours={int(hours)}"
        )

        self._get(
            path,
            lambda reply:
            self._handle_device_availability(
                reply,
                ip,
            ),
        )

    # =====================================================
    # DEVICE INCIDENTS
    # =====================================================

    def get_device_incidents(
        self,
        ip: str,
    ):

        if not ip:
            return

        self._get(
            "/api/v1/incidents",
            lambda reply:
            self._handle_device_incidents(
                reply,
                ip,
            ),
        )

    # =====================================================
    # PROBE HISTORY
    # =====================================================

    def get_probe_history(
        self,
        ip: str,
        minutes: int = 60,
        request_token=None,
    ):

        if not ip:
            return

        minutes = max(
            1,
            int(minutes),
        )

        self._get(
            (
                f"/api/v1/probe-history/"
                f"{ip}"
                f"?minutes={minutes}"
                f"&max_points=1500"
            ),
            lambda reply:
            self._handle_probe_history(
                reply,
                ip,
                request_token,
            ),
        )

    # =====================================================
    # GENERIC GET
    # =====================================================

    def _get(
        self,
        path: str,
        handler,
    ):

        url = QUrl(
            f"{self.base_url}{path}"
        )

        request = QNetworkRequest(
            url
        )

        reply = self.network.get(
            request
        )

        reply.finished.connect(
            lambda: handler(
                reply
            )
        )

    # =====================================================
    # STATUS RESPONSE
    # =====================================================

    def _handle_status(
        self,
        reply: QNetworkReply,
    ):

        try:

            data = self._read_reply(
                reply
            )

            if data is not None:

                self.status_received.emit(
                    data
                )

        finally:

            reply.deleteLater()

    # =====================================================
    # INCIDENT RESPONSE
    # =====================================================

    def _handle_incidents(
        self,
        reply: QNetworkReply,
    ):

        try:

            data = self._read_reply(
                reply
            )

            if data is None:

                return

            incidents = []

            if isinstance(
                data,
                list,
            ):

                incidents = data

            elif isinstance(
                data,
                dict,
            ):

                for key in (
                    "incidents",
                    "items",
                    "data",
                ):

                    value = data.get(
                        key
                    )

                    if isinstance(
                        value,
                        list,
                    ):

                        incidents = value

                        break

            self.incidents_received.emit(
                incidents
            )

        finally:

            reply.deleteLater()

    # =====================================================
    # AVAILABILITY RESPONSE
    # =====================================================

    def _handle_device_availability(
        self,
        reply: QNetworkReply,
        ip: str,
    ):

        try:

            data = self._read_reply(
                reply
            )

            if data is None:
                return

            device_data = self._find_device_data(
                data,
                ip,
                expected_keys=(
                    "availability_percent",
                    "availability",
                    "uptime_percent",
                    "monitored_seconds",
                    "downtime_seconds",
                    "offline_seconds",
                    "incident_count",
                ),
            )

            self.device_availability_received.emit(
                ip,
                device_data or {},
            )

        finally:

            reply.deleteLater()

    # =====================================================
    # DEVICE INCIDENTS RESPONSE
    # =====================================================

    def _handle_device_incidents(
        self,
        reply: QNetworkReply,
        ip: str,
    ):

        try:

            data = self._read_reply(
                reply
            )

            if data is None:
                return

            incidents = []

            if isinstance(
                data,
                list,
            ):

                incidents = data

            elif isinstance(
                data,
                dict,
            ):

                for key in (
                    "incidents",
                    "items",
                    "data",
                    "results",
                ):

                    value = data.get(
                        key
                    )

                    if isinstance(
                        value,
                        list,
                    ):

                        incidents = value
                        break

            # =============================================
            # FILTRAR PELO IP
            # =============================================

            device_incidents = [
                incident
                for incident in incidents
                if (
                    isinstance(
                        incident,
                        dict,
                    )
                    and
                    str(
                        incident.get(
                            "ip",
                            "",
                        )
                    )
                    == str(ip)
                )
            ]

            # Mais recente primeiro.
            device_incidents.sort(
                key=lambda item:
                str(
                    item.get(
                        "started_at",
                        "",
                    )
                ),
                reverse=True,
            )

            current_incident = None
            latest_closed = None

            for incident in device_incidents:

                status = str(
                    incident.get(
                        "status",
                        "",
                    )
                ).upper()

                if (
                    status == "OPEN"
                    and current_incident is None
                ):

                    current_incident = (
                        incident
                    )

                if (
                    status == "CLOSED"
                    and latest_closed is None
                ):

                    latest_closed = (
                        incident
                    )

            self.device_incidents_received.emit(
                ip,
                {
                    "current": (
                        current_incident
                        or {}
                    ),
                    "latest": (
                        latest_closed
                        or {}
                    ),
                },
            )

        finally:

            reply.deleteLater()

    # =====================================================
    # DATA SEARCH HELPERS
    # =====================================================

    @classmethod
    def _find_probe_samples(
        cls,
        data,
    ):

        if isinstance(
            data,
            list,
        ):

            valid_samples = [
                item
                for item in data
                if (
                    isinstance(
                        item,
                        dict,
                    )
                    and
                    (
                        "observed_at" in item
                        or "timestamp" in item
                        or "created_at" in item
                    )
                    and
                    (
                        "latency_ms" in item
                        or "probe_status" in item
                        or "status" in item
                    )
                )
            ]

            if valid_samples:

                return valid_samples

            for item in data:

                result = cls._find_probe_samples(
                    item
                )

                if result:

                    return result

            return []

        if isinstance(
            data,
            dict,
        ):

            for value in data.values():

                result = cls._find_probe_samples(
                    value
                )

                if result:

                    return result

        return []

    @classmethod
    def _find_device_data(
        cls,
        data,
        ip: str,
        expected_keys=None,
    ):

        expected_keys = expected_keys or ()

        if isinstance(
            data,
            dict,
        ):

            data_ip = str(
                data.get(
                    "ip",
                    "",
                )
            )

            has_expected_data = (
                not expected_keys
                or any(
                    key in data
                    for key in expected_keys
                )
            )

            if (
                data_ip == str(ip)
                and has_expected_data
            ):

                return data

            for value in data.values():

                result = cls._find_device_data(
                    value,
                    ip,
                    expected_keys,
                )

                if result:

                    return result

        elif isinstance(
            data,
            list,
        ):

            for item in data:

                result = cls._find_device_data(
                    item,
                    ip,
                    expected_keys,
                )

                if result:

                    return result

        return None

    # =====================================================
    # PROBE HISTORY RESPONSE
    # =====================================================

    def _handle_probe_history(
        self,
        reply: QNetworkReply,
        ip: str,
        request_token=None,
    ):

        try:

            data = self._read_reply(
                reply
            )

            if data is None:
                if request_token is not None:
                    self.probe_history_context_received.emit(
                        ip,
                        request_token,
                        None,
                    )
                return

            history = []
            summary = {}
            minutes = None
            total_samples = 0

            if isinstance(
                data,
                dict,
            ):

                history = data.get(
                    "history",
                    [],
                )

                summary = data.get(
                    "summary",
                    {},
                )

                minutes = data.get(
                    "minutes"
                )

                total_samples = data.get(
                    "total_samples",
                    len(history),
                )

            elif isinstance(
                data,
                list,
            ):

                # Compatibilidade temporária
                # com resposta antiga.
                history = data

                total_samples = len(
                    history
                )

            payload = {
                "history": history,
                "summary": summary,
                "minutes": minutes,
                "total_samples": total_samples,
            }

            self.probe_history_received.emit(ip, payload)

            if request_token is not None:
                self.probe_history_context_received.emit(
                    ip,
                    request_token,
                    payload,
                )

        finally:

            reply.deleteLater()

    # =====================================================
    # READ RESPONSE
    # =====================================================

    def _read_reply(
        self,
        reply: QNetworkReply,
    ):

        if (
            reply.error()
            != QNetworkReply.NetworkError.NoError
        ):

            self.connection_error.emit(
                reply.errorString()
            )

            return None

        try:

            raw_data = bytes(
                reply.readAll()
            ).decode(
                "utf-8"
            )

            return json.loads(
                raw_data
            )

        except Exception as exc:

            self.connection_error.emit(
                str(exc)
            )

            return None
