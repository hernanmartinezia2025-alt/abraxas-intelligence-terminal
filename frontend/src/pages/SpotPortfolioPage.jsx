import React, { useEffect, useMemo, useState } from "react";
import { createSpotTransaction, getSpotAnalysis, getSpotPortfolio, getSpotProjection } from "../api/client.js";

const money = (value) => Number(value || 0).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const percent = (value) => `${Number(value || 0) >= 0 ? "+" : ""}${Number(value || 0).toFixed(2)}%`;

function ProjectionChart({ points = [] }) {
  if (points.length < 2) return <div className="chart-state">Configura el escenario para ver la curva.</div>;
  const max = Math.max(...points.map((point) => point.value), 1);
  const line = points.map((point, index) => `${(index / (points.length - 1)) * 100},${96 - point.value / max * 88}`).join(" ");
  const contributed = points.map((point, index) => `${(index / (points.length - 1)) * 100},${96 - point.contributed / max * 88}`).join(" ");
  return <svg className="spot-projection-chart" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Escenario de crecimiento de cartera"><polyline className="contributed" points={contributed} /><polyline className="projected" points={line} /></svg>;
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

export default function SpotPortfolioPage({ selectedSymbol = "BTCUSDT" }) {
  const [snapshot, setSnapshot] = useState(null);
  const [ticket, setTicket] = useState({ symbol: selectedSymbol, side: "buy", quantity: "0.001", notes: "" });
  const [scenario, setScenario] = useState({ monthly_contribution: 250, years: 4, annual_return_pct: 0 });
  const [projection, setProjection] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [message, setMessage] = useState("");

  async function load() { try { setSnapshot(await getSpotPortfolio()); setMessage(""); } catch (error) { setMessage(error.message); } }
  useEffect(() => { load(); }, []);
  useEffect(() => { setTicket((current) => ({ ...current, symbol: selectedSymbol })); }, [selectedSymbol]);
  useEffect(() => {
    setAnalysis(null);
    getSpotAnalysis(selectedSymbol, "1d", 300).then(setAnalysis).catch((error) => setMessage(error.message));
  }, [selectedSymbol]);
  useEffect(() => {
    if (!snapshot) return;
    getSpotProjection({ initial_value: snapshot.equity, ...scenario }).then(setProjection).catch((error) => setMessage(error.message));
  }, [snapshot?.equity, scenario.monthly_contribution, scenario.years, scenario.annual_return_pct]);

  async function submit(event) {
    event.preventDefault();
    setMessage("Registrando operación...");
    try {
      const result = await createSpotTransaction({ ...ticket, quantity: Number(ticket.quantity) });
      setSnapshot(result.snapshot);
      setMessage(`Operación #${result.transaction_id} persistida.`);
    } catch (error) { setMessage(error.message); }
  }

  const allocation = useMemo(() => snapshot?.holdings || [], [snapshot]);
  if (!snapshot) return <section className="page-loading-state"><strong>Cargando cartera spot...</strong><small>{message}</small></section>;

  return <section className="spot-portfolio-page">
    <div className="spot-summary-grid">
      <article><span>Patrimonio</span><strong>{money(snapshot.equity)}</strong><small>cash + valor de mercado</small></article>
      <article><span>Disponible</span><strong>{money(snapshot.portfolio.cash_balance)}</strong><small>USDT simulado</small></article>
      <article><span>Invertido</span><strong>{money(snapshot.market_value)}</strong><small>{allocation.length} activos</small></article>
      <article><span>PnL no realizado</span><strong className={snapshot.unrealized_pnl >= 0 ? "positive" : "negative"}>{money(snapshot.unrealized_pnl)}</strong><small>{percent(snapshot.return_pct)}</small></article>
    </div>

    <div className="spot-workbench">
      <section className="exchange-panel spot-ticket">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Spot simulation</p><h2>Compra / venta auditable</h2></div><span>NO LIVE</span></div>
        <form onSubmit={submit}>
          <label>Activo<input value={ticket.symbol} onChange={(event) => setTicket({ ...ticket, symbol: event.target.value.toUpperCase() })} /></label>
          <label>Operación<select value={ticket.side} onChange={(event) => setTicket({ ...ticket, side: event.target.value })}><option value="buy">Comprar</option><option value="sell">Vender</option></select></label>
          <label>Cantidad<input type="number" min="0" step="any" value={ticket.quantity} onChange={(event) => setTicket({ ...ticket, quantity: event.target.value })} /></label>
          <label>Nota<input value={ticket.notes} onChange={(event) => setTicket({ ...ticket, notes: event.target.value })} placeholder="tesis o motivo" /></label>
          <button type="submit">Registrar operación spot</button>
          <small>{message || "Precio desde market_snapshots; fee 0.10%; ejecución real bloqueada."}</small>
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

    <section className="exchange-panel spot-holdings">
      <div className="exchange-panel-head compact"><div><p className="eyebrow">Holdings</p><h2>Cartera spot simulada</h2></div><span>SQLITE / AUDITABLE</span></div>
      {allocation.length ? <div className="spot-holdings-table"><div className="table-head"><span>Activo</span><span>Cantidad</span><span>Costo medio</span><span>Precio</span><span>Peso</span><span>PnL</span></div>{allocation.map((holding) => <div key={holding.symbol}><strong>{holding.symbol}</strong><span>{Number(holding.quantity).toFixed(8)}</span><span>{money(holding.average_cost)}</span><span>{money(holding.market_price)}</span><span>{holding.weight_pct.toFixed(2)}%</span><b className={holding.unrealized_pnl >= 0 ? "positive" : "negative"}>{money(holding.unrealized_pnl)} · {percent(holding.return_pct)}</b></div>)}</div> : <div className="chart-state">Sin compras spot simuladas todavía.</div>}
    </section>

    <section className="exchange-panel spot-analysis-panel">
      <div className="exchange-panel-head compact"><div><p className="eyebrow">Daily evidence engine</p><h2>{selectedSymbol} · estructura de largo plazo</h2></div><span>{analysis ? `${analysis.candles_used} CANDLES` : "CARGANDO"}</span></div>
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
      </> : <div className="chart-state">Preparando candles diarios reales para el análisis.</div>}
    </section>

    <section className="exchange-panel methodology-lanes">
      <article><span>Chartismo</span><strong>Próximo</strong><p>Estructura, soportes, resistencias e invalidación sobre candles reales.</p></article>
      <article><span>Wyckoff</span><strong>Laboratorio</strong><p>Esfuerzo/resultado y rangos como evidencia; fases siempre etiquetadas como hipótesis.</p></article>
      <article><span>Elliott</span><strong>Asistido</strong><p>Conteo manual con alternativas; no se presentará un conteo automático como certeza.</p></article>
      <article><span>Trading Latino 5F</span><strong>Operativo</strong><p>Squeeze, ADX, EMA55, POC aproximado y tiempo; candidato observable, nunca orden automática.</p></article>
    </section>
  </section>;
}
