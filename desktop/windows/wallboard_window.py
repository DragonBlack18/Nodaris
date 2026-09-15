from __future__ import annotations

import math
import time
from datetime import datetime
from ipaddress import ip_address

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from desktop.device_admin_client import DeviceAdminClient
from desktop import theme
from desktop.theme import nodaris_global_visual_qss, wallboard_window_qss
from desktop.widgets.wallboard_incident_alert import (
    WallboardIncidentAlert,
)
from desktop.widgets.wallboard_ip_item import WallboardIpItem


class WallboardWindow(QMainWindow):
    """
    Wallboard read-only do NODARIS.

    Não executa ping, cria incidentes, acessa SQLite diretamente nem possui
    Health Engine próprio. Toda informação vem da API local.
    """

    # =========================================================
    # API HEALTH
    # =========================================================

    POLL_INTERVAL_MS = 2000

    API_STALE_WARNING_SECONDS = 8
    API_STALE_CRITICAL_SECONDS = 20

    # =========================================================
    # SCAN HEALTH
    # =========================================================

    DEFAULT_SCAN_INTERVAL_SECONDS = 5.0

    SCAN_WARNING_MULTIPLIER = 3.0
    SCAN_CRITICAL_MULTIPLIER = 6.0

    MIN_SCAN_WARNING_SECONDS = 15.0
    MIN_SCAN_CRITICAL_SECONDS = 30.0

    ITEM_HEIGHT = 32
    MIN_ITEM_WIDTH = 175
    HORIZONTAL_GAP = 10
    VERTICAL_GAP = 4
    MIN_COLUMNS = 1
    MAX_COLUMNS = 8

    # =====================================================
    # AUTO PAGINATION
    # =====================================================

    PAGE_INTERVAL_MS = 10_000
    MIN_ROWS_PER_PAGE = 1

    STATUS_PRIORITY = {
        "OFFLINE": 0,
        "SUSPECT": 1,
        "RECOVERING": 2,
        "ERROR": 3,
        "UNKNOWN": 4,
        "ONLINE": 5,
        "MAINTENANCE": 6,
    }

    def __init__(self, api_client, parent=None):
        super().__init__(parent)

        self.api = api_client
        self.devices = []
        self.device_items = {}

        # Catálogo administrativo vindo de /devices, indexado por IP.
        self.device_catalog = {}

        # Último estado técnico recebido de /status, indexado por IP.
        self.status_by_ip = {}

        # =========================================================
        # INCIDENT ALERT STATE
        # =========================================================

        self._incident_baseline_ready = False
        self._seen_incident_keys = set()
        self._incident_alert_queue = []

        # Incidente atualmente exibido no popup da TV.
        self._active_incident_alert = None

        self.last_api_received_monotonic = None
        self.last_scan_at = None
        self.last_scan_value = None
        self.last_scan_progress_monotonic = None
        self.scan_interval_seconds = self.DEFAULT_SCAN_INTERVAL_SECONDS
        self._current_columns = None
        self.current_page = 0
        self.total_pages = 1
        self.page_capacity = 0
        self.rows_per_page = 1
        self._last_layout_signature = None

        self.setWindowTitle("NODARIS TV")
        self.resize(1500, 880)
        self.setMinimumSize(900, 600)

        self._build_ui()
        self._apply_style()

        # =========================================================
        # FLOATING INCIDENT ALERT
        # =========================================================

        self.incident_alert = WallboardIncidentAlert(
            parent=self.centralWidget()
        )
        self.incident_alert.dismissed.connect(
            self._incident_alert_dismissed
        )
        self.incident_alert.hide()

        QTimer.singleShot(0, self._position_incident_alert)

        # A TV utiliza o catálogo exclusivamente em modo de leitura.
        self.device_catalog_client = DeviceAdminClient(parent=self)
        self.device_catalog_client.devices_received.connect(
            self._catalog_devices_received
        )

        self.api.status_received.connect(self._status_received)
        self.api.incidents_received.connect(self._incidents_received)
        self.api.connection_error.connect(self._connection_error)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._request_status)
        self.poll_timer.start(self.POLL_INTERVAL_MS)

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._update_live_header)
        self.ui_timer.start(1000)

        self.page_timer = QTimer(self)
        self.page_timer.setInterval(self.PAGE_INTERVAL_MS)
        self.page_timer.timeout.connect(self._next_page)

        # =========================================================
        # INCIDENT POLLING
        # =========================================================

        self.incident_timer = QTimer(self)
        self.incident_timer.setInterval(3000)
        self.incident_timer.timeout.connect(self._request_incidents)
        self.incident_timer.start()

        # =========================================================
        # DEVICE CATALOG POLLING
        # =========================================================

        self.device_catalog_timer = QTimer(self)
        self.device_catalog_timer.setInterval(2000)
        self.device_catalog_timer.timeout.connect(
            self._request_device_catalog
        )
        self.device_catalog_timer.start()

        QTimer.singleShot(0, self._request_status)
        QTimer.singleShot(300, self._request_device_catalog)
        QTimer.singleShot(500, self._request_incidents)
        QTimer.singleShot(100, self._relayout_matrix)
        self._update_live_header()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("wallboardCentral")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(22, 16, 22, 14)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(20)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.title_label = QLabel("NODARIS")
        self.title_label.setObjectName("wallboardTitle")
        self.health_label = QLabel("● AGUARDANDO MONITORAMENTO")
        self.health_label.setObjectName("monitorHealth")
        self.health_label.setProperty("state", "waiting")
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.health_label)
        header.addLayout(title_box)
        header.addStretch(1)

        clock_box = QVBoxLayout()
        clock_box.setSpacing(1)
        self.clock_label = QLabel("--:--:--")
        self.clock_label.setObjectName("wallboardClock")
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.last_update_label = QLabel(
            "Última atualização: aguardando..."
        )
        self.last_update_label.setObjectName("lastUpdate")
        self.last_update_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.last_scan_label = QLabel(
            "Última varredura: aguardando..."
        )
        self.last_scan_label.setObjectName("lastScan")
        self.last_scan_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_box.addWidget(self.clock_label)
        clock_box.addWidget(self.last_update_label)
        clock_box.addWidget(self.last_scan_label)
        header.addLayout(clock_box)
        root.addLayout(header)

        summary_frame = QFrame()
        summary_frame.setObjectName("summaryFrame")
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(10, 7, 10, 7)
        summary_layout.setSpacing(6)
        self.summary_labels = {}

        for key, title in (
            ("ALL", "MONITORADOS"),
            ("ONLINE", "ONLINE"),
            ("SUSPECT", "SUSPECT"),
            ("OFFLINE", "OFFLINE"),
            ("RECOVERING", "RECOVERING"),
        ):
            item = QFrame()
            item.setObjectName("summaryItem")
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(8, 2, 8, 2)
            item_layout.setSpacing(6)
            value_label = QLabel("0")
            value_label.setObjectName("summaryValue")
            title_label = QLabel(title)
            title_label.setObjectName("summaryTitle")
            item_layout.addWidget(value_label)
            item_layout.addWidget(title_label)
            item_layout.addStretch(1)
            summary_layout.addWidget(item, 1)
            self.summary_labels[key] = value_label

        root.addWidget(summary_frame)

        # =================================================
        # PROBLEM STRIP
        # =================================================

        self.problem_strip = QFrame()
        self.problem_strip.setObjectName("problemStrip")

        problem_layout = QVBoxLayout(self.problem_strip)
        problem_layout.setContentsMargins(12, 8, 12, 8)
        problem_layout.setSpacing(5)

        self.problem_title_label = QLabel("⚠ ATENÇÃO")
        self.problem_title_label.setObjectName("problemTitle")
        problem_layout.addWidget(self.problem_title_label)

        self.problem_items_layout = QGridLayout()
        self.problem_items_layout.setContentsMargins(0, 0, 0, 0)
        self.problem_items_layout.setHorizontalSpacing(18)
        self.problem_items_layout.setVerticalSpacing(3)
        problem_layout.addLayout(self.problem_items_layout)

        self.problem_strip.hide()
        root.addWidget(self.problem_strip)

        matrix_header = QHBoxLayout()
        matrix_header.setContentsMargins(2, 0, 2, 0)
        self.devices_title = QLabel("EQUIPAMENTOS")
        self.devices_title.setObjectName("sectionTitle")
        self.device_count_label = QLabel("0 equipamentos")
        self.device_count_label.setObjectName("sectionInfo")
        self.page_label = QLabel("")
        self.page_label.setObjectName("pageInfo")
        self.matrix_info_label = QLabel("")
        self.matrix_info_label.setObjectName("matrixInfo")
        matrix_header.addWidget(self.devices_title)
        matrix_header.addWidget(self.device_count_label)
        matrix_header.addStretch(1)
        matrix_header.addWidget(self.page_label)
        matrix_header.addWidget(self.matrix_info_label)
        root.addLayout(matrix_header)

        self.matrix_host = QWidget()
        self.matrix_host.setObjectName("matrixHost")
        self.devices_grid = QGridLayout(self.matrix_host)
        self.devices_grid.setContentsMargins(0, 0, 0, 0)
        self.devices_grid.setHorizontalSpacing(self.HORIZONTAL_GAP)
        self.devices_grid.setVerticalSpacing(self.VERTICAL_GAP)
        self.devices_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        root.addWidget(self.matrix_host, 1)

        # =================================================
        # LEGEND
        # =================================================

        legend = QFrame()
        legend.setObjectName("statusLegend")
        legend_layout = QHBoxLayout(legend)
        legend_layout.setContentsMargins(2, 2, 2, 0)
        legend_layout.setSpacing(18)
        legend_layout.addStretch(1)

        for status, title in (
            ("online", "● Online"),
            ("suspect", "● Suspect"),
            ("recovering", "● Recovering"),
            ("offline", "● Offline"),
        ):
            label = QLabel(title)
            label.setObjectName("legendItem")
            label.setProperty("status", status)
            legend_layout.addWidget(label)

        legend_layout.addStretch(1)
        root.addWidget(legend)

        self.empty_label = QLabel(
            "Aguardando dados dos equipamentos..."
        )
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.devices_grid.addWidget(self.empty_label, 0, 0)

    # =====================================================
    # API / MATRIX ITEMS
    # =====================================================

    def _request_status(self):
        self.api.get_status()

    def _request_incidents(self):
        self.api.get_open_incidents()

    def _request_device_catalog(self):
        self.device_catalog_client.get_devices()

    def _catalog_devices_received(self, devices):
        if not isinstance(devices, list):
            return

        catalog = {}
        for device in devices:
            if not isinstance(device, dict):
                continue

            ip = str(device.get("ip", "")).strip()
            if not ip:
                continue

            catalog[ip] = dict(device)

        self.device_catalog = catalog

        # Uma alteração administrativa pode tornar um
        # alerta da TV inválido imediatamente.
        self._sync_incident_alert_suppression()

        self._rebuild_wallboard_devices()

    def _rebuild_wallboard_devices(self):
        """
        Une o catálogo administrativo de /devices à telemetria de /status.

        O catálogo decide quais equipamentos existem. O status apenas
        complementa cada cadastro com estado técnico e telemetria.
        """

        merged_devices = []

        for ip, catalog_device in self.device_catalog.items():
            merged = dict(catalog_device)
            status_device = self.status_by_ip.get(ip)

            if isinstance(status_device, dict):
                for key, value in status_device.items():
                    if key in (
                        "name",
                        "nome",
                        "gateway",
                        "maintenance",
                    ):
                        continue
                    merged[key] = value

                health = status_device.get("health")
                if isinstance(health, dict):
                    merged["health"] = dict(health)
            else:
                # Cadastros novos aparecem antes mesmo do primeiro probe.
                merged.setdefault("status", "UNKNOWN")

            # Identidade e manutenção sempre pertencem ao catálogo.
            merged["ip"] = ip
            merged["name"] = str(
                catalog_device.get("name")
                or catalog_device.get("nome")
                or ip
            )
            merged["gateway"] = str(
                catalog_device.get("gateway") or ""
            )
            merged["maintenance"] = bool(
                catalog_device.get("maintenance", False)
            )
            merged_devices.append(merged)

        # /status pode chegar alguns milissegundos antes do catálogo.
        if not self.device_catalog and self.status_by_ip:
            merged_devices = [
                dict(device) for device in self.status_by_ip.values()
            ]

        self.devices = merged_devices
        self._update_summary(merged_devices)
        self._update_problem_strip(merged_devices)
        self._sync_device_items(merged_devices)

    def _status_received(self, data):
        self.last_api_received_monotonic = time.monotonic()

        # =========================================================
        # SCAN STATE
        # =========================================================

        scan_value = self._find_value(
            data,
            ("last_scan_at", "last_scan"),
        )

        if scan_value is not None:
            scan_value_text = str(scan_value)
            self.last_scan_at = scan_value_text

            # A mudança do valor prova que o MonitorEngine realizou
            # outra varredura.
            if scan_value_text != self.last_scan_value:
                self.last_scan_value = scan_value_text
                self.last_scan_progress_monotonic = time.monotonic()

        # =========================================================
        # SCAN INTERVAL
        # =========================================================

        interval_value = self._find_value(
            data,
            (
                "intervalo",
                "scan_interval",
                "scan_interval_seconds",
                "interval_seconds",
                "monitor_interval",
            ),
        )

        if interval_value is not None:
            try:
                parsed_interval = float(interval_value)
                if parsed_interval > 0:
                    self.scan_interval_seconds = parsed_interval
            except (TypeError, ValueError):
                pass

        status_devices = self._extract_devices(data)
        status_map = {}

        for device in status_devices:
            if not isinstance(device, dict):
                continue

            ip = str(device.get("ip", "")).strip()
            if not ip:
                continue

            status_map[ip] = dict(device)

        self.status_by_ip = status_map
        self._rebuild_wallboard_devices()
        self._update_live_header()

    def _connection_error(self, message: str):
        if self.last_api_received_monotonic is None:
            self.health_label.setText("● API INDISPONÍVEL")
            self._set_health_state("critical")
            return

        self._update_live_header()

    @staticmethod
    def _incident_key(incident: dict) -> str:
        incident_id = incident.get("id")

        if incident_id is not None:
            return f"id:{incident_id}"

        ip = str(incident.get("ip", ""))
        started_at = str(
            incident.get("started_at")
            or incident.get("opened_at")
            or incident.get("start_at")
            or ""
        )
        return f"{ip}|{started_at}"

    def _incidents_received(self, data):

        incidents = self._extract_incidents(
            data
        )

        current_keys = set()

        open_incidents = []

        for incident in incidents:

            if not isinstance(
                incident,
                dict,
            ):
                continue

            status = str(
                incident.get(
                    "status",
                    "OPEN",
                )
            ).upper()

            if status not in (
                "OPEN",
                "ACTIVE",
            ):
                continue

            key = self._incident_key(
                incident
            )

            current_keys.add(
                key
            )

            open_incidents.append(
                (
                    key,
                    incident,
                )
            )

        # =================================================
        # INITIAL BASELINE
        # =================================================
        #
        # Incidentes que já existiam antes da abertura
        # da TV não geram popup retroativo.

        if not self._incident_baseline_ready:

            self._seen_incident_keys.update(
                current_keys
            )

            self._incident_baseline_ready = True

            self._sync_incident_alert_suppression()

            return

        # =================================================
        # NEW INCIDENTS
        # =================================================

        for key, incident in open_incidents:

            if key in self._seen_incident_keys:
                continue

            # Marcamos como visto mesmo quando suprimido.
            #
            # Assim um incidente ocorrido durante
            # manutenção não aparece posteriormente
            # como se fosse um alerta novo.
            self._seen_incident_keys.add(
                key
            )

            if not self._incident_is_actionable(
                incident
            ):
                continue

            self._incident_alert_queue.append(
                incident
            )

        self._sync_incident_alert_suppression()

        self._show_next_incident_alert()

    def _incident_is_actionable(
        self,
        incident: dict,
    ) -> bool:
        """
        Retorna True somente quando o incidente
        ainda merece alerta operacional na TV.

        Histórico não é alterado.
        """

        if not isinstance(
            incident,
            dict,
        ):
            return False

        ip = str(
            incident.get(
                "ip",
                "",
            )
        ).strip()

        if not ip:
            return False

        # =============================================
        # DEVICE MUST STILL EXIST
        # =============================================

        catalog_device = (
            self.device_catalog.get(
                ip
            )
        )

        if not isinstance(
            catalog_device,
            dict,
        ):
            return False

        # =============================================
        # MAINTENANCE SUPPRESSION
        # =============================================

        if bool(
            catalog_device.get(
                "maintenance",
                False,
            )
        ):
            return False

        # =============================================
        # CURRENT TECHNICAL STATE
        # =============================================
        #
        # Se já temos telemetria atual, um equipamento
        # que voltou a ficar normal não deve receber
        # popup de um incidente antigo ainda aberto.

        status_device = (
            self.status_by_ip.get(
                ip
            )
        )

        if isinstance(
            status_device,
            dict,
        ):

            current_status = (
                self._device_status(
                    status_device
                )
            )

            if current_status not in {
                "OFFLINE",
                "RECOVERING",
            }:
                return False

        return True

    def _sync_incident_alert_suppression(
        self,
    ):
        """
        Remove da fila e da tela alertas que
        deixaram de ser operacionalmente válidos.
        """

        self._incident_alert_queue = [
            incident
            for incident in self._incident_alert_queue
            if self._incident_is_actionable(
                incident
            )
        ]

        active = (
            self._active_incident_alert
        )

        if not isinstance(
            active,
            dict,
        ):
            return

        if self._incident_is_actionable(
            active
        ):
            return

        # O equipamento entrou em manutenção,
        # foi removido ou já não exige alerta.

        if hasattr(
            self.incident_alert,
            "hide_timer",
        ):
            self.incident_alert.hide_timer.stop()

        self.incident_alert.hide()

        self._active_incident_alert = None

        QTimer.singleShot(
            0,
            self._show_next_incident_alert,
        )

    def _show_next_incident_alert(
        self,
    ):

        if self.incident_alert.isVisible():
            return

        while self._incident_alert_queue:

            incident = (
                self._incident_alert_queue.pop(
                    0
                )
            )

            # Valida novamente imediatamente antes
            # da exibição.
            #
            # O equipamento pode ter entrado em
            # manutenção enquanto aguardava na fila.

            if not self._incident_is_actionable(
                incident
            ):
                continue

            self._active_incident_alert = (
                incident
            )

            self.incident_alert.show_incident(
                incident
            )

            self._position_incident_alert()

            self.incident_alert.raise_()

            return

    def _incident_alert_dismissed(
        self,
    ):

        self._active_incident_alert = None

        self._show_next_incident_alert()

    def _position_incident_alert(self):
        if not hasattr(self, "incident_alert"):
            return

        parent = self.centralWidget()
        if parent is None:
            return

        alert_width = self.incident_alert.width()
        x = max(20, (parent.width() - alert_width) // 2)
        self.incident_alert.move(x, 105)

        if self.incident_alert.isVisible():
            self.incident_alert.raise_()

    def _sync_device_items(self, devices):
        received_ips = set()
        for device in devices:
            if not isinstance(device, dict):
                continue
            ip = str(device.get("ip", "")).strip()
            if not ip:
                continue
            received_ips.add(ip)
            item = self.device_items.get(ip)
            if item is None:
                item = WallboardIpItem()
                self.device_items[ip] = item
            item.update_device(device)

        for ip in list(self.device_items.keys()):
            if ip in received_ips:
                continue
            item = self.device_items.pop(ip)
            self.devices_grid.removeWidget(item)
            item.deleteLater()

        self.device_count_label.setText(
            f"{len(self.device_items)} equipamentos"
        )
        self._relayout_matrix(force=True)

    # =====================================================
    # RESPONSIVE MATRIX / ORDER
    # =====================================================

    def _calculate_matrix_geometry(
        self,
        item_count: int,
    ) -> tuple[int, int, int]:
        """Retorna colunas, linhas por página e capacidade visível."""

        if item_count <= 0:
            return (1, 1, 1)

        available_width = max(1, self.matrix_host.width())
        available_height = max(1, self.matrix_host.height())

        if available_width < 100:
            available_width = max(800, self.width() - 44)
        if available_height < 100:
            available_height = max(400, self.height() - 220)

        width_per_item = self.MIN_ITEM_WIDTH + self.HORIZONTAL_GAP
        max_columns = int(
            (available_width + self.HORIZONTAL_GAP) / width_per_item
        )
        max_columns = max(
            self.MIN_COLUMNS,
            min(self.MAX_COLUMNS, max_columns),
        )

        height_per_item = self.ITEM_HEIGHT + self.VERTICAL_GAP
        rows_per_page = int(
            (available_height + self.VERTICAL_GAP) / height_per_item
        )
        rows_per_page = max(self.MIN_ROWS_PER_PAGE, rows_per_page)

        required_columns = math.ceil(item_count / rows_per_page)
        columns = min(max_columns, max(1, required_columns))
        capacity = max(1, columns * rows_per_page)

        return (columns, rows_per_page, capacity)

    def _relayout_matrix(self, force=False):
        all_items = list(self.device_items.values())

        if not all_items:
            self._clear_grid()
            self.empty_label.show()
            self.devices_grid.addWidget(self.empty_label, 0, 0)
            self.current_page = 0
            self.total_pages = 1
            self.page_capacity = 0
            self.page_label.setText("")
            self.matrix_info_label.setText("")
            self._update_page_timer()
            return

        all_items.sort(key=self._item_sort_key)

        columns, rows_per_page, capacity = (
            self._calculate_matrix_geometry(len(all_items))
        )
        self._current_columns = columns
        self.rows_per_page = rows_per_page
        self.page_capacity = capacity

        total_pages = max(1, math.ceil(len(all_items) / capacity))
        self.total_pages = total_pages

        if self.current_page >= total_pages:
            self.current_page = total_pages - 1
        self.current_page = max(0, self.current_page)

        layout_signature = (
            columns,
            rows_per_page,
            capacity,
            total_pages,
            self.current_page,
            len(all_items),
            tuple(
                (item.current_ip, item.current_status)
                for item in all_items
            ),
        )

        if (
            not force
            and layout_signature == self._last_layout_signature
        ):
            self._update_page_timer()
            return

        self._last_layout_signature = layout_signature

        start_index = self.current_page * capacity
        end_index = min(start_index + capacity, len(all_items))
        visible_items = all_items[start_index:end_index]

        self._clear_grid()
        self.empty_label.hide()

        # Preenche para baixo antes de começar a próxima coluna.
        for index, item in enumerate(visible_items):
            self.devices_grid.addWidget(
                item,
                index % rows_per_page,
                index // rows_per_page,
            )

        for column in range(columns):
            self.devices_grid.setColumnStretch(column, 1)

        if total_pages > 1:
            self.page_label.setText(
                f"Página {self.current_page + 1}/{total_pages}"
            )
        else:
            self.page_label.setText("")

        visible_rows = min(rows_per_page, len(visible_items))
        self.matrix_info_label.setText(
            f"{columns} colunas • {visible_rows} linhas"
        )
        self._update_page_timer()

    def _update_page_timer(self):
        if self.total_pages > 1:
            if not self.page_timer.isActive():
                self.page_timer.start(self.PAGE_INTERVAL_MS)
        elif self.page_timer.isActive():
            self.page_timer.stop()

    def _next_page(self):
        if self.total_pages <= 1:
            return

        self.current_page = (self.current_page + 1) % self.total_pages
        self._relayout_matrix(force=True)

        if self.page_timer.isActive():
            self.page_timer.start(self.PAGE_INTERVAL_MS)

    def _previous_page(self):
        if self.total_pages <= 1:
            return

        self.current_page = (self.current_page - 1) % self.total_pages
        self._relayout_matrix(force=True)

        if self.page_timer.isActive():
            self.page_timer.start(self.PAGE_INTERVAL_MS)

    def _clear_grid(self):
        while self.devices_grid.count():
            layout_item = self.devices_grid.takeAt(0)
            widget = layout_item.widget()
            if isinstance(widget, WallboardIpItem):
                widget.installEventFilter(self)

        # takeAt() remove o item do layout, mas não oculta o QWidget.
        # Após o relayout, sincronizamos a visibilidade com a página
        # realmente presente na grade. Não muda ordem nem capacidade.
        if not getattr(self, "_grid_visibility_sync_pending", False):
            self._grid_visibility_sync_pending = True
            QTimer.singleShot(0, self._sync_grid_visibility)

    def _sync_grid_visibility(self):
        self._grid_visibility_sync_pending = False
        current_widgets = {
            self.devices_grid.itemAt(index).widget()
            for index in range(self.devices_grid.count())
        }

        for widget in self.matrix_host.findChildren(WallboardIpItem):
            if widget in current_widgets:
                if widget.isHidden():
                    widget.show()
            elif not widget.isHidden():
                widget.hide()

    def eventFilter(self, watched, event):
        if (
            isinstance(watched, WallboardIpItem)
            and event.type() == QEvent.Type.Show
            and self.devices_grid.indexOf(watched) < 0
        ):
            watched.hide()

        return super().eventFilter(watched, event)

    def _item_sort_key(self, item):
        return (
            self.STATUS_PRIORITY.get(item.current_status, 99),
            self._ip_sort_value(item.current_ip),
        )

    @staticmethod
    def _ip_sort_value(ip: str):
        try:
            return (0, int(ip_address(ip)))
        except ValueError:
            return (1, str(ip))

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

    def _update_problem_strip(self, devices):
        problems = []

        for device in devices:
            if not isinstance(device, dict):
                continue

            status = self._device_status(device)
            if status not in ("OFFLINE", "SUSPECT", "RECOVERING"):
                continue

            problems.append(
                (
                    self.STATUS_PRIORITY.get(status, 99),
                    self._ip_sort_value(str(device.get("ip", ""))),
                    device,
                    status,
                )
            )

        while self.problem_items_layout.count():
            item = self.problem_items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not problems:
            self.problem_strip.hide()
            return

        problems.sort(key=lambda item: (item[0], item[1]))
        count = len(problems)
        suffix = "EQUIPAMENTO" if count == 1 else "EQUIPAMENTOS"
        self.problem_title_label.setText(
            f"⚠ ATENÇÃO — {count} {suffix}"
        )

        columns = min(3, count)
        for index, (_, _, device, status) in enumerate(problems):
            ip = str(device.get("ip", "") or "--")
            name = str(
                device.get("name")
                or device.get("nome")
                or "Equipamento"
            )
            label = QLabel(f"●  {ip}   {status}   {name}")
            label.setObjectName("problemItem")
            label.setProperty("status", status.lower())
            label.setProperty("fullText", label.text())
            label.setToolTip(name)
            self.problem_items_layout.addWidget(
                label,
                index // columns,
                index % columns,
            )

        for column in range(columns):
            self.problem_items_layout.setColumnStretch(column, 1)

        self.problem_strip.show()
        QTimer.singleShot(0, self._fit_problem_item_labels)

    def _fit_problem_item_labels(self):
        """Indica com reticências nomes que não cabem na faixa da TV."""

        for index in range(self.problem_items_layout.count()):
            label = self.problem_items_layout.itemAt(index).widget()
            if not isinstance(label, QLabel):
                continue

            full_text = label.property("fullText")
            if not isinstance(full_text, str) or label.width() <= 0:
                continue

            fitted = label.fontMetrics().elidedText(
                full_text,
                Qt.TextElideMode.ElideRight,
                max(1, label.width() - 2),
            )
            if label.text() != fitted:
                label.setText(fitted)

    def _scan_thresholds(self) -> tuple[float, float]:
        interval = max(
            1.0,
            float(self.scan_interval_seconds),
        )

        warning = max(
            self.MIN_SCAN_WARNING_SECONDS,
            interval * self.SCAN_WARNING_MULTIPLIER,
        )
        critical = max(
            self.MIN_SCAN_CRITICAL_SECONDS,
            interval * self.SCAN_CRITICAL_MULTIPLIER,
        )

        # O limite crítico precisa permanecer maior que o de alerta.
        critical = max(critical, warning + interval)

        return (warning, critical)

    def _scan_age_seconds(self):
        """
        Calcula há quanto tempo ocorreu a última varredura conhecida.

        Prioriza o timestamp fornecido pelo backend.
        """

        if not self.last_scan_at:
            return None

        try:
            value = str(self.last_scan_at).strip()
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if parsed.tzinfo is None:
                now = datetime.now()
            else:
                now = datetime.now(parsed.tzinfo)

            seconds = (now - parsed).total_seconds()
            return max(0.0, seconds)
        except (TypeError, ValueError):
            # Se o timestamp tiver formato desconhecido, usamos a
            # progressão observada localmente.
            if self.last_scan_progress_monotonic is None:
                return None

            return max(
                0.0,
                time.monotonic() - self.last_scan_progress_monotonic,
            )

    @staticmethod
    def _format_age(seconds) -> str:
        if seconds is None:
            return "desconhecida"

        seconds = max(0, int(seconds))

        if seconds < 2:
            return "agora"
        if seconds < 60:
            return f"há {seconds}s"

        minutes = seconds // 60
        remaining_seconds = seconds % 60

        if minutes < 60:
            if remaining_seconds:
                return f"há {minutes}m {remaining_seconds}s"
            return f"há {minutes}m"

        hours = minutes // 60
        remaining_minutes = minutes % 60

        if remaining_minutes:
            return f"há {hours}h {remaining_minutes}m"
        return f"há {hours}h"

    def _update_live_header(self):
        now = datetime.now()
        self.clock_label.setText(now.strftime("%H:%M:%S"))

        # A API ainda não respondeu nenhuma vez.
        if self.last_api_received_monotonic is None:
            self.last_update_label.setText(
                "Última atualização: aguardando..."
            )
            self.last_scan_label.setText(
                "Última varredura: aguardando..."
            )
            return

        # A idade da resposta da API sempre tem prioridade.
        api_age = max(
            0.0,
            time.monotonic() - self.last_api_received_monotonic,
        )
        self.last_update_label.setText(
            f"Última atualização: {self._format_age(api_age)}"
        )

        scan_age = self._scan_age_seconds()
        self.last_scan_label.setText(
            f"Última varredura: {self._format_age(scan_age)}"
        )

        if api_age > self.API_STALE_CRITICAL_SECONDS:
            self.health_label.setText("● MONITORAMENTO INDISPONÍVEL")
            self._set_health_state("critical")
            return

        if api_age > self.API_STALE_WARNING_SECONDS:
            self.health_label.setText("● DADOS DESATUALIZADOS")
            self._set_health_state("warning")
            return

        # Com a API viva, verificamos a progressão do MonitorEngine.
        if scan_age is None:
            self.health_label.setText(
                "● API ONLINE • AGUARDANDO VARREDURA"
            )
            self._set_health_state("warning")
            return

        scan_warning, scan_critical = self._scan_thresholds()

        if scan_age > scan_critical:
            self.health_label.setText(
                "● MOTOR DE MONITORAMENTO PARADO"
            )
            self._set_health_state("critical")
            return

        if scan_age > scan_warning:
            self.health_label.setText("● VARREDURA ATRASADA")
            self._set_health_state("warning")
            return

        self.health_label.setText("● MONITOR OPERACIONAL")
        self._set_health_state("healthy")

    def _set_health_state(self, state: str):
        self.health_label.setProperty("state", state)
        style = self.health_label.style()
        style.unpolish(self.health_label)
        style.polish(self.health_label)
        self.health_label.update()

    # =====================================================
    # DATA NORMALIZATION / RESPONSIVE
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
            result = cls._extract_devices(nested_data)
            if result:
                return result
        return []

    @classmethod
    def _extract_incidents(cls, data) -> list[dict]:
        if isinstance(data, list):
            return [
                item for item in data if isinstance(item, dict)
            ]

        if not isinstance(data, dict):
            return []

        for key in ("incidents", "items", "results", "data"):
            value = data.get(key)

            if isinstance(value, list):
                return [
                    item for item in value if isinstance(item, dict)
                ]

            if isinstance(value, dict):
                nested = cls._extract_incidents(value)
                if nested:
                    return nested

        return []

    @staticmethod
    def _device_status(device: dict) -> str:
        if bool(
            device.get(
                "maintenance",
                False,
            )
        ):
            return "MAINTENANCE"

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

    # =========================================================
    # FULLSCREEN
    # =========================================================

    def enter_fullscreen(self):
        """
        Coloca o Wallboard em tela cheia.

        Não altera nenhum estado do monitoramento.
        """

        if self.isFullScreen():
            return

        self.showFullScreen()

        QTimer.singleShot(
            100,
            self._relayout_matrix,
        )

    def exit_fullscreen(self):
        """Retorna o Wallboard ao modo janela."""

        if not self.isFullScreen():
            return

        self.showNormal()

        QTimer.singleShot(
            100,
            self._relayout_matrix,
        )

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            event.accept()
            return

        # ESC apenas sai do fullscreen. Não fecha o Wallboard.
        if key == Qt.Key.Key_Escape and self.isFullScreen():
            self.exit_fullscreen()
            event.accept()
            return

        if key in (
            Qt.Key.Key_Right,
            Qt.Key.Key_PageDown,
        ):
            self._next_page()
            event.accept()
            return

        if key in (
            Qt.Key.Key_Left,
            Qt.Key.Key_PageUp,
        ):
            self._previous_page()
            event.accept()
            return

        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "devices_grid"):
            QTimer.singleShot(0, self._relayout_matrix)
        if hasattr(self, "problem_items_layout"):
            QTimer.singleShot(0, self._fit_problem_item_labels)
        if hasattr(self, "incident_alert"):
            QTimer.singleShot(0, self._position_incident_alert)

    # =====================================================
    # STYLE
    # =====================================================

    def _apply_style(self):
        legacy_qss = """
            QMainWindow { background: %(BG_APP)s; }
            QWidget#wallboardCentral {
                background: %(BG_APP)s;
                color: %(TEXT_PRIMARY)s;
            }
            QLabel#wallboardTitle {
                color: %(TEXT_PRIMARY)s;
                font-size: 25px;
                font-weight: 900;
            }
            QLabel#wallboardClock {
                color: %(TEXT_PRIMARY)s;
                font-size: 25px;
                font-weight: 800;
            }
            QLabel#lastUpdate {
                color: %(TEXT_MUTED)s;
                font-size: 11px;
            }
            QLabel#lastScan {
                color: %(TEXT_MUTED)s;
                font-size: 10px;
            }
            QLabel#monitorHealth {
                font-size: 11px;
                font-weight: 800;
            }
            QLabel#monitorHealth[state="waiting"] { color: %(TEXT_MUTED)s; }
            QLabel#monitorHealth[state="healthy"] { color: %(SUCCESS)s; }
            QLabel#monitorHealth[state="warning"] { color: %(WARNING)s; }
            QLabel#monitorHealth[state="critical"] { color: %(DANGER)s; }
            QFrame#summaryFrame {
                background: %(BG_PANEL)s;
                border: 1px solid %(BORDER)s;
                border-radius: 8px;
            }
            QFrame#summaryItem {
                background: transparent;
                border: none;
            }
            QLabel#summaryValue {
                color: %(TEXT_PRIMARY)s;
                font-size: 17px;
                font-weight: 900;
            }
            QLabel#summaryTitle {
                color: %(TEXT_MUTED)s;
                font-size: 9px;
                font-weight: 800;
            }
            QLabel#sectionTitle {
                color: %(TEXT_SECONDARY)s;
                font-size: 10px;
                font-weight: 900;
            }
            QLabel#sectionInfo, QLabel#matrixInfo {
                color: %(TEXT_MUTED)s;
                font-size: 10px;
            }
            QLabel#pageInfo {
                color: %(ACCENT)s;
                font-size: 10px;
                font-weight: 800;
                padding-right: 12px;
            }
            QFrame#problemStrip {
                background: %(WARNING_SOFT)s;
                border: 1px solid %(WARNING)s;
                border-radius: 7px;
            }
            QLabel#problemTitle {
                color: %(WARNING)s;
                font-size: 11px;
                font-weight: 900;
            }
            QLabel#problemItem {
                color: %(TEXT_SECONDARY)s;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#problemItem[status="offline"] { color: %(DANGER)s; }
            QLabel#problemItem[status="suspect"] { color: %(SUSPECT)s; }
            QLabel#problemItem[status="recovering"] { color: %(RECOVERING)s; }
            QWidget#matrixHost { background: transparent; }
            QLabel#emptyState {
                color: %(TEXT_MUTED)s;
                font-size: 14px;
                padding: 50px;
            }
            QFrame#wallboardIpItem {
                background: %(BG_PANEL)s;
                border: 1px solid %(BORDER)s;
                border-radius: 5px;
            }
            QFrame#wallboardIpItem:hover {
                background: %(BG_PANEL)s;
                border-color: %(BORDER_STRONG)s;
            }
            QFrame#wallboardIpItem[status="suspect"] {
                background: %(SUSPECT_SOFT)s;
                border-color: %(SUSPECT)s;
            }
            QFrame#wallboardIpItem[status="recovering"] {
                background: %(RECOVERING_SOFT)s;
                border-color: %(RECOVERING)s;
            }
            QFrame#wallboardIpItem[status="offline"] {
                background: %(DANGER_SOFT)s;
                border-color: %(DANGER)s;
            }
            QFrame#wallboardIpItem[status="maintenance"] {
                background: %(BG_PANEL)s;
                border-color: %(MAINTENANCE)s;
            }
            QFrame#wallboardIpItem[status="error"] {
                background: %(ERROR_SOFT)s;
                border-color: %(ERROR)s;
            }
            QLabel#statusDot {
                font-size: 18px;
                font-weight: 900;
            }
            QLabel#statusDot[status="online"] { color: %(SUCCESS)s; }
            QLabel#statusDot[status="suspect"] { color: %(SUSPECT)s; }
            QLabel#statusDot[status="recovering"] { color: %(RECOVERING)s; }
            QLabel#statusDot[status="offline"] { color: %(DANGER)s; }
            QLabel#statusDot[status="unknown"] { color: %(UNKNOWN)s; }
            QLabel#statusDot[status="error"] { color: %(ERROR)s; }
            QLabel#statusDot[status="maintenance"] { color: %(MAINTENANCE)s; }
            QLabel#ipText {
                color: %(TEXT_SECONDARY)s;
                font-size: 12px;
                font-weight: 650;
            }
            QLabel#ipText[status="offline"] {
                color: %(DANGER)s;
                font-weight: 800;
            }
            QLabel#ipText[status="suspect"] { color: %(SUSPECT)s; }
            QLabel#ipText[status="recovering"] { color: %(RECOVERING)s; }
            QLabel#ipText[status="maintenance"] {
                color: %(MAINTENANCE)s;
                font-weight: 700;
            }
            QLabel#ipValue {
                color: %(TEXT_MUTED)s;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#ipValue[status="offline"] {
                color: %(DANGER)s;
                font-weight: 900;
            }
            QLabel#ipValue[status="suspect"] {
                color: %(SUSPECT)s;
                font-weight: 900;
            }
            QLabel#ipValue[status="recovering"] {
                color: %(RECOVERING)s;
                font-weight: 900;
            }
            QLabel#ipValue[status="error"] { color: %(ERROR)s; }
            QLabel#ipValue[status="maintenance"] {
                color: %(MAINTENANCE)s;
                font-weight: 800;
            }
            QFrame#statusLegend {
                background: transparent;
                border: none;
            }
            QLabel#legendItem {
                color: %(TEXT_MUTED)s;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#legendItem[status="online"] { color: %(SUCCESS)s; }
            QLabel#legendItem[status="suspect"] { color: %(SUSPECT)s; }
            QLabel#legendItem[status="recovering"] { color: %(RECOVERING)s; }
            QLabel#legendItem[status="offline"] { color: %(DANGER)s; }
            """
        legacy_qss = legacy_qss % vars(theme)
        self.setStyleSheet(
            legacy_qss + wallboard_window_qss() + nodaris_global_visual_qss()
        )
