# ABRAXAS Intelligence Terminal V1 Blueprint

## Decision

V1 starts clean. The old project remains as `v0-prototype` knowledge, not as the codebase to keep patching.

The goal is not to make ABRAXAS smaller in ambition. The goal is to make the codebase smaller, clearer and more durable.

## Product Core

ABRAXAS is a local market intelligence terminal.

It observes markets, stores local data, computes simple signals, studies context and lets the user test hypotheses. It does not predict prices, recommend investments or execute real orders.

## What V1 Keeps

- Market Radar: snapshots, simple risk labels and ABRAXAS readings.
- Charts: candles, volume and basic indicators.
- Statistics: returns, volatility, z-score, drawdown and probability studies.
- Strategy Lab: rules, simple backtests and reports.
- Asset Universe: multiple assets and sources.
- Context Vectors: macro/historical narratives and manual research notes.
- Tools: Pine export, health checks and reports.

## What V1 Does Not Copy

- Streamlit UI.
- Frontend monolith.
- Giant `api.py` with all routes mixed.
- Agent-framework naming or abstractions.
- News/AI/order execution/private keys.
- Large legacy folders, venv, node_modules, dist, local DB files.

## Backend Architecture

```text
backend/app/
  main.py                  FastAPI app factory/import point
  api/routes/              thin HTTP route modules
  core/config.py           paths, settings and constants
  storage/sqlite.py        SQLite connection and schema
  market/binance.py        Binance public API client
  market/sentiment.py      Fear & Greed public API client
  market/signals.py        deterministic signal rules
  services/radar_service.py orchestration for radar snapshots
  services/candle_service.py candle retrieval and normalization
```

Rules:

- Routes should be thin.
- Services coordinate work.
- Market modules fetch external public data.
- Storage module owns SQLite schema and persistence.
- No absolute paths.
- No API keys in code.

## Frontend Architecture

```text
frontend/src/
  main.jsx
  App.jsx
  api/client.js
  components/
  features/radar/
  features/charts/
  features/strategy/
  features/context/
  features/data/
```

Rules:

- No giant `App.jsx`.
- Every product area gets its own feature folder.
- API calls stay in `api/client.js`.
- Shared UI lives in `components/`.
- Styling stays predictable and product-focused.

## First Milestone

A clean V1 shell should run with:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

and:

```powershell
cd frontend
npm.cmd run dev
```

Minimum endpoints:

- `GET /api/health`
- `GET /api/radar`
- `POST /api/radar/update`
- `GET /api/candles`

## Migration Rule

Only migrate code from V0 when it satisfies one of these:

- It is already proven and small.
- It has a clear owner module in V1.
- It can be tested or manually verified quickly.
- It does not bring UI or architecture debt with it.

If a V0 function is useful but messy, rewrite it from the idea, not by copy-paste.