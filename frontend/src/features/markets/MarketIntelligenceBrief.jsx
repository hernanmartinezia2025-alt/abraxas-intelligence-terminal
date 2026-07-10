import React, { useEffect, useState } from "react";
import { getMonteCarlo, getRegime, getStatisticsSummary } from "../../api/client.js";

function value(value, digits = 2, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits })}${suffix}`;
}

function operationalPosture(regime, summary) {
  const risk = Number(regime.risk_score);
  const bias = String(regime.market_bias || "").toLowerCase();
  if (risk >= 65) return { label: "NO OPERAR", tone: "danger", detail: "Riesgo estadístico elevado: esperar reducción de volatilidad y nueva lectura." };
  if (regime.regime_label === "compression") return { label: "RANGO / ESPERAR", tone: "neutral", detail: "El mercado está comprimido: no perseguir ruptura sin confirmación y volumen." };
  if (bias.includes("bull") || bias.includes("up")) return { label: "SESGO ALCISTA", tone: "positive", detail: "Buscar confirmación de continuidad; el brief no envía órdenes." };
  if (bias.includes("bear") || bias.includes("down")) return { label: "SESGO BAJISTA", tone: "negative", detail: "Priorizar protección y confirmación; el brief no envía órdenes." };
  return { label: Number(summary.latest_return_pct || 0) >= 0 ? "OBSERVAR / FUERZA" : "OBSERVAR / DEBILIDAD", tone: "neutral", detail: "Lectura informativa: esperar confluencia antes de cambiar el plan." };
}

export default function MarketIntelligenceBrief({ selectedSymbol = "BTCUSDT" }) {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load({ silent = false } = {}) {
    if (!silent) setLoading(true);
    setError("");
    try {
      const [summary, regime, monteCarlo] = await Promise.all([
        getStatisticsSummary({ symbol: selectedSymbol, interval: "15m", limit: 300 }),
        getRegime({ symbol: selectedSymbol, timeframe: "15m", limit: 120 }),
        getMonteCarlo({ symbol: selectedSymbol, interval: "15m", limit: 300, horizonSteps: 48, paths: 700 }),
      ]);
      setPayload({ summary, regime, monteCarlo });
    } catch (err) {
      setError(err.message);
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(() => load({ silent: true }), 90000);
    return () => window.clearInterval(timer);
  }, [selectedSymbol]);

  const summary = payload?.summary || {};
  const regime = payload?.regime || {};
  const monteCarlo = payload?.monteCarlo || {};
  const percentiles = monteCarlo.percentiles || {};
  const posture = operationalPosture(regime, summary);

  return (
    <section className="market-intelligence-brief exchange-panel">
      <div className="exchange-panel-head compact">
        <div>
          <p className="eyebrow">Market Intelligence Brief</p>
          <h2>{selectedSymbol} · lectura cuantitativa</h2>
        </div>
        <button type="button" onClick={() => load()} disabled={loading}>{loading ? "Calculando..." : "Actualizar lectura"}</button>
      </div>
      {error && <div className="stat-error">La lectura no está disponible: {error}</div>}
      <div className="market-intelligence-metrics">
        <article><span>Régimen</span><strong>{regime.regime_label || "--"}</strong><small>{regime.market_bias || "sin sesgo"}</small></article>
        <article><span>Confianza</span><strong>{value(regime.confidence, 1, "%")}</strong><small>persistencia del régimen</small></article>
        <article><span>Riesgo</span><strong>{value(regime.risk_score, 1)}</strong><small>{regime.volatility_state || "sin lectura"}</small></article>
        <article><span>Z-score</span><strong>{value(summary.z_score, 2)}</strong><small>movimiento reciente</small></article>
        <article><span>VaR 95</span><strong>{value(summary.var_95_pct, 2, "%")}</strong><small>cola histórica</small></article>
        <article><span>Prob. arriba</span><strong>{value(monteCarlo.probability_up_pct, 1, "%")}</strong><small>Monte Carlo · 48 pasos</small></article>
      </div>
      <div className="market-intelligence-reading">
        <div className="intelligence-reading-copy">
          <span>Interpretación cuantitativa</span>
          <p>{regime.reading || summary.reading || "Esperando datos suficientes para construir la lectura."}</p>
          <small>{monteCarlo.disclaimer || "Escenarios probabilísticos; no son una predicción ni una orden."}</small>
        </div>
        <div className="scenario-summary-grid">
          <article><span>Cola baja P05</span><strong>${value(percentiles.p05, 2)}</strong></article>
          <article><span>Mediana P50</span><strong>${value(percentiles.p50, 2)}</strong></article>
          <article><span>Cola alta P95</span><strong>${value(percentiles.p95, 2)}</strong></article>
          <article><span>Probabilidad</span><strong>{value(monteCarlo.probability_up_pct, 1, "%")} ↑ / {value(monteCarlo.probability_down_pct, 1, "%")} ↓</strong></article>
        </div>
      </div>
      <div className={`market-execution-readout ${posture.tone}`}>
        <div><span>Postura operativa</span><strong>{posture.label}</strong></div>
        <p>{posture.detail}</p>
        <small>Guardrail: esta lectura informa al operador y al futuro bot; no ejecuta órdenes.</small>
      </div>
    </section>
  );
}
