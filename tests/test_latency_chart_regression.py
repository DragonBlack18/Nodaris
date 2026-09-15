"""Regressão funcional do gráfico de latência do Admin NODARIS."""

import os
import unittest
from datetime import datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCharts import QLineSeries, QScatterSeries
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from desktop.api_client import ApiClient
from desktop.widgets.latency_chart import LatencyChartWidget, normalize_latency_ms
from desktop.windows.device_detail_window import DeviceDetailWindow
from desktop.windows.main_window import MainWindow


def sample(latency, status="ONLINE", offset=0):
    return {
        "observed_at": (datetime.now() + timedelta(seconds=offset)).isoformat(),
        "status": status,
        "latency_ms": latency,
    }


class QtCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])


class LatencyNormalizationTests(QtCase):
    def test_valid_and_invalid_values(self):
        invalid = [None, -1, -0.01, float("nan"), "nan", float("inf"),
                   float("-inf"), True, False, "", "abc"]
        for value in invalid:
            with self.subTest(value=value):
                self.assertIsNone(normalize_latency_ms(value))

        valid = [(0, 0.0), (0.0, 0.0), (0.5, 0.5),
                 ("0.5", 0.5), (42, 42.0), ("42.5", 42.5)]
        for value, expected in valid:
            with self.subTest(value=value):
                self.assertEqual(normalize_latency_ms(value), expected)


class ChartTests(QtCase):
    def setUp(self):
        self.chart = LatencyChartWidget()

    def test_empty_and_error_do_not_draw_false_latency(self):
        self.chart.set_samples([])
        self.assertEqual(self.chart.valid_latencies, [])
        self.assertEqual(len(self.chart.chart.series()), 0)
        self.chart.set_samples([sample(None, "ERROR"), sample(0, "ERROR")])
        self.assertEqual(len(self.chart.chart.series()), 0)

    def test_one_sample_and_real_zero_are_visible(self):
        self.chart.set_samples([sample(42)])
        self.assertEqual(self.chart.valid_latencies, [42.0])
        series = self.chart.chart.series()
        self.assertEqual(len(series), 1)
        self.assertIsInstance(series[0], QScatterSeries)
        self.assertEqual(series[0].points()[0].y(), 42.0)
        self.chart.set_samples([sample(0.0)])
        self.assertEqual(self.chart.chart.series()[0].points()[0].y(), 0.0)

    def test_offline_has_gap_without_zero_marker(self):
        self.chart.set_samples([
            sample(10, offset=-50), sample(12, offset=-40),
            sample(None, "OFFLINE", -30), sample(None, "OFFLINE", -20),
            sample(15, offset=-10), sample(17),
        ])
        series = self.chart.chart.series()
        self.assertEqual(len(series), 2)
        self.assertTrue(all(isinstance(item, QLineSeries) for item in series))
        self.assertEqual([len(item.points()) for item in series], [2, 2])
        self.assertEqual(self.chart.valid_latencies, [10, 12, 15, 17])

    def test_invalid_gap_and_stats(self):
        self.chart.set_samples([
            sample(10, offset=-40), sample(20, offset=-30),
            sample(None, offset=-20), sample(-1, offset=-10), sample(30),
        ])
        self.assertEqual(self.chart.valid_latencies, [10, 20, 30])
        self.assertIn("média 20.00 ms", self.chart.summary_label.text())
        self.assertEqual(len(self.chart.chart.series()), 2)
        self.chart.set_samples([sample(None), sample(-1), sample("nan")])
        self.assertEqual(self.chart.valid_latencies, [])
        self.assertNotIn("nan ms", self.chart.summary_label.text())

    def test_constant_spike_order_and_replacement(self):
        self.chart.set_samples([
            sample(42, offset=-20), sample(42, offset=-10), sample(42),
        ])
        self.assertGreater(self.chart.axis_y.max(), 42)
        self.assertIn("média 42.00 ms", self.chart.summary_label.text())
        self.chart.set_samples([
            sample(12), sample(10, offset=-30), sample(500, offset=-10),
            sample(11, offset=-20),
        ])
        self.assertEqual(self.chart.valid_latencies, [10, 11, 500, 12])
        self.assertGreater(self.chart.axis_y.max(), 500)
        points = self.chart.chart.series()[0].points()
        self.assertEqual([point.y() for point in points], [10, 11, 500, 12])
        self.assertEqual([point.x() for point in points], sorted(point.x() for point in points))
        self.chart.set_samples([sample(5)])
        self.assertEqual(self.chart.valid_latencies, [5])
        self.assertEqual(len(self.chart.chart.series()), 1)

    def test_future_and_invalid_timestamps_are_ignored(self):
        self.chart.set_samples([sample(10, offset=300),
                                {"observed_at": "not-a-date", "latency_ms": 9}])
        self.assertEqual(self.chart.valid_latencies, [])
        self.assertEqual(len(self.chart.chart.series()), 0)

    def test_resize_keeps_chart_valid(self):
        self.chart.set_samples([sample(10, offset=-10), sample(500)])
        self.chart.show()
        for width in (680, 1100, 680):
            self.chart.resize(width, 370)
            self.app.processEvents()
            self.assertGreater(self.chart.axis_y.max(), 500)
            self.assertFalse(self.chart.grab().isNull())
        self.chart.close()


