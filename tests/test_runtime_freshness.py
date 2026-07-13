from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from backend.app.market.freshness import validate_feature_freshness, validate_price_freshness


class RuntimeFreshnessTests(unittest.TestCase):
    def test_closed_recent_feature_is_accepted(self) -> None:
        now_ms = 1_800_000_000_000
        result = validate_feature_freshness(now_ms - 1_800_000, "15m", now_ms=now_ms)
        self.assertTrue(result["closed"])
        self.assertEqual(result["age_seconds"], 900)

    def test_open_or_stale_feature_is_rejected(self) -> None:
        now_ms = 1_800_000_000_000
        with self.assertRaisesRegex(ValueError, "open candle"):
            validate_feature_freshness(now_ms - 100_000, "15m", now_ms=now_ms)
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_feature_freshness(now_ms - 4_000_000, "15m", now_ms=now_ms)

    def test_stale_market_price_is_rejected(self) -> None:
        now = datetime.now(timezone.utc)
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_price_freshness((now - timedelta(minutes=6)).isoformat(), now=now)


if __name__ == "__main__":
    unittest.main()
