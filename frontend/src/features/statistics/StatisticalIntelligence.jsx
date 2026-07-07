import React, { useEffect, useMemo, useState } from "react";
import { getStatistics } from "../../api/client.js";

const INTERVALS = ["5m", "15m", "1h", "4h", "1d"];

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function MetricTile({ label, value, tone = "neutral", suffix = "" }) {
  return (
    <article className={`stat-tile ${tone}`}>
      <span>{label}</span>
      <strong>
        {value}
        {suffix}
      </strong>
    </article>
  );
}

function Histogram({ bins = [] }) {
  const maxCount = Math.max(...bins.map((bin) => bin.count), 1);
  return (
    <div className="histogram" aria-label="Distribucion de retornos">
      {bins.map((bin) => {
        const height = Math.max(6, (bin.count / maxCount) * 100);
        const positive = Number(bin.to) >= 0;
        return (
          <span
            key={`${bin.from}-${bin.to}`}
            className={positive ? "positive" : "negative"}
            style={{ height: `${height}%` }}
            title={`${bin.from}% a ${bin.to}%: ${bin.count}`}
          />
        );
      })}
    </div>
  );
}

function GaussianCurve({ points = [] }) {
  const path = useMemo(() => {
    if (!points.length) return "";
    const xs = points.map((point) => point.x);
    const ys = points.map((point) => point.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const maxY = Math.max(...ys, 1);
    return points
      .map((point, index) => {
        const x = ((point.x - minX) / (maxX - minX || 1)) * 100;
        const y = 100 - (point.y / maxY) * 86 - 7;
        return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(" ");
  }, [points]);

  return (
    <svg className="gaussian-curve" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Campana de Gauss">
      <line x1="0" y1="84" x2="100" y2="84" />
      <path d={path} />
    </svg>
  );
}

function MonteCarloRange({ monteCarlo }) {
  const percentiles = monteCarlo?.percentiles || {};
  const low = Number(percentiles.p05 || 0);
  const high = Number(percentiles.p95 || 0);
  const median = Number(percentiles.p50 || 0);
  const current = Number(monteCarlo?.current_price || 0);
  const span = high - low || 1;
  const medianPos = ((median - low) / span) * 100;
  const currentPos = ((current - low) / span) * 100;

  return (
    <div className="mc-range">
      <div className="mc-track">
        <i style={{ left: `${Math.max(0, Math.min(100, medianPos))}%` }} title="Mediana simulada" />
        <b style={{ left: `${Math.max(0, Math.min(100, currentPos))}%` }} title="Precio actual" />
      </div>
      <div className="mc-labels">
        <span>P05 {formatNumber(low, 2)}</span>
        <span>P50 {formatNumber(median, 2)}</span>
        <span>P95 {formatNumber(high, 2)}</span>
      </div>
    </div>
  );
}

export default function StatisticalIntelligence({ selectedSymbol }) {
  const [interval, setInterval] = useState("15m");
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadStatistics({ silent = false } = {}) {
    if (!silent) setLoading(true);
    setError("");
    try {
      const data = await getStatistics({ symbol: selectedSymbol, interval });
      setPayload(data);
    } catch (err) {
      setError(err.message);
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    loadStatistics();
    const timer = window.setInterval(() => {
      loadStatistics({ silent: true });
    }, 75000);
    return () => window.clearInterval(timer);
  }, [selectedSymbol, interval]);

  const summary = payload?.summary;
  const monteCarlo = payload?.monte_carlo;
  const moveTone = Number(summary?.latest_return_pct || 0) >= 0 ? "positive" : "negative";
  const zTone = Math.abs(Number(summary?.z_score || 0)) >= 2 ? "warning" : "neutral";

  return (
    <section className="stat-intel-panel">
      <div className="exchange-panel-head">
        <div>
          <p className="eyebrow">Statistical Intelligence</p>
          <h2>{selectedSymbol}</h2>
        </div>
        <div className="timeframe-row">
          {INTERVALS.map((item) => (
            <button
              type="button"
              key={item}
              className={item === interval ? "active" : ""}
              onClick={() => setInterval(item)}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="stat-error">{error}</div>}

      <div className="stat-body">
        <div className="stat-grid">
          <MetricTile label="Precio" value={`$${formatNumber(summary?.current_price, 2)}`} />
          <MetricTile label="Ultima vela" value={formatNumber(summary?.latest_return_pct, 3)} suffix="%" tone={moveTone} />
          <MetricTile label="Volatilidad" value={formatNumber(summary?.volatility_pct, 3)} suffix="%" />
          <MetricTile label="Z-score" value={formatNumber(summary?.z_score, 2)} tone={zTone} />
          <MetricTile label="Percentil mov." value={formatNumber(summary?.latest_move_percentile, 1)} suffix="%" />
          <MetricTile label="Max drawdown" value={formatNumber(summary?.max_drawdown_pct, 2)} suffix="%" tone="negative" />
          <MetricTile label="VaR 95" value={formatNumber(summary?.var_95_pct, 2)} suffix="%" tone="warning" />
          <MetricTile label="Muestras" value={summary?.sample_count || "--"} />
        </div>

        <div className="stat-analysis-grid">
          <article className="stat-card">
            <div>
              <p className="eyebrow">Distribucion</p>
              <h2>Retornos por vela</h2>
            </div>
            <Histogram bins={summary?.distribution?.bins || []} />
            <small>Histograma de retornos recientes. Barras rojas = retornos negativos; verdes = positivos.</small>
          </article>

          <article className="stat-card">
            <div>
              <p className="eyebrow">Gauss</p>
              <h2>Campana normal</h2>
            </div>
            <GaussianCurve points={summary?.gaussian_curve || []} />
            <small>
              Media {formatNumber(summary?.mean_return_pct, 4)}% | IC 95: {formatNumber(summary?.confidence_interval_95_pct?.[0], 3)}% a{" "}
              {formatNumber(summary?.confidence_interval_95_pct?.[1], 3)}%
            </small>
          </article>

          <article className="stat-card wide">
            <div>
              <p className="eyebrow">Monte Carlo</p>
              <h2>Escenarios simulados</h2>
            </div>
            <MonteCarloRange monteCarlo={monteCarlo} />
            <div className="mc-prob-row">
              <span>
                Prob. arriba <b>{formatNumber(monteCarlo?.probability_up_pct, 1)}%</b>
              </span>
              <span>
                Prob. abajo <b>{formatNumber(monteCarlo?.probability_down_pct, 1)}%</b>
              </span>
              <span>
                Stress P05 <b>{formatNumber(monteCarlo?.stress_return_pct, 2)}%</b>
              </span>
            </div>
            <small>{monteCarlo?.disclaimer}</small>
          </article>
        </div>

        <article className="stat-reading">
          <p className="eyebrow">Lectura ABRAXAS</p>
          <p>{summary?.reading || (loading ? "Calculando estadistica..." : "Sin lectura estadistica todavia.")}</p>
          <p>{monteCarlo?.reading}</p>
        </article>
      </div>
    </section>
  );
}
