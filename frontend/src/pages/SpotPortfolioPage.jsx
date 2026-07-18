import React, { useEffect, useMemo, useState } from "react";
import {
  createSpotCashFlow,
  createSpotTransaction,
  getSpotAnalysis,
  getSpotPortfolio,
  getSpotProjection,
  quoteSpotTransaction,
  recordSpotValuation,
  resetSpotPortfolio,
} from "../api/client.js";

const money = (value) => Number(value || 0).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const percent = (value) => `${Number(value || 0) >= 0 ? "+" : ""}${Number(value || 0).toFixed(2)}%`;

function ProjectionChart({ points = [] }) {
  if (points.length < 2) return <div className="chart-state">Configura el escenario para ver la curva.</div>;
  const max = Math.max(...points.map((point) => point.value), 1);
  const line = points.map((point, index) => `${(index / (points.length - 1)) * 100},${96 - point.value / max * 88}`).join(" ");
  const contributed = points.map((point, index) => `${(index / (points.length - 1)) * 100},${96 - point.contributed / max * 88}`).join(" ");
  return <svg className="spot-projection-chart" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Escenario de crecimiento de cartera"><polyline className="contributed" points={contributed} /><polyline className="projected" points={line} /></svg>;
}

function EquityHistoryChart({ points = [] }) {
  if (!points.length) return <div className="chart-state">La curva comenzará con la primera operación o valuación registrada.</div>;
  const values = points.map((point) => Number(point.equity));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, Math.max(Math.abs(max), 1) * 0.002);
  const line = points.length === 1 ? "0,50 100,50" : points.map((point, index) => {
    const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
    const y = 92 - ((Number(point.equity) - min) / range) * 78;
    return `${x},${y}`;
  }).join(" ");
  return <div className="spot-equity-visual">
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Curva patrimonial persistida"><polyline points={line} /></svg>
    <div><span>{money(values[0])} inicial</span><strong>{money(values.at(-1))}</strong><span>{points.length} valuaciones</span></div>
  </div>;
}

const metric = (value, digits = 2) => value === null || value === undefined ? "--" : Number(value).toFixed(digits);

function TradingLatinoPanel({ strategy }) {
  if (!strategy) return null;
  const filters = strategy.filters;
  const rows = [
    { key: "directionality", label: "1 · Direccionalidad", value: filters.directionality.direction.replaceAll("_", " "), detail: `SQZMOM ${metric(filters.directionality.value, 4)} · previo ${metric(filters.directionality.previous, 4)}` },
    { key: "adx_strength", label: "2 · Fuerza ADX", value: filters.adx_strength.slope.replaceAll("_", " "), detail: `ADX14 ${metric(filters.adx_strength.value)} · previo ${metric(filters.adx_strength.previous)}` },
    { key: "ema_value_area", label: "3 · Área EMA", value: `${metric(filters.ema_value_area.distance_ema55_pct)}% de EMA55`, detail: `EMA10 ${money(filters.ema_value_area.ema10)} · EMA55 ${money(filters.ema_value_area.ema55)}` },
    { key: "volume_profile", label: "4 · POC de volumen", value: money(filters.volume_profile.poc), detail: "aproximación candle-volume" },
    { key: "time", label: "5 · Tiempo", value: filters.time.status.replaceAll("_", " "), detail: `${filters.time.setup_age_bars} velas · progreso ${metric(filters.time.price_progress_pct)}%` },
  ];
  return <section className={`trading-latino-panel ${strategy.decision === "buy_candidate" ? "candidate" : "blocked"}`}>
    <div className="trading-latino-head">
      <div><p className="eyebrow">Trading Latino · contrato auditable</p><h3>Setup long spot · cinco filtros</h3></div>
      <div className="trading-latino-score"><strong>{strategy.filters_passed}/5</strong><span>{strategy.decision.replaceAll("_", " ")}</span></div>
    </div>
    <div className="trading-latino-filters">
      {rows.map((row) => <article className={filters[row.key].passed ? "passed" : "failed"} key={row.key}>
        <div><span>{row.label}</span><b>{filters[row.key].passed ? "PASA" : "BLOQUEA"}</b></div>
        <strong>{row.value}</strong><small>{row.detail}</small>
      </article>)}
    </div>
    <div className="trading-latino-guardrail"><span>{strategy.guardrail}</span><small>{filters.volume_profile.warning}</small></div>
  </section>;
}

