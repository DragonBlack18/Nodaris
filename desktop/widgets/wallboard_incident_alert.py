from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from desktop import theme
from desktop.theme import wallboard_incident_alert_qss


class WallboardIncidentAlert(QFrame):
    """
    Alerta visual temporário do Wallboard.

    Não detecta queda, cria incidente ou executa ping. Apenas apresenta
    um incidente que já foi confirmado pelo backend.
    """

    dismissed = Signal()

    DISPLAY_TIME_MS = 8_000

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("wallboardIncidentAlert")
        self.setFixedWidth(620)
        self.setMinimumHeight(145)
        self.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground,
            True,
        )

        self._build_ui()
        self._apply_style()

        legacy_style = self.styleSheet()
        self.setStyleSheet(
            legacy_style + wallboard_incident_alert_qss()
        )

        self.hide()

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._finish)

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        self.dot_label = QLabel("●")
        self.dot_label.setObjectName("alertDot")
        self.title_label = QLabel("NOVA PERDA DE COMUNICAÇÃO")
        self.title_label.setObjectName("alertTitle")

        title_row.addWidget(self.dot_label)
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        root.addLayout(title_row)

        self.name_label = QLabel("Equipamento")
        self.name_label.setObjectName("alertDevice")
        root.addWidget(self.name_label)

        info_row = QHBoxLayout()
        info_row.setSpacing(20)

        self.ip_label = QLabel("--")
        self.ip_label.setObjectName("alertIp")
        self.status_label = QLabel("OFFLINE")
        self.status_label.setObjectName("alertStatus")

        info_row.addWidget(self.ip_label)
        info_row.addWidget(self.status_label)
        info_row.addStretch(1)
        root.addLayout(info_row)

        self.time_label = QLabel("Detectado agora")
        self.time_label.setObjectName("alertTime")
        root.addWidget(self.time_label)

    # =====================================================
    # PUBLIC / CLOSE
    # =====================================================

    def show_incident(self, incident: dict):
        if not isinstance(incident, dict):
            return

        ip = str(incident.get("ip", "")).strip()
        name = str(
            incident.get("name")
            or incident.get("device_name")
            or incident.get("nome")
            or ip
            or "Equipamento"
        )
        started_at = (
            incident.get("started_at")
            or incident.get("opened_at")
            or incident.get("start_at")
        )

        self.name_label.setText(name)
        self.ip_label.setText(ip or "--")
        self.status_label.setText("OFFLINE")
        self.time_label.setText(
            self._format_detection_time(started_at)
        )

        self.show()
        self.raise_()
        self.hide_timer.start(self.DISPLAY_TIME_MS)

    def _finish(self):
        self.hide()
        self.dismissed.emit()

    # =====================================================
    # TIME
    # =====================================================

    @staticmethod
    def _format_detection_time(value) -> str:
        if not value:
            return "Detectado agora"

        try:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone()
            return "Detectado às " + parsed.strftime("%H:%M:%S")
        except (TypeError, ValueError):
            return f"Detectado em {value}"

    # =====================================================
    # STYLE
    # =====================================================

    def _apply_style(self):
        self.setStyleSheet(
            """
            QFrame#wallboardIncidentAlert {
                background: %(DANGER_SOFT)s;
                border: 2px solid %(DANGER)s;
                border-radius: 12px;
            }
            QLabel#alertDot {
                color: %(DANGER)s;
                font-size: 22px;
                font-weight: 900;
            }
            QLabel#alertTitle {
                color: %(DANGER)s;
                font-size: 14px;
                font-weight: 900;
            }
            QLabel#alertDevice {
                color: %(TEXT_PRIMARY)s;
                font-size: 24px;
                font-weight: 900;
            }
            QLabel#alertIp {
                color: %(TEXT_SECONDARY)s;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#alertStatus {
                background: %(DANGER_SOFT)s;
                color: %(DANGER)s;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 900;
            }
            QLabel#alertTime {
                color: %(TEXT_MUTED)s;
                font-size: 11px;
            }
            """ % vars(theme)
        )
