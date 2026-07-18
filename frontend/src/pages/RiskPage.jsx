import React, { useEffect, useState } from "react";
import { archiveRiskPolicy, getRiskProfile, saveRiskPolicy, updateKillSwitch, updateRiskLimits, validateRiskIntent } from "../api/client.js";
import PageSubtabs from "../components/PageSubtabs.jsx";

const EMPTY = { max_position_pct: 10, max_daily_loss_pct: 3, max_drawdown_pct: 12, cooldown_minutes: 30, symbol_whitelist: [] };
const POLICY_EMPTY = { scope_type: "account", scope_id: "1", name: "Paper account guardrails", notes: "Scoped operational mandate", max_position_pct: 10, max_daily_loss_pct: 3, max_drawdown_pct: 12, cooldown_minutes: 30, symbol_whitelist: "BTCUSDT, ETHUSDT" };

export default function RiskPage() {
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [reason, setReason] = useState("Manual operator control");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [intent, setIntent] = useState({ symbol: "BTCUSDT", requested_notional: 500, account_equity: 10000, daily_pnl: 0, current_drawdown_pct: 0, account_id: "1", bot_id: "" });
  const [decision, setDecision] = useState(null);
  const [policyForm, setPolicyForm] = useState(POLICY_EMPTY);
  const [activeTab, setActiveTab] = useState("overview");

  const load = async () => {
    try {
      const result = await getRiskProfile();
      setProfile(result);
      setForm(result.limits);
      setError("");
    } catch (requestError) { setError(requestError.message); }
  };

  useEffect(() => { load(); }, []);

  const saveLimits = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await updateRiskLimits({
        ...form,
        max_position_pct: Number(form.max_position_pct),
        max_daily_loss_pct: Number(form.max_daily_loss_pct),
        max_drawdown_pct: Number(form.max_drawdown_pct),
        cooldown_minutes: Number(form.cooldown_minutes),
        symbol_whitelist: String(form.symbol_whitelist).split(",").map((value) => value.trim()).filter(Boolean),
      });
      setProfile(result); setForm(result.limits); setError("");
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  const toggleKillSwitch = async () => {
    setBusy(true);
    try {
      const result = await updateKillSwitch({ active: !profile.kill_switch.active, reason });
      setProfile(result); setError("");
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  const savePolicy = async (event) => {
    event.preventDefault(); setBusy(true);
    try {
      await saveRiskPolicy(policyForm.scope_type, Number(policyForm.scope_id), {
        name: policyForm.name,
        notes: policyForm.notes,
        max_position_pct: Number(policyForm.max_position_pct),
        max_daily_loss_pct: Number(policyForm.max_daily_loss_pct),
        max_drawdown_pct: Number(policyForm.max_drawdown_pct),
        cooldown_minutes: Number(policyForm.cooldown_minutes),
        symbol_whitelist: String(policyForm.symbol_whitelist).split(",").map((value) => value.trim()).filter(Boolean),
      });
      await load(); setError("");
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  const editPolicy = (policy) => setPolicyForm({
    scope_type: policy.scope_type, scope_id: String(policy.scope_id), name: policy.name,
    notes: policy.notes, ...policy.limits, symbol_whitelist: policy.limits.symbol_whitelist.join(", "),
  });

  const archivePolicy = async (policy) => {
    if (!window.confirm(`Archivar política ${policy.name}? Las validaciones futuras volverán a heredar la capa superior.`)) return;
    setBusy(true);
    try { await archiveRiskPolicy(policy.scope_type, policy.scope_id, { reason: `Archived by operator from Risk console · ${policy.name}` }); await load(); }
    catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  const killActive = profile?.kill_switch?.active ?? true;
  const runValidation = async (event) => {
    event.preventDefault(); setBusy(true);
    try {
      const result = await validateRiskIntent({ ...intent, mode: "validation", side: "long", requested_notional: Number(intent.requested_notional), account_equity: Number(intent.account_equity), daily_pnl: Number(intent.daily_pnl), current_drawdown_pct: Number(intent.current_drawdown_pct), account_id: intent.account_id ? Number(intent.account_id) : null, bot_id: intent.bot_id ? Number(intent.bot_id) : null });
      setDecision(result); setError("");
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };
  return (
    <section className="ops-page risk-engine-page">
      <section className={`panel-accent ops-command risk-command ${killActive ? "halted" : "armed"}`}>
        <div>
          <p className="eyebrow">Risk Engine · backend enforced</p>
          <h2>{killActive ? "Ejecucion detenida" : "Motor habilitado para validacion"}</h2>
          <span>Los límites y cada cambio quedan persistidos en SQLite. Paper y rebalanceos Spot pasan por este motor; live permanece bloqueado.</span>
        </div>
        <strong>{killActive ? "KILL SWITCH ON" : "KILL SWITCH OFF"}</strong>
      </section>

      {error && <div className="chart-state error">{error}</div>}
      <PageSubtabs
        tabs={[
          ["overview", "Overview", "estado operativo"],
          ["controls", "Controls", "limites + kill switch"],
          ["policies", "Policies", "cuentas + bots"],
          ["validator", "Validator", "pre-trade gate"],
          ["ledger", "Ledger", "decisiones + cambios"],
        ]}
        activeTab={activeTab}
        onChange={setActiveTab}
      />
      {!profile ? <div className="chart-state">Cargando estado real del backend…</div> : <>
        {activeTab === "overview" && <section className="risk-overview-grid">
          <article><span>Kill switch</span><strong className={killActive ? "negative" : "positive"}>{killActive ? "ACTIVE" : "INACTIVE"}</strong><small>{profile.kill_switch.reason}</small></article>
          <article><span>Paper + Spot simulation</span><strong>RISK GATED</strong><small>Toda orden pasa por validación backend.</small></article>
          <article><span>Live execution</span><strong className="negative">BLOCKED</strong><small>Sin adapters privados ni API keys.</small></article>
          <article><span>Position limit</span><strong>{Number(profile.limits.max_position_pct).toFixed(2)}%</strong><small>Exposición proyectada máxima por activo.</small></article>
          <article><span>Daily loss</span><strong>{Number(profile.limits.max_daily_loss_pct).toFixed(2)}%</strong><small>Corte por perdida diaria.</small></article>
          <article><span>Max drawdown</span><strong>{Number(profile.limits.max_drawdown_pct).toFixed(2)}%</strong><small>Guardrail sobre equity.</small></article>
          <article><span>Scoped policies</span><strong>{profile.policies?.filter((policy) => policy.status === "active").length || 0}</strong><small>Cuenta y bot · la regla más restrictiva gana.</small></article>
        </section>}

        {activeTab === "controls" && <section className="risk-workspace">
          <form className="exchange-panel risk-limits-form" onSubmit={saveLimits}>
            <div className="exchange-panel-head compact"><div><p className="eyebrow">Perfil global</p><h2>Limites operativos</h2></div><span>SQLite</span></div>
            <div className="risk-fields">
              {[
                ["max_position_pct", "Posicion maxima", "%"],
                ["max_daily_loss_pct", "Perdida diaria maxima", "%"],
                ["max_drawdown_pct", "Drawdown maximo", "%"],
                ["cooldown_minutes", "Cooldown", "min"],
              ].map(([key, label, unit]) => <label key={key}><span>{label}</span><div><input type="number" min="0" step="0.1" value={form[key]} onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))} /><i>{unit}</i></div></label>)}
              <label className="risk-whitelist"><span>Symbol whitelist</span><input value={Array.isArray(form.symbol_whitelist) ? form.symbol_whitelist.join(", ") : form.symbol_whitelist} onChange={(event) => setForm((current) => ({ ...current, symbol_whitelist: event.target.value }))} /></label>
            </div>
            <button className="primary-action" disabled={busy} type="submit">Guardar limites</button>
          </form>

          <section className="exchange-panel kill-switch-panel">
            <div className="exchange-panel-head compact"><div><p className="eyebrow">Corte de emergencia</p><h2>Kill switch</h2></div><span>{killActive ? "ACTIVE" : "INACTIVE"}</span></div>
            <p>{profile.kill_switch.reason}</p>
            <label><span>Motivo auditable</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} /></label>
            <button className={killActive ? "primary-action" : "danger-action"} disabled={busy || reason.trim().length < 3} onClick={toggleKillSwitch}>{killActive ? "Desactivar corte" : "Activar corte inmediato"}</button>
            <small>Desactivar el corte no habilita paper/live; solamente prepara la capa de validacion.</small>
          </section>
        </section>}

        {activeTab === "policies" && <section className="risk-policy-workspace">
          <form className="exchange-panel risk-policy-form" onSubmit={savePolicy}>
            <div className="exchange-panel-head compact"><div><p className="eyebrow">Hierarchical mandate</p><h2>Política por cuenta o bot</h2></div><span>MOST RESTRICTIVE</span></div>
            <div className="risk-policy-targets">
              <label><span>Ámbito</span><select value={policyForm.scope_type} onChange={(event) => { const scope = event.target.value; const targets = scope === "account" ? profile.policy_targets.accounts : profile.policy_targets.bots; setPolicyForm((current) => ({ ...current, scope_type: scope, scope_id: String(targets[0]?.id || "") })); }}><option value="account">Cuenta paper</option><option value="bot">Bot</option></select></label>
              <label><span>Destino</span><select required value={policyForm.scope_id} onChange={(event) => setPolicyForm((current) => ({ ...current, scope_id: event.target.value }))}>{(policyForm.scope_type === "account" ? profile.policy_targets.accounts : profile.policy_targets.bots).map((target) => <option key={target.id} value={target.id}>#{target.id} · {target.name || `Paper ${Number(target.cash_balance).toLocaleString()}`}</option>)}</select></label>
            </div>
            <label className="risk-policy-name"><span>Nombre</span><input required minLength="3" value={policyForm.name} onChange={(event) => setPolicyForm((current) => ({ ...current, name: event.target.value }))} /></label>
            <div className="risk-policy-fields">{[
              ["max_position_pct", "Posición máxima", "%"], ["max_daily_loss_pct", "Pérdida diaria", "%"],
              ["max_drawdown_pct", "Drawdown máximo", "%"], ["cooldown_minutes", "Cooldown", "min"],
            ].map(([key, label, unit]) => <label key={key}><span>{label}</span><div><input required type="number" min="0.1" step="0.1" value={policyForm[key]} onChange={(event) => setPolicyForm((current) => ({ ...current, [key]: event.target.value }))} /><i>{unit}</i></div></label>)}</div>
            <label className="risk-policy-name"><span>Whitelist</span><input required value={policyForm.symbol_whitelist} onChange={(event) => setPolicyForm((current) => ({ ...current, symbol_whitelist: event.target.value }))} /></label>
            <label className="risk-policy-name"><span>Nota auditable</span><textarea required minLength="3" value={policyForm.notes} onChange={(event) => setPolicyForm((current) => ({ ...current, notes: event.target.value }))} /></label>
            <button className="primary-action" disabled={busy || !policyForm.scope_id} type="submit">Guardar nueva versión</button>
            <small>La política hija nunca amplía el riesgo global: usa mínimos para exposición/pérdidas y máximo para cooldown.</small>
          </form>

          <section className="exchange-panel risk-policy-registry">
            <div className="exchange-panel-head compact"><div><p className="eyebrow">Immutable versions</p><h2>Registro de políticas</h2></div><span>{profile.policies?.length || 0} POLICIES</span></div>
            <div className="risk-policy-list">{(profile.policies || []).map((policy) => <article className={policy.status} key={policy.id}>
              <header><div><span>{policy.scope_type.toUpperCase()} #{policy.scope_id}</span><strong>{policy.name}</strong></div><b>V{policy.current_version} · {policy.status.toUpperCase()}</b></header>
              <div><span><small>Posición</small><strong>{Number(policy.limits.max_position_pct).toFixed(1)}%</strong></span><span><small>Daily loss</small><strong>{Number(policy.limits.max_daily_loss_pct).toFixed(1)}%</strong></span><span><small>Drawdown</small><strong>{Number(policy.limits.max_drawdown_pct).toFixed(1)}%</strong></span><span><small>Cooldown</small><strong>{policy.limits.cooldown_minutes}m</strong></span></div>
              <p>{policy.limits.symbol_whitelist.join(" · ")}</p><small>{policy.notes}</small>
              <footer><button type="button" onClick={() => editPolicy(policy)}>Editar como V{policy.current_version + 1}</button>{policy.status === "active" && <button className="danger-action" type="button" disabled={busy} onClick={() => archivePolicy(policy)}>Archivar</button>}</footer>
            </article>)}{!(profile.policies || []).length && <div className="chart-state">Sin overrides. Global hard limits gobierna todas las validaciones.</div>}</div>
          </section>
        </section>}

        {activeTab === "ledger" && <section className="exchange-panel risk-audit-panel">
          <div className="exchange-panel-head compact"><div><p className="eyebrow">Audit trail</p><h2>Eventos recientes</h2></div><span>{profile.audit_log.length} eventos</span></div>
          {profile.audit_log.length ? <div className="risk-audit-list">{profile.audit_log.map((event) => <article key={event.id}><span>{event.event_type}</span><strong>{event.payload.reason || event.payload.name || (event.payload.symbol_whitelist || []).join(", ") || `Policy #${event.payload.policy_id || "--"}`}</strong><time>{new Date(event.created_at).toLocaleString()}</time></article>)}</div> : <div className="chart-state">Sin modificaciones todavía. El perfil seguro inicial ya está activo.</div>}
        </section>}

        {activeTab === "validator" && <section className="exchange-panel risk-validator-panel">
          <div className="exchange-panel-head compact"><div><p className="eyebrow">Pre-trade gate</p><h2>Validar intencion</h2></div><span>NO EXECUTION</span></div>
          <div className="risk-validator-grid">
            <form className="risk-fields" onSubmit={runValidation}>
              {[["symbol", "Symbol", "text"], ["requested_notional", "Notional solicitado", "number"], ["account_equity", "Equity cuenta", "number"], ["daily_pnl", "PnL diario", "number"], ["current_drawdown_pct", "Drawdown actual %", "number"], ["account_id", "Account ID opcional", "number"], ["bot_id", "Bot ID opcional", "number"]].map(([key, label, type]) => <label key={key}><span>{label}</span><input type={type} step="0.1" value={intent[key]} onChange={(event) => setIntent((current) => ({ ...current, [key]: event.target.value }))} /></label>)}
              <button className="primary-action" disabled={busy} type="submit">Evaluar contra Risk Engine</button>
            </form>
            <div className={`risk-decision ${decision?.approved ? "approved" : "rejected"}`}>
              {!decision ? <p>Completa la intencion para obtener una decision backend auditable.</p> : <><span>VALIDATION #{decision.validation_id}</span><h2>{decision.decision.toUpperCase()}</h2><p>{decision.approved ? "Todos los controles aprobaron la intencion." : decision.reasons.join(" · ")}</p><div>{decision.checks.map((check) => <small className={check.passed ? "pass" : "fail"} key={check.code}>{check.passed ? "PASS" : "FAIL"} · {check.code}</small>)}</div><div className="risk-resolution-trace">{decision.policy_resolution.layers.map((layer) => <small key={`${layer.scope_type}-${layer.scope_id}`}>{layer.scope_type.toUpperCase()} #{layer.scope_id} · {layer.version}</small>)}</div><code>{decision.policy_fingerprint.slice(0, 12)}…</code><em>No se ejecuto ninguna orden.</em></>}
            </div>
          </div>
        </section>}

        {activeTab === "ledger" && <section className="exchange-panel risk-validation-history">
          <div className="exchange-panel-head compact"><div><p className="eyebrow">Decision ledger</p><h2>Validaciones pre-trade</h2></div><span>{profile.validation_log?.length || 0} DECISIONES</span></div>
          <div className="risk-validation-list">
            {(profile.validation_log || []).map((validation) => <article className={validation.approved ? "approved" : "rejected"} key={validation.id}>
              <header><div><span>VALIDATION #{validation.id} · A{validation.account_id || "--"} · B{validation.bot_id || "--"}</span><strong>{validation.symbol} · {validation.mode.toUpperCase()}</strong></div><b>{validation.approved ? "APPROVED" : "REJECTED"}</b></header>
              <div className="risk-validation-metrics"><span><small>Notional</small><strong>${Number(validation.request.requested_notional || 0).toLocaleString()}</strong></span><span><small>Position</small><strong>{Number(validation.decision.metrics?.position_pct || 0).toFixed(2)}%</strong></span><span><small>Drawdown</small><strong>{Number(validation.decision.metrics?.current_drawdown_pct || 0).toFixed(2)}%</strong></span></div>
              <p>{validation.approved ? "Todos los guardrails aprobaron." : validation.decision.reasons.join(" · ")}</p>
              <div className="risk-resolution-trace">{(validation.policy_resolution?.layers || []).map((layer) => <small key={`${layer.scope_type}-${layer.scope_id}`}>{layer.scope_type.toUpperCase()} #{layer.scope_id} · {layer.version}</small>)}</div>
              <footer><code>{validation.execution_intent_id ? `INTENT ${validation.execution_intent_id.slice(0, 8)}` : `POLICY ${(validation.policy_fingerprint || "legacy").slice(0, 8)}`}</code><span>{validation.execution_status || "no execution"}</span><time>{new Date(validation.created_at).toLocaleString()}</time></footer>
            </article>)}
            {!(profile.validation_log || []).length && <div className="chart-state">Todavia no existen decisiones pre-trade persistidas.</div>}
          </div>
        </section>}
      </>}

      <section className="exchange-panel ops-panel"><div className="ops-warning"><strong>Live execution remains locked.</strong><p>No se gestionan claves reales. Paper Trading y los rebalanceos Spot consumen obligatoriamente esta validación antes de registrar operaciones simuladas.</p></div></section>
    </section>
  );
}
