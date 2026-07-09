import React, { useEffect, useState } from "react";
import { getMonteCarlo, getRegimeSnapshots, getStatisticsRuns, getStatisticsSummary } from "../../api/client.js";

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function formatTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function RunRow({ run }) {
  const metrics = run.metrics || {};
  const summary = metrics.summary || metrics;
  const monteCarlo = metrics.monte_carlo || metrics;
  const volatility = summary.volatility_pct ?? "--";
  const probabilityUp = monteCarlo.probability_up_pct ?? "--";

  return (
    <article className="research-row">
      <div>
        <strong>{run.run_type}</strong>
        <span>{run.symbol} / {run.timeframe}</span>
      </div>
      <b>{formatNumber(volatility, 3)}% vol</b>
      <b>{formatNumber(probabilityUp, 1)}% up</b>
      <small>{formatTime(run.created_at)}</small>
    </article>
  );
}

function RegimeRow({ snapshot }) {
  return (
    <article className="research-row">
      <div>
        <strong>{snapshot.regime_label}</strong>
        <span>{snapshot.market_bias || "neutral"} / {snapshot.timeframe}</span>
      </div>
      <b>{formatNumber(snapshot.confidence, 1)}% conf</b>
      <b>{formatNumber(snapshot.risk_score, 2)} risk</b>
      <small>{formatTime(snapshot.created_at || snapshot.timestamp)}</small>
    </article>
  );
}

export default function ResearchArchive({ selectedSymbol = "BTCUSDT" }) {
  const [runs, setRuns] = useState([]);
  const [regimes, setRegimes] = useState([]);
  const [summary, setSummary] = useState(null);
  const [monteCarlo, setMonteCarlo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState("");
  const [error, setError] = useState("");
  const interval = "15m";

  async function loadArchive({ silent = false } = {}) {
    if (!silent) setLoading(true);
    setError("");
    try {
      const [runsPayload, regimesPayload] = await Promise.all([
        getStatisticsRuns({ symbol: selectedSymbol, limit: 10 }),
        getRegimeSnapshots({ symbol: selectedSymbol, limit: 10 }),
      ]);
      setRuns(runsPayload.runs || []);
      setRegimes(regimesPayload.snapshots || []);
    } catch (err) {
      setError(err.message);
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function runSummary() {
    setRunning("summary");
    setError("");
    try {
      const payload = await getStatisticsSummary({ symbol: selectedSymbol, interval, limit: 300 });
      setSummary(payload);
      await loadArchive({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning("");
    }
  }

  async function runMonteCarlo() {
    setRunning("monte-carlo");
    setError("");
    try {
      const payload = await getMonteCarlo({ symbol: selectedSymbol, interval, limit: 300, horizonSteps: 48, paths: 700 });
      setMonteCarlo(payload);
      await loadArchive({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning("");
    }
  }

  useEffect(() => {
    loadArchive();
    const timer = window.setInterval(() => {
      loadArchive({ silent: true });
    }, 90000);
    return () => window.clearInterval(timer);
  }, [selectedSymbol]);

  return (
    <section className="research-archive">
      <div className="exchange-panel-head compact">
        <div>
          <p className="eyebrow">Research Memory</p>
          <h2>{selectedSymbol} analytical archive</h2>
        </div>
        <div className="dataset-toolbar">
          <button type="button" onClick={() => loadArchive()} disabled={loading}>
            {loading ? "Leyendo..." : "Refrescar archivo"}
          </button>
          <button type="button" onClick={runSummary} disabled={running === "summary"}>
            {running === "summary" ? "Calculando..." : "Run summary"}
          </button>
          <button type="button" onClick={runMonteCarlo} disabled={running === "monte-carlo"}>
            {running === "monte-carlo" ? "Simulando..." : "Run Monte Carlo"}
          </button>
        </div>
      </div>

      {error && <div className="stat-error">{error}</div>}

      <div className="research-result-grid">
        <article>
          <span>Summary run</span>
          <strong>{summary?.statistics_run_id || "--"}</strong>
          <small>
            price ${formatNumber(summary?.current_price, 2)} | vol {formatNumber(summary?.volatility_pct, 3)}% | z{" "}
            {formatNumber(summary?.z_score, 2)}
          </small>
        </article>
        <article>
          <span>Monte Carlo run</span>
          <strong>{monteCarlo?.statistics_run_id || "--"}</strong>
          <small>
            up {formatNumber(monteCarlo?.probability_up_pct, 1)}% | p50{" "}
            {formatNumber(monteCarlo?.percentiles?.p50, 2)} | p95 {formatNumber(monteCarlo?.percentiles?.p95, 2)}
          </small>
        </article>
      </div>

      <div className="research-archive-grid">
        <article className="research-list">
          <div>
            <p className="eyebrow">Statistics Runs</p>
            <h2>Ultimos calculos</h2>
          </div>
          <div>
            {runs.map((run) => (
              <RunRow key={run.id} run={run} />
            ))}
            {!runs.length && <span className="research-empty">Sin runs persistidos para este activo.</span>}
          </div>
        </article>

        <article className="research-list">
          <div>
            <p className="eyebrow">Regime Snapshots</p>
            <h2>Memoria de regimen</h2>
          </div>
          <div>
            {regimes.map((snapshot) => (
              <RegimeRow key={snapshot.id} snapshot={snapshot} />
            ))}
            {!regimes.length && <span className="research-empty">Sin snapshots persistidos para este activo.</span>}
          </div>
        </article>
      </div>
    </section>
  );
}
