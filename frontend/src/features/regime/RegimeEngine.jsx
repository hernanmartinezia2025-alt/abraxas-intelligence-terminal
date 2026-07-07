import React, { useEffect, useState } from "react";
import { getRegime } from "../../api/client.js";

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function regimeTone(label) {
  if (label === "stress") return "danger";
  if (label === "extended") return "warning";
  if (label === "momentum_up") return "positive";
  if (label === "momentum_down") return "negative";
  if (label === "compression") return "compressed";
  return "neutral";
}

export default function RegimeEngine({ selectedSymbol }) {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const timeframe = "15m";

  async function loadRegime({ silent = false, refresh = false } = {}) {
    if (!silent) setLoading(true);
    setError("");
    try {
      const data = await getRegime({ symbol: selectedSymbol, timeframe, refresh });
      setPayload(data);
    } catch (err) {
      setError(err.message);
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    loadRegime();
    const timer = window.setInterval(() => {
      loadRegime({ silent: true });
    }, 90000);
    return () => window.clearInterval(timer);
  }, [selectedSymbol]);

  const tone = regimeTone(payload?.regime_label);

  return (
    <section className={`regime-engine ${tone}`}>
      <div className="exchange-panel-head compact">
        <div>
          <p className="eyebrow">Regime Engine</p>
          <h2>{selectedSymbol} / {timeframe}</h2>
        </div>
        <button type="button" onClick={() => loadRegime({ refresh: true })} disabled={loading}>
          {loading ? "Leyendo..." : "Recalcular"}
        </button>
      </div>

      {error && <div className="stat-error">{error}</div>}

      <div className="regime-body">
        <article className="regime-main">
          <span>Regimen actual</span>
          <strong>{payload?.regime_label || "--"}</strong>
          <p>{payload?.reading || "Esperando features suficientes para clasificar regimen."}</p>
        </article>

        <div className="regime-metrics">
          <article>
            <span>Confianza</span>
            <strong>{formatNumber(payload?.confidence, 1)}%</strong>
          </article>
          <article>
            <span>Risk score</span>
            <strong>{formatNumber(payload?.risk_score, 2)}</strong>
          </article>
          <article>
            <span>Sesgo</span>
            <strong>{payload?.market_bias || "--"}</strong>
          </article>
          <article>
            <span>Volatilidad</span>
            <strong>{payload?.volatility_state || "--"}</strong>
          </article>
          <article>
            <span>Tendencia</span>
            <strong>{payload?.trend_state || "--"}</strong>
          </article>
          <article>
            <span>Drawdown</span>
            <strong>{payload?.drawdown_state || "--"}</strong>
          </article>
        </div>

        <article className="regime-reasons">
          <p className="eyebrow">Razones</p>
          <div>
            {(payload?.reasons || []).map((reason) => (
              <span key={reason}>{reason}</span>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}
