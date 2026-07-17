from __future__ import annotations

import re

from backend.app.analytics.chart_indicators import compute_indicator
from backend.app.services.candle_service import get_candles
from backend.app.storage.chart_indicators import (
    archive_indicator_preset,
    list_indicator_presets,
    save_indicator_preset,
)

SUPPORTED_KINDS = {"sma", "ema", "bollinger"}
DEFAULT_COLORS = {"sma": "#dfc079", "ema": "#7aa7ff", "bollinger": "#9a8cff"}
IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_indicators(indicators: list[dict]) -> list[dict]:
    if not 1 <= len(indicators) <= 8:
        raise ValueError("A chart workspace requires between 1 and 8 indicators.")
    normalized: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(indicators):
        kind = str(item.get("kind") or "").lower().strip()
        if kind not in SUPPORTED_KINDS:
            raise ValueError(f"Unsupported indicator kind: {kind or 'empty'}.")
        period = int(item.get("period") or 0)
        if not 2 <= period <= 500:
            raise ValueError("Indicator period must be between 2 and 500.")
        identifier = str(item.get("id") or f"{kind}-{period}-{index + 1}").lower().strip()
        if not IDENTIFIER_PATTERN.fullmatch(identifier):
            raise ValueError(f"Invalid indicator id: {identifier}.")
        if identifier in seen:
            raise ValueError(f"Duplicate indicator id: {identifier}.")
        seen.add(identifier)
        color = str(item.get("color") or DEFAULT_COLORS[kind])
        if not COLOR_PATTERN.fullmatch(color):
            raise ValueError(f"Invalid indicator color: {color}.")
        raw_deviation = item.get("deviation")
        deviation = 2.0 if raw_deviation is None else float(raw_deviation)
        if kind == "bollinger" and not 0.1 <= deviation <= 10:
            raise ValueError("Bollinger deviation must be between 0.1 and 10.")
        label = str(item.get("label") or f"{kind.upper()} {period}").strip()[:80]
        normalized.append(
            {
                "id": identifier,
                "kind": kind,
                "period": period,
                "deviation": deviation,
                "color": color.lower(),
                "line_width": max(1, min(int(item.get("line_width", 2)), 4)),
                "label": label,
                "visible": bool(item.get("visible", True)),
            }
        )
    return normalized


def compute_chart_workspace(
    symbol: str,
    timeframe: str,
    limit: int,
    indicators: list[dict],
) -> dict:
    normalized_symbol = symbol.upper().strip()
    normalized = normalize_indicators(indicators)
    required = max(item["period"] for item in normalized)
    if limit < required + 5:
        raise ValueError(f"limit must be at least {required + 5} for the requested indicators.")
    candle_payload = get_candles(normalized_symbol, timeframe, limit)
    candles = candle_payload.get("candles") or []
    if len(candles) < required:
        raise ValueError(f"Only {len(candles)} candles are available; {required} are required.")
    return {
        "contract": "chart_indicator_workspace_v1",
        "symbol": normalized_symbol,
        "timeframe": timeframe,
        "candle_count": len(candles),
        "served_from": candle_payload.get("served_from"),
        "indicators": [compute_indicator(candles, item) for item in normalized if item["visible"]],
        "normalized_config": normalized,
        "claim_boundary": (
            "Visual indicator series calculated deterministically from the returned OHLCV window. "
            "The current open candle may change; these series do not create bot signals or orders."
        ),
        "execution_created": False,
    }


def save_workspace_preset(name: str, symbol: str, timeframe: str, indicators: list[dict]) -> dict:
    normalized_name = name.strip()
    if not 3 <= len(normalized_name) <= 80:
        raise ValueError("Preset name must contain between 3 and 80 characters.")
    normalized = normalize_indicators(indicators)
    return save_indicator_preset(normalized_name, symbol.upper().strip(), timeframe, normalized)


def workspace_presets(symbol: str = "", timeframe: str = "", include_archived: bool = False) -> dict:
    presets = list_indicator_presets(symbol, timeframe, include_archived)
    return {"contract": "chart_indicator_presets_v1", "count": len(presets), "presets": presets}


def archive_workspace_preset(preset_id: int) -> dict:
    return archive_indicator_preset(preset_id)
