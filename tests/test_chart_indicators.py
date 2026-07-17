from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.analytics.chart_indicators import (
    bollinger_bands,
    exponential_moving_average,
    simple_moving_average,
)
from backend.app.services.chart_indicator_service import save_workspace_preset
from backend.app.services.data_center_service import get_dataset_preview
from backend.app.storage import sqlite as storage_sqlite


def candles(values: list[float]) -> list[dict]:
    return [
        {"timestamp": 1_700_000_000_000 + index * 60_000, "close": value}
        for index, value in enumerate(values)
    ]


class ChartIndicatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = storage_sqlite.DB_PATH
        storage_sqlite.DB_PATH = Path(self.temp_dir.name) / "chart-indicators.db"
        storage_sqlite.initialize_database()

    def tearDown(self) -> None:
        storage_sqlite.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_indicators_are_deterministic_and_do_not_look_ahead(self) -> None:
        rows = candles([10, 11, 12, 13, 14, 15])
        sma = simple_moving_average(rows, 3)
        ema = exponential_moving_average(rows, 3)
        bands = bollinger_bands(rows, 3, 2)
        self.assertEqual([point["value"] for point in sma], [11.0, 12.0, 13.0, 14.0])
        self.assertEqual(ema[0]["value"], 11.0)
        self.assertEqual(len(bands["upper"]), 4)

        changed = candles([10, 11, 12, 13, 14, 150])
        changed_sma = simple_moving_average(changed, 3)
        self.assertEqual(sma[:-1], changed_sma[:-1])
        self.assertNotEqual(sma[-1]["value"], changed_sma[-1]["value"])

    def test_preset_versions_are_idempotent_and_visible_in_data_center(self) -> None:
        first = save_workspace_preset(
            "Trend desk",
            "BTCUSDT",
            "15m",
            [{"id": "ema-55", "kind": "ema", "period": 55, "color": "#7aa7ff"}],
        )
        repeated = save_workspace_preset(
            "Trend desk",
            "BTCUSDT",
            "15m",
            [{"id": "ema-55", "kind": "ema", "period": 55, "color": "#7aa7ff"}],
        )
        changed = save_workspace_preset(
            "Trend desk",
            "BTCUSDT",
            "15m",
            [{"id": "ema-89", "kind": "ema", "period": 89, "color": "#7aa7ff"}],
        )
        self.assertEqual(first["active_version"], 1)
        self.assertEqual(repeated["active_version"], 1)
        self.assertEqual(changed["active_version"], 2)

        preview = get_dataset_preview("chart_indicator_preset_versions", limit=10)
        self.assertTrue(preview["dataset"]["exists"])
        self.assertEqual(len(preview["rows"]), 2)


if __name__ == "__main__":
    unittest.main()
