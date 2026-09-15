from __future__ import annotations

import json
from urllib.parse import quote

from PySide6.QtCore import QByteArray, QObject, QUrl, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)

from api.config import API_BASE_URL


class DeviceAdminClient(QObject):
    """Cliente HTTP exclusivo da administração de equipamentos."""

    devices_received = Signal(object)
    operation_succeeded = Signal(str, object)
    operation_failed = Signal(str)

    def __init__(
        self,
        base_url: str = API_BASE_URL,
        parent=None,
    ):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.network = QNetworkAccessManager(self)

    # =====================================================
    # OPERATIONS
    # =====================================================

    def get_devices(self):
        reply = self.network.get(self._request("/api/v1/devices"))
        reply.finished.connect(lambda: self._handle_list(reply))

    def create_device(
        self,
        ip: str,
        name: str,
        gateway: str = "",
        maintenance: bool = False,
    ):
        payload = {
            "ip": ip,
            "name": name,
            "gateway": gateway,
            "maintenance": bool(maintenance),
        }
        reply = self.network.post(
            self._json_request("/api/v1/devices"),
            self._json_bytes(payload),
        )
        reply.finished.connect(
            lambda: self._handle_operation(reply, "create")
        )

    def update_device(
        self,
        current_ip: str,
        new_ip: str,
        name: str,
        gateway: str = "",
        maintenance: bool = False,
    ):
        encoded_ip = quote(current_ip, safe="")
        payload = {
            "ip": new_ip,
            "name": name,
            "gateway": gateway,
            "maintenance": bool(maintenance),
        }
        reply = self.network.put(
            self._json_request(f"/api/v1/devices/{encoded_ip}"),
            self._json_bytes(payload),
        )
        reply.finished.connect(
            lambda: self._handle_operation(reply, "update")
        )

    def delete_device(self, ip: str):
        encoded_ip = quote(ip, safe="")
        reply = self.network.deleteResource(
            self._request(f"/api/v1/devices/{encoded_ip}")
        )
        reply.finished.connect(
            lambda: self._handle_operation(reply, "delete")
        )

    # =====================================================
    # REQUESTS / RESPONSES
    # =====================================================

    def _request(self, path: str) -> QNetworkRequest:
        return QNetworkRequest(QUrl(self.base_url + path))

    def _json_request(self, path: str) -> QNetworkRequest:
        request = self._request(path)
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/json",
        )
        return request

    @staticmethod
    def _json_bytes(data: dict) -> QByteArray:
        payload = json.dumps(
            data,
            ensure_ascii=False,
        ).encode("utf-8")
        return QByteArray(payload)

    def _handle_list(self, reply: QNetworkReply):
        try:
            success, data = self._read_reply(reply)
            if not success:
                self.operation_failed.emit(self._error_message(data))
                return

            self.devices_received.emit(self._extract_devices(data))
        finally:
            reply.deleteLater()

    def _handle_operation(
        self,
        reply: QNetworkReply,
        operation: str,
    ):
        try:
            success, data = self._read_reply(reply)
            if not success:
                self.operation_failed.emit(self._error_message(data))
                return

            if not isinstance(data, dict):
                data = {}
            self.operation_succeeded.emit(operation, data)
        finally:
            reply.deleteLater()

    @staticmethod
    def _read_reply(reply: QNetworkReply):
        raw = bytes(reply.readAll())
        data = None

        if raw:
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                data = {
                    "detail": raw.decode("utf-8", errors="ignore")
                }

        status_code = reply.attribute(
            QNetworkRequest.Attribute.HttpStatusCodeAttribute
        )
        network_error = (
            reply.error() != QNetworkReply.NetworkError.NoError
        )
        success = (
            not network_error
            and status_code is not None
            and 200 <= int(status_code) < 300
        )
        return success, data

    # =====================================================
    # NORMALIZATION
    # =====================================================

    @classmethod
    def _extract_devices(cls, data) -> list[dict]:
        if isinstance(data, list):
            return [
                item for item in data if isinstance(item, dict)
            ]
        if not isinstance(data, dict):
            return []

        for key in (
            "devices",
            "equipments",
            "equipamentos",
            "items",
            "results",
            "data",
        ):
            value = data.get(key)
            if isinstance(value, list):
                return [
                    item for item in value if isinstance(item, dict)
                ]
            if isinstance(value, dict):
                nested = cls._extract_devices(value)
                if nested:
                    return nested
        return []

    @staticmethod
    def _error_message(data) -> str:
        if isinstance(data, dict):
            detail = data.get("detail")
            if detail:
                return str(detail)
        return "Não foi possível realizar a operação."
