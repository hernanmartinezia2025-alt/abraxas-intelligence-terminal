import React, { useEffect, useMemo, useState } from "react";
import { createBot, getBot, getBots } from "../api/client.js";

const BOT_STAGES = [
  ["Saved Bots", "online", "Bots persistidos en SQLite con versiones auditables."],
  ["Strategy JSON", "online", "Cada version guarda reglas, parametros y perfil de riesgo."],
  ["Backtests", "next", "Probar cada version contra market_candles antes de simular en vivo."],
  ["Paper Mode", "locked", "Simulacion en tiempo real sin tocar dinero ni claves."],
  ["ROI Profile", "planned", "ROI, drawdown, win rate, profit factor y curva de equity."],
  ["Live Execution", "blocked", "Bloqueado hasta tener risk engine, permisos y kill switch."],
];

const RISK_OPTIONS = ["conservative", "balanced", "aggressive"];
const TIMEFRAMES = ["5m", "15m", "1h", "4h"];

function defaultStrategy(symbol, timeframe, riskProfile) {
  const riskMap = {
    conservative: { max_position_pct: 5, stop_loss_pct: 1.2, take_profit_pct: 2.2 },
    balanced: { max_position_pct: 10, stop_loss_pct: 2, take_profit_pct: 4 },
    aggressive: { max_position_pct: 18, stop_loss_pct: 3.2, take_profit_pct: 6 },
  };
  return {
    engine: "rules",
    symbol,
    timeframe,
    entry: [
      { field: "return_5", operator: ">", value: 0 },
      { field: "trend_strength", operator: ">", value: 0.2 },
      { field: "risk_score", operator: "<", value: riskProfile === "aggressive" ? 78 : 65 },
    ],
    exit: [
      { field: "return_1", operator: "<", value: riskProfile === "conservative" ? -0.35 : -0.6 },
      { field: "z_score", operator: "<", value: -2 },
    ],
    risk: riskMap[riskProfile] || riskMap.balanced,
  };
}

function formatTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function BotsPage({ selectedSymbol = "BTCUSDT" }) {
  const [bots, setBots] = useState([]);
  const [selectedBotId, setSelectedBotId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    name: "",
    description: "",
    base_symbol: selectedSymbol,
    timeframe: "15m",
    risk_profile: "balanced",
  });

  const latestVersion = detail?.versions?.[0];
  const strategyPreview = useMemo(() => {
    if (!latestVersion?.strategy) return "{}";
    return JSON.stringify(latestVersion.strategy, null, 2);
  }, [latestVersion]);

  async function loadBots({ silent = false } = {}) {
    if (!silent) setLoading(true);
    setError("");
    try {
      const payload = await getBots(100);
      setBots(payload.bots || []);
      const nextId = selectedBotId || payload.bots?.[0]?.id || null;
      if (nextId) setSelectedBotId(nextId);
    } catch (err) {
      setError(err.message);
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function loadDetail(botId) {
    if (!botId) {
      setDetail(null);
      return;
    }
    setError("");
    try {
      const payload = await getBot(botId);
      setDetail(payload);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCreateBot(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const baseSymbol = form.base_symbol || selectedSymbol;
    const strategy = defaultStrategy(baseSymbol, form.timeframe, form.risk_profile);
    try {
      const payload = await createBot({
        ...form,
        name: form.name || `${baseSymbol} ${form.timeframe} bot`,
        base_symbol: baseSymbol,
        strategy,
        notes: "Version inicial generada desde Bot Forge.",
      });
      setSelectedBotId(payload.bot.id);
      setDetail(payload);
      setForm((current) => ({ ...current, name: "", description: "" }));
      await loadBots({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    loadBots();
  }, []);

  useEffect(() => {
    setForm((current) => ({ ...current, base_symbol: selectedSymbol }));
  }, [selectedSymbol]);

  useEffect(() => {
    loadDetail(selectedBotId);
  }, [selectedBotId]);

  return (
    <section className="ops-page">
      <section className="panel-accent ops-command">
        <div>
          <p className="eyebrow">Bot Forge</p>
          <h2>Bots reales, ejecucion bloqueada</h2>
          <span>Crear y versionar bots ya persiste en SQLite. Backtest, paper mode y live execution van por capas separadas.</span>
        </div>
        <strong>NO LIVE</strong>
      </section>

      {error && <div className="error-box">{error}</div>}

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

      <section className="bot-forge-grid">
        <form className="exchange-panel bot-form" onSubmit={handleCreateBot}>
          <div className="exchange-panel-head compact">
            <div>
              <p className="eyebrow">Create Bot</p>
              <h2>Nuevo bot versionado</h2>
            </div>
            <span>SQLite</span>
          </div>
          <div className="bot-form-body">
            <label>
              Nombre
              <input
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder={`${form.base_symbol} ${form.timeframe} bot`}
              />
            </label>
            <label>
              Descripcion
              <textarea
                value={form.description}
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="Hipotesis, mercado, setup y limite conceptual."
              />
            </label>
            <div className="bot-form-row">
              <label>
                Activo
                <input
                  value={form.base_symbol}
                  onChange={(event) => setForm((current) => ({ ...current, base_symbol: event.target.value.toUpperCase() }))}
                />
              </label>
              <label>
                Timeframe
                <select value={form.timeframe} onChange={(event) => setForm((current) => ({ ...current, timeframe: event.target.value }))}>
                  {TIMEFRAMES.map((timeframe) => (
                    <option key={timeframe}>{timeframe}</option>
                  ))}
                </select>
              </label>
              <label>
                Riesgo
                <select
                  value={form.risk_profile}
                  onChange={(event) => setForm((current) => ({ ...current, risk_profile: event.target.value }))}
                >
                  {RISK_OPTIONS.map((risk) => (
                    <option key={risk}>{risk}</option>
                  ))}
                </select>
              </label>
            </div>
            <button type="submit" disabled={saving}>
              {saving ? "Guardando..." : "Crear bot draft"}
            </button>
          </div>
        </form>

        <section className="exchange-panel bot-list-panel">
          <div className="exchange-panel-head compact">
            <div>
              <p className="eyebrow">Saved Bots</p>
              <h2>{bots.length} bots guardados</h2>
            </div>
            <button type="button" onClick={() => loadBots()} disabled={loading}>
              {loading ? "Leyendo..." : "Refrescar"}
            </button>
          </div>
          <div className="bot-list">
            {bots.map((bot) => (
              <button
                className={bot.id === selectedBotId ? "active" : ""}
                key={bot.id}
                onClick={() => setSelectedBotId(bot.id)}
                type="button"
              >
                <div>
                  <strong>{bot.name}</strong>
                  <span>{bot.base_symbol} / {bot.timeframe}</span>
                </div>
                <b>{bot.status}</b>
              </button>
            ))}
            {!bots.length && <span className="research-empty">Todavia no hay bots guardados.</span>}
          </div>
        </section>
      </section>

      <section className="exchange-panel bot-detail-panel">
        <div className="exchange-panel-head compact">
          <div>
            <p className="eyebrow">Bot Detail</p>
            <h2>{detail?.bot?.name || "Sin bot seleccionado"}</h2>
          </div>
          <span>{latestVersion ? `v${latestVersion.version}` : "no version"}</span>
        </div>
        {detail?.bot ? (
          <div className="bot-detail-grid">
            <article>
              <span>Estado</span>
              <strong>{detail.bot.status}</strong>
              <small>{detail.bot.mode}</small>
            </article>
            <article>
              <span>Activo</span>
              <strong>{detail.bot.base_symbol}</strong>
              <small>{detail.bot.timeframe}</small>
            </article>
            <article>
              <span>Riesgo</span>
              <strong>{detail.bot.risk_profile}</strong>
              <small>{formatTime(detail.bot.updated_at)}</small>
            </article>
            <article>
              <span>Versiones</span>
              <strong>{detail.versions.length}</strong>
              <small>auditables</small>
            </article>
            <pre>{strategyPreview}</pre>
          </div>
        ) : (
          <div className="map-empty">
            <strong>Sin bot seleccionado</strong>
            <span>Crea un bot draft o selecciona uno existente para ver su estrategia.</span>
          </div>
        )}
      </section>
    </section>
  );
}
