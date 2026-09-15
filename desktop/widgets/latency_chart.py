from datetime import datetime, timedelta
import math

from PySide6.QtCharts import (
    QChart,
    QChartView,
    QDateTimeAxis,
    QLineSeries,
    QScatterSeries,
    QValueAxis,
)
from PySide6.QtCore import (
    QDateTime,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from desktop.theme import latency_chart_palette


def normalize_latency_ms(value) -> float | None:
    """Aceita apenas medições finitas e não negativas (zero é válido)."""

    if value is None or isinstance(value, bool):
        return None

    try:
        latency = float(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(latency) or latency < 0:
        return None

    return latency


class LatencyChartWidget(QFrame):

    period_requested = Signal(
        int
    )

    PERIODS = {
        "15 min": 15,
        "1 hora": 60,
        "6 horas": 360,
        "24 horas": 1440,
    }

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(parent)

        self.setObjectName(
            "latencyChartPanel"
        )

        self.setMinimumHeight(
            370
        )

        self.samples = []
        self.valid_latencies = []

        self._nodaris_palette = latency_chart_palette()

        self._build_ui()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            16,
            14,
            16,
            14,
        )

        root.setSpacing(
            10
        )

        # =================================================
        # HEADER
        # =================================================

        header = QHBoxLayout()

        title = QLabel(
            "LATÊNCIA — HISTÓRICO"
        )

        title.setObjectName(
            "chartTitle"
        )

        header.addWidget(
            title
        )

        header.addStretch()

        self.period_combo = QComboBox()

        self.period_combo.setObjectName(
            "chartPeriod"
        )

        self.period_combo.addItems(
            list(
                self.PERIODS.keys()
            )
        )

        self.period_combo.setCurrentText(
            "1 hora"
        )

        self.period_combo.currentTextChanged.connect(
            self._period_changed
        )

        header.addWidget(
            self.period_combo
        )

        root.addLayout(
            header
        )

        # =================================================
        # CHART
        # =================================================

        self.chart = QChart()

        self.chart.legend().hide()

        self.chart.setBackgroundVisible(
            False
        )

        self.chart.setBackgroundBrush(
            QBrush(QColor(self._nodaris_palette["background"]))
        )

        self.chart.setPlotAreaBackgroundVisible(
            True
        )

        self.chart.setPlotAreaBackgroundBrush(
            QBrush(
                QColor(
                    self._nodaris_palette["plot_background"]
                )
            )
        )

        self.axis_x = QDateTimeAxis()

        self.axis_x.setFormat(
            "HH:mm"
        )

        self.axis_x.setTickCount(
            7
        )

        self.axis_y = QValueAxis()

        self.axis_y.setLabelFormat(
            "%.1f"
        )

        self.axis_y.setTitleText(
            "ms"
        )

        self.axis_y.setTickCount(
            6
        )

        label_brush = QBrush(
            QColor(
                self._nodaris_palette["axis"]
            )
        )

        self.axis_x.setLabelsBrush(
            label_brush
        )

        self.axis_y.setLabelsBrush(
            label_brush
        )

        self.axis_y.setTitleBrush(
            label_brush
        )

        grid_pen = QPen(
            QColor(
                self._nodaris_palette["grid"]
            )
        )

        self.axis_x.setGridLinePen(
            grid_pen
        )

        self.axis_y.setGridLinePen(
            grid_pen
        )

        axis_pen = QPen(
            QColor(
                self._nodaris_palette["border"]
            )
        )

        self.axis_x.setLinePen(
            axis_pen
        )

        self.axis_y.setLinePen(
            axis_pen
        )

        self.chart.addAxis(
            self.axis_x,
            Qt.AlignmentFlag.AlignBottom,
        )

        self.chart.addAxis(
            self.axis_y,
            Qt.AlignmentFlag.AlignLeft,
        )

        self.chart_view = QChartView(
            self.chart
        )

        self.chart_view.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        self.chart_view.setMinimumHeight(
            300
        )

        self.chart_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.chart_view.setStyleSheet(
            """
            QChartView {
                background: transparent;
                border: none;
            }
            """
        )

        root.addWidget(
            self.chart_view
        )

        # =================================================
        # SUMMARY
        # =================================================

        self.summary_label = QLabel(
            "Aguardando histórico..."
        )

        self.summary_label.setObjectName(
            "chartSummary"
        )

        root.addWidget(
            self.summary_label
        )

    # =====================================================
    # DATA
    # =====================================================

    def set_samples(
        self,
        samples,
    ):

        if not isinstance(
            samples,
            list,
        ):

            samples = []

        # Cada resposta é um snapshot completo, nunca um append.
        self.samples = list(samples)

        self._redraw()

    def clear(
        self,
    ):

        self.samples = []

        self._redraw()

    def current_period_minutes(
        self,
    ) -> int:

        return int(
            self.PERIODS.get(
                self.period_combo.currentText(),
                60,
            )
        )

    def _period_changed(
        self,
        period_name: str,
    ):

        minutes = (
            self.PERIODS.get(
                period_name,
                60,
            )
        )

        self.period_requested.emit(
            int(minutes)
        )

    # =====================================================
    # DRAW
    # =====================================================

    def _redraw(
        self,
        *_,
    ):

        self.chart.removeAllSeries()

        period_name = (
            self.period_combo.currentText()
        )

        period_minutes = (
            self.PERIODS.get(
                period_name,
                60,
            )
        )

        period_seconds = (
            period_minutes
            * 60
        )

        now = datetime.now().astimezone()

        start = (
            now
            - timedelta(
                seconds=period_seconds
            )
        )

        filtered = []

        for sample in self.samples:

            if not isinstance(
                sample,
                dict,
            ):

                continue

            observed_at = (
                self._sample_datetime(
                    sample
                )
            )

            if observed_at is None:

                continue

            if observed_at < start or observed_at > now:

                continue

            filtered.append(
                (
                    observed_at,
                    sample,
                )
            )

        filtered.sort(
            key=lambda item:
            item[0]
        )

        # =================================================
        # X AXIS
        # =================================================

        start_ms = int(
            start.timestamp()
            * 1000
        )

        now_ms = int(
            now.timestamp()
            * 1000
        )

        self.axis_x.setRange(
            QDateTime.fromMSecsSinceEpoch(
                start_ms
            ),
            QDateTime.fromMSecsSinceEpoch(
                now_ms
            ),
        )

        if period_seconds <= 3600:

            self.axis_x.setFormat(
                "HH:mm:ss"
            )

        else:

            self.axis_x.setFormat(
                "HH:mm"
            )

        # =================================================
        # BUILD SEGMENTS
        # =================================================

        segments = []

        current_segment = []

        offline_count = 0

        singleton_points = []

        latency_values = []

        for observed_at, sample in filtered:

            latency = (
                self._sample_latency(
                    sample
                )
            )

            status = (
                self._sample_status(
                    sample
                )
            )

            timestamp_ms = int(
                observed_at.timestamp()
                * 1000
            )

            # -------------------------------------------------
            # LATENCY SAMPLE
            # -------------------------------------------------

            if (
                latency is not None
                and status != "OFFLINE"
                and status != "ERROR"
            ):

                current_segment.append(
                    (
                        timestamp_ms,
                        latency,
                    )
                )

                latency_values.append(
                    latency
                )

                continue

            # -------------------------------------------------
            # GAP
            # -------------------------------------------------

            if current_segment:

                segments.append(
                    current_segment
                )

                current_segment = []

            if status == "OFFLINE":
                offline_count += 1

        if current_segment:

            segments.append(
                current_segment
            )

        # A janela de Detalhes usa exatamente as medições exibidas quando
        # precisa recalcular estatísticas de uma resposta não agregada.
        self.valid_latencies = list(latency_values)

        # =================================================
        # LATENCY SERIES
        # =================================================

        latency_pen = QPen(
            QColor(
                self._nodaris_palette["line"]
            )
        )

        latency_pen.setWidthF(
            2.0
        )

        for segment in segments:

            if len(segment) == 1:
                singleton_points.append(segment[0])
                continue

            series = QLineSeries()

            series.setPen(
                latency_pen
            )

            for timestamp_ms, latency in segment:

                series.append(
                    float(
                        timestamp_ms
                    ),
                    float(
                        latency
                    ),
                )

            self.chart.addSeries(
                series
            )

            series.attachAxis(
                self.axis_x
            )

            series.attachAxis(
                self.axis_y
            )

        # =================================================
        # ISOLATED VALID MEASUREMENTS
        # =================================================

        if singleton_points:

            point_series = QScatterSeries()

            point_series.setMarkerSize(
                7.0
            )

            point_series.setColor(
                QColor(
                    self._nodaris_palette["line"]
                )
            )

            point_series.setBorderColor(
                QColor(
                    self._nodaris_palette["line"]
                )
            )

            for timestamp_ms, value in singleton_points:

                point_series.append(
                    float(
                        timestamp_ms
                    ),
                    value,
                )

            self.chart.addSeries(
                point_series
            )

            point_series.attachAxis(
                self.axis_x
            )

            point_series.attachAxis(
                self.axis_y
            )

        # =================================================
        # Y AXIS
        # =================================================

        if latency_values:

            maximum_latency = max(
                latency_values
            )

            headroom = maximum_latency * 1.20
            y_max = max(
                5.0,
                headroom if math.isfinite(headroom) else maximum_latency,
            )

        else:

            y_max = 5.0

        self.axis_y.setRange(
            0.0,
            y_max,
        )

        # =================================================
        # SUMMARY
        # =================================================

        if not filtered:

            self.summary_label.setText(
                "Sem amostras disponíveis "
                "neste período."
            )

            return

        if latency_values:

            average = (
                sum(
                    latency_values
                )
                / len(
                    latency_values
                )
            )

            maximum = max(
                latency_values
            )

            minimum = min(
                latency_values
            )

            summary = (
                f"{len(latency_values)} amostras"
                f"  •  média {average:.2f} ms"
                f"  •  mín. {minimum:.2f} ms"
                f"  •  máx. {maximum:.2f} ms"
            )

        else:

            summary = (
                "Nenhuma amostra de latência "
                "válida neste período"
            )

        if offline_count:

            summary += (
                f"  •  {offline_count} "
                "amostras offline"
            )

        self.summary_label.setText(
            summary
        )

    # =====================================================
    # SAMPLE HELPERS
    # =====================================================

    @staticmethod
    def _sample_datetime(
        sample: dict,
    ):

        value = None

        for key in (
            "observed_at",
            "timestamp",
            "created_at",
            "time",
        ):

            if sample.get(
                key
            ):

                value = sample.get(
                    key
                )

                break

        if not value:

            return None

        try:

            parsed = datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            )

            # O banco grava timestamps sem timezone.
            # Interpretamos esses valores como horário local.
            if parsed.tzinfo is None:

                local_timezone = (
                    datetime.now()
                    .astimezone()
                    .tzinfo
                )

                parsed = parsed.replace(
                    tzinfo=local_timezone
                )

            else:

                parsed = parsed.astimezone()

            return parsed

        except (
            TypeError,
            ValueError,
        ):

            return None

    @staticmethod
    def _sample_latency(
        sample: dict,
    ):

        value = None

        for key in (
            "latency_ms",
            "rtt_ms",
            "latency",
        ):

            candidate = sample.get(
                key
            )

            if candidate is not None:

                value = candidate
                break

        if value is None:

            return None

        return normalize_latency_ms(value)

    @staticmethod
    def _sample_status(
        sample: dict,
    ) -> str:

        # Effective status tem prioridade porque:
        #
        # raw OFFLINE pode ainda significar SUSPECT.
        #
        # Só queremos marcador vermelho para uma
        # queda realmente confirmada.

        for key in (
            "effective_status",
            "status",
            "probe_status",
        ):

            value = sample.get(
                key
            )

            if value:

                return str(
                    value
                ).upper()

        return "UNKNOWN"
