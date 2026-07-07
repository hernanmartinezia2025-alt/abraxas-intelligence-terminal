import React from "react";
import { latestRows } from "../../utils/assets.js";

function formatPrice(value) {
  return Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatCompact(value) {
  return Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 0, notation: "compact" });
}

function formatPercent(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function marketState(rows) {
  if (!rows.length) return { label: "WAITING", tone: "neutral", detail: "sin snapshots", reading: "La terminal esta lista. Falta la primera lectura de mercado." };
  const avg = rows.reduce((sum, row) => sum + Number(row.change_24h || 0), 0) / rows.length;
  const extreme = rows.some((row) => String(row.risk_level || "").includes("HIGH"));
  if (extreme) return { label: "ACTIVE", tone: "warning", detail: "riesgo elevado", reading: "Hay energia en el mercado. Prioridad: observar confirmacion y no perseguir movimiento." };
  if (avg > 1.5) return { label: "BID", tone: "positive", detail: "sesgo comprador", reading: "La presion compradora domina el radar. Buscar estructura, no impulso desnudo." };
  if (avg < -1.5) return { label: "OFFER", tone: "negative", detail: "sesgo vendedor", reading: "La presion vendedora pesa. Cuidar entradas tempranas y mirar volumen." };
  return { label: "BALANCED", tone: "neutral", detail: "sin extremo", reading: "Mercado sin extremos claros. Ventaja en esperar, comparar y medir." };
}

function strongestMove(rows) {
  if (!rows.length) return null;
  return rows.reduce((best, row) => (Math.abs(Number(row.change_24h)) > Math.abs(Number(best.change_24h)) ? row : best), rows[0]);
}

function compactRisk(level) {
  const value = String(level || "NORMAL");
  if (value === "HIGH_EUPHORIA_RISK") return "EUPHORIA";
  if (value === "HIGH_FEAR_RISK") return "FEAR";
  if (value === "HIGH_VOLATILITY") return "VOLATILITY";
  return "NORMAL";
}

export default function RadarPanel({ rows }) {
  const assets = latestRows(rows);
  const state = marketState(assets);
  const fear = assets[0];
  const leader = strongestMove(assets);

  return (
    <section className="radar-section" id="radar">
      <div className="radar-command panel-accent">
        <div className="radar-state-copy">
          <p className="eyebrow">Radar State</p>
          <h2 className={state.tone}>{state.label}</h2>
          <span>{state.detail}</span>
          <p>{state.reading}</p>
        </div>
        <div className="radar-side-metrics">
          <div className="fear-greed-tile">
            <span>Fear & Greed</span>
            <strong>{fear?.fear_greed_value ?? "--"}</strong>
            <small>{fear?.fear_greed_label || "sin dato"}</small>
          </div>
          <div className="leader-tile">
            <span>Mayor movimiento</span>
            <strong>{leader?.symbol || "--"}</strong>
            <small>{leader ? formatPercent(leader.change_24h) : "sin dato"}</small>
          </div>
        </div>
      </div>

      <div className="asset-grid">
        {assets.length === 0 && (
          <article className="empty-state">
            <span>Sin snapshots</span>
            <strong>Actualizar radar</strong>
            <small>La base V1 esta lista para guardar la primera lectura.</small>
          </article>
        )}
        {assets.map((row) => {
          const change = Number(row.change_24h || 0);
          const tone = change >= 0 ? "positive" : "negative";
          return (
            <article className={`asset-card ${tone}`} key={row.symbol}>
              <div className="asset-head">
                <span>{row.symbol}</span>
                <em>{change >= 0 ? "UP" : "DOWN"}</em>
              </div>
              <strong>${formatPrice(row.price)}</strong>
              <div className="asset-meta">
                <b className={tone}>{formatPercent(change)}</b>
                <small>{compactRisk(row.risk_level)}</small>
              </div>
              <div className="volume-line">
                <span>Volumen 24h</span>
                <b>${formatCompact(row.volume_24h)}</b>
              </div>
              <p>{row.abraxas_reading}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
