import React, { useEffect, useState } from "react";
import { getRiskProfile, updateKillSwitch, updateRiskLimits } from "../api/client.js";

const EMPTY = { max_position_pct: 10, max_daily_loss_pct: 3, max_drawdown_pct: 12, cooldown_minutes: 30, symbol_whitelist: [] };

export default function RiskPage() {
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [reason, setReason] = useState("Manual operator control");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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
  return (
    <section className="ops-page risk-engine-page">
      <section className={`panel-accent ops-command risk-command ${killActive ? "halted" : "armed"}`}>
        <div>
          <p className="eyebrow">Risk Engine · backend enforced</p>
          <h2>{killActive ? "Ejecucion detenida" : "Motor habilitado para validacion"}</h2>
          <span>Los limites y cada cambio quedan persistidos en SQLite. Paper y live continúan bloqueados.</span>
        </div>
        <strong>{killActive ? "KILL SWITCH ON" : "KILL SWITCH OFF"}</strong>
      </section>

      {error && <div className="chart-state error">{error}</div>}
      {!profile ? <div className="chart-state">Cargando estado real del backend…</div> : <>
        <section className="risk-workspace">
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
        </section>

        <section className="exchange-panel risk-audit-panel">
          <div className="exchange-panel-head compact"><div><p className="eyebrow">Audit trail</p><h2>Eventos recientes</h2></div><span>{profile.audit_log.length} eventos</span></div>
          {profile.audit_log.length ? <div className="risk-audit-list">{profile.audit_log.map((event) => <article key={event.id}><span>{event.event_type}</span><strong>{event.payload.reason || (event.payload.symbol_whitelist || []).join(", ")}</strong><time>{new Date(event.created_at).toLocaleString()}</time></article>)}</div> : <div className="chart-state">Sin modificaciones todavía. El perfil seguro inicial ya está activo.</div>}
        </section>
      </>}

      <section className="exchange-panel ops-panel"><div className="ops-warning"><strong>Live execution remains locked.</strong><p>No se gestionan claves ni órdenes. El siguiente consumidor autorizado será Paper Trading y deberá pasar esta validación backend.</p></div></section>
    </section>
  );
}
