import React from "react";

const RISK_CONTROLS = [
  ["Max position size", "planned", "Limite duro por bot, usuario, exchange y simbolo."],
  ["Max daily loss", "planned", "Corte operativo cuando el dia supera perdida definida."],
  ["Max drawdown", "planned", "Pausa automatica si la curva cae mas de lo permitido."],
  ["Cooldown", "planned", "Tiempo muerto despues de perdidas o volatilidad anomala."],
  ["Symbol whitelist", "planned", "Cada bot opera solo activos autorizados."],
  ["Kill switch", "mandatory", "Corte total de paper/live execution desde backend."],
];

export default function RiskPage() {
  return (
    <section className="ops-page">
      <section className="panel-accent ops-command">
        <div>
          <p className="eyebrow">Risk Engine</p>
          <h2>Control antes que ejecucion</h2>
          <span>Ningun bot debe tocar dinero real sin limites duros, logs y posibilidad de corte inmediato.</span>
        </div>
        <strong>LOCKED</strong>
      </section>

      <section className="ops-grid">
        {RISK_CONTROLS.map(([title, state, description]) => (
          <article className={`ops-card ${state}`} key={title}>
            <div>
              <span>{state}</span>
              <h2>{title}</h2>
            </div>
            <p>{description}</p>
          </article>
        ))}
      </section>

      <section className="exchange-panel ops-panel">
        <div className="exchange-panel-head compact">
          <div>
            <p className="eyebrow">Doctrine</p>
            <h2>Regla de seguridad</h2>
          </div>
          <span>backend-only</span>
        </div>
        <div className="ops-warning">
          <strong>No live execution yet.</strong>
          <p>Exchange keys, ordenes reales y automatizacion live quedan fuera hasta tener RBAC, secretos cifrados, paper mode, auditoria y kill switch.</p>
        </div>
      </section>
    </section>
  );
}
