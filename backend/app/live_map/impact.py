from __future__ import annotations

import re
from collections import OrderedDict

IMPACT_RULES: list[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = [
    (
        ("oil", "energy", "hormuz", "opec", "refinery", "crude", "lng", "pipeline"),
        ("OIL", "BRENT", "XLE", "NATGAS"),
        ("energy", "commodities"),
    ),
    (
        ("war", "conflict", "missile", "invasion", "strike", "military", "attack"),
        ("VIX", "GOLD", "OIL", "SPY"),
        ("geopolitics", "risk"),
    ),
    (
        ("sanctions", "trade war", "tariff", "embargo"),
        ("DXY", "GOLD", "OIL", "SPY"),
        ("policy", "trade"),
    ),
    (
        ("chips", "taiwan", "semiconductor", "tsmc", "chipmaker"),
        ("NVDA", "SMH", "TSM", "QQQ"),
        ("semiconductors", "supply-chain"),
    ),
    (
        ("ai", "datacenter", "data center", "compute", "gpu", "nuclear power"),
        ("NVDA", "SMH", "XLK", "URA", "NATGAS"),
        ("ai-infrastructure", "power-demand"),
    ),
    (
        ("cyberattack", "cyber attack", "ransomware", "hack", "data breach"),
        ("BTC", "QQQ", "CYBERSECURITY"),
        ("cybersecurity", "digital-risk"),
    ),
    (
        ("earthquake", "tsunami", "wildfire", "flood", "cyclone", "volcano", "disaster"),
        (),
        ("disaster", "supply-risk"),
    ),
    (
        ("central bank", "inflation", "rates", "rate hike", "monetary policy", "fed", "ecb"),
        ("DXY", "GOLD", "TLT", "SPY", "BTC"),
        ("macro", "rates"),
    ),
    (
        ("shipping", "red sea", "suez", "panama canal", "port", "freight"),
        ("OIL", "BRENT", "SPY", "DXY"),
        ("shipping", "supply-chain"),
    ),
]

ENERGY_REGIONS = (
    "iran",
    "iraq",
    "saudi arabia",
    "qatar",
    "united arab emirates",
    "hormuz",
    "gulf",
    "texas",
    "venezuela",
    "norway",
)


def contains_keyword(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None


def map_event_impact(title: str, summary: str = "") -> tuple[list[str], list[str]]:
    text = f"{title} {summary}".lower()
    assets: OrderedDict[str, None] = OrderedDict()
    tags: OrderedDict[str, None] = OrderedDict()

    for keywords, mapped_assets, mapped_tags in IMPACT_RULES:
        if any(contains_keyword(text, keyword) for keyword in keywords):
            for asset in mapped_assets:
                assets[asset] = None
            for tag in mapped_tags:
                tags[tag] = None

    if any(contains_keyword(text, word) for word in ("earthquake", "disaster", "wildfire", "flood")) and any(
        contains_keyword(text, region) for region in ENERGY_REGIONS
    ):
        for asset in ("OIL", "NATGAS"):
            assets[asset] = None
        tags["energy-region"] = None

    return list(assets.keys()), list(tags.keys())


def classify_news_severity(title: str, summary: str = "") -> str:
    text = f"{title} {summary}".lower()
    critical_terms = ("nuclear", "missile strike", "invasion", "major cyberattack", "state of emergency")
    high_terms = ("war", "conflict", "sanctions", "cyberattack", "central bank", "inflation", "hormuz")
    medium_terms = ("oil", "energy", "ai", "chips", "semiconductor", "shipping", "protest")

    if any(contains_keyword(text, term) for term in critical_terms):
        return "critical"
    if any(contains_keyword(text, term) for term in high_terms):
        return "high"
    if any(contains_keyword(text, term) for term in medium_terms):
        return "medium"
    return "low"
