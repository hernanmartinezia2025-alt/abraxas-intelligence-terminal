import React, { useEffect, useMemo, useRef, useState } from "react";
import { getBacktest } from "../../api/client.js";
import BacktestComparisonChart from "../charts/BacktestComparisonChart.jsx";

const METRICS = [
  { key: "roi_pct", label: "ROI estrategia", kind: "percentage", digits: 4, direction: "higher" },
  { key: "benchmark_roi_pct", label: "Buy & hold", kind: "percentage", digits: 4, direction: "neutral" },
  { key: "alpha_pct", label: "Alpha", kind: "percentage", digits: 4, direction: "higher" },
  { key: "max_drawdown_pct", label: "Max drawdown", kind: "percentage", digits: 4, direction: "higher" },
  { key: "win_rate_pct", label: "Win rate", kind: "percentage", digits: 2, direction: "higher" },
  { key: "profit_factor", label: "Profit factor", kind: "number", digits: 4, direction: "higher" },
  { key: "total_trades", label: "Trades", kind: "integer", digits: 0, direction: "neutral" },
  { key: "net_pnl", label: "PnL neto", kind: "number", digits: 4, direction: "higher" },
  { key: "total_fees", label: "Fees", kind: "number", digits: 4, direction: "lower" },
];

function metricValue(run, key) {
  if (!run) return null;
  if (run.metrics && Object.prototype.hasOwnProperty.call(run.metrics, key)) return run.metrics[key];
  if (Object.prototype.hasOwnProperty.call(run, key)) return run[key];
  return null;
}

