from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "abraxas.db"

DEFAULT_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "TONUSDT",
    "DOTUSDT",
    "MATICUSDT",
]
DEFAULT_INTERVAL = "15m"
REQUEST_TIMEOUT = 12

DATA_DIR.mkdir(exist_ok=True)
