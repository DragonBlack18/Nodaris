from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from desktop.widgets.wallboard_device_card import WallboardDeviceCard


class WallboardWindow(QMainWindow):
    """Painel de monitoramento read-only para TV."""

    POLL_INTERVAL_MS = 2000
    STALE_WARNING_SECONDS = 8
    STALE_CRITICAL_SECONDS = 20

    STATUS_PRIORITY = {
        "OFFLINE": 0,
        "SUSPECT": 1,
        "RECOVERING": 2,
        "ONLINE": 3,
        "UNKNOWN": 4,
        "ERROR": 5,
    }

    def __init__(self, api_client, parent=None):
        super().__init__(parent)

        self.api = api_client
        self.device_cards = {}
        self.devices = []
        self.last_api_received_monotonic = None
        self.last_scan_at = None
        self._current_columns = None

        self.setWindowTitle("MonitorPing TV")
        self.resize(1440, 850)
        self.setMinimumSize(900, 600)

        self._build_ui()
        self._apply_style()

        self.api.status_received.connect(self._status_received)
        self.api.connection_error.connect(self._connection_error)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._request_status)
        self.poll_timer.start(self.POLL_INTERVAL_MS)

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._update_live_header)
        self.ui_timer.start(1000)

        QTimer.singleShot(0, self._request_status)
        self._update_live_header()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("wallboardCentral")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(26, 20, 26, 18)
        root.setSpacing(18)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(20)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_label = QLabel("MONITORPING")
        self.title_label.setObjectName("wallboardTitle")
        self.health_label = QLabel("â— AGUARDANDO MONITORAMENTO")
        self.health_label.setObjectName("monitorHealth")
        self.health_label.setProperty("state", "waiting")
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.health_label)
        header.addLayout(title_box)
        header.addStretch(1)

        update_box = QVBoxLayout()
        update_box.setSpacing(2)
        self.last_update_label = QLabel(
            "Ãšltima atualizaÃ§Ã£o: aguardando..."
        )
        self.last_update_label.setObjectName("lastUpdate")
        self.last_update_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.clock_label = QLabel("--:--:--")
        self.clock_label.setObjectName("wallboardClock")
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        update_box.addWidget(self.clock_label)
        update_box.addWidget(self.last_update_label)
        header.addLayout(update_box)
        root.addLayout(header)

        summary_frame = QFrame()
        summary_frame.setObjectName("summaryFrame")
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(16, 12, 16, 12)
        summary_layout.setSpacing(12)
        self.summary_labels = {}

        for key, title in (
            ("ALL", "MONITORADOS"),
            ("ONLINE", "ONLINE"),
            ("SUSPECT", "SUSPECT"),
            ("OFFLINE", "OFFLINE"),
            ("RECOVERING", "RECOVERING"),
        ):
            box = QFrame()
            box.setObjectName("summaryItem")
            item_layout = QVBoxLayout(box)
            item_layout.setContentsMargins(12, 6, 12, 6)
            item_layout.setSpacing(2)
            value = QLabel("0")
            value.setObjectName("summaryValue")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel(title)
            label.setObjectName("summaryTitle")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item_layout.addWidget(value)
            item_layout.addWidget(label)
            summary_layout.addWidget(box, 1)
            self.summary_labels[key] = value

        root.addWidget(summary_frame)

        section_row = QHBoxLayout()
        self.devices_title = QLabel("EQUIPAMENTOS")
        self.devices_title.setObjectName("sectionTitle")
        self.device_count_label = QLabel("0 equipamentos")
        self.device_count_label.setObjectName("sectionInfo")
        section_row.addWidget(self.devices_title)
        section_row.addStretch(1)
        section_row.addWidget(self.device_count_label)
        root.addLayout(section_row)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("wallboardScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.grid_container = QWidget()
        self.grid_container.setObjectName("wallboardGridContainer")
        self.devices_grid = QGridLayout(self.grid_container)
        self.devices_grid.setContentsMargins(0, 0, 0, 0)
        self.devices_grid.setHorizontalSpacing(14)
        self.devices_grid.setVerticalSpacing(14)
        self.devices_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.grid_container)
        root.addWidget(self.scroll, 1)

        self.empty_label = QLabel(
            "Aguardando dados dos equipamentos..."
        )
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.devices_grid.addWidget(self.empty_label, 0, 0)

    # =====================================================
    # API
    # =====================================================

    def _request_status(self):
        self.api.get_status()

    def _status_received(self, data):
        self.last_api_received_monotonic = time.monotonic()
        self.last_scan_at = self._find_value(
            data,
            ("last_scan_at", "last_scan", "updated_at"),
        )
        devices = self._extract_devices(data)
        self.devices = devices
        self._update_summary(devices)
        self._sync_device_cards(devices)
        self._update_live_header()

    def _connection_error(self, message: str):
        # MantÃ©m os Ãºltimos cards enquanto o stale detector sinaliza
        # que os dados deixaram de ser confiÃ¡veis.
        if self.last_api_received_monotonic is None:
            self.health_label.setText("â— API INDISPONÃVEL")
            self._set_health_state("critical")

    # =====================================================
    # CARDS / RESPONSIVE GRID
    # =====================================================

    def _sync_device_cards(self, devices):
        received_ips = set()
        for device in devices:
            if not isinstance(device, dict):
                continue
            ip = str(device.get("ip", "")).strip()
            if not ip:
                continue
            received_ips.add(ip)
            card = self.device_cards.get(ip)
            if card is None:
                card = WallboardDeviceCard()
                self.device_cards[ip] = card
            card.update_device(device)

        for ip in list(self.device_cards.keys()):
            if ip in received_ips:
                continue
            card = self.device_cards.pop(ip)
            self.devices_grid.removeWidget(card)
            card.deleteLater()

        self._layout_cards(force=True)

    def _column_count(self) -> int:
        width = max(1, self.scroll.viewport().width())
        if width >= 1750:
            return 5
        if width >= 1350:
            return 4
        if width >= 980:
            return 3
        if width >= 680:
            return 2
        return 1

    def _layout_cards(self, force=False):
        columns = self._column_count()
        if not force and columns == self._current_columns:
            return
        self._current_columns = columns

        while self.devices_grid.count():
            self.devices_grid.takeAt(0)

        cards = list(self.device_cards.values())
        cards.sort(
            key=lambda card: (
                self.STATUS_PRIORITY.get(card.current_status, 99),
                card.current_ip,
            )
        )

        if not cards:
            self.empty_label.setText("Nenhum equipamento recebido da API.")
            self.empty_label.show()
            self.devices_grid.addWidget(
                self.empty_label,
                0,
                0,
                1,
                columns,
            )
            self.device_count_label.setText("0 equipamentos")
            return

        self.empty_label.hide()
        for index, card in enumerate(cards):
            self.devices_grid.addWidget(
                card,
                index // columns,
                index % columns,
            )
        for column in range(columns):
            self.devices_grid.setColumnStretch(column, 1)
        self.device_count_label.setText(f"{len(cards)} equipamentos")

    # =====================================================
    # SUMMARY / HEADER
    # =====================================================

    def _update_summary(self, devices):
        counts = {
            "ALL": 0,
            "ONLINE": 0,
            "SUSPECT": 0,
            "OFFLINE": 0,
            "RECOVERING": 0,
        }
        for device in devices:
            if not isinstance(device, dict):
                continue
            status = self._device_status(device)
            counts["ALL"] += 1
            if status in counts:
                counts[status] += 1
        for key, label in self.summary_labels.items():
            label.setText(str(counts.get(key, 0)))

    def _update_live_header(self):
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S"))
        if self.last_api_received_monotonic is None:
            self.last_update_label.setText(
                "Ãšltima atualizaÃ§Ã£o: aguardando..."
            )
            return

        elapsed = max(
            0.0,
            time.monotonic() - self.last_api_received_monotonic,
        )
        update_text = "agora" if elapsed < 1.5 else f"hÃ¡ {int(elapsed)}s"
        self.last_update_label.setText(
            f"Ãšltima atualizaÃ§Ã£o: {update_text}"
        )

        if elapsed <= self.STALE_WARNING_SECONDS:
            self.health_label.setText("â— MONITOR OPERACIONAL")
            self._set_health_state("healthy")
        elif elapsed <= self.STALE_CRITICAL_SECONDS:
            self.health_label.setText("â— DADOS DESATUALIZADOS")
            self._set_health_state("warning")
        else:
            self.health_label.setText("â— MONITORAMENTO INDISPONÃVEL")
            self._set_health_state("critical")

    def _set_health_state(self, state: str):
        self.health_label.setProperty("state", state)
        style = self.health_label.style()
        style.unpolish(self.health_label)
        style.polish(self.health_label)
        self.health_label.update()

    # =====================================================
    # DATA NORMALIZATION
    # =====================================================

    @classmethod
    def _extract_devices(cls, data) -> list[dict]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if not isinstance(data, dict):
            return []

        for key in (
            "devices",
            "equipments",
            "equipamentos",
            "items",
            "results",
        ):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                result = []
                for item_ip, item in value.items():
                    if not isinstance(item, dict):
                        continue
                    normalized = dict(item)
                    normalized.setdefault("ip", str(item_ip))
                    result.append(normalized)
                if result:
                    return result

        nested_data = data.get("data")
        if nested_data is not None and nested_data is not data:
            nested_result = cls._extract_devices(nested_data)
            if nested_result:
                return nested_result
        return []

    @staticmethod
    def _device_status(device: dict) -> str:
        health = device.get("health") or {}
        if not isinstance(health, dict):
            health = {}
        return str(
            health.get("status")
            or health.get("effective_status")
            or device.get("effective_status")
            or device.get("status")
            or "UNKNOWN"
        ).upper()

    @classmethod
    def _find_value(cls, data, keys):
        if isinstance(data, dict):
            for key in keys:
                value = data.get(key)
                if value is not None:
                    return value
            for value in data.values():
                found = cls._find_value(value, keys)
                if found is not None:
                    return found
        return None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "devices_grid"):
            self._layout_cards()

    # =====================================================
    # STYLE
    # =====================================================

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background: #0d1117;
            }
            QWidget#wallboardCentral {
                background: #0d1117;
                color: #f0f3f6;
            }
            QLabel#wallboardTitle {
                color: #ffffff;
                font-size: 27px;
                font-weight: 900;
            }
            QLabel#wallboardClock {
                color: #ffffff;
                font-size: 27px;
                font-weight: 800;
            }
            QLabel#lastUpdate {
                color: #8b949e;
                font-size: 12px;
            }
            QLabel#monitorHealth {
                font-size: 12px;
                font-weight: 800;
            }
            QLabel#monitorHealth[state="waiting"] { color: #8b949e; }
            QLabel#monitorHealth[state="healthy"] { color: #3fb950; }
            QLabel#monitorHealth[state="warning"] { color: #d29922; }
            QLabel#monitorHealth[state="critical"] { color: #f85149; }
            QFrame#summaryFrame {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 12px;
            }
            QFrame#summaryItem {
                background: transparent;
                border: none;
            }
            QLabel#summaryValue {
                color: #ffffff;
                font-size: 23px;
                font-weight: 900;
            }
            QLabel#summaryTitle {
                color: #8b949e;
                font-size: 10px;
                font-weight: 800;
            }
            QLabel#sectionTitle {
                color: #8b949e;
                font-size: 11px;
                font-weight: 900;
            }
            QLabel#sectionInfo {
                color: #6e7681;
                font-size: 11px;
            }
            QScrollArea#wallboardScroll {
                background: transparent;
                border: none;
            }
            QWidget#wallboardGridContainer { background: #0d1117; }
            QLabel#emptyState {
                color: #8b949e;
                font-size: 14px;
                padding: 50px;
            }
            QFrame#wallboardDeviceCard {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 12px;
            }
            QFrame#wallboardDeviceCard[status="online"] {
                border-left: 5px solid #238636;
            }
            QFrame#wallboardDeviceCard[status="suspect"],
            QFrame#wallboardDeviceCard[status="recovering"] {
                background: #2b2212;
                border: 1px solid #9e6a03;
                border-left: 5px solid #d29922;
            }
            QFrame#wallboardDeviceCard[status="offline"] {
                background: #3a1517;
                border: 1px solid #da3633;
                border-left: 6px solid #f85149;
            }
            QFrame#wallboardDeviceCard[status="unknown"] {
                border-left: 5px solid #6e7681;
            }
            QLabel#deviceName {
                color: #ffffff;
                font-size: 15px;
                font-weight: 800;
            }
            QLabel#deviceIp {
                color: #8b949e;
                font-size: 11px;
            }
            QLabel#deviceValue {
                color: #ffffff;
                font-size: 21px;
                font-weight: 900;
            }
            QLabel#deviceSecondary {
                color: #8b949e;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#deviceStatus {
                background: #21262d;
                color: #c9d1d9;
                border-radius: 7px;
                padding: 5px 8px;
                font-size: 9px;
                font-weight: 900;
            }
            QLabel#deviceStatus[status="online"] {
                background: #12351d;
                color: #56d364;
            }
            QLabel#deviceStatus[status="suspect"],
            QLabel#deviceStatus[status="recovering"] {
                background: #493000;
                color: #e3b341;
            }
            QLabel#deviceStatus[status="offline"] {
                background: #5a1e20;
                color: #ff7b72;
            }
            QScrollBar:vertical {
                background: #0d1117;
                width: 9px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #30363d;
                border-radius: 4px;
                min-height: 40px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0px; }
            """
        )