class DetailTests(QtCase):
    def setUp(self):
        self.detail = DeviceDetailWindow()
        self.requests = []
        self.detail.api.get_probe_history = (
            lambda ip, minutes=60, request_token=None:
            self.requests.append((ip, minutes, request_token))
        )
        self.detail.api.get_device_availability = lambda *a, **kw: None
        self.detail.api.get_device_incidents = lambda *a, **kw: None
        self.detail.show()
        self.app.processEvents()

    def tearDown(self):
        self.detail.close()
        self.app.processEvents()

    @staticmethod
    def device(ip):
        return {"ip": ip, "name": ip, "status": "ONLINE", "health": {}}

    def response(self, token, samples, summary=None):
        ip = token[1]
        self.detail._probe_history_context_received(ip, token, {
            "history": samples, "summary": summary or {},
            "total_samples": len(samples),
        })

    def test_switch_ip_resets_before_and_after_empty_response(self):
        self.detail.set_device(self.device("192.0.2.1"))
        token_a = self.requests[-1][2]
        self.response(token_a, [sample(40), sample(42), sample(44)])
        self.assertEqual(self.detail.average_latency_card.value_label.text(), "42.00 ms")
        self.detail.set_device(self.device("192.0.2.2"))
        token_b = self.requests[-1][2]
        self.assertEqual(self.detail.average_latency_card.value_label.text(), "--")
        self.assertEqual(len(self.detail.latency_chart.chart.series()), 0)
        self.response(token_b, [])
        self.assertEqual(self.detail.average_latency_card.value_label.text(), "--")
        self.response(token_a, [sample(99)])
        self.assertEqual(self.detail.average_latency_card.value_label.text(), "--")

    def test_period_race_and_error_response(self):
        self.detail.set_device(self.device("192.0.2.1"))
        old = self.requests[-1][2]
        self.detail.latency_chart.period_combo.setCurrentText("15 min")
        token_15 = self.requests[-1][2]
        self.detail.latency_chart.period_combo.setCurrentText("24 horas")
        token_24 = self.requests[-1][2]
        self.assertNotEqual(token_15, token_24)
        self.response(token_24, [sample(10), sample(20)])
        self.assertEqual(self.detail.average_latency_card.value_label.text(), "15.00 ms")
        self.response(token_15, [sample(99)])
        self.response(old, [sample(88)])
        self.assertEqual(self.detail.average_latency_card.value_label.text(), "15.00 ms")
        self.detail._probe_history_context_received("192.0.2.1", token_24, None)
        self.assertEqual(self.detail.average_latency_card.value_label.text(), "--")
        self.assertEqual(self.detail._last_probe_history_request_at, 0.0)

    def test_response_can_arrive_between_set_device_and_show(self):
        self.detail.hide()
        self.app.processEvents()
        self.detail.set_device(self.device("192.0.2.1"))
        token = self.requests[-1][2]
        self.assertFalse(self.detail.isVisible())
        self.response(token, [sample(10), sample(20)])
        self.assertEqual(self.detail.average_latency_card.value_label.text(), "15.00 ms")

    def test_invalid_and_offline_statistics(self):
        self.detail.set_device(self.device("192.0.2.1"))
        token = self.requests[-1][2]
        self.response(token, [sample(10), sample(None, "OFFLINE"),
                              sample(-1), sample("nan"), sample(20)])
        self.assertEqual(self.detail.average_latency_card.value_label.text(), "15.00 ms")
        self.assertEqual(self.detail.min_latency_card.value_label.text(), "10.00 ms")
        self.assertEqual(self.detail.max_latency_card.value_label.text(), "20.00 ms")
        self.response(token, [sample(None, "ERROR"), sample(None, "OFFLINE")])
        self.assertEqual(self.detail.average_latency_card.value_label.text(), "--")
        self.assertEqual(len(self.detail.latency_chart.chart.series()), 0)

    def test_full_period_summary_survives_downsampling(self):
        self.detail.set_device(self.device("192.0.2.1"))
        token = self.requests[-1][2]
        self.detail._probe_history_context_received("192.0.2.1", token, {
            "history": [sample(10), sample(20)],
            "total_samples": 2000,
            "summary": {
                "average_latency_ms": 16,
                "minimum_latency_ms": 5,
                "maximum_latency_ms": 30,
                "loss_percent": 2,
            },
        })
        self.assertEqual(self.detail.average_latency_card.value_label.text(), "16.00 ms")
        self.assertEqual(self.detail.min_latency_card.value_label.text(), "5.00 ms")
        self.assertEqual(self.detail.max_latency_card.value_label.text(), "30.00 ms")

    def test_real_zero_remains_valid_in_detail(self):
        self.detail.set_device(self.device("192.0.2.1"))
        self.response(self.requests[-1][2], [sample(0), sample(0.5), sample(1)])
        self.assertEqual(self.detail.average_latency_card.value_label.text(), "0.50 ms")
        self.assertEqual(self.detail.min_latency_card.value_label.text(), "0.00 ms")

    def test_close_reopen_ten_times_without_timers_or_callbacks(self):
        self.detail.set_device(self.device("192.0.2.1"))
        first = self.requests[-1][2]
        timer_count = len(self.detail.findChildren(QTimer))
        self.assertEqual(timer_count, 1)
        for _ in range(10):
            self.detail.close()
            self.app.processEvents()
            self.assertFalse(self.detail.incident_timer.isActive())
            self.detail._probe_history_context_received(
                "192.0.2.1", first, {"history": [sample(99)]}
            )
            self.assertEqual(self.detail.average_latency_card.value_label.text(), "--")
            self.detail.show()
            self.detail.set_device(self.device("192.0.2.1"))
            self.app.processEvents()
            self.assertTrue(self.detail.incident_timer.isActive())
            self.assertEqual(len(self.detail.findChildren(QTimer)), timer_count)
        self.assertEqual(len(self.requests), 11)


