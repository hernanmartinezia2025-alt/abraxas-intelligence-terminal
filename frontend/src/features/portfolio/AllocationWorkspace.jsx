import React, { useMemo, useState } from "react";

const money = (value) => Number(value || 0).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const pct = (value) => `${Number(value || 0).toFixed(2)}%`;

export default function AllocationWorkspace({ data, busy, onSave, onArchive, onPlan, onApply }) {
  const [form, setForm] = useState({
    name: "Core spot allocation",
    min_trade_notional: "25",
    targets: [
      { symbol: "BTCUSDT", target_pct: "50" },
      { symbol: "ETHUSDT", target_pct: "30" },
    ],
  });
  const targetTotal = useMemo(
    () => form.targets.reduce((total, target) => total + (Number(target.target_pct) || 0), 0),
    [form.targets],
  );
  const latestRun = data.runs?.[0] || null;
  const riskPreview = latestRun?.metrics?.risk_preview || [];
  const riskReady = latestRun?.metrics?.risk_ready;

  function updateTarget(index, field, value) {
    setForm((current) => ({
      ...current,
      targets: current.targets.map((target, targetIndex) => targetIndex === index
        ? { ...target, [field]: field === "symbol" ? value.toUpperCase() : value }
        : target),
    }));
  }

  function addTarget() {
    setForm((current) => ({ ...current, targets: [...current.targets, { symbol: "", target_pct: "" }] }));
  }

  function removeTarget(index) {
    setForm((current) => ({ ...current, targets: current.targets.filter((_, targetIndex) => targetIndex !== index) }));
  }

  function submit(event) {
    event.preventDefault();
    onSave({
      name: form.name,
      min_trade_notional: Number(form.min_trade_notional),
      targets: form.targets.map((target) => ({ symbol: target.symbol, target_pct: Number(target.target_pct) })),
    });
  }

  return <>
    <section className="exchange-panel spot-allocation-command">
      <div><p className="eyebrow">Target allocation · two-phase control</p><h2>Asignación objetivo y rebalanceo asistido</h2><span>PLANIFICAR congela el cálculo. APLICAR registra ventas y compras en el simulador Spot; nunca envía órdenes reales.</span></div>
      <div><strong>{data.policies?.filter((policy) => policy.status === "active").length || 0}</strong><span>POLÍTICAS ACTIVAS</span><small>LIVE BLOQUEADO</small></div>
    </section>

    <div className="spot-allocation-workspace">
      <section className="exchange-panel spot-allocation-builder">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Versioned contract</p><h2>Nueva política</h2></div><span>GUARDAR ≠ APLICAR</span></div>
        <form onSubmit={submit}>
          <label>Nombre<input required minLength="3" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
          <label>Operación mínima USDT<input required type="number" min="1" step="any" value={form.min_trade_notional} onChange={(event) => setForm({ ...form, min_trade_notional: event.target.value })} /></label>
          <div className="allocation-target-head"><span>ACTIVO</span><span>PESO OBJETIVO</span><span /></div>
          <div className="allocation-target-rows">
            {form.targets.map((target, index) => <div key={`${index}-${target.symbol}`}>
              <input required minLength="3" placeholder="BTCUSDT" value={target.symbol} onChange={(event) => updateTarget(index, "symbol", event.target.value)} />
              <label><input required type="number" min="0.01" max="100" step="0.01" value={target.target_pct} onChange={(event) => updateTarget(index, "target_pct", event.target.value)} /><span>%</span></label>
              <button type="button" disabled={form.targets.length === 1} onClick={() => removeTarget(index)} aria-label={`Quitar ${target.symbol || "activo"}`}>×</button>
            </div>)}
          </div>
          <button className="allocation-add-target" type="button" disabled={form.targets.length >= 50} onClick={addTarget}>+ Agregar activo</button>
          <div className={`allocation-total ${targetTotal > 100 ? "invalid" : ""}`}><span>Activos <b>{pct(targetTotal)}</b></span><span>Cash residual <b>{pct(Math.max(0, 100 - targetTotal))}</b></span></div>
          <button className="allocation-save" disabled={busy || targetTotal <= 0 || targetTotal > 100} type="submit">Guardar versión · no rebalancear</button>
          <small>Los símbolos deben tener un mark real persistido. Repetir la misma configuración no crea otra versión.</small>
        </form>
      </section>

      <section className="exchange-panel spot-allocation-policies">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Policy registry</p><h2>Contratos persistidos</h2></div><span>{data.policies?.length || 0} POLÍTICAS</span></div>
        {data.policies?.length ? <div className="allocation-policy-list">{data.policies.map((policy) => <article className={policy.status} key={policy.id}>
          <header><div><span>#{policy.id} · V{policy.active_version}</span><strong>{policy.name}</strong></div><b>{policy.status.toUpperCase()}</b></header>
          <div className="allocation-policy-targets">{policy.active_config.targets.map((target) => <span key={target.symbol}><b>{target.symbol}</b>{pct(target.target_pct)}</span>)}<span><b>CASH</b>{pct(100 - policy.active_config.targets.reduce((sum, target) => sum + Number(target.target_pct), 0))}</span></div>
          <p>Umbral {money(policy.active_config.min_trade_notional)} · hash {policy.active_config.config_hash.slice(0, 10)}</p>
          <footer>{policy.status === "active" && <button disabled={busy} onClick={() => onPlan(policy.id)}>Planificar rebalanceo</button>}{policy.status !== "archived" && <button disabled={busy} onClick={() => onArchive(policy.id)}>Archivar</button>}</footer>
        </article>)}</div> : <div className="chart-state">Todavía no hay políticas. Guardar crea un contrato, no modifica la cartera.</div>}
      </section>
    </div>

    <section className="exchange-panel spot-rebalance-run">
      <div className="exchange-panel-head compact"><div><p className="eyebrow">Persisted rebalance run</p><h2>{latestRun ? `Plan #${latestRun.id} · ${latestRun.status}` : "Sin plan calculado"}</h2></div>{latestRun && <span className={riskReady === false ? "negative" : "positive"}>{riskReady === false ? "RISK BLOQUEA" : riskReady === true ? "RISK READY" : "RISK AL APLICAR"}</span>}</div>
      {latestRun ? <>
        <div className="rebalance-metrics">
          <article><span>Patrimonio al plan</span><strong>{money(latestRun.equity_at_plan)}</strong><small>mark {latestRun.source_timestamp ? new Date(latestRun.source_timestamp).toLocaleString() : "sin timestamp"}</small></article>
          <article><span>Desvío actual</span><strong>{pct(latestRun.metrics.current_drift_pct_points)}</strong><small>suma absoluta de pesos</small></article>
          <article><span>Desvío esperado</span><strong>{pct(latestRun.metrics.expected_drift_pct_points)}</strong><small>después de fees</small></article>
          <article><span>Fees estimados</span><strong>{money(latestRun.metrics.estimated_fees)}</strong><small>{latestRun.plan.length} órdenes simuladas</small></article>
        </div>
        <div className="rebalance-order-table">
          <div className="table-head"><span>#</span><span>Lado</span><span>Activo</span><span>Cantidad</span><span>Notional</span><span>Mark</span></div>
          {latestRun.plan.map((order) => <div key={`${latestRun.id}-${order.order_index}`}><span>{order.order_index}</span><b className={order.side === "buy" ? "positive" : "negative"}>{order.side.toUpperCase()}</b><strong>{order.symbol}</strong><span>{Number(order.planned_quantity).toFixed(8)}</span><span>{money(order.planned_notional)}</span><span>{money(order.reference_price)}</span></div>)}
        </div>
        {riskPreview.length ? <div className="rebalance-risk-preview">{riskPreview.map((decision) => <article className={decision.approved ? "approved" : "rejected"} key={decision.order_index}>
          <header><span>RISK PREVIEW · ORDEN #{decision.order_index}</span><b>{decision.approved ? "READY" : "BLOCKED"}</b></header>
          <strong>{decision.symbol} · {decision.side.toUpperCase()}</strong>
          <div>{decision.checks.map((check) => <small className={check.passed ? "pass" : "fail"} key={check.code}>{check.passed ? "PASS" : "FAIL"} · {check.code}</small>)}</div>
          <p>{decision.approved ? "Todos los guardrails aprobaron el preview." : decision.reasons.join(" · ")}</p>
        </article>)}</div> : null}
        <footer className="rebalance-apply-bar"><div><strong>{riskReady === false ? "Resolver Risk y recalcular" : latestRun.status === "draft" ? "Plan listo para revisión" : `Estado ${latestRun.status}`}</strong><small>La aplicación revalida con el estado vigente y persiste cada validation_id.</small></div>{["draft", "applying", "partial"].includes(latestRun.status) && <button disabled={busy || riskReady === false} onClick={() => onApply(latestRun.id)}>Aplicar en simulación Spot</button>}</footer>
        {latestRun.execution?.length ? <div className="rebalance-execution-log">{latestRun.execution.map((item) => <span key={item.order_index}><b>#{item.order_index} {item.symbol}</b><strong className={item.status === "executed" ? "positive" : "negative"}>{item.status}</strong><small>{item.transaction_id ? `tx #${item.transaction_id}${item.recovered ? " · recuperada" : ""}` : item.reason}{item.risk_validation_id ? ` · risk #${item.risk_validation_id}` : ""}</small></span>)}</div> : null}
      </> : <div className="chart-state">Selecciona “Planificar rebalanceo” en una política activa para calcular con los marks actuales.</div>}
    </section>
  </>;
}