function finiteValue(value) {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatValue(value, kind, digits = 2) {
  const numeric = finiteValue(value);
  if (numeric === null) return "--";
  if (kind === "integer") return numeric.toLocaleString(undefined, { maximumFractionDigits: 0 });
  const formatted = numeric.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return kind === "percentage" ? `${formatted}%` : formatted;
}

function formatDelta(value, kind, digits = 2) {
  if (value === null) return "--";
  const sign = value > 0 ? "+" : "";
  if (kind === "integer") return `${sign}${value.toFixed(0)}`;
  const suffix = kind === "percentage" ? " pp" : "";
  return `${sign}${value.toFixed(digits)}${suffix}`;
}

function advantage(valueA, valueB, direction) {
  const numericA = finiteValue(valueA);
  const numericB = finiteValue(valueB);
  if (numericA === null || numericB === null || direction === "neutral") return null;
  if (numericA === numericB) return "equal";
  const aWins = direction === "higher" ? numericA > numericB : numericA < numericB;
  return aWins ? "a" : "b";
}

function mergedMetrics(run) {
  return run ? { ...run, ...(run.metrics || {}) } : {};
}

function comparabilityIssues(runA, runB) {
  if (!runA || !runB) return [];
  const metricsA = mergedMetrics(runA);
  const metricsB = mergedMetrics(runB);
  const issues = [];
  if (runA.symbol !== runB.symbol) issues.push("Simbolos distintos.");
  if (runA.timeframe !== runB.timeframe) issues.push("Timeframes distintos.");
  if (runA.input_start !== runB.input_start || runA.input_end !== runB.input_end) {
    issues.push("Rangos temporales distintos.");
  }
  if (finiteValue(runA.initial_equity) !== finiteValue(runB.initial_equity)) {
    issues.push("Capitales iniciales distintos; el chart usa retorno normalizado.");
  }
  if (metricsA.engine_version !== metricsB.engine_version) issues.push("Versiones de engine distintas.");
  if (metricsA.execution_model !== metricsB.execution_model) issues.push("Modelos de ejecucion distintos.");
  if (finiteValue(metricsA.fee_pct) !== finiteValue(metricsB.fee_pct)) issues.push("Fees configuradas distintas.");
  if (finiteValue(metricsA.slippage_pct) !== finiteValue(metricsB.slippage_pct)) {
    issues.push("Slippage configurado distinto.");
  }
  const dataPointsA = finiteValue(metricsA.data_points);
  const dataPointsB = finiteValue(metricsB.data_points);
  if (dataPointsA === null || dataPointsB === null) {
    issues.push("Cantidad de puntos no auditable en al menos un run legacy.");
  } else if (dataPointsA !== dataPointsB) {
    issues.push(`Cantidad de puntos distinta (${dataPointsA} vs ${dataPointsB}).`);
  }
  return issues;
}

function formatDate(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function BacktestComparisonPanel({ botId, runs = [], versions = [] }) {
  const [runIds, setRunIds] = useState({ a: "", b: "" });
  const [details, setDetails] = useState({ a: null, b: null });
  const [loading, setLoading] = useState({ a: false, b: false });
  const [errors, setErrors] = useState({ a: "", b: "" });
  const requestGenerationRef = useRef(0);
  const activeBotIdRef = useRef(botId);
  activeBotIdRef.current = botId;
  const runKey = runs.map((run) => run.id).join(":");
  const versionById = useMemo(
    () => new Map(versions.map((version) => [version.id, version.version])),
    [versions]
  );
  const issues = useMemo(() => comparabilityIssues(details.a, details.b), [details]);

  useEffect(() => {
    requestGenerationRef.current += 1;
    setRunIds({
      a: runs[0] ? String(runs[0].id) : "",
      b: runs[1] ? String(runs[1].id) : "",
    });
    setDetails({ a: null, b: null });
    setErrors({ a: "", b: "" });
  }, [botId, runKey]);

  useEffect(() => {
    const generation = ++requestGenerationRef.current;
    const expectedBotId = botId;
    const requested = { a: Number(runIds.a), b: Number(runIds.b) };
    setDetails({ a: null, b: null });
    setErrors({ a: "", b: "" });

    if (!requested.a || !requested.b || requested.a === requested.b) {
      setLoading({ a: false, b: false });
      return undefined;
    }

    setLoading({ a: true, b: true });
    const loadSlot = async (slot) => {
      try {
        const payload = await getBacktest(requested[slot]);
        if (
          requestGenerationRef.current !== generation
          || activeBotIdRef.current !== expectedBotId
          || payload.id !== requested[slot]
          || payload.bot_id !== expectedBotId
        ) return;
        setDetails((current) => ({ ...current, [slot]: payload }));
      } catch (error) {
        if (requestGenerationRef.current !== generation) return;
        setErrors((current) => ({ ...current, [slot]: error.message }));
      } finally {
        if (requestGenerationRef.current === generation) {
          setLoading((current) => ({ ...current, [slot]: false }));
        }
      }
    };

    loadSlot("a");
    loadSlot("b");
    return () => {
      if (requestGenerationRef.current === generation) requestGenerationRef.current += 1;
    };
  }, [botId, runIds.a, runIds.b]);

  if (runs.length < 2) {
    return (
      <section className="exchange-panel backtest-comparison-panel">
        <div className="exchange-panel-head compact">
          <div>
            <p className="eyebrow">Run Comparison</p>
            <h2>Comparacion A/B</h2>
          </div>
          <span>LOCKED</span>
        </div>
        <div className="map-empty">
          <strong>Se necesitan dos runs persistidos</strong>
          <span>Ejecuta otro backtest para habilitar la comparacion.</span>
        </div>
      </section>
    );
  }

  const optionLabel = (run) => {
    const version = versionById.get(run.bot_version_id);
    return `Run #${run.id} · ${version ? `v${version}` : `version #${run.bot_version_id}`} · ${formatDate(run.created_at)}`;
  };
  const ready = Boolean(details.a && details.b);
  const status = loading.a || loading.b ? "LOADING" : ready ? (issues.length ? "EXPLORATORY" : "METADATA MATCH") : "INCOMPLETE";

  return (
    <section className="exchange-panel backtest-comparison-panel">
      <div className="exchange-panel-head compact">
        <div>
          <p className="eyebrow">Run Comparison</p>
          <h2>Comparacion A/B entre runs y versiones</h2>
        </div>
        <span className={ready && !issues.length ? "positive" : ""} aria-live="polite">{status}</span>
      </div>

      <div className="backtest-compare-controls">
        <label>
          Run A
          <select value={runIds.a} onChange={(event) => setRunIds((current) => ({ ...current, a: event.target.value }))}>
            {runs.map((run) => (
              <option key={run.id} value={run.id} disabled={String(run.id) === runIds.b}>{optionLabel(run)}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => setRunIds((current) => ({ a: current.b, b: current.a }))}
          disabled={!runIds.a || !runIds.b}
        >
          Intercambiar A/B
        </button>
        <label>
          Run B
          <select value={runIds.b} onChange={(event) => setRunIds((current) => ({ ...current, b: event.target.value }))}>
            {runs.map((run) => (
              <option key={run.id} value={run.id} disabled={String(run.id) === runIds.a}>{optionLabel(run)}</option>
            ))}
          </select>
        </label>
      </div>

      {(errors.a || errors.b) && (
        <div className="comparison-errors" role="alert">
          {errors.a && <span>Run A: {errors.a}</span>}
          {errors.b && <span>Run B: {errors.b}</span>}
        </div>
      )}

      {(details.a || details.b || errors.a || errors.b) && (
        <div className="comparison-run-meta">
          {["a", "b"].map((slot) => {
            const run = details[slot];
            if (!run) {
              return (
                <article className={slot} key={slot}>
                  <span>Run {slot.toUpperCase()}</span>
                  <strong>{loading[slot] ? "Cargando" : "No disponible"}</strong>
                  <small>{errors[slot] || "Esperando detalle persistido."}</small>
                </article>
              );
            }
            const metrics = mergedMetrics(run);
            return (
              <article className={slot} key={slot}>
                <span>Run {slot.toUpperCase()}</span>
                <strong>#{run.id} · {versionById.has(run.bot_version_id) ? `v${versionById.get(run.bot_version_id)}` : `version #${run.bot_version_id}`}</strong>
                <small>{run.symbol} / {run.timeframe} · engine {metrics.engine_version || "--"}</small>
                <small>{formatDate(run.input_start)} → {formatDate(run.input_end)}</small>
              </article>
            );
          })}
        </div>
      )}

      {ready ? (
        <>
          <div className={`comparison-compatibility ${issues.length ? "warning" : "ready"}`}>
            <strong>{issues.length ? "Comparacion de referencia; no equivalente uno-a-uno." : "Runs alineados por la metadata persistida."}</strong>
            {issues.map((issue) => <span key={issue}>{issue}</span>)}
            <small>Gap de auditoria: todavia no se persiste fingerprint del dataset de candles.</small>
          </div>

          <BacktestComparisonChart runA={details.a} runB={details.b} />

          <div className="backtest-comparison-table-wrap">
            <table>
              <caption>Delta = Run A − Run B. Los porcentajes se expresan en puntos porcentuales.</caption>
              <thead>
                <tr>
                  <th scope="col">Metrica</th>
                  <th scope="col">Run A</th>
                  <th scope="col">Run B</th>
                  <th scope="col">Delta A − B</th>
                  <th scope="col">Ventaja</th>
                </tr>
              </thead>
              <tbody>
                {METRICS.map((metric) => {
                  const valueA = metricValue(details.a, metric.key);
                  const valueB = metricValue(details.b, metric.key);
                  const numericA = finiteValue(valueA);
                  const numericB = finiteValue(valueB);
                  const delta = numericA === null || numericB === null ? null : numericA - numericB;
                  const winner = advantage(valueA, valueB, metric.direction);
                  return (
                    <tr key={metric.key}>
                      <th scope="row">{metric.label}</th>
                      <td className={winner === "a" ? "comparison-winner" : ""}>{formatValue(valueA, metric.kind, metric.digits)}</td>
                      <td className={winner === "b" ? "comparison-winner" : ""}>{formatValue(valueB, metric.kind, metric.digits)}</td>
                      <td>{formatDelta(delta, metric.kind, metric.digits)}</td>
                      <td>{winner === "a" ? "Run A" : winner === "b" ? "Run B" : winner === "equal" ? "Empate" : "Contexto"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="map-empty" aria-live="polite">
          <strong>{loading.a || loading.b ? "Cargando runs persistidos" : "Comparacion incompleta"}</strong>
          <span>Los dos detalles deben estar disponibles para calcular deltas sin inventar valores.</span>
        </div>
      )}
    </section>
  );
}
