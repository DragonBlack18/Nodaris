from PySide6.QtCore import QEvent, QPoint, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from desktop.device_admin_client import DeviceAdminClient
from desktop import theme
from desktop.theme import (
    BG_APP,
    admin_alert_notification_qss,
    admin_window_qss,
    nodaris_desktop_controls_qss,
    nodaris_global_visual_qss,
    status_color,
    status_soft_color,
)
from desktop.widgets.alert_card import (
    AlertCard,
)
from desktop.widgets.status_card import (
    StatusCard,
)
from desktop.windows.device_detail_window import (
    DeviceDetailWindow,
)
from desktop.windows.device_management_window import (
    DeviceManagementWindow,
)

class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "NODARIS Admin"
        )

        self.resize(
            1250,
            780,
        )

        self.setMinimumSize(
            950,
            650,
        )

        self.device_widgets = {}

        self.devices_by_ip = {}

        # =========================================================
        # DEVICE CATALOG SYNC
        # =========================================================

        self.device_catalog = {}
        self.status_devices = []

        self.current_detail_ip = None

        self.device_management_window = None

        self.detail_window = DeviceDetailWindow(
            self
        )

        self._build_ui()

        self._apply_style()

        self.device_catalog_client = DeviceAdminClient(parent=self)
        self.device_catalog_client.devices_received.connect(
            self._catalog_devices_received
        )

        self.device_catalog_timer = QTimer(self)
        self.device_catalog_timer.setInterval(2000)
        self.device_catalog_timer.timeout.connect(
            self._request_device_catalog
        )
        self.device_catalog_timer.start()

        QTimer.singleShot(300, self._request_device_catalog)

    # =====================================================
    # BUILD
    # =====================================================

    def _build_ui(self):

        central = QWidget()

        central.setObjectName(
            "central"
        )

        self.setCentralWidget(
            central
        )

        root = QVBoxLayout(
            central
        )

        root.setContentsMargins(
            28,
            24,
            28,
            24,
        )

        root.setSpacing(
            20
        )

        # =================================================
        # HEADER
        # =================================================

        header = QHBoxLayout()

        title_layout = QVBoxLayout()

        title = QLabel(
            "NODARIS"
        )

        title.setObjectName(
            "mainTitle"
        )

        subtitle = QLabel(
            "Network Availability Monitor"
        )

        subtitle.setObjectName(
            "subtitle"
        )

        title_layout.addWidget(
            title
        )

        title_layout.addWidget(
            subtitle
        )

        header.addLayout(
            title_layout
        )

        header.addStretch()

        devices_button = QPushButton(
            "Equipamentos"
        )

        devices_button.setObjectName(
            "managementButton"
        )

        devices_button.setFixedHeight(
            theme.CONTROL_HEIGHT_LG
        )

        devices_button.clicked.connect(
            self._open_device_management
        )

        header.addWidget(
            devices_button
        )

        self.connection_label = QLabel(
            "● CONECTANDO..."
        )

        self.connection_label.setObjectName(
            "connectionStatus"
        )

        self.connection_label.setFixedHeight(
            theme.CONTROL_HEIGHT_LG
        )

        self.connection_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        header.addWidget(
            self.connection_label
        )

        root.addLayout(
            header
        )

        # =================================================
        # SUMMARY
        # =================================================

        summary = QHBoxLayout()

        summary.setSpacing(
            12
        )

        self.total_card = StatusCard(
            "TOTAL"
        )

        self.online_card = StatusCard(
            "ONLINE"
        )

        self.suspect_card = StatusCard(
            "SUSPECT"
        )

        self.offline_card = StatusCard(
            "OFFLINE"
        )

        self.recovering_card = StatusCard(
            "RECOVERING"
        )

        summary.addWidget(
            self.total_card
        )

        summary.addWidget(
            self.online_card
        )

        summary.addWidget(
            self.suspect_card
        )

        summary.addWidget(
            self.offline_card
        )

        summary.addWidget(
            self.recovering_card
        )

        root.addLayout(
            summary
        )

        # =================================================
        # ALERT NOTIFICATION CENTER
        # =================================================

        self._active_alert_count = 0

        self.alert_button = QToolButton()
        self.alert_button.setObjectName(
            "alertNotificationButton"
        )

        self.alert_button.setFixedHeight(
            theme.CONTROL_HEIGHT_LG
        )
        self.alert_button.setText("⚠")
        self.alert_button.setToolTip(
            "Nenhum alerta ativo"
        )
        self.alert_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.alert_button.clicked.connect(
            self._toggle_alerts_popup
        )
        header.insertWidget(
            header.indexOf(devices_button),
            self.alert_button,
        )

        self.alerts_floating = QFrame(
            self,
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint,
        )

        self.alerts_floating.setObjectName(
            "alertsFloating"
        )

        self.alerts_floating.setFixedWidth(
            380
        )

        floating_layout = QVBoxLayout(
            self.alerts_floating
        )

        floating_layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )

        floating_layout.setSpacing(
            8
        )

        floating_header = QHBoxLayout()

        floating_title = QLabel(
            "ALERTAS ATIVOS"
        )

        floating_title.setObjectName(
            "floatingAlertTitle"
        )

        self.alert_count = QLabel(
            "0"
        )

        self.alert_count.setObjectName(
            "alertCount"
        )

        floating_header.addWidget(
            floating_title
        )

        floating_header.addWidget(
            self.alert_count
        )

        floating_header.addStretch()

        floating_layout.addLayout(
            floating_header
        )

        self.alerts_scroll = QScrollArea()
        self.alerts_scroll.setObjectName(
            "alertsScroll"
        )
        self.alerts_scroll.setWidgetResizable(True)
        self.alerts_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.alerts_scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.alerts_scroll_content = QWidget()
        self.alerts_scroll_content.setObjectName(
            "alertsScrollContent"
        )

        self.alert_cards_layout = QVBoxLayout(
            self.alerts_scroll_content
        )

        self.alert_cards_layout.setContentsMargins(
            0, 0, 0, 0
        )

        self.alert_cards_layout.setSpacing(
            6
        )

        self.alerts_scroll.setWidget(
            self.alerts_scroll_content
        )
        floating_layout.addWidget(
            self.alerts_scroll
        )

        self.alerts_floating.hide()

        # Fechar ao clicar em qualquer outro widget do Admin,
        # inclusive quando a plataforma não propagar o clique ao popup.
        QApplication.instance().installEventFilter(self)

        # =================================================
        # DEVICE SECTION
        # =================================================

        devices_title = QLabel(
            "EQUIPAMENTOS MONITORADOS"
        )

        devices_title.setObjectName(
            "sectionTitle"
        )

        root.addWidget(
            devices_title
        )

        scroll = QScrollArea()

        scroll.setObjectName(
            "devicesScroll"
        )

        scroll.viewport().setStyleSheet(
            f"background: {BG_APP};"
        )

        scroll.setWidgetResizable(
            True
        )

        scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.devices_container = QWidget()

        self.devices_container.setObjectName(
            "devicesContainer"
        )

        self.devices_layout = QVBoxLayout(
            self.devices_container
        )

        self.devices_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )

        self.devices_layout.setSpacing(
            8
        )

        scroll.setWidget(
            self.devices_container
        )

        root.addWidget(
            scroll,
            1,
        )

                # Máximo 3 notificações
                # simultâneas na tela.
    # =====================================================

    def _request_device_catalog(self):
        self.device_catalog_client.get_devices()

    def _catalog_devices_received(self, devices):
        if not isinstance(devices, list):
            return

        new_catalog = {}
        for device in devices:
            if not isinstance(device, dict):
                continue

            ip = str(device.get("ip", "")).strip()
            if not ip:
                continue

            new_catalog[ip] = dict(device)

        catalog_changed = new_catalog != self.device_catalog
        self.device_catalog = new_catalog

        # MainWindow não possui o ApiClient principal. Quando o catálogo
        # muda, reconstruímos imediatamente com o último status conhecido;
        # o polling normal atualizará a telemetria em até dois segundos.
        if catalog_changed:
            devices = self._merge_catalog_with_status(
                self.status_devices
            )
            self._update_dashboard_devices(devices)

    def _merge_catalog_with_status(self, status_devices):
        """
        /devices decide quais equipamentos existem; /status acrescenta
        apenas estado de rede e telemetria.
        """

        if not isinstance(status_devices, list):
            status_devices = []

        if not self.device_catalog:
            return list(status_devices)

        status_by_ip = {}
        for device in status_devices:
            if not isinstance(device, dict):
                continue

            ip = str(device.get("ip", "")).strip()
            if ip:
                status_by_ip[ip] = device

        merged_devices = []
        for ip, catalog_device in self.device_catalog.items():
            merged = dict(catalog_device)
            status_device = status_by_ip.get(ip)

            if isinstance(status_device, dict):
                for key, value in status_device.items():
                    if key in (
                        "ip",
                        "name",
                        "nome",
                        "gateway",
                        "maintenance",
                    ):
                        continue
                    merged[key] = value
            else:
                merged["status"] = "UNKNOWN"

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

        return merged_devices

    @staticmethod
    def _device_status(device: dict) -> str:

        # Manutenção é um estado administrativo visual.
        # Ela tem prioridade sobre o último estado técnico
        # ONLINE/OFFLINE exibido na interface.
        if bool(
            device.get(
                "maintenance",
                False,
            )
        ):
            return "MAINTENANCE"

        health = device.get("health") or {}

        if not isinstance(
            health,
            dict,
        ):
            health = {}

        return str(
            health.get("status")
            or health.get("effective_status")
            or device.get("effective_status")
            or device.get("status")
            or "UNKNOWN"
        ).upper()

    def _update_dashboard_devices(self, devices):
        if not isinstance(devices, list):
            devices = []

        counts = {
            "ONLINE": 0,
            "OFFLINE": 0,
            "SUSPECT": 0,
            "RECOVERING": 0,
        }
        valid_devices = []

        for device in devices:
            if not isinstance(device, dict):
                continue

            valid_devices.append(device)
            status = self._device_status(device)
            if status in counts:
                counts[status] += 1

        self.total_card.set_value(len(valid_devices))
        self.online_card.set_value(counts["ONLINE"])
        self.suspect_card.set_value(counts["SUSPECT"])
        self.offline_card.set_value(counts["OFFLINE"])
        self.recovering_card.set_value(counts["RECOVERING"])
        self._update_devices(valid_devices)

    def update_status(
        self,
        data: dict,
    ):

        self.connection_label.setText(
            "● MONITORANDO"
        )

        # Uma resposta válida da API significa que
        # a conexão foi restabelecida.
        #
        # Remove do rodapé qualquer erro antigo,
        # como "Connection refused".
        self.statusBar().showMessage(
            "Monitoramento operacional."
        )

        status_devices = data.get(
            "devices",
            [],
        )

        if not isinstance(
            status_devices,
            list,
        ):
            status_devices = []

        self.status_devices = (
            status_devices
        )

        devices = (
            self._merge_catalog_with_status(
                status_devices
            )
        )

        self._update_dashboard_devices(
            devices
        )

    # =====================================================
    # INCIDENTS
    # =====================================================

    def _refresh_alert_button_style(self):

        self.alert_button.setProperty(
            "active",
            self._active_alert_count > 0,
        )

        style = self.alert_button.style()
        style.unpolish(self.alert_button)
        style.polish(self.alert_button)

    def _toggle_alerts_popup(self):

        if self._active_alert_count <= 0:
            self.alerts_floating.hide()
            return

        if self.alerts_floating.isVisible():
            self.alerts_floating.hide()
            return

        self._resize_alerts_popup()
        self._position_alerts()
        self.alerts_floating.show()
        self.alerts_floating.raise_()

    def eventFilter(self, watched, event):

        if (
            event.type() == QEvent.Type.MouseButtonPress
            and self.alerts_floating.isVisible()
            and isinstance(watched, QWidget)
            and watched is not self.alert_button
            and watched is not self.alerts_floating
            and not self.alerts_floating.isAncestorOf(watched)
        ):
            self.alerts_floating.hide()

        return super().eventFilter(watched, event)

    def _resize_alerts_popup(self):

        # O sizeHint do container pode estar desatualizado enquanto
        # o polling substitui os cards de um popup aberto.
        card_heights = []
        for index in range(self.alert_cards_layout.count()):
            widget = self.alert_cards_layout.itemAt(index).widget()
            if widget is not None:
                card_heights.append(widget.sizeHint().height())

        content_height = (
            sum(card_heights)
            + max(0, len(card_heights) - 1)
            * self.alert_cards_layout.spacing()
        )
        popup_height = min(
            450,
            max(120, content_height + 70),
        )
        self.alerts_floating.setFixedHeight(
            popup_height
        )

    def update_incidents(
        self,
        incidents,
    ):

        if not isinstance(
            incidents,
            list,
        ):
            incidents = []

        # =================================================
        # ACTIVE OPERATIONAL ALERTS
        # =================================================
        #
        # /incidents continua sendo a fonte histórica.
        #
        # Porém o painel "ALERTAS" representa somente
        # problemas que exigem atenção AGORA.
        #
        # Portanto:
        # - equipamento removido não aparece;
        # - manutenção não aparece;
        # - equipamento já ONLINE não aparece;
        # - somente um alerta por IP é exibido.

        current_devices = (
            self._merge_catalog_with_status(
                self.status_devices
            )
        )

        current_by_ip = {
            str(
                device.get(
                    "ip",
                    "",
                )
            ).strip(): device

            for device in current_devices

            if (
                isinstance(
                    device,
                    dict,
                )
                and str(
                    device.get(
                        "ip",
                        "",
                    )
                ).strip()
            )
        }

        active_incidents = []

        seen_ips = set()

        for incident in incidents:

            if not isinstance(
                incident,
                dict,
            ):
                continue

            ip = str(
                incident.get(
                    "ip",
                    "",
                )
            ).strip()

            if not ip:
                continue

            # Impede duplicidade visual do mesmo
            # equipamento no painel de alertas.
            if ip in seen_ips:
                continue

            device = current_by_ip.get(
                ip
            )

            # Equipamento não existe mais no catálogo.
            if device is None:
                continue

            # Manutenção é uma supressão operacional.
            if bool(
                device.get(
                    "maintenance",
                    False,
                )
            ):
                continue

            current_status = (
                self._device_status(
                    device
                )
            )

            # Um incidente histórico pode continuar
            # armazenado, mas não é um alerta atual
            # quando o equipamento já está normal.
            if current_status not in {
                "OFFLINE",
                "RECOVERING",
            }:
                continue

            seen_ips.add(
                ip
            )

            active_incidents.append(
                incident
            )

        incidents = active_incidents

        scroll_position = (
            self.alerts_scroll.verticalScrollBar().value()
        )

        # =================================================
        # CLEAR CURRENT CARDS
        # =================================================

        while self.alert_cards_layout.count():

            item = (
                self.alert_cards_layout.takeAt(
                    0
                )
            )

            widget = item.widget()

            if widget:
                widget.deleteLater()

        # =================================================
        # COUNTER
        # =================================================

        self._active_alert_count = len(incidents)

        self.alert_count.setText(
            str(self._active_alert_count)
        )

        if self._active_alert_count:
            count = self._active_alert_count
            plural = (
                "alerta ativo"
                if count == 1
                else "alertas ativos"
            )
            self.alert_button.setText(f"⚠ {count}")
            self.alert_button.setToolTip(
                f"{count} {plural} — clique para visualizar"
            )
        else:
            self.alert_button.setText("⚠")
            self.alert_button.setToolTip(
                "Nenhum alerta ativo"
            )

        self._refresh_alert_button_style()

        if not incidents:

            self.alerts_floating.hide()

            return

        # =================================================
        # CARDS
        # =================================================
        #
        # Todos os alertas ativos ficam disponíveis no scroll.

        for incident in incidents:

            card = AlertCard(
                incident
            )

            card.device_requested.connect(
                self._device_requested
            )

            self.alert_cards_layout.addWidget(
                card
            )

        self.alert_cards_layout.addStretch()
        self._resize_alerts_popup()
        QTimer.singleShot(
            0,
            lambda value=scroll_position:
            self.alerts_scroll.verticalScrollBar().setValue(value),
        )

        # Polling atualiza o popup aberto, sem abri-lo sozinho.
        if self.alerts_floating.isVisible():
            self._position_alerts()

    def _position_alerts(
        self,
    ):

        button_position = self.alert_button.mapToGlobal(
            QPoint(0, self.alert_button.height() + 6)
        )
        popup_width = self.alerts_floating.width()
        popup_height = self.alerts_floating.height()

        x = (
            button_position.x()
            + self.alert_button.width()
            - popup_width
        )
        y = button_position.y()

        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            x = max(
                available.left() + 8,
                min(x, available.right() - popup_width - 8),
            )
            if y + popup_height > available.bottom() - 8:
                button_top = self.alert_button.mapToGlobal(
                    QPoint(0, 0)
                )
                y = button_top.y() - popup_height - 6
            y = max(
                available.top() + 8,
                min(y, available.bottom() - popup_height - 8),
            )

        self.alerts_floating.move(x, y)

    def resizeEvent(
        self,
        event,
    ):

        super().resizeEvent(
            event
        )

        if (
            hasattr(self, "alerts_floating")
            and self.alerts_floating.isVisible()
        ):
            self._position_alerts()

    # =====================================================
    # DEVICES
    # =====================================================

    def _update_devices(
        self,
        devices: list,
    ):

        self.devices_by_ip = {
            device.get("ip"): device
            for device in devices
            if device.get("ip")
        }

        # Mantém a janela de detalhes
        # sincronizada com o monitoramento.
        if self.current_detail_ip and self.detail_window.isVisible():

            current_device = self.devices_by_ip.get(
                self.current_detail_ip
            )

            if current_device:

                self.detail_window.set_device(
                    current_device
                )

        while (
            self.devices_layout.count()
        ):

            item = (
                self.devices_layout.takeAt(
                    0
                )
            )

            widget = item.widget()

            if widget:

                widget.deleteLater()

        for device in devices:

            self.devices_layout.addWidget(
                self._create_device_row(
                    device
                )
            )

    # =====================================================
    # DEVICE ROW
    # =====================================================

    def _create_device_row(
        self,
        device: dict,
    ):

        frame = QFrame()

        frame.setObjectName(
            "deviceRow"
        )

        layout = QHBoxLayout(
            frame
        )

        layout.setContentsMargins(
            18,
            12,
            18,
            12,
        )

        identity = QVBoxLayout()

        name = QLabel(
            device.get(
                "name",
                "Sem nome",
            )
        )

        name.setObjectName(
            "deviceName"
        )

        ip = QLabel(
            device.get(
                "ip",
                "",
            )
        )

        ip.setObjectName(
            "deviceIp"
        )

        identity.addWidget(
            name
        )

        identity.addWidget(
            ip
        )

        layout.addLayout(
            identity
        )

        layout.addStretch()

        status_key = self._device_status(
            device
        )

        if status_key == "MAINTENANCE":
            status_text = "MANUTENÇÃO"
        else:
            status_text = status_key

        frame.setProperty(
            "status",
            status_key.lower(),
        )

        status = QLabel(
            status_text
        )

        status.setObjectName(
            f"status_{status_key.lower()}"
        )

        status.setStyleSheet(
            f"color: {status_color(status_key)};"
            f"background-color: {status_soft_color(status_key)};"
        )

        latency = device.get(
            "latency_ms"
        )

        if latency is None:

            latency_text = "--"

        else:

            try:

                latency_text = (
                    f"{float(latency):.2f} ms"
                )

            except Exception:

                latency_text = "--"

        latency_label = QLabel(
            latency_text
        )

        latency_label.setObjectName(
            "latency"
        )

        latency_label.setMinimumWidth(
            100
        )

        latency_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        layout.addWidget(
            status
        )

        layout.addWidget(
            latency_label
        )

        details_button = QPushButton(
            "Detalhes"
        )

        details_button.setObjectName(
            "deviceButton"
        )

        device_ip = device.get(
            "ip",
            "",
        )

        details_button.clicked.connect(
            lambda checked=False, ip=device_ip:
            self._device_requested(ip)
        )

        layout.addWidget(
            details_button
        )

        return frame

    # =====================================================
    # DEVICE ACTION
    # =====================================================

    def _device_requested(
        self,
        ip: str,
    ):

        if not ip:

            return

        device = self.devices_by_ip.get(
            ip
        )

        if not device:

            self.statusBar().showMessage(
                f"Equipamento não encontrado: {ip}",
                5000,
            )

            return

        self.current_detail_ip = ip

        self.detail_window.set_device(
            device
        )

        self.detail_window.show()

        self.detail_window.raise_()

        self.detail_window.activateWindow()

        self.statusBar().showMessage(
            f"Visualizando {ip}",
            3000,
        )

    # =====================================================
    # DEVICE MANAGEMENT
    # =====================================================

    def _open_device_management(self):
        if self.device_management_window is None:
            self.device_management_window = DeviceManagementWindow(
                parent=self
            )

        self.device_management_window.show()
        self.device_management_window.raise_()
        self.device_management_window.activateWindow()
        self.device_management_window.refresh_devices()

    # =====================================================
    # ERROR
    # =====================================================

    def set_connection_error(
        self,
        error: str,
    ):

        self.connection_label.setText(
            "● API INDISPONÍVEL"
        )

        self.statusBar().showMessage(
            f"Erro de conexão: {error}"
        )

    # =====================================================
    # STYLE
    # =====================================================

    def _apply_style(self):

        qss = (
            theme.app_base_qss()
            + """
            QMainWindow {
                background-color: {BG_APP};
            }

            QWidget#central {
                background-color: {BG_APP};
                color: {TEXT_PRIMARY};
                font-family: "{FONT_FAMILY}";
                font-size: {FONT_SIZE_MD}px;
            }

            QLabel#mainTitle {
                font-size: {FONT_SIZE_2XL}px;
                font-weight: 800;
                color: {TEXT_PRIMARY};
            }

            QLabel#subtitle {
                color: {TEXT_MUTED};
                font-size: {FONT_SIZE_SM}px;
            }

            QLabel#connectionStatus {
                color: {SUCCESS};
                background-color: {SUCCESS_SOFT};
                border: 1px solid {SUCCESS};
                border-radius: {RADIUS_SM}px;
                padding: 5px 10px;
                font-size: {FONT_SIZE_XS}px;
                font-weight: 700;
            }

            QLabel#sectionTitle {
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_SM}px;
                font-weight: 700;
            }

            QFrame#statusCard {
                background-color: {BG_PANEL};
                border: 1px solid {BORDER};
                border-radius: {RADIUS_MD}px;
            }

            QLabel#statusCardTitle {
                color: {TEXT_MUTED};
                font-size: {FONT_SIZE_XS}px;
                font-weight: 700;
            }

            QLabel#statusCardValue {
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_3XL}px;
                font-weight: 800;
            }

            QLabel#alertCount {
                background-color: {DANGER};
                color: {TEXT_PRIMARY};
                border-radius: {RADIUS_MD}px;
                padding: 2px 8px;
                font-weight: 700;
            }

            QFrame#alertsFloating {
                background-color: {BG_ELEVATED};
                border: 1px solid {BORDER_STRONG};
                border-radius: {RADIUS_LG}px;
            }

            QScrollArea#alertsScroll,
            QWidget#alertsScrollContent {
                background: transparent;
                border: none;
            }

            QScrollArea#alertsScroll QScrollBar:vertical {
                width: 8px;
                background: transparent;
            }

            QScrollArea#alertsScroll QScrollBar::handle:vertical {
                min-height: 28px;
                background-color: {BORDER_STRONG};
                border-radius: 4px;
            }

            QScrollArea#alertsScroll QScrollBar::handle:vertical:hover {
                background-color: {TEXT_DISABLED};
            }

            QScrollArea#alertsScroll QScrollBar::add-line:vertical,
            QScrollArea#alertsScroll QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QLabel#floatingAlertTitle {
                color: {DANGER};
                font-size: {FONT_SIZE_XS}px;
                font-weight: 800;
            }

            QFrame#alertCard {
                background-color: {DANGER_SOFT};
                border: 1px solid {DANGER};
                border-radius: {RADIUS_MD}px;
            }

            QLabel#alertIndicator {
                color: {DANGER};
                font-size: {FONT_SIZE_XL}px;
            }

            QLabel#alertDeviceName {
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_MD}px;
                font-weight: 700;
            }

            QLabel#alertDuration {
                color: {TEXT_MUTED};
                font-size: {FONT_SIZE_XS}px;
            }

            QPushButton#alertButton {
                background-color: {BG_ELEVATED};
                color: {TEXT_SECONDARY};
                border: 1px solid {BORDER_STRONG};
                border-radius: {RADIUS_SM}px;
                padding: 5px 9px;
                font-weight: 600;
            }

            QPushButton#alertButton:hover {
                background-color: {BG_PANEL_ALT};
                border-color: {ACCENT};
                color: {TEXT_PRIMARY};
            }

            QPushButton#managementButton {
                background-color: {ACCENT};
                color: {BG_APP};
                border: 1px solid {ACCENT};
                border-radius: {RADIUS_MD}px;
                padding: 7px 13px;
                font-size: {FONT_SIZE_SM}px;
                font-weight: 700;
            }

            QPushButton#managementButton:hover {
                background-color: {ACCENT_HOVER};
                border-color: {ACCENT_HOVER};
                color: {BG_APP};
            }

            QPushButton#managementButton:pressed {
                background-color: {ACCENT_PRESSED};
                border-color: {ACCENT_PRESSED};
            }

            QPushButton#deviceButton {
                background-color: {BG_ELEVATED};
                color: {TEXT_SECONDARY};
                border: 1px solid {BORDER_STRONG};
                border-radius: {RADIUS_SM}px;
                padding: 7px 13px;
                font-size: {FONT_SIZE_SM}px;
                font-weight: 600;
            }

            QPushButton#deviceButton:hover {
                background-color: {BG_PANEL_ALT};
                border-color: {ACCENT};
                color: {TEXT_PRIMARY};
            }

            QPushButton#deviceButton:pressed {
                background-color: {BG_PANEL};
                border-color: {ACCENT_PRESSED};
            }

            QFrame#deviceRow {
                background-color: {BG_PANEL};
                border: 1px solid {BORDER};
                border-radius: {RADIUS_MD}px;
            }

            QFrame#deviceRow[status="online"] {
                border-left: 3px solid {SUCCESS};
            }

            QFrame#deviceRow[status="suspect"] {
                border-left: 3px solid {SUSPECT};
            }

            QFrame#deviceRow[status="recovering"] {
                border-left: 3px solid {RECOVERING};
            }

            QFrame#deviceRow[status="offline"] {
                border-left: 3px solid {DANGER};
            }

            QFrame#deviceRow[status="unknown"] {
                border-left: 3px solid {BORDER_STRONG};
            }

            QFrame#deviceRow[status="maintenance"] {
                border-left: 3px solid {MAINTENANCE};
            }

            QFrame#deviceRow:hover {
                background-color: {BG_PANEL_ALT};
            }

            QLabel#deviceName {
                color: {TEXT_PRIMARY};
                font-weight: 700;
                font-size: {FONT_SIZE_LG}px;
            }

            QLabel#deviceIp {
                color: {TEXT_MUTED};
                font-size: {FONT_SIZE_SM}px;
            }

            QLabel#status_online,
            QLabel#status_offline,
            QLabel#status_suspect,
            QLabel#status_recovering,
            QLabel#status_unknown,
            QLabel#status_maintenance {
                border: 1px solid {BORDER};
                border-radius: {RADIUS_SM}px;
                padding: 4px 10px;
                font-weight: 700;
            }

            QLabel#latency {
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_SM}px;
            }

            QScrollArea#devicesScroll {
                background-color: {BG_APP};
                border: none;
            }

            QWidget#devicesContainer {
                background-color: {BG_APP};
            }

            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollBar:vertical {
                background-color: {BG_APP};
                width: 10px;
                margin: 2px 0;
            }

            QScrollBar::handle:vertical {
                background-color: {BORDER_STRONG};
                min-height: 30px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: {TEXT_DISABLED};
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
                background: transparent;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }

            QStatusBar {
                background-color: {BG_PANEL};
                color: {TEXT_MUTED};
                border-top: 1px solid {BORDER};
                font-size: {FONT_SIZE_SM}px;
                padding: 3px 8px;
            }

            QStatusBar::item {
                border: none;
            }
            """
        )

        tokens = {
            name: value
            for name, value in vars(theme).items()
            if name.isupper()
            and isinstance(value, (str, int))
        }

        for name, value in tokens.items():
            qss = qss.replace(
                "{" + name + "}",
                str(value),
            )

        self.setStyleSheet(
            qss
            + admin_window_qss()
            + nodaris_global_visual_qss()
            + nodaris_desktop_controls_qss()
            + admin_alert_notification_qss()
        )

    # =====================================================
    # CLOSE
    # =====================================================

    def closeEvent(
        self,
        event,
    ):

        event.ignore()

        self.hide()
