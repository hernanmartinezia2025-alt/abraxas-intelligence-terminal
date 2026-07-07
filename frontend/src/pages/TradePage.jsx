import React, { useState } from "react";
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

function orderRows(price, side) {
  const base = Number(price || 100);
  return Array.from({ length: 8 }).map((_, index) => {
    const step = (index + 1) * 0.0018;
    const level = side === "ask" ? base * (1 + step) : base * (1 - step);
    const size = 0.42 + index * 0.17;
    return { level, size };
  });
}

export default function TradePage({ rows, selectedSymbol = "BTCUSDT", onSelectSymbol }) {
  const [interval, setInterval] = useState("15m");
  const assets = latestRows(rows);
  const active = assets.find((asset) => asset.symbol === selectedSymbol) || assets[0];
  const asks = orderRows(active?.price, "ask").reverse();
  const bids = orderRows(active?.price, "bid");

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
              <h2>{active?.symbol || "BTCUSDT"}</h2>
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
            <MarketChart interval={interval} symbol={active?.symbol || selectedSymbol} />
          </div>
        </section>

        <aside className="trade-side-stack">
          <section className="exchange-panel order-book">
            <div className="exchange-panel-head compact">
              <div>
                <p className="eyebrow">Order book</p>
                <h2>Depth</h2>
              </div>
            </div>
            <div className="book-table">
              {asks.map((row) => (
                <div className="book-row ask" key={`ask-${row.level}`}>
                  <span>{formatPrice(row.level)}</span>
                  <b>{row.size.toFixed(3)}</b>
                </div>
              ))}
              <div className="mid-price">${formatPrice(active?.price)}</div>
              {bids.map((row) => (
                <div className="book-row bid" key={`bid-${row.level}`}>
                  <span>{formatPrice(row.level)}</span>
                  <b>{row.size.toFixed(3)}</b>
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
