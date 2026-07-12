import unittest

from backend.app.analytics.performance import calculate_performance_metrics


class PerformanceAnalyticsTests(unittest.TestCase):
    def test_period_metrics_are_finite_and_explicit(self) -> None:
        equities = [100, 102, 101, 104, 103, 108]
        curve = [
            {"timestamp": index * 86_400_000, "equity": equity}
            for index, equity in enumerate(equities)
        ]
        metrics = calculate_performance_metrics(curve, "1d")
        self.assertEqual(metrics["status"], "ready")
        self.assertEqual(metrics["methodology"], "period_returns")
        self.assertEqual(metrics["period_samples"], 5)
        self.assertEqual(metrics["period_win_rate_pct"], 60.0)
        self.assertIsNotNone(metrics["sharpe_ratio"])
        self.assertIsNotNone(metrics["sortino_ratio"])
        self.assertLess(metrics["period_cvar_95_pct"], 0)
        self.assertGreater(metrics["ulcer_index_pct"], 0)

    def test_insufficient_curve_does_not_invent_metrics(self) -> None:
        metrics = calculate_performance_metrics([{"timestamp": 1, "equity": 100}], "15m")
        self.assertEqual(metrics["status"], "insufficient_data")
        self.assertNotIn("sharpe_ratio", metrics)


if __name__ == "__main__":
    unittest.main()