class ClientCompatibilityTests(QtCase):
    def test_legacy_and_context_signals_share_one_request(self):
        client = ApiClient()
        pending = []
        legacy = []
        correlated = []
        client._get = lambda path, handler: pending.append((path, handler))
        client._read_reply = lambda reply: {"history": [sample(4)], "summary": {}}
        client.probe_history_received.connect(lambda ip, data: legacy.append((ip, data)))
        client.probe_history_context_received.connect(
            lambda ip, token, data: correlated.append((ip, token, data))
        )

        class Reply:
            def deleteLater(self):
                pass

        client.get_probe_history("192.0.2.1", request_token=(1, "192.0.2.1", 60))
        self.assertEqual(len(pending), 1)
        pending[0][1](Reply())
        self.assertEqual(len(legacy), 1)
        self.assertEqual(len(correlated), 1)
        self.assertEqual(correlated[0][1], (1, "192.0.2.1", 60))
        self.assertEqual(legacy[0][1], correlated[0][2])
        client.get_probe_history("192.0.2.2")
        pending[1][1](Reply())
        self.assertEqual(len(legacy), 2)
        self.assertEqual(len(correlated), 1)

        client._read_reply = lambda reply: None
        client.get_probe_history("192.0.2.3", request_token=(3, "192.0.2.3", 15))
        pending[2][1](Reply())
        self.assertEqual(len(legacy), 2)
        self.assertEqual(correlated[-1], ("192.0.2.3", (3, "192.0.2.3", 15), None))


class MainIntegrationTests(QtCase):
    def test_hidden_detail_does_not_fetch_again(self):
        main = MainWindow()
        main.device_catalog_timer.stop()
        main.detail_window.incident_timer.stop()
        device = {"ip": "192.0.2.1", "name": "A", "status": "ONLINE", "health": {}}
        requests = []
        main.detail_window.api.get_probe_history = (
            lambda ip, minutes=60, request_token=None:
            requests.append((ip, minutes, request_token))
        )
        main.detail_window.api.get_device_availability = lambda *a, **kw: None
        main.detail_window.api.get_device_incidents = lambda *a, **kw: None
        main.devices_by_ip = {device["ip"]: device}
        main._device_requested(device["ip"])
        self.app.processEvents()
        self.assertEqual(len(requests), 1)
        main.detail_window.close()
        main.current_detail_ip = device["ip"]
        main._update_devices([device])
        self.assertEqual(len(requests), 1)
        main._device_requested(device["ip"])
        self.assertEqual(len(requests), 2)
        main.detail_window.close()
        main.hide()


if __name__ == "__main__":
    unittest.main()