function TradingLatinoDoctrine({ doctrine }) {
  if (!doctrine) return null;
  const principles = doctrine.principles;
  const contrarianLabels = {
    watch_accumulation_after_confirmation: "Vigilar acumulación",
    protect_gains_do_not_chase: "Proteger ganancias",
    no_contrarian_extreme: "Sin extremo emocional",
    sentiment_unavailable: "Sentimiento sin datos",
  };
  const postureLabels = {
    observe: "Observar",
    protect_capital: "Proteger capital",
    candidate_requires_risk_plan: "Candidato · falta plan de riesgo",
  };
  const cards = [
    { label: "Huella institucional", value: "POC proxy", detail: `${money(principles.liquidity_footprint.poc)} · concentración, no identidad` },
    { label: "Probabilidades", value: "Edge sin validar", detail: `${principles.probability_discipline.confluence_score}/${principles.probability_discipline.confluence_total} es confluencia, no win rate` },
    { label: "Contra la manada", value: contrarianLabels[principles.contrarian_psychology.status] || principles.contrarian_psychology.status, detail: `Fear & Greed ${principles.contrarian_psychology.fear_greed_value ?? "--"} · ${principles.contrarian_psychology.fear_greed_regime}` },
    { label: "El tiempo invalida", value: principles.time_invalidation.invalidated ? "Setup vencido" : principles.time_invalidation.status.replaceAll("_", " "), detail: `${principles.time_invalidation.setup_age_bars} velas · progreso ${metric(principles.time_invalidation.price_progress_pct)}%` },
    { label: "Supervivencia", value: principles.capital_survival.kill_switch_active ? "Kill switch ON" : "Risk gate disponible", detail: `posición máx. ${metric(principles.capital_survival.max_position_pct)}% · DD máx. ${metric(principles.capital_survival.max_drawdown_pct)}%` },
  ];
  return <section className="trading-doctrine-panel">
    <div className="trading-doctrine-head">
      <div><p className="eyebrow">Doctrina operativa · datos + límites</p><h3>Paciencia, probabilidad y supervivencia</h3></div>
      <div><strong>{postureLabels[doctrine.posture] || doctrine.posture.replaceAll("_", " ")}</strong><span>NO ORDER</span></div>
    </div>
    <div className="trading-doctrine-grid">{cards.map((card) => <article key={card.label}><span>{card.label}</span><strong>{card.value}</strong><small>{card.detail}</small></article>)}</div>
    <div className="trading-doctrine-gaps"><b>Controles pendientes reales</b><span>Backtest 5F persistido</span><span>VPVR trade-level</span><span>Break-even y parciales spot</span></div>
  </section>;
}

function MarketModeBoundary({ policy }) {
  if (!policy) return null;
  return <section className="market-mode-boundary">
    <article className="spot-mode-card">
      <div><span>SPOT · PATRIMONIO</span><b>SIMULACIÓN</b></div>
      <strong>Acumular con paciencia</strong>
      <p>1D / 1W · long-only · 1x · DCA manual limitado por asignación.</p>
      <small>No usar SL automático no elimina drawdown, fallo del activo, custodia ni costo de oportunidad.</small>
    </article>
    <div className="mode-separation-lock"><span>≠</span><b>NO CONVERTIR MODOS</b><small>Una pérdida de futuros nunca se transforma en holding spot.</small></div>
    <article className="futures-mode-card">
      <div><span>FUTUROS · FLUJO</span><b>LOCKED</b></div>
      <strong>Infraestructura incompleta</strong>
      <p>1H / 4H · SL obligatorio · 3–5x planeado · máximo duro 10x.</p>
      <small>{policy.futures.unlock_requirements.length} controles pendientes antes de habilitar paper-margin.</small>
    </article>
  </section>;
}

