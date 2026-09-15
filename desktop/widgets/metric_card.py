from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from desktop.theme import metric_card_qss

class MetricCard(QFrame):
    """
    Card reutilizável para exibição de métricas
    na interface do MonitorPing.
    """

    def __init__(
        self,
        title: str,
        value: str = "--",
        parent=None,
    ):
        super().__init__(parent)

        self.setObjectName("metricCard")
        self.setMinimumHeight(105)

        self.setMinimumWidth(180)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            18,
            15,
            18,
            15,
        )

        layout.setSpacing(7)

        # Título
        self.title_label = QLabel(title)

        self.title_label.setObjectName(
            "metricTitle"
        )
        self.title_label.setProperty("metricTitle", True)

        # Valor
        self.value_label = QLabel(
            str(value)
        )

        self.value_label.setObjectName(
            "metricValue"
        )
        self.value_label.setProperty("metricValue", True)

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.value_label
        )

        layout.addStretch()

        legacy_style = self.styleSheet()
        self.setStyleSheet(legacy_style + metric_card_qss())

    def set_value(
        self,
        value,
    ):
        """
        Atualiza o valor apresentado no card.
        """

        if value is None:
            value = "--"

        self.value_label.setText(
            str(value)
        )

    def set_title(
        self,
        title: str,
    ):
        """
        Permite alterar o título posteriormente.
        """

        self.title_label.setText(
            str(title)
        )
