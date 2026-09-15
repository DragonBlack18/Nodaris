from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

class AlertCard(QFrame):

    device_requested = Signal(str)

    def __init__(
        self,
        incident: dict,
        parent=None,
    ):
        super().__init__(parent)

        self.incident = (
            incident or {}
        )

        self.setObjectName(
            "alertCard"
        )

        self._build_ui()

    def _build_ui(
        self,
    ):

        root = QHBoxLayout(
            self
        )

        root.setContentsMargins(
            12,
            10,
            12,
            10,
        )

        root.setSpacing(
            10
        )

        indicator = QLabel(
            "●"
        )

        indicator.setObjectName(
            "alertIndicator"
        )

        root.addWidget(
            indicator
        )

        content = QVBoxLayout()

        content.setSpacing(
            2
        )

        name = (
            self.incident.get(
                "name"
            )
            or "Equipamento"
        )

        ip = (
            self.incident.get(
                "ip"
            )
            or "--"
        )

        self.device_label = QLabel(
            str(name)
        )

        self.device_label.setObjectName(
            "alertDeviceName"
        )

        self.device_label.setWordWrap(True)
        self.device_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.info_label = QLabel(
            f"{ip}  •  "
            f"{self._get_duration_text()}"
        )

        self.info_label.setObjectName(
            "alertDuration"
        )

        content.addWidget(
            self.device_label
        )

        content.addWidget(
            self.info_label
        )

        root.addLayout(
            content,
            1,
        )

        button = QPushButton(
            "Abrir"
        )

        button.setObjectName(
            "alertButton"
        )

        button.clicked.connect(
            lambda:
            self.device_requested.emit(
                str(ip)
            )
        )

        root.addWidget(
            button
        )

    def _get_duration_text(
        self,
    ) -> str:

        started_at = (
            self.incident.get(
                "started_at"
            )
        )

        if not started_at:

            return "offline"

        try:

            start = datetime.fromisoformat(
                str(started_at).replace(
                    "Z",
                    "+00:00",
                )
            )

            if start.tzinfo:

                now = datetime.now(
                    start.tzinfo
                )

            else:

                now = datetime.now()

            seconds = max(
                0,
                int(
                    (
                        now - start
                    ).total_seconds()
                ),
            )

            if seconds < 60:

                return (
                    f"há {seconds}s"
                )

            minutes = (
                seconds // 60
            )

            if minutes < 60:

                return (
                    f"há {minutes} min"
                )

            hours = (
                minutes // 60
            )

            remaining = (
                minutes % 60
            )

            return (
                f"há {hours}h "
                f"{remaining}min"
            )

        except Exception:

            return "offline"