export default function SpotPortfolioPage({ selectedSymbol = "BTCUSDT" }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [snapshot, setSnapshot] = useState(null);
  const [ticket, setTicket] = useState({ symbol: selectedSymbol, side: "buy", quantity: "0.001", notes: "" });
  const [quote, setQuote] = useState(null);
  const [quoteError, setQuoteError] = useState("");
  const [cashFlow, setCashFlow] = useState({ flow_type: "deposit", amount: "250", notes: "aporte DCA" });
  const [resetForm, setResetForm] = useState({ initial_cash: "10000", reason: "nuevo ciclo patrimonial" });
  const [scenario, setScenario] = useState({ monthly_contribution: 250, years: 4, annual_return_pct: 0 });
  const [projection, setProjection] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analysisTimeframe, setAnalysisTimeframe] = useState("1d");
  const [message, setMessage] = useState("");

  async function load() { try { setSnapshot(await getSpotPortfolio()); setMessage(""); } catch (error) { setMessage(error.message); } }
  useEffect(() => { load(); }, []);
  useEffect(() => { setTicket((current) => ({ ...current, symbol: selectedSymbol })); }, [selectedSymbol]);
  useEffect(() => {
    setAnalysis(null);
    getSpotAnalysis(selectedSymbol, analysisTimeframe, 300).then(setAnalysis).catch((error) => setMessage(error.message));
  }, [selectedSymbol, analysisTimeframe]);
  useEffect(() => {
    if (!snapshot) return;
    getSpotProjection({ initial_value: snapshot.equity, ...scenario }).then(setProjection).catch((error) => setMessage(error.message));
  }, [snapshot?.equity, scenario.monthly_contribution, scenario.years, scenario.annual_return_pct]);
  useEffect(() => {
    const quantity = Number(ticket.quantity);
    if (!ticket.symbol || !Number.isFinite(quantity) || quantity <= 0) { setQuote(null); setQuoteError(""); return undefined; }
    const timer = window.setTimeout(() => {
      quoteSpotTransaction({ ...ticket, quantity }).then((result) => { setQuote(result); setQuoteError(""); }).catch((error) => { setQuote(null); setQuoteError(error.message); });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [ticket.symbol, ticket.side, ticket.quantity, snapshot?.portfolio?.cash_balance]);

  async function submit(event) {
    event.preventDefault();
    setMessage("Registrando operación...");
    try {
      const result = await createSpotTransaction({ ...ticket, quantity: Number(ticket.quantity) });
      setSnapshot(result.snapshot);
      setMessage(`Operación #${result.transaction_id} persistida.`);
    } catch (error) { setMessage(error.message); }
  }

  async function submitCashFlow(event) {
    event.preventDefault();
    setMessage("Registrando movimiento de caja...");
    try {
      const result = await createSpotCashFlow({ ...cashFlow, amount: Number(cashFlow.amount) });
      setSnapshot(result.snapshot);
      setMessage(`Movimiento de caja #${result.cash_flow_id} persistido.`);
    } catch (error) { setMessage(error.message); }
  }

  async function refreshValuation() {
    setMessage("Contrastando marks persistidos...");
    try {
      const result = await recordSpotValuation();
      setSnapshot(result.snapshot);
      setMessage(result.recorded ? "Nueva valuación agregada a la curva." : "Sin cambios de cartera o marks; no se duplicó la valuación.");
    } catch (error) { setMessage(error.message); }
  }

  async function resetCycle(event) {
    event.preventDefault();
    setMessage("Iniciando nuevo ciclo patrimonial...");
    try {
      const result = await resetSpotPortfolio({ initial_cash: Number(resetForm.initial_cash), reason: resetForm.reason });
      setSnapshot(result.snapshot);
      setMessage(`Ciclo ${result.cycle_number} iniciado; el historial anterior permanece en el ledger.`);
    } catch (error) { setMessage(error.message); }
  }

  const allocation = useMemo(() => snapshot?.holdings || [], [snapshot]);
  if (!snapshot) return <section className="page-loading-state"><strong>Cargando cartera spot...</strong><small>{message}</small></section>;

  return <section className="spot-portfolio-page">
    <div className="spot-summary-grid">
      <article><span>Patrimonio</span><strong>{money(snapshot.equity)}</strong><small>cash + valor de mercado</small></article>
      <article><span>Disponible</span><strong>{money(snapshot.portfolio.cash_balance)}</strong><small>USDT simulado</small></article>
      <article><span>Invertido</span><strong>{money(snapshot.market_value)}</strong><small>{allocation.length} activos</small></article>
      <article><span>PnL total</span><strong className={snapshot.total_pnl >= 0 ? "positive" : "negative"}>{money(snapshot.total_pnl)}</strong><small>{percent(snapshot.total_return_pct)}</small></article>
      <article><span>PnL no realizado</span><strong className={snapshot.unrealized_pnl >= 0 ? "positive" : "negative"}>{money(snapshot.unrealized_pnl)}</strong><small>{percent(snapshot.return_pct)}</small></article>
      <article><span>Ciclo activo</span><strong>#{snapshot.portfolio.active_cycle}</strong><small>{money(snapshot.net_contributions)} aportado</small></article>
    </div>

    <nav className="spot-section-tabs" aria-label="Secciones de cartera">
      {[["overview", "Cartera", "posición + curva"], ["analysis", "Inteligencia", "1D / 1W"], ["ledger", "Auditoría", "caja + eventos"]].map(([key, label, detail]) => <button key={key} className={activeTab === key ? "active" : ""} onClick={() => setActiveTab(key)}><strong>{label}</strong><small>{detail}</small></button>)}
    </nav>
    {message && <div className="spot-status-line">{message}</div>}

    {activeTab === "overview" && <>
    <MarketModeBoundary policy={analysis?.market_mode_policy} />

    <div className="spot-workbench">
      <section className="exchange-panel spot-ticket">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Spot simulation</p><h2>Compra / venta auditable</h2></div><span>NO LIVE</span></div>
        <form onSubmit={submit}>
          <label>Activo<input value={ticket.symbol} onChange={(event) => setTicket({ ...ticket, symbol: event.target.value.toUpperCase() })} /></label>
          <label>Operación<select value={ticket.side} onChange={(event) => setTicket({ ...ticket, side: event.target.value })}><option value="buy">Comprar</option><option value="sell">Vender</option></select></label>
          <label>Cantidad<input type="number" min="0" step="any" value={ticket.quantity} onChange={(event) => setTicket({ ...ticket, quantity: event.target.value })} /></label>
          <label>Nota<input value={ticket.notes} onChange={(event) => setTicket({ ...ticket, notes: event.target.value })} placeholder="tesis o motivo" /></label>
          <div className={`spot-quote ${quote?.allowed ? "allowed" : "blocked"}`}>
            <span>PREVIEW · SIN EJECUCIÓN</span>
            {quote ? <><strong>{money(quote.notional)} + {money(quote.fee)} fee</strong><small>Mark {money(quote.price)} · caja posterior {money(quote.cash_balance_after)}</small>{!quote.allowed && <b>{quote.rejection_reason}</b>}</> : <small>{quoteError || "Esperando una cantidad válida."}</small>}
          </div>
          <button type="submit" disabled={!quote?.allowed}>Registrar operación spot</button>
          <small>Precio desde market_snapshots; fee 0.10%; ejecución real bloqueada.</small>
        </form>
      </section>

      <section className="exchange-panel spot-scenario">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Long-term lab</p><h2>Escenario de aportes</h2></div><span>SUPUESTOS DEL USUARIO</span></div>
        <div className="scenario-controls">
          <label>Aporte mensual<input type="number" min="0" value={scenario.monthly_contribution} onChange={(event) => setScenario({ ...scenario, monthly_contribution: Number(event.target.value) })} /></label>
          <label>Años<input type="number" min="1" max="40" value={scenario.years} onChange={(event) => setScenario({ ...scenario, years: Number(event.target.value) })} /></label>
          <label>Retorno anual supuesto<input type="number" min="-95" max="500" value={scenario.annual_return_pct} onChange={(event) => setScenario({ ...scenario, annual_return_pct: Number(event.target.value) })} /></label>
        </div>
        <ProjectionChart points={projection?.points} />
        <div className="scenario-result"><span>Capital aportado <b>{money(projection?.total_contributed)}</b></span><span>Valor matemático <b>{money(projection?.final_value)}</b></span></div>
        <small>{projection?.warning}</small>
      </section>
    </div>

    <section className="exchange-panel spot-equity-panel">
      <div className="exchange-panel-head compact"><div><p className="eyebrow">Persisted equity</p><h2>Curva patrimonial real del simulador</h2></div><button onClick={refreshValuation}>Registrar valuación</button></div>
      <EquityHistoryChart points={snapshot.equity_history} />
      <small>Solo agrega un punto cuando cambia la cartera o cambia el mark persistido; no duplica lecturas idénticas.</small>
    </section>

    <section className="exchange-panel spot-holdings">
      <div className="exchange-panel-head compact"><div><p className="eyebrow">Holdings</p><h2>Cartera spot simulada</h2></div><span>SQLITE / AUDITABLE</span></div>
      {allocation.length ? <div className="spot-holdings-table"><div className="table-head"><span>Activo</span><span>Cantidad</span><span>Costo medio</span><span>Precio</span><span>Peso</span><span>PnL</span></div>{allocation.map((holding) => <div key={holding.symbol}><strong>{holding.symbol}</strong><span>{Number(holding.quantity).toFixed(8)}</span><span>{money(holding.average_cost)}</span><span>{money(holding.market_price)}</span><span>{holding.weight_pct.toFixed(2)}%</span><b className={holding.unrealized_pnl >= 0 ? "positive" : "negative"}>{money(holding.unrealized_pnl)} · {percent(holding.return_pct)}</b></div>)}</div> : <div className="chart-state">Sin compras spot simuladas todavía.</div>}
    </section>
    </>}

    {activeTab === "analysis" && <>
    <section className="exchange-panel spot-analysis-panel">
      <div className="exchange-panel-head compact"><div><p className="eyebrow">Long-term evidence engine</p><h2>{selectedSymbol} · estructura de largo plazo</h2></div><div className="spot-timeframe-switch"><button className={analysisTimeframe === "1d" ? "active" : ""} onClick={() => setAnalysisTimeframe("1d")}>1D</button><button className={analysisTimeframe === "1w" ? "active" : ""} onClick={() => setAnalysisTimeframe("1w")}>1W</button><span>{analysis ? `${analysis.candles_used} CANDLES` : "CARGANDO"}</span></div></div>
      {analysis ? <>
        <div className="spot-analysis-grid">
          <article><span>Tendencia</span><strong>{analysis.chartism.trend.replaceAll("_", " ")}</strong><small>Cierre {money(analysis.latest_close)}</small></article>
          <article><span>Soporte 90</span><strong>{money(analysis.chartism.support_90)}</strong><small>mínimo observado</small></article>
          <article><span>Resistencia 90</span><strong>{money(analysis.chartism.resistance_90)}</strong><small>máximo observado</small></article>
          <article><span>Posición del rango</span><strong>{analysis.chartism.range_position_pct.toFixed(1)}%</strong><small>0 soporte · 100 resistencia</small></article>
          <article><span>Wyckoff</span><strong>{analysis.wyckoff.hypothesis.replaceAll("_", " ")}</strong><small>volumen relativo {analysis.wyckoff.relative_volume_20 ? analysis.wyckoff.relative_volume_20.toFixed(2) : "--"}x</small></article>
          <article><span>Elliott</span><strong>{analysis.elliott.pivots.length} pivotes</strong><small>conteo manual requerido</small></article>
        </div>
        <div className="spot-analysis-reading"><span>Hipótesis Wyckoff</span><p>{analysis.wyckoff.evidence}</p><small>{analysis.elliott.warning}</small></div>
        <TradingLatinoPanel strategy={analysis.trading_latino_5f} />
        <TradingLatinoDoctrine doctrine={analysis.trading_latino_doctrine} />
      </> : <div className="chart-state">Preparando candles diarios reales para el análisis.</div>}
    </section>

    <section className="exchange-panel methodology-lanes">
      <article><span>Chartismo</span><strong>Próximo</strong><p>Estructura, soportes, resistencias e invalidación sobre candles reales.</p></article>
      <article><span>Wyckoff</span><strong>Laboratorio</strong><p>Esfuerzo/resultado y rangos como evidencia; fases siempre etiquetadas como hipótesis.</p></article>
      <article><span>Elliott</span><strong>Asistido</strong><p>Conteo manual con alternativas; no se presentará un conteo automático como certeza.</p></article>
      <article><span>Trading Latino 5F</span><strong>Operativo</strong><p>Squeeze, ADX, EMA55, POC aproximado y tiempo; candidato observable, nunca orden automática.</p></article>
    </section>
    </>}

    {activeTab === "ledger" && <>
      <div className="spot-account-controls">
        <section className="exchange-panel spot-cash-flow">
          <div className="exchange-panel-head compact"><div><p className="eyebrow">Capital flows</p><h2>Aporte / retiro simulado</h2></div><span>SEPARADO DEL PnL</span></div>
          <form onSubmit={submitCashFlow}>
            <label>Tipo<select value={cashFlow.flow_type} onChange={(event) => setCashFlow({ ...cashFlow, flow_type: event.target.value })}><option value="deposit">Aporte</option><option value="withdrawal">Retiro</option></select></label>
            <label>Monto<input type="number" min="0.01" step="any" value={cashFlow.amount} onChange={(event) => setCashFlow({ ...cashFlow, amount: event.target.value })} /></label>
            <label>Nota<input value={cashFlow.notes} onChange={(event) => setCashFlow({ ...cashFlow, notes: event.target.value })} /></label>
            <button type="submit">Registrar movimiento</button>
          </form>
        </section>
        <section className="exchange-panel spot-reset-cycle">
          <div className="exchange-panel-head compact"><div><p className="eyebrow">Cycle control</p><h2>Nuevo ciclo patrimonial</h2></div><span>HISTORIAL PRESERVADO</span></div>
          <form onSubmit={resetCycle}>
            <label>Capital inicial<input type="number" min="100" step="any" value={resetForm.initial_cash} onChange={(event) => setResetForm({ ...resetForm, initial_cash: event.target.value })} /></label>
            <label>Motivo<input value={resetForm.reason} minLength="3" onChange={(event) => setResetForm({ ...resetForm, reason: event.target.value })} /></label>
            <button type="submit">Cerrar ciclo e iniciar otro</button>
            <small>Pone holdings en cero y abre un ciclo nuevo. No borra ledger ni operaciones históricas.</small>
          </form>
        </section>
      </div>

      <section className="exchange-panel spot-ledger-panel">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Append-only ledger</p><h2>Eventos patrimoniales</h2></div><span>{snapshot.ledger.length} EVENTOS</span></div>
        {snapshot.ledger.length ? <div className="spot-ledger-list">{snapshot.ledger.map((entry) => <article key={entry.id}><div><strong>{entry.event_type.replaceAll("_", " ")}</strong><small>Ciclo {entry.cycle_number} · #{entry.reference_id || "—"}</small></div><div><span>{entry.symbol || "CASH"}</span><b className={entry.cash_delta >= 0 ? "positive" : "negative"}>{money(entry.cash_delta)}</b></div><time>{new Date(entry.created_at).toLocaleString()}</time></article>)}</div> : <div className="chart-state">Sin eventos patrimoniales todavía.</div>}
      </section>

      <section className="exchange-panel spot-transaction-history">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Current cycle</p><h2>Operaciones y aportes</h2></div><span>CICLO {snapshot.portfolio.active_cycle}</span></div>
        <div className="spot-history-columns">
          <div><h3>Transacciones</h3>{snapshot.transactions.length ? snapshot.transactions.map((item) => <p key={item.id}><strong>{item.side.toUpperCase()} {item.symbol}</strong><span>{Number(item.quantity).toFixed(8)} · {money(item.price)}</span></p>) : <small>Sin operaciones en este ciclo.</small>}</div>
          <div><h3>Movimientos de caja</h3>{snapshot.cash_flows.length ? snapshot.cash_flows.map((item) => <p key={item.id}><strong>{item.flow_type.toUpperCase()}</strong><span>{money(item.cash_delta)} · {item.notes || "sin nota"}</span></p>) : <small>Sin aportes o retiros en este ciclo.</small>}</div>
        </div>
      </section>
    </>}
  </section>;
}
