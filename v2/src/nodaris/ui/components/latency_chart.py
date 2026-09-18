from __future__ import annotations

import math
from datetime import datetime

from PySide6.QtCharts import QChart, QChartView, QDateTimeAxis, QLineSeries, QValueAxis
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from nodaris.ui.theme import tokens as t


def normalize_latency_ms(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        latency = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(latency) or latency < 0:
        return None
    return latency


class LatencyChart(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)
        self.setMinimumHeight(330)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("LATÊNCIA — HISTÓRICO")
        title.setObjectName("sectionTitle")
        self.summary_label = QLabel("Sem amostras")
        self.summary_label.setStyleSheet(f"color:{t.TEXT_MUTED};")

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.summary_label)
        root.addLayout(header)

        self.series = QLineSeries()
        self.series.setPen(QPen(QColor(t.ACCENT), 2))

        self.chart = QChart()
        self.chart.legend().hide()
        self.chart.setBackgroundVisible(False)
        self.chart.setPlotAreaBackgroundVisible(True)
        self.chart.setPlotAreaBackgroundBrush(QBrush(QColor(t.BG_PANEL)))
        self.chart.addSeries(self.series)

        self.axis_x = QDateTimeAxis()
        self.axis_x.setFormat("HH:mm")
        self.axis_x.setTickCount(7)
        self.axis_y = QValueAxis()
        self.axis_y.setLabelFormat("%.1f")
        self.axis_y.setTitleText("ms")
        self.axis_y.setTickCount(6)

        label_brush = QBrush(QColor(t.TEXT_MUTED))
        self.axis_x.setLabelsBrush(label_brush)
        self.axis_y.setLabelsBrush(label_brush)
        self.axis_y.setTitleBrush(label_brush)

        grid_pen = QPen(QColor(t.BORDER))
        self.axis_x.setGridLinePen(grid_pen)
        self.axis_y.setGridLinePen(grid_pen)

        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        self.series.attachAxis(self.axis_x)
        self.series.attachAxis(self.axis_y)

        view = QChartView(self.chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setStyleSheet("background: transparent; border: none;")
        root.addWidget(view, 1)

        self.clear()

    def clear(self) -> None:
        self.series.clear()
        now = QDateTime.currentDateTime()
        self.axis_x.setRange(now.addSecs(-3600), now)
        self.axis_y.setRange(0.0, 10.0)
        self.summary_label.setText("Sem amostras")

    def set_samples(self, samples: list[dict]) -> None:
        points: list[tuple[int, float]] = []

        for sample in samples:
            if not isinstance(sample, dict):
                continue
            latency = normalize_latency_ms(sample.get("latency_ms"))
            if latency is None:
                continue

            raw_time = sample.get("observed_at") or sample.get("timestamp")
            try:
                observed = (
                    raw_time
                    if isinstance(raw_time, datetime)
                    else datetime.fromisoformat(str(raw_time))
                )
            except (TypeError, ValueError):
                continue

            points.append((int(observed.timestamp() * 1000), latency))

        if not points:
            self.clear()
            return

        points.sort(key=lambda item: item[0])
        self.series.clear()
        for timestamp_ms, latency in points:
            self.series.append(timestamp_ms, latency)

        start = QDateTime.fromMSecsSinceEpoch(points[0][0])
        end = QDateTime.fromMSecsSinceEpoch(points[-1][0])
        if start == end:
            start = start.addSecs(-60)
            end = end.addSecs(60)

        max_latency = max(value for _, value in points)
        self.axis_x.setRange(start, end)
        self.axis_y.setRange(0.0, max(10.0, max_latency * 1.2))

        average = sum(value for _, value in points) / len(points)
        self.summary_label.setText(
            f"{len(points)} amostras · média {average:.1f} ms · máx {max_latency:.1f} ms"
        )
