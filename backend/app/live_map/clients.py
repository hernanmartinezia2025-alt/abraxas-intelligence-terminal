from __future__ import annotations

import hashlib
import html
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests

from backend.app.core.config import REQUEST_TIMEOUT
from backend.app.live_map.geo import country_centroid, infer_country, normalize_country
from backend.app.live_map.impact import classify_news_severity, map_event_impact

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
USGS_EARTHQUAKES_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
GDACS_RSS_URL = "https://www.gdacs.org/xml/rss.xml"

GDELT_QUERY = "(oil OR energy OR sanctions OR Taiwan OR Ukraine OR Iran OR inflation OR cyberattack)"

HEADERS = {"User-Agent": "ABRAXAS-Market-Radar/1.0 local research"}
GDACS_NS = {
    "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
    "georss": "http://www.georss.org/georss",
    "gdacs": "http://www.gdacs.org",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def stable_id(source: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:20]
    return f"{source}:{digest}"


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(without_tags).split())


def parse_datetime(value: Any) -> datetime:
    if value is None:
        return utc_now()
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, timezone.utc)

    text = str(value).strip()
    if not text:
        return utc_now()
    if text.isdigit():
        return parse_datetime(int(text))

    for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        pass

    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return utc_now()


def freshness_minutes(published_at: datetime) -> int:
    return max(0, int((utc_now() - published_at).total_seconds() // 60))


def country_label(country: str | None) -> str | None:
    normalized = normalize_country(country)
    if not normalized:
        return None
    return normalized.title()


def coordinates_for_news(article: dict, title: str) -> tuple[float | None, float | None, str | None]:
    raw_country = article.get("sourcecountry") or article.get("sourceCountry")
    country = normalize_country(raw_country) or infer_country(title)
    centroid = country_centroid(country)
    if not centroid:
        return None, None, country_label(country)
    lat, lon = centroid
    return lat, lon, country_label(country)


def fetch_gdelt_news(limit: int = 60) -> list[dict]:
    response = requests.get(
        GDELT_DOC_URL,
        params={
            "query": GDELT_QUERY,
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(limit),
            "sort": "date",
            "timespan": "24h",
        },
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    if "json" not in (response.headers.get("content-type") or "").lower():
        raise RuntimeError(f"GDELT returned non-JSON response: {response.text[:160]}")
    payload = response.json()
    articles = payload.get("articles", []) if isinstance(payload, dict) else []
    events = []

    for article in articles[:limit]:
        title = clean_text(article.get("title")) or "GDELT news item"
        url = article.get("url") or article.get("url_mobile") or ""
        published = parse_datetime(article.get("seendate") or article.get("date"))
        lat, lon, country = coordinates_for_news(article, title)
        if lat is None or lon is None:
            continue

        summary = clean_text(article.get("summary")) or title
        related_assets, vector_tags = map_event_impact(title, summary)
        event = {
            "id": stable_id("gdelt", url or title),
            "type": "news",
            "title": title,
            "summary": summary,
            "lat": lat,
            "lon": lon,
            "country": country,
            "source": "GDELT",
            "url": url,
            "severity": classify_news_severity(title, summary),
            "published_at": published.isoformat(),
            "freshness_minutes": freshness_minutes(published),
            "related_assets": related_assets,
            "vector_tags": vector_tags,
            "raw_url": GDELT_DOC_URL,
            "raw_payload": {
                "domain": article.get("domain"),
                "language": article.get("language"),
                "sourcecountry": article.get("sourcecountry"),
            },
        }
        events.append(event)

    return events


def earthquake_severity(magnitude: float) -> str:
    if magnitude >= 6.5:
        return "critical"
    if magnitude >= 5.5:
        return "high"
    if magnitude >= 4.5:
        return "medium"
    return "low"


def fetch_usgs_earthquakes(limit: int = 80) -> list[dict]:
    response = requests.get(USGS_EARTHQUAKES_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    events = []

    for feature in payload.get("features", [])[:limit]:
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            continue
        lon, lat = float(coordinates[0]), float(coordinates[1])
        magnitude = float(props.get("mag") or 0)
        place = clean_text(props.get("place")) or "Unknown location"
        published = parse_datetime(props.get("time"))
        title = f"M{magnitude:.1f} earthquake - {place}"
        depth = coordinates[2] if len(coordinates) > 2 else None
        summary = f"Magnitude {magnitude:.1f}. Depth {depth}km. {place}."
        country = place.split(",")[-1].strip() if "," in place else infer_country(place)
        related_assets, vector_tags = map_event_impact(title, summary)

        events.append(
            {
                "id": f"usgs:{feature.get('id') or stable_id('usgs', props.get('url') or title)}",
                "type": "earthquake",
                "title": title,
                "summary": summary,
                "lat": lat,
                "lon": lon,
                "country": country_label(country),
                "source": "USGS",
                "url": props.get("url") or "",
                "severity": earthquake_severity(magnitude),
                "published_at": published.isoformat(),
                "freshness_minutes": freshness_minutes(published),
                "related_assets": related_assets,
                "vector_tags": vector_tags or ["earthquake"],
                "raw_url": USGS_EARTHQUAKES_URL,
                "raw_payload": {"magnitude": magnitude, "place": place, "status": props.get("status")},
            }
        )

    return events


def gdacs_severity(alert_level: str | None, score: str | None) -> str:
    level = (alert_level or "").lower()
    if level == "red":
        return "critical"
    if level == "orange":
        return "high"
    if level == "green":
        return "low"
    try:
        numeric = float(score or 0)
    except ValueError:
        numeric = 0
    if numeric >= 3:
        return "high"
    if numeric >= 2:
        return "medium"
    return "low"


def parse_georss_point(value: str | None) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    parts = value.strip().split()
    if len(parts) < 2:
        return None, None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None, None


def fetch_gdacs_alerts(limit: int = 80) -> list[dict]:
    response = requests.get(GDACS_RSS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    events = []

    for item in root.findall("./channel/item")[:limit]:
        title = clean_text(item.findtext("title")) or "GDACS alert"
        description = clean_text(item.findtext("description"))
        url = item.findtext("link") or ""
        guid = item.findtext("guid") or url or title
        published = parse_datetime(item.findtext("pubDate"))
        point = item.findtext("georss:point", namespaces=GDACS_NS)
        lat, lon = parse_georss_point(point)
        if lat is None or lon is None:
            continue
        event_type = item.findtext("gdacs:eventtype", namespaces=GDACS_NS) or "DISASTER"
        alert_level = item.findtext("gdacs:alertlevel", namespaces=GDACS_NS)
        score = item.findtext("gdacs:alertscore", namespaces=GDACS_NS)
        country = infer_country(f"{title} {description}")
        related_assets, vector_tags = map_event_impact(title, description)
        vector_tags = list(dict.fromkeys([event_type.lower(), *vector_tags]))

        events.append(
            {
                "id": f"gdacs:{guid}",
                "type": "disaster",
                "title": title,
                "summary": description or title,
                "lat": lat,
                "lon": lon,
                "country": country_label(country),
                "source": "GDACS",
                "url": url,
                "severity": gdacs_severity(alert_level, score),
                "published_at": published.isoformat(),
                "freshness_minutes": freshness_minutes(published),
                "related_assets": related_assets,
                "vector_tags": vector_tags,
                "raw_url": GDACS_RSS_URL,
                "raw_payload": {"eventtype": event_type, "alertlevel": alert_level, "alertscore": score},
            }
        )

    return events


def timed_fetch(source: str, fetcher, max_stale_minutes: int) -> tuple[list[dict], dict]:
    started = time.perf_counter()
    try:
        events = fetcher()
        latency_ms = int((time.perf_counter() - started) * 1000)
        return events, {
            "source": source,
            "ok": True,
            "last_success_at": utc_now().isoformat(),
            "latency_ms": latency_ms,
            "event_count": len(events),
            "error": "",
            "max_stale_minutes": max_stale_minutes,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return [], {
            "source": source,
            "ok": False,
            "last_success_at": None,
            "latency_ms": latency_ms,
            "event_count": 0,
            "error": str(exc),
            "max_stale_minutes": max_stale_minutes,
        }
