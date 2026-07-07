from __future__ import annotations

COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "argentina": (-38.4161, -63.6167),
    "australia": (-25.2744, 133.7751),
    "brazil": (-14.235, -51.9253),
    "canada": (56.1304, -106.3468),
    "chile": (-35.6751, -71.543),
    "china": (35.8617, 104.1954),
    "egypt": (26.8206, 30.8025),
    "france": (46.2276, 2.2137),
    "germany": (51.1657, 10.4515),
    "india": (20.5937, 78.9629),
    "indonesia": (-0.7893, 113.9213),
    "iran": (32.4279, 53.688),
    "iraq": (33.2232, 43.6793),
    "ireland": (53.1424, -7.6921),
    "israel": (31.0461, 34.8516),
    "italy": (41.8719, 12.5674),
    "japan": (36.2048, 138.2529),
    "lebanon": (33.8547, 35.8623),
    "malaysia": (4.2105, 101.9758),
    "mexico": (23.6345, -102.5528),
    "netherlands": (52.1326, 5.2913),
    "nigeria": (9.082, 8.6753),
    "norway": (60.472, 8.4689),
    "pakistan": (30.3753, 69.3451),
    "philippines": (12.8797, 121.774),
    "poland": (51.9194, 19.1451),
    "qatar": (25.3548, 51.1839),
    "russia": (61.524, 105.3188),
    "saudi arabia": (23.8859, 45.0792),
    "singapore": (1.3521, 103.8198),
    "south africa": (-30.5595, 22.9375),
    "south korea": (35.9078, 127.7669),
    "spain": (40.4637, -3.7492),
    "syria": (34.8021, 38.9968),
    "taiwan": (23.6978, 120.9605),
    "thailand": (15.87, 100.9925),
    "turkey": (38.9637, 35.2433),
    "ukraine": (48.3794, 31.1656),
    "united arab emirates": (23.4241, 53.8478),
    "united kingdom": (55.3781, -3.436),
    "united states": (37.0902, -95.7129),
    "venezuela": (6.4238, -66.5897),
    "vietnam": (14.0583, 108.2772),
}

COUNTRY_ALIASES = {
    "us": "united states",
    "usa": "united states",
    "u.s.": "united states",
    "u.s.a.": "united states",
    "america": "united states",
    "uk": "united kingdom",
    "u.k.": "united kingdom",
    "uae": "united arab emirates",
    "south korea": "south korea",
    "korea, south": "south korea",
    "russian federation": "russia",
}


def normalize_country(value: str | None) -> str | None:
    if not value:
        return None
    normalized = " ".join(value.strip().lower().replace("_", " ").split())
    return COUNTRY_ALIASES.get(normalized, normalized)


def country_centroid(country: str | None) -> tuple[float, float] | None:
    normalized = normalize_country(country)
    if not normalized:
        return None
    return COUNTRY_CENTROIDS.get(normalized)


def infer_country(text: str) -> str | None:
    haystack = text.lower()
    for country in COUNTRY_CENTROIDS:
        if country in haystack:
            return country
    for alias, country in COUNTRY_ALIASES.items():
        if alias in haystack:
            return country
    return None

