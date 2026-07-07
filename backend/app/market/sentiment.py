from __future__ import annotations

import requests

from backend.app.core.config import REQUEST_TIMEOUT

FNG_URL = "https://api.alternative.me/fng/"


def fetch_fear_greed() -> dict:
    response = requests.get(FNG_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()["data"][0]
    return {
        "value": int(data["value"]),
        "label": data["value_classification"],
    }