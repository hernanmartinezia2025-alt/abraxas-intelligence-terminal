# ABRAXAS Intelligence Terminal

Clean V1 codebase for ABRAXAS.

ABRAXAS is a local market intelligence terminal. It observes markets, stores local snapshots, computes simple signals and prepares a clean foundation for charts, strategy research, live world events, context vectors and data health.

It does not predict prices, recommend investments or execute real orders.

## Run Backend

```powershell
cd "C:\Users\marti\OneDrive\Escritorio\PROGRAMACION\New folder\abraxas-intelligence-terminal"
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Health:

```text
http://127.0.0.1:8000/api/health
```

Live Map:

```text
http://127.0.0.1:8000/api/live-map/events
http://127.0.0.1:8000/api/live-map/news
http://127.0.0.1:8000/api/live-map/alerts
http://127.0.0.1:8000/api/live-map/health
```

Statistics:

```text
http://127.0.0.1:8000/api/statistics?symbol=BTCUSDT&interval=15m
http://127.0.0.1:8000/api/statistics/summary?symbol=BTCUSDT&interval=15m
http://127.0.0.1:8000/api/statistics/monte-carlo?symbol=BTCUSDT&interval=15m
http://127.0.0.1:8000/api/statistics/runs?symbol=BTCUSDT&timeframe=15m
```

Data API Center:

```text
http://127.0.0.1:8000/api/data/catalog
http://127.0.0.1:8000/api/data/sources
http://127.0.0.1:8000/api/data/health
http://127.0.0.1:8000/api/data/datasets
```

Feature Store:

```text
http://127.0.0.1:8000/api/features?symbol=BTCUSDT&timeframe=15m
POST http://127.0.0.1:8000/api/features/build?symbol=BTCUSDT&timeframe=15m
```

Regime Engine:

```text
http://127.0.0.1:8000/api/regime?symbol=BTCUSDT&timeframe=15m
http://127.0.0.1:8000/api/regime/snapshots?symbol=BTCUSDT&timeframe=15m
```

## Run Frontend

```powershell
cd "C:\Users\marti\OneDrive\Escritorio\PROGRAMACION\New folder\abraxas-intelligence-terminal\frontend"
npm.cmd install
npm.cmd run dev
```

Open:

```text
http://127.0.0.1:5173/
```

Live Map:

```text
http://127.0.0.1:5173/#map
```

## Active Modules

- `backend/app/api/routes`: HTTP route modules.
- `backend/app/services`: orchestration logic.
- `backend/app/market`: public market data clients and signal rules.
- `backend/app/analytics`: pandas/numpy statistical calculations.
- `backend/app/live_map`: GDELT, USGS and GDACS clients plus event impact mapping.
- `backend/app/storage`: SQLite schema and connection.
- `backend/app/services/data_center_service.py`: Data API Center catalog, source health and analytical dataset registry.
- `frontend/src/features`: product modules.
- `frontend/src/components`: shared UI.

## Data API Center

The Data page now reads real backend metadata:

- API/source registry
- SQLite health
- dataset catalog
- row counts
- last timestamps
- PowerBI readiness
- future bot feature-store readiness

Candles requested through `/api/candles` are persisted into SQLite table `market_candles`. If the live Binance request fails and local candles exist, the API can serve the cached candles instead of returning an empty chart.

The same candle flow also generates `asset_features` when enough candles exist. These are numeric bot-ready features such as returns, volatility, z-score, drawdown, trend strength, volume change, risk score and regime label.

The Regime Engine reads `asset_features`, classifies current market state and stores auditable `regime_snapshots`.

The intended flow is:

```text
external APIs -> normalization -> SQLite/cache -> analytical datasets -> frontend/bots/PowerBI
```

## Statistical Intelligence

The Research page includes a first statistical layer:

- return distribution
- volatility
- z-score
- drawdown
- Value at Risk approximation
- Gaussian curve
- Monte Carlo scenarios
- ABRAXAS plain-language reading
- auditable `statistics_runs` stored in SQLite

These calculations are observational. They do not predict prices or recommend trades.

## Live World Map

The Live Map uses public/free sources:

- GDELT for market-relevant geolocated news when the public API allows requests.
- USGS GeoJSON feeds for earthquakes.
- GDACS RSS/GeoRSS for global disaster alerts.

Events are cached locally in SQLite tables `live_events` and `live_source_health`. GDELT may temporarily return rate-limit errors; source health reports that without breaking the map.

## No Legacy

This folder intentionally does not copy the V0 monolith, Streamlit UI, local database, venv, node_modules or generated dist files.
