import React from "react";

const BOT_STAGES = [
  ["Bot Forge", "next", "Crear perfiles de bot desde hipotesis, features y reglas."],
  ["Saved Bots", "planned", "Guardar bots con estado, version y configuracion auditable."],
  ["Backtests", "required", "Probar cada version contra market_candles antes de simular."],
  ["Paper Mode", "locked", "Simulacion en tiempo real sin tocar dinero ni claves."],
  ["ROI Profile", "planned", "ROI, drawdown, win rate, profit factor y curva de equity."],
  ["Live Execution", "blocked", "Bloqueado hasta tener risk engine, permisos y kill switch."],
];

const BOT_REQUIREMENTS = [
  "market_candles persistidos",
  "asset_features bot-ready",
  "regime_snapshots disponibles",
  "backtest_runs pendiente",
  "risk limits pendiente",
  "paper trading pendiente",
];

export default function BotsPage() {
  return (
    <section className="ops-page">
      <section className="panel-accent ops-command">
        <div>
          <p className="eyebrow">Bot Forge</p>
          <h2>Laboratorio de bots auditables</h2>
          <span>Los bots aparecen como universo propio, pero la ejecucion real queda bloqueada hasta backtest, paper mode y risk engine.</span>
        </div>
        <strong>NO LIVE</strong>
      </section>

      <section className="ops-grid">
        {BOT_STAGES.map(([title, state, description]) => (
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
            <p className="eyebrow">Bot requirements</p>
            <h2>Entrada minima antes de crear bots reales</h2>
          </div>
          <span>audit first</span>
        </div>
        <div className="ops-checklist">
          {BOT_REQUIREMENTS.map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      </section>
    </section>
  );
}
