import React, { useEffect, useMemo, useState } from "react";
import { evaluateSLHunter, getSLHunterEvaluations, getSLHunterReadiness } from "../../api/client.js";

const STATE_ORDER = ["scanning", "sweep_unconfirmed", "exhaustion_pending", "observation_candidate", "executing"];

function number(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function stateLabel(state) {
  return {
    scanning: "Escaneando",
    sweep_unconfirmed: "Barrido sin confirmar",
    exhaustion_pending: "Agotamiento pendiente",
    target_pending: "Muro objetivo pendiente",
    observation_candidate: "Candidato observable",
    executing: "Ejecucion bloqueada",
  }[state] || state || "Sin evaluacion";
}

export default function SLHunterPanel({ defaultSymbol = "BTCUSDT" }) {
  const [readiness, setReadiness] = useState(null);
  const [history, setHistory] = useState([]);
  const [evaluation, setEvaluation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ symbol: defaultSymbol, timeframe: "1m", account_equity: 10000, risk_pct: 0.5 });

  async function loadContext() {
    try {
      const [ready, runs] = await Promise.all([getSLHunterReadiness(), getSLHunterEvaluations({ limit: 8, symbol: form.symbol })]);
      setReadiness(ready);
      setHistory(runs.evaluations || []);
      if (!evaluation && runs.evaluations?.[0]) setEvaluation(runs.evaluations[0]);
    } catch (loadError) {
      setError(loadError.message);
    }
  }

  useEffect(() => { loadContext(); }, []);

  useEffect(() => {
    setForm((current) => ({ ...current, symbol: defaultSymbol }));
  }, [defaultSymbol]);

  async function handleEvaluate(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await evaluateSLHunter({ ...form, limit: 200 });
      setEvaluation(result);
      const runs = await getSLHunterEvaluations({ limit: 8, symbol: form.symbol });
      setHistory(runs.evaluations || []);
    } catch (evaluationError) {
      setError(evaluationError.message);
    } finally {
      setLoading(false);
    }
  }

  const result = evaluation?.result || null;
  const sweep = result?.evidence?.sweep || {};
  const exhaustion = result?.evidence?.exhaustion || {};
  const depth = result?.evidence?.depth || {};
  const plan = result?.risk_plan;
  const currentIndex = useMemo(() => {
    if (!result) return -1;
    const mapped = result.state === "target_pending" ? "observation_candidate" : result.state;
    return STATE_ORDER.indexOf(mapped);
  }, [result]);
  const visibleState = result?.state === "target_pending" ? "observation_candidate" : result?.state;

  return (
    <section className="sl-hunter-lab">
      <section className="exchange-panel sl-hunter-command">
        <div>
          <p className="eyebrow">Liquidity Sweep Observer v1</p>
          <h2>SL Hunter · evidencia antes que narrativa</h2>
          <span>Vela cerrada + volumen + Squeeze/ADX + snapshot Binance Depth. No prueba intencion institucional.</span>
        </div>
        <div className="sl-hunter-lock"><b>NO ORDER</b><span>LIVE / PAPER LOCKED</span></div>
      </section>

      {error && <div className="error-box">{error}</div>}

      <section className="exchange-panel">
        <div className="exchange-panel-head compact">
          <div><p className="eyebrow">Capability Gate</p><h2>Qué datos existen realmente</h2></div>
          <span>{readiness?.status || "checking"}</span>
        </div>
        <div className="sl-capability-grid">
          {(readiness?.available || []).map((item) => <article className="available" key={item}><b>REAL</b><strong>{item.replaceAll("_", " ")}</strong></article>)}
          {(readiness?.missing || []).map((item) => <article className="missing" key={item}><b>MISSING</b><strong>{item.replaceAll("_", " ")}</strong></article>)}
        </div>
      </section>

      <section className="exchange-panel">
        <form className="sl-hunter-controls" onSubmit={handleEvaluate}>
          <label>Activo<input value={form.symbol} onChange={(event) => setForm({ ...form, symbol: event.target.value.toUpperCase() })} /></label>
          <label>Timeframe<select value={form.timeframe} onChange={(event) => setForm({ ...form, timeframe: event.target.value })}><option value="1m">1 minuto</option><option value="5m">5 minutos</option></select></label>
          <label>Equity de referencia<input type="number" min="1" value={form.account_equity} onChange={(event) => setForm({ ...form, account_equity: Number(event.target.value) })} /></label>
          <label>Riesgo teórico %<input type="number" min="0.01" max="2" step="0.05" value={form.risk_pct} onChange={(event) => setForm({ ...form, risk_pct: Number(event.target.value) })} /></label>
          <button type="submit" disabled={loading}>{loading ? "Evaluando fuentes..." : "Evaluar snapshot real"}</button>
        </form>
      </section>

      <section className="sl-state-machine">
        {[
          ["scanning", "01", "Targeting"], ["sweep_unconfirmed", "02", "Wick + volumen"],
          ["exhaustion_pending", "03", "Squeeze + ADX"], ["observation_candidate", "04", "Plan de riesgo"],
          ["executing", "05", "Execution locked"],
        ].map(([state, index, label], position) => (
          <article className={`${position <= currentIndex ? "reached" : ""} ${state === "executing" ? "locked" : ""}`} key={state}>
            <span>{index}</span><strong>{label}</strong><small>{state === visibleState ? "ESTADO ACTUAL" : state === "executing" ? "INACCESIBLE" : ""}</small>
          </article>
        ))}
      </section>

      <section className="sl-hunter-grid">
        <article className="exchange-panel sl-evidence-panel">
          <div className="exchange-panel-head compact"><div><p className="eyebrow">Latest Evaluation</p><h2>{stateLabel(result?.state)}</h2></div><span>{result?.symbol || form.symbol} · {result?.timeframe || form.timeframe}</span></div>
          <div className="sl-metric-grid">
            <div><span>Dirección</span><strong>{result?.direction || "--"}</strong></div>
            <div><span>Wick / rango</span><strong>{number((sweep.wick_share || 0) * 100)}%</strong><small>umbral 35%</small></div>
            <div><span>Volumen z</span><strong>{number(sweep.volume_z_score)}</strong><small>umbral 1.50</small></div>
            <div><span>Squeeze</span><strong>{exhaustion.squeeze?.direction || "--"}</strong><small>{exhaustion.squeeze_passed ? "PASS" : "WAIT"}</small></div>
            <div><span>ADX</span><strong>{number(exhaustion.adx)}</strong><small>{exhaustion.adx_slope || "--"}</small></div>
            <div><span>Wall target</span><strong>{depth.target_wall ? `$${number(depth.target_wall.price)}` : "--"}</strong><small>snapshot L2</small></div>
          </div>
          <p className="sl-claim-boundary">{result?.claim_boundary || "Ejecutá una evaluación para leer la última vela cerrada y el Depth actual."}</p>
        </article>

        <article className="exchange-panel sl-risk-plan">
          <div className="exchange-panel-head compact"><div><p className="eyebrow">Risk Plan</p><h2>Francotirador · bloqueado</h2></div><span>OBSERVATION ONLY</span></div>
          <div className="sl-plan-values">
            <div><span>Entrada ref.</span><strong>${number(plan?.entry_reference)}</strong></div>
            <div><span>SL estructural</span><strong>${number(plan?.structural_stop)}</strong></div>
            <div><span>TP front-run</span><strong>${number(plan?.target)}</strong></div>
            <div><span>Riesgo</span><strong>${number(plan?.risk_budget)}</strong></div>
            <div><span>R:R</span><strong>{number(plan?.reward_risk)}</strong></div>
            <div><span>Quantity teórica</span><strong>{number(plan?.quantity, 6)}</strong></div>
          </div>
          <small>El sizing es informativo. No crea proposal, intent, orden ni fill.</small>
        </article>
      </section>

      <section className="exchange-panel">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">SQLite Audit</p><h2>Evaluaciones persistidas</h2></div><span>{history.length} visibles</span></div>
        <div className="sl-history">
          {history.length === 0 && <p>Sin evaluaciones todavía.</p>}
          {history.map((item) => <button type="button" key={item.id} onClick={() => setEvaluation(item)}><span>#{item.id}</span><strong>{item.symbol} {item.timeframe}</strong><b>{stateLabel(item.state)}</b><small>{new Date(item.created_at).toLocaleString()}</small></button>)}
        </div>
      </section>
    </section>
  );
}
