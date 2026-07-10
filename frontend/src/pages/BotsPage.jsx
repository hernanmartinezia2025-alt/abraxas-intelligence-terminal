import React, { useEffect, useMemo, useRef, useState } from "react";
import { createBot, getBacktest, getBot, getBotBacktests, getBots, runBotBacktest } from "../api/client.js";
import BacktestComparisonPanel from "../features/backtests/BacktestComparisonPanel.jsx";
import BacktestEquityChart from "../features/charts/BacktestEquityChart.jsx";

const BOT_STAGES = [
  ["Saved Bots", "online", "Bots persistidos en SQLite con versiones auditables."],
  ["Strategy JSON", "online", "Cada version guarda reglas, parametros y perfil de riesgo."],
  ["Backtests", "online", "Runs auditables por version con costos, trades y equity persistidos."],
  ["Paper Mode", "locked", "Simulacion en tiempo real sin tocar dinero ni claves."],
  ["ROI Profile", "online", "ROI, benchmark, drawdown, profit factor, equity y comparacion A/B."],
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

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function formatPercentage(value, digits = 2) {
  const formatted = formatNumber(value, digits);
  return formatted === "--" ? formatted : `${formatted}%`;
}

export default function BotsPage({ selectedSymbol = "BTCUSDT" }) {
  const [bots, setBots] = useState([]);
  const [selectedBotId, setSelectedBotId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [backtesting, setBacktesting] = useState(false);
  const [runDetailLoading, setRunDetailLoading] = useState(false);
  const [backtests, setBacktests] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [selectedRun, setSelectedRun] = useState(null);
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    name: "",
    description: "",
    base_symbol: selectedSymbol,
    timeframe: "15m",
    risk_profile: "balanced",
  });
  const [backtestParams, setBacktestParams] = useState({
    initial_equity: 10000,
    fee_pct: 0.1,
    slippage_pct: 0.05,
    limit: 500,
  });
  const selectedBotIdRef = useRef(null);
  const detailRequestRef = useRef(0);
  const backtestsRequestRef = useRef(0);
  const runDetailRequestRef = useRef(0);

  const detailMatchesSelection = detail?.bot?.id === selectedBotId;
  const latestVersion = detailMatchesSelection ? detail?.versions?.[0] : null;
  const selectedVersion = detailMatchesSelection
    ? detail?.versions?.find((version) => version.id === Number(selectedVersionId)) || latestVersion
    : null;
  const visibleBacktests = selectedVersion
    ? backtests.filter((run) => run.bot_version_id === selectedVersion.id)
    : [];
  const runVersion = detail?.versions?.find((version) => version.id === selectedRun?.bot_version_id);
  const runMetrics = selectedRun ? { ...selectedRun, ...(selectedRun.metrics || {}) } : {};
  const effectiveEngineVersion = runMetrics.engine_version || selectedRun?.engine_version || "";
  const isV2Run = String(effectiveEngineVersion).startsWith("2.");
  const runWarnings = selectedRun?.warnings || runMetrics.warnings || [];
  const runTrades = selectedRun?.trades || [];
  const runEquity = selectedRun?.equity_curve || [];
  const strategyPreview = useMemo(() => {
    if (!selectedVersion?.strategy) return "{}";
    return JSON.stringify(selectedVersion.strategy, null, 2);
  }, [selectedVersion]);
  const numericBacktestParams = {
    initial_equity: Number(backtestParams.initial_equity),
    fee_pct: Number(backtestParams.fee_pct),
    slippage_pct: Number(backtestParams.slippage_pct),
    limit: Number(backtestParams.limit),
  };
  const backtestParamsValid = (
    numericBacktestParams.initial_equity > 0
    && numericBacktestParams.initial_equity <= 1_000_000_000
    && numericBacktestParams.fee_pct >= 0
    && numericBacktestParams.fee_pct <= 5
    && numericBacktestParams.slippage_pct >= 0
    && numericBacktestParams.slippage_pct <= 5
    && Number.isInteger(numericBacktestParams.limit)
    && numericBacktestParams.limit >= 60
    && numericBacktestParams.limit <= 1000
  );

  async function loadBots({ silent = false } = {}) {
    if (!silent) setLoading(true);
    setError("");
    try {
      const payload = await getBots(100);
      setBots(payload.bots || []);
      const currentExists = payload.bots?.some((bot) => bot.id === selectedBotIdRef.current);
      const nextId = currentExists ? selectedBotIdRef.current : payload.bots?.[0]?.id || null;
      if (nextId !== selectedBotIdRef.current) selectBot(nextId);
    } catch (err) {
      setError(err.message);
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function loadDetail(botId) {
    const requestId = ++detailRequestRef.current;
    if (!botId) {
      setDetail(null);
      setSelectedVersionId("");
      return;
    }
    setError("");
    try {
      const payload = await getBot(botId);
      if (requestId !== detailRequestRef.current || selectedBotIdRef.current !== botId) return;
      setDetail(payload);
      setSelectedVersionId((current) => {
        const exists = payload.versions?.some((version) => version.id === Number(current));
        return exists ? current : String(payload.versions?.[0]?.id || "");
      });
    } catch (err) {
      if (requestId !== detailRequestRef.current) return;
      setError(err.message);
    }
  }

  async function loadBacktests(botId, { preferredRunId = null } = {}) {
    const requestId = ++backtestsRequestRef.current;
    if (!botId) {
      setBacktests([]);
      setSelectedRunId(null);
      setSelectedRun(null);
      return;
    }
    try {
      const payload = await getBotBacktests(botId, 20);
      if (requestId !== backtestsRequestRef.current || selectedBotIdRef.current !== botId) return;
      const runs = payload.runs || [];
      setBacktests(runs);
      setSelectedRunId((current) => {
        const requested = preferredRunId || current;
        return runs.some((run) => run.id === Number(requested)) ? Number(requested) : runs[0]?.id || null;
      });
    } catch (err) {
      if (requestId !== backtestsRequestRef.current) return;
      setError(err.message);
    }
  }

  async function loadRunDetail(runId) {
    const requestId = ++runDetailRequestRef.current;
    if (!runId) {
      setSelectedRun(null);
      setRunDetailLoading(false);
      return;
    }
    const expectedBotId = selectedBotIdRef.current;
    setRunDetailLoading(true);
    setSelectedRun(null);
    try {
      const payload = await getBacktest(runId);
      if (
        requestId !== runDetailRequestRef.current
        || selectedBotIdRef.current !== expectedBotId
        || payload.bot_id !== expectedBotId
      ) return;
      setSelectedRun(payload);
    } catch (err) {
      if (requestId !== runDetailRequestRef.current) return;
      setError(err.message);
      setSelectedRun(null);
    } finally {
      if (requestId === runDetailRequestRef.current) setRunDetailLoading(false);
    }
  }

  function selectBot(botId) {
    detailRequestRef.current += 1;
    backtestsRequestRef.current += 1;
    runDetailRequestRef.current += 1;
    selectedBotIdRef.current = botId;
    setSelectedBotId(botId);
    setDetail(null);
    setSelectedVersionId("");
    setBacktests([]);
    setSelectedRunId(null);
    setSelectedRun(null);
    setRunDetailLoading(false);
  }

  function selectVersion(versionId) {
    runDetailRequestRef.current += 1;
    setSelectedVersionId(versionId);
    const nextRun = backtests.find((run) => run.bot_version_id === Number(versionId));
    setSelectedRunId(nextRun?.id || null);
    setSelectedRun(null);
  }

  function selectRun(runId) {
    runDetailRequestRef.current += 1;
    setSelectedRunId(runId);
    setSelectedRun(null);
    setRunDetailLoading(Boolean(runId));
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
      selectBot(payload.bot.id);
      setDetail(payload);
      setSelectedVersionId(String(payload.versions?.[0]?.id || ""));
      setForm((current) => ({ ...current, name: "", description: "" }));
      await loadBots({ silent: true });
      await loadBacktests(payload.bot.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleRunBacktest() {
    if (!detailMatchesSelection || !selectedVersion) return;
    if (!backtestParamsValid) {
      setError("Revisa los parametros: capital positivo, costos entre 0% y 5%, y 60-1000 barras enteras.");
      return;
    }
    const botId = selectedBotId;
    setBacktesting(true);
    setError("");
    try {
      const payload = await runBotBacktest(botId, {
        version_id: selectedVersion.id,
        ...numericBacktestParams,
      });
      if (selectedBotIdRef.current !== botId) return;
      setSelectedRun(payload);
      setSelectedRunId(payload.id);
      await loadBacktests(botId, { preferredRunId: payload.id });
    } catch (err) {
      setError(err.message);
    } finally {
      setBacktesting(false);
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
    loadBacktests(selectedBotId);
  }, [selectedBotId]);

  useEffect(() => {
    if (!selectedVersionId) return;
    const matchingRuns = backtests.filter((run) => run.bot_version_id === Number(selectedVersionId));
    if (!matchingRuns.some((run) => run.id === selectedRunId)) {
      runDetailRequestRef.current += 1;
      setSelectedRun(null);
      setSelectedRunId(matchingRuns[0]?.id || null);
    }
  }, [backtests, selectedRunId, selectedVersionId]);

  useEffect(() => {
    if (selectedRun?.id === selectedRunId) {
      setRunDetailLoading(false);
      return;
    }
    loadRunDetail(selectedRunId);
  }, [selectedRunId]);

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
                onClick={() => selectBot(bot.id)}
                type="button"
                aria-pressed={bot.id === selectedBotId}
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
            <h2>{detailMatchesSelection ? detail.bot.name : "Sin bot seleccionado"}</h2>
          </div>
          <button
            type="button"
            onClick={handleRunBacktest}
            disabled={!detailMatchesSelection || !selectedVersion || !backtestParamsValid || backtesting}
          >
            {backtesting ? "Backtesting..." : "Run backtest"}
          </button>
        </div>
        {detailMatchesSelection ? (
          <div>
            <div className="backtest-controls">
              <label>
                Version
                <select value={selectedVersionId} onChange={(event) => selectVersion(event.target.value)} disabled={backtesting}>
                  {(detail.versions || []).map((version) => (
                    <option key={version.id} value={version.id}>v{version.version} · #{version.id}</option>
                  ))}
                </select>
              </label>
              <label>
                Capital inicial
                <input
                  type="number"
                  min="1"
                  max="1000000000"
                  step="100"
                  disabled={backtesting}
                  value={backtestParams.initial_equity}
                  onChange={(event) => setBacktestParams((current) => ({ ...current, initial_equity: event.target.value }))}
                />
              </label>
              <label>
                Fee %
                <input
                  type="number"
                  min="0"
                  max="5"
                  step="0.01"
                  disabled={backtesting}
                  value={backtestParams.fee_pct}
                  onChange={(event) => setBacktestParams((current) => ({ ...current, fee_pct: event.target.value }))}
                />
              </label>
              <label>
                Slippage %
                <input
                  type="number"
                  min="0"
                  max="5"
                  step="0.01"
                  disabled={backtesting}
                  value={backtestParams.slippage_pct}
                  onChange={(event) => setBacktestParams((current) => ({ ...current, slippage_pct: event.target.value }))}
                />
              </label>
              <label>
                Barras solicitadas
                <input
                  type="number"
                  min="60"
                  max="1000"
                  step="20"
                  disabled={backtesting}
                  value={backtestParams.limit}
                  onChange={(event) => setBacktestParams((current) => ({ ...current, limit: event.target.value }))}
                />
              </label>
            </div>
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
                <span>Version del run</span>
                <strong>{selectedRun ? (runVersion ? `v${runVersion.version}` : `#${selectedRun.bot_version_id}`) : "--"}</strong>
                <small>{selectedRun ? `run #${selectedRun.id}` : "sin run"}</small>
              </article>
              <article>
                <span>Engine</span>
                <strong>{effectiveEngineVersion || "--"}</strong>
                <small>{runMetrics.position_mode || selectedRun?.position_mode || "long-only"}</small>
              </article>
              <article>
                <span>ROI estrategia</span>
                <strong>{formatPercentage(runMetrics.roi_pct, 2)}</strong>
                <small>{selectedRun ? formatTime(selectedRun.created_at) : "sin backtest"}</small>
              </article>
              <article>
                <span>Buy &amp; hold</span>
                <strong>{formatPercentage(runMetrics.benchmark_roi_pct, 2)}</strong>
                <small>mismo rango</small>
              </article>
              <article>
                <span>Alpha</span>
                <strong>{formatPercentage(runMetrics.alpha_pct, 2)}</strong>
                <small>ROI - benchmark</small>
              </article>
              <article>
                <span>Drawdown</span>
                <strong>{formatPercentage(runMetrics.max_drawdown_pct, 2)}</strong>
                <small>max DD</small>
              </article>
              <article>
                <span>Trades</span>
                <strong>{runMetrics.total_trades ?? "--"}</strong>
                <small>win {formatPercentage(runMetrics.win_rate_pct, 1)}</small>
              </article>
              <article>
                <span>Profit factor</span>
                <strong>{formatNumber(runMetrics.profit_factor, 2)}</strong>
                <small>{isV2Run ? "sobre PnL neto" : "metrica legacy"}</small>
              </article>
              <article>
                <span>Fees pagadas</span>
                <strong>{formatNumber(runMetrics.total_fees, 2)}</strong>
                <small>fee {formatNumber(runMetrics.fee_pct, 3)}%</small>
              </article>
              <article>
                <span>Warnings</span>
                <strong>{runWarnings.length}</strong>
                <small>{runMetrics.data_points ?? "--"} puntos</small>
              </article>
              <pre>{strategyPreview}</pre>
            </div>
          </div>
        ) : (
          <div className="map-empty">
            <strong>Sin bot seleccionado</strong>
            <span>Crea un bot draft o selecciona uno existente para ver su estrategia.</span>
          </div>
        )}
      </section>

      <section className="exchange-panel bot-detail-panel">
        <div className="exchange-panel-head compact">
          <div>
            <p className="eyebrow">Backtest Runs</p>
            <h2>{visibleBacktests.length} simulaciones de {selectedVersion ? `v${selectedVersion.version}` : "la version"}</h2>
          </div>
          <span>SQLite</span>
        </div>
        <div className="backtest-list">
          {visibleBacktests.map((run) => (
            <button
              type="button"
              className={run.id === selectedRunId ? "active" : ""}
              key={run.id}
              onClick={() => selectRun(run.id)}
              aria-pressed={run.id === selectedRunId}
            >
              <div>
                <strong>Run #{run.id}</strong>
                <span>{run.symbol} / {run.timeframe} · version #{run.bot_version_id}</span>
              </div>
              <b className={Number(run.roi_pct || 0) >= 0 ? "positive" : "negative"}>{formatPercentage(run.roi_pct, 2)}</b>
              <b>{formatPercentage(run.max_drawdown_pct, 2)} DD</b>
              <b>{run.total_trades} trades</b>
              <small>{formatTime(run.created_at)}</small>
            </button>
          ))}
          {!visibleBacktests.length && (
            <div className="map-empty">
              <strong>Sin backtests todavia</strong>
              <span>Ejecuta Run backtest para guardar el primer resultado de esta version.</span>
            </div>
          )}
        </div>
      </section>

      <BacktestComparisonPanel
        botId={selectedBotId}
        runs={backtests}
        versions={detailMatchesSelection ? detail.versions || [] : []}
      />

      <section className="exchange-panel backtest-analysis-panel">
        <div className="exchange-panel-head compact">
          <div>
            <p className="eyebrow">Backtest Detail</p>
            <h2>{selectedRun ? `Run #${selectedRun.id} · equity y auditoria` : "Selecciona un run"}</h2>
          </div>
          <span>{runDetailLoading ? "LOADING" : selectedRun?.execution_model || runMetrics.execution_model || "SQLite"}</span>
        </div>
        {selectedRun ? (
          <div className="backtest-analysis-grid">
            <BacktestEquityChart points={runEquity} />
            <aside className="backtest-warning-panel">
              <div>
                <span>Rango</span>
                <strong>{formatTime(selectedRun.input_start)} → {formatTime(selectedRun.input_end)}</strong>
              </div>
              <div>
                <span>Modelo de ejecucion</span>
                <strong>{runMetrics.execution_model || selectedRun.execution_model}</strong>
              </div>
              <div>
                <span>Calidad de datos</span>
                <strong>{selectedRun.data_quality?.rows_used ?? runMetrics.data_points ?? "--"} filas · {selectedRun.data_quality?.gap_count ?? "--"} gaps</strong>
              </div>
              <div className="backtest-warning-list">
                {runWarnings.map((item, index) => (
                  <article className={item.severity || "warning"} key={`${item.code || "warning"}-${index}`}>
                    <b>{item.code || "WARNING"}</b>
                    <p>{item.message}</p>
                  </article>
                ))}
                {!runWarnings.length && <span className="research-empty">Sin warnings registrados para este run.</span>}
              </div>
            </aside>
          </div>
        ) : (
          <div className="map-empty">
            <strong>Sin detalle seleccionado</strong>
            <span>Selecciona un run persistido para cargar su equity, benchmark, warnings y trades.</span>
          </div>
        )}
      </section>

      <section className="exchange-panel backtest-trades-panel">
        <div className="exchange-panel-head compact">
          <div>
            <p className="eyebrow">Trades</p>
            <h2>{selectedRun ? `${runTrades.length} operaciones persistidas` : "Tabla por backtest"}</h2>
          </div>
          <span>NET PNL</span>
        </div>
        {runTrades.length ? (
          <div className="backtest-trades-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Entrada</th>
                  <th>Salida</th>
                  <th>Entry px</th>
                  <th>Exit px</th>
                  <th>Cantidad</th>
                  <th>Fees</th>
                  <th>PnL neto</th>
                  <th>Retorno</th>
                  <th>Motivo</th>
                </tr>
              </thead>
              <tbody>
                {runTrades.map((trade, index) => (
                  <tr key={trade.id || trade.trade_index || index}>
                    <td>{trade.trade_index || index + 1}</td>
                    <td>{formatTime(trade.entry_timestamp)}</td>
                    <td>{formatTime(trade.exit_timestamp)}</td>
                    <td>{formatNumber(trade.entry_price, 4)}</td>
                    <td>{formatNumber(trade.exit_price, 4)}</td>
                    <td>{formatNumber(trade.quantity, 6)}</td>
                    <td>{formatNumber(trade.fees_paid, 3)}</td>
                    <td className={Number(trade.pnl || 0) >= 0 ? "positive" : "negative"}>{formatNumber(trade.pnl, 3)}</td>
                    <td className={Number(trade.return_pct || 0) >= 0 ? "positive" : "negative"}>{formatNumber(trade.return_pct, 2)}%</td>
                    <td>{trade.exit_reason || (trade.forced_exit ? "end_of_data" : "legacy")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="map-empty">
            <strong>Sin trades persistidos</strong>
            <span>{selectedRun ? "El run no produjo operaciones o es un registro legacy sin detalle normalizado." : "Selecciona un run para ver sus operaciones."}</span>
          </div>
        )}
      </section>
    </section>
  );
}
