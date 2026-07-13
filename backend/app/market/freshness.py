from __future__ import annotations

from datetime import datetime, timezone


TIMEFRAME_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
PRICE_MAX_AGE_SECONDS = 300
PROPOSAL_TTL_SECONDS = 300
MAX_PRICE_DRIFT_PCT = 2.0


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def validate_feature_freshness(timestamp_ms: int, timeframe: str, now_ms: int | None = None) -> dict:
    interval = TIMEFRAME_MS.get(timeframe)
    if not interval:
        raise ValueError(f"Unsupported timeframe freshness policy: {timeframe}")
    current = int(now_ms if now_ms is not None else utc_now().timestamp() * 1000)
    close_time = int(timestamp_ms) + interval
    if close_time > current:
        raise ValueError("Latest asset feature belongs to an open candle")
    age_ms = current - close_time
    max_age_ms = interval * 3
    if age_ms > max_age_ms:
        raise ValueError(f"Latest asset feature is stale ({age_ms // 1000}s old)")
    return {"closed": True, "age_seconds": age_ms // 1000, "max_age_seconds": max_age_ms // 1000}


def validate_price_freshness(timestamp: str, now: datetime | None = None) -> dict:
    age = max(0.0, ((now or utc_now()) - parse_timestamp(timestamp)).total_seconds())
    if age > PRICE_MAX_AGE_SECONDS:
        raise ValueError(f"Persisted market price is stale ({int(age)}s old)")
    return {"age_seconds": round(age, 2), "max_age_seconds": PRICE_MAX_AGE_SECONDS}
