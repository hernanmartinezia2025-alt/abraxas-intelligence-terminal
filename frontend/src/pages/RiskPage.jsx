import React, { useEffect, useState } from "react";
import { getRiskProfile, updateKillSwitch, updateRiskLimits, validateRiskIntent } from "../api/client.js";
import PageSubtabs from "../components/PageSubtabs.jsx";

const EMPTY = { max_position_pct: 10, max_daily_loss_pct: 3, max_drawdown_pct: 12, cooldown_minutes: 30, symbol_whitelist: [] };

export default function RiskPage() {
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [reason, setReason] = useState("Manual operator control");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [intent, setIntent] = useState({ symbol: "BTCUSDT", requested_notional: 500, account_equity: 10000, daily_pnl: 0, current_drawdown_pct: 0 });
  const [decision, setDecision] = useState(null);
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

  const killActive = profile?.kill_switch?.active ?? true;
  const runValidation = async (event) => {
    event.preventDefault(); setBusy(true);
    try {
      const result = await validateRiskIntent({ ...intent, mode: "validation", side: "long", requested_notional: Number(intent.requested_notional), account_equity: Number(intent.account_equity), daily_pnl: Number(intent.daily_pnl), current_drawdown_pct: Number(intent.current_drawdown_pct) });
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
          <span>Los limites y cada cambio quedan persistidos en SQLite. Paper pasa por este motor; live permanece bloqueado.</span>
        </div>
        <strong>{killActive ? "KILL SWITCH ON" : "KILL SWITCH OFF"}</strong>
      </section>

      {error && <div className="chart-state error">{error}</div>}
      <PageSubtabs
        tabs={[
          ["overview", "Overview", "estado operativo"],
          ["controls", "Controls", "limites + kill switch"],
          ["validator", "Validator", "pre-trade gate"],
          ["ledger", "Ledger", "decisiones + cambios"],
        ]}
        activeTab={activeTab}
        onChange={setActiveTab}
      />
      {!profile ? <div className="chart-state">Cargando estado real del backend…</div> : <>
        {activeTab === "overview" && <section className="risk-overview-grid">
          <article><span>Kill switch</span><strong className={killActive ? "negative" : "positive"}>{killActive ? "ACTIVE" : "INACTIVE"}</strong><small>{profile.kill_switch.reason}</small></article>
          <article><span>Paper execution</span><strong>RISK GATED</strong><small>Toda orden pasa por validacion backend.</small></article>
          <article><span>Live execution</span><strong className="negative">BLOCKED</strong><small>Sin adapters privados ni API keys.</small></article>
          <article><span>Position limit</span><strong>{Number(profile.limits.max_position_pct).toFixed(2)}%</strong><small>Maximo por intencion.</small></article>
          <article><span>Daily loss</span><strong>{Number(profile.limits.max_daily_loss_pct).toFixed(2)}%</strong><small>Corte por perdida diaria.</small></article>
          <article><span>Max drawdown</span><strong>{Number(profile.limits.max_drawdown_pct).toFixed(2)}%</strong><small>Guardrail sobre equity.</small></article>
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

        {activeTab === "ledger" && <section className="exchange-panel risk-audit-panel">
          <div className="exchange-panel-head compact"><div><p className="eyebrow">Audit trail</p><h2>Eventos recientes</h2></div><span>{profile.audit_log.length} eventos</span></div>
          {profile.audit_log.length ? <div className="risk-audit-list">{profile.audit_log.map((event) => <article key={event.id}><span>{event.event_type}</span><strong>{event.payload.reason || (event.payload.symbol_whitelist || []).join(", ")}</strong><time>{new Date(event.created_at).toLocaleString()}</time></article>)}</div> : <div className="chart-state">Sin modificaciones todavía. El perfil seguro inicial ya está activo.</div>}
        </section>}

        {activeTab === "validator" && <section className="exchange-panel risk-validator-panel">
          <div className="exchange-panel-head compact"><div><p className="eyebrow">Pre-trade gate</p><h2>Validar intencion</h2></div><span>NO EXECUTION</span></div>
          <div className="risk-validator-grid">
            <form className="risk-fields" onSubmit={runValidation}>
              {[["symbol", "Symbol", "text"], ["requested_notional", "Notional solicitado", "number"], ["account_equity", "Equity cuenta", "number"], ["daily_pnl", "PnL diario", "number"], ["current_drawdown_pct", "Drawdown actual %", "number"]].map(([key, label, type]) => <label key={key}><span>{label}</span><input type={type} step="0.1" value={intent[key]} onChange={(event) => setIntent((current) => ({ ...current, [key]: event.target.value }))} /></label>)}
              <button className="primary-action" disabled={busy} type="submit">Evaluar contra Risk Engine</button>
            </form>
            <div className={`risk-decision ${decision?.approved ? "approved" : "rejected"}`}>
              {!decision ? <p>Completa la intencion para obtener una decision backend auditable.</p> : <><span>VALIDATION #{decision.validation_id}</span><h2>{decision.decision.toUpperCase()}</h2><p>{decision.approved ? "Todos los controles aprobaron la intencion." : decision.reasons.join(" · ")}</p><div>{decision.checks.map((check) => <small className={check.passed ? "pass" : "fail"} key={check.code}>{check.passed ? "PASS" : "FAIL"} · {check.code}</small>)}</div><em>No se ejecuto ninguna orden.</em></>}
            </div>
          </div>
        </section>}

        {activeTab === "ledger" && <section className="exchange-panel risk-validation-history">
          <div className="exchange-panel-head compact"><div><p className="eyebrow">Decision ledger</p><h2>Validaciones pre-trade</h2></div><span>{profile.validation_log?.length || 0} DECISIONES</span></div>
          <div className="risk-validation-list">
            {(profile.validation_log || []).map((validation) => <article className={validation.approved ? "approved" : "rejected"} key={validation.id}>
              <header><div><span>VALIDATION #{validation.id}</span><strong>{validation.symbol} · {validation.mode.toUpperCase()}</strong></div><b>{validation.approved ? "APPROVED" : "REJECTED"}</b></header>
              <div className="risk-validation-metrics"><span><small>Notional</small><strong>${Number(validation.request.requested_notional || 0).toLocaleString()}</strong></span><span><small>Position</small><strong>{Number(validation.decision.metrics?.position_pct || 0).toFixed(2)}%</strong></span><span><small>Drawdown</small><strong>{Number(validation.decision.metrics?.current_drawdown_pct || 0).toFixed(2)}%</strong></span></div>
              <p>{validation.approved ? "Todos los guardrails aprobaron." : validation.decision.reasons.join(" · ")}</p>
              <footer><code>{validation.execution_intent_id ? `INTENT ${validation.execution_intent_id.slice(0, 8)}` : "VALIDATION ONLY"}</code><span>{validation.execution_status || "no execution"}</span><time>{new Date(validation.created_at).toLocaleString()}</time></footer>
            </article>)}
            {!(profile.validation_log || []).length && <div className="chart-state">Todavia no existen decisiones pre-trade persistidas.</div>}
          </div>
        </section>}
      </>}

      <section className="exchange-panel ops-panel"><div className="ops-warning"><strong>Live execution remains locked.</strong><p>No se gestionan claves reales. Paper Trading ya consume obligatoriamente esta validacion backend antes de crear fills simulados.</p></div></section>
    </section>
  );
}
