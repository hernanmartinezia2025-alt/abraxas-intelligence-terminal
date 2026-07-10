from __future__ import annotations

from collections import defaultdict
from typing import Any


def _latest_by_symbol(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest.setdefault(str(row["symbol"]), row)
    return list(latest.values())


def _regime(value: int) -> tuple[str, str, str, list[str]]:
    if value <= 24:
        return (
            "FUD_EXTREME",
            "FUD extremo",
            "Vigilar acumulacion, no perseguir una caida.",
            [
                "Esperar estabilizacion y confirmar estructura en el chart.",
                "Revisar el riesgo por activo antes de cualquier entrada escalonada.",
            ],
        )
    if value <= 44:
        return (
            "FUD",
            "Miedo predominante",
            "Mercado defensivo: priorizar confirmacion sobre anticipacion.",
            [
                "No asumir rebote solo por sentimiento.",
                "Comparar amplitud, volumen y riesgo individual.",
            ],
        )
    if value <= 55:
        return (
            "NEUTRAL",
            "Sentimiento equilibrado",
            "No hay extremo de sentimiento que altere el plan por si solo.",
            [
                "Usar la estructura y el riesgo del activo como decision principal.",
                "Evitar convertir una lectura neutral en una tesis direccional.",
            ],
        )
    if value <= 74:
        return (
            "FOMO",
            "Apetito de riesgo elevado",
            "No perseguir extension; vigilar disciplina de salida y riesgo.",
            [
                "Validar que el movimiento no dependa de un solo activo.",
                "Revisar niveles de toma parcial definidos por el plan, no por impulso.",
            ],
        )
    return (
        "FOMO_EXTREME",
        "FOMO extremo",
        "Riesgo de euforia: proteger ganancias y no ampliar riesgo por impulso.",
        [
            "No convertir una subida extendida en una entrada tardia.",
            "Revisar reduccion de riesgo solo segun el plan y los limites vigentes.",
        ],
    )


def build_sentiment_analysis(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Build an auditable market-sentiment readout from stored radar snapshots."""
    assets = _latest_by_symbol(rows)
    if not assets:
        return None

    current = assets[0]
    value = int(current["fear_greed_value"])
    regime, title, guidance, checklist = _regime(value)
    changes = [float(row["change_24h"] or 0) for row in assets]
    positive = sum(change > 0 for change in changes)
    negative = sum(change < 0 for change in changes)
    unchanged = len(changes) - positive - negative
    average_change = sum(changes) / len(changes) if changes else 0.0
    total_volume = sum(float(row.get("volume_24h") or 0) for row in assets)
    high_risk = sum(1 for row in assets if str(row.get("risk_level") or "").startswith("HIGH"))

    by_timestamp: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        by_timestamp[str(row["timestamp"])].append(int(row["fear_greed_value"]))
    samples = [
        {"timestamp": timestamp, "value": round(sum(values) / len(values)), "label": None}
        for timestamp, values in by_timestamp.items()
    ]
    samples.sort(key=lambda sample: sample["timestamp"], reverse=True)
    history = samples[:7]
    previous_value = history[1]["value"] if len(history) > 1 else None

    return {
        "source": "Alternative.me Fear & Greed + SQLite market_snapshots",
        "value": value,
        "label": str(current["fear_greed_label"]),
        "regime": regime,
        "title": title,
        "guidance": guidance,
        "checklist": checklist,
        "market_breadth": {
            "tracked_assets": len(assets),
            "positive": positive,
            "negative": negative,
            "unchanged": unchanged,
            "average_change_24h": round(average_change, 4),
            "positive_share": round((positive / len(assets)) * 100, 2) if assets else 0.0,
            "total_volume_24h": round(total_volume, 2),
            "high_risk": high_risk,
        },
        "history": history,
        "previous_value": previous_value,
        "history_note": (
            "El indice se publica diariamente; los snapshots intradia pueden repetir el mismo valor."
        ),
        "horizons": [
            {"key": "1h", "label": "1 hora", "status": "unavailable", "reason": "Alternative.me no publica esta granularidad."},
            {"key": "4h", "label": "4 horas", "status": "unavailable", "reason": "Alternative.me no publica esta granularidad."},
            {"key": "1d", "label": "Diario", "status": "available", "reason": "Fuente actual: Alternative.me."},
        ],
    }
