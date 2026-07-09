import React, { useEffect, useState } from "react";
import { getOrderBook } from "../api/client.js";
import MarketChart from "../features/charts/MarketChart.jsx";
import { latestRows } from "../utils/assets.js";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h"];

function formatPrice(value) {
  return Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPercent(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function formatQuantity(value) {
  return Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 3, maximumFractionDigits: 6 });
}

function formatClock(value) {
  if (!value) return "--";
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function TradePage({ rows, selectedSymbol = "BTCUSDT", onSelectSymbol }) {
  const [interval, setInterval] = useState("15m");
  const [orderBook, setOrderBook] = useState(null);
  const [bookLoading, setBookLoading] = useState(false);
  const [bookError, setBookError] = useState("");
  const assets = latestRows(rows);
  const active = assets.find((asset) => asset.symbol === selectedSymbol) || assets[0];
  const activeSymbol = active?.symbol || selectedSymbol || "BTCUSDT";
  const asks = (orderBook?.asks || []).slice(0, 8).reverse();
  const bids = (orderBook?.bids || []).slice(0, 8);
  const midPrice = orderBook?.mid_price || active?.price;

  async function loadOrderBook({ silent = false } = {}) {
    if (!silent) setBookLoading(true);
    setBookError("");
    try {
      const payload = await getOrderBook(activeSymbol, 20);
      setOrderBook(payload);
    } catch (err) {
      setBookError(err.message);
    } finally {
      if (!silent) setBookLoading(false);
    }
  }

  useEffect(() => {
    setOrderBook(null);
    loadOrderBook();
    const timer = window.setInterval(() => {
      loadOrderBook({ silent: true });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activeSymbol]);

  return (
    <section className="trade-page">
      <div className="market-strip">
        {assets.map((asset) => {
          const change = Number(asset.change_24h || 0);
          const tone = change >= 0 ? "positive" : "negative";
          return (
            <button
              className={`market-chip ${tone} ${asset.symbol === active?.symbol ? "active" : ""}`}
              key={asset.symbol}
              onClick={() => onSelectSymbol?.(asset.symbol)}
              type="button"
            >
              <span>{asset.symbol}</span>
              <strong>${formatPrice(asset.price)}</strong>
              <b>{formatPercent(change)}</b>
            </button>
          );
        })}
      </div>

      <div className="trade-grid">
        <section className="exchange-panel trade-chart">
          <div className="exchange-panel-head">
            <div>
              <p className="eyebrow">Spot chart</p>
              <h2>{activeSymbol}</h2>
            </div>
            <div className="timeframe-row">
              {TIMEFRAMES.map((timeframe) => (
                <button
                  className={interval === timeframe ? "active" : ""}
                  key={timeframe}
                  onClick={() => setInterval(timeframe)}
                  type="button"
                >
                  {timeframe}
                </button>
              ))}
            </div>
          </div>
          <div className="panel-body">
            <MarketChart interval={interval} symbol={activeSymbol} />
          </div>
        </section>

        <aside className="trade-side-stack">
          <section className="exchange-panel order-book">
            <div className="exchange-panel-head compact">
              <div>
                <p className="eyebrow">Live order book</p>
                <h2>Binance Depth</h2>
              </div>
              <span>{bookLoading ? "loading" : `REST ${formatClock(orderBook?.fetched_at)}`}</span>
            </div>
            <div className="book-table">
              {bookError && <div className="book-state error">{bookError}</div>}
              {!bookError && !asks.length && !bids.length && <div className="book-state">Cargando profundidad real...</div>}
              {asks.map((row) => (
                <div className="book-row ask" key={`ask-${row.price}`}>
                  <span>{formatPrice(row.price)}</span>
                  <b>{formatQuantity(row.quantity)}</b>
                </div>
              ))}
              <div className="mid-price">
                <span>${formatPrice(midPrice)}</span>
                {orderBook?.spread_percent !== null && orderBook?.spread_percent !== undefined && (
                  <small>spread {orderBook.spread_percent.toFixed(4)}%</small>
                )}
              </div>
              {bids.map((row) => (
                <div className="book-row bid" key={`bid-${row.price}`}>
                  <span>{formatPrice(row.price)}</span>
                  <b>{formatQuantity(row.quantity)}</b>
                </div>
              ))}
            </div>
          </section>

          <section className="exchange-panel ticket-panel">
            <div className="exchange-panel-head compact">
              <div>
                <p className="eyebrow">Observation</p>
                <h2>No execution</h2>
              </div>
            </div>
            <div className="ticket-body">
              <label>
                Asset
                <strong>{active?.symbol || "--"}</strong>
              </label>
              <label>
                Risk
                <strong>{active?.risk_level || "NORMAL"}</strong>
              </label>
              <p>{active?.abraxas_reading || "Actualiza mercado para cargar la lectura operativa."}</p>
            </div>
          </section>
        </aside>

        <section className="exchange-panel tape-panel">
          <div className="exchange-panel-head compact">
            <div>
              <p className="eyebrow">Market tape</p>
              <h2>Readings</h2>
            </div>
          </div>
          <div className="tape-list">
            {assets.map((asset) => (
              <article key={asset.symbol}>
                <b>{asset.symbol}</b>
                <span>{asset.abraxas_reading}</span>
              </article>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
