from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import bots, candles, chart_indicators, data_center, exchanges, features, health, liquidity_sweep, live_map, market_universe, microstructure, order_book, paper, radar, regime, risk, spot_portfolio, statistics
from backend.app.storage.sqlite import initialize_database
from backend.app.services.microstructure_collector import collector, reconcile_collector_state

app = FastAPI(title="ABRAXAS Intelligence Terminal API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_origin_regex=r"^http://(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+):5173$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(bots.router)
app.include_router(radar.router)
app.include_router(candles.router)
app.include_router(chart_indicators.router)
app.include_router(order_book.router)
app.include_router(liquidity_sweep.router)
app.include_router(microstructure.router)
app.include_router(market_universe.router)
app.include_router(live_map.router)
app.include_router(statistics.router)
app.include_router(data_center.router)
app.include_router(features.router)
app.include_router(regime.router)
app.include_router(risk.router)
app.include_router(paper.router)
app.include_router(spot_portfolio.router)
app.include_router(exchanges.router)


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    reconcile_collector_state()


@app.on_event("shutdown")
async def shutdown() -> None:
    await collector.stop(reason="backend_shutdown")
