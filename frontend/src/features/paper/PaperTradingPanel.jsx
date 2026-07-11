import React, { useEffect, useState } from "react";
import { getPaperAccount, placePaperOrder, resetPaperAccount } from "../../api/client.js";

const money = (value) => Number(value || 0).toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });

export default function PaperTradingPanel({ botId, defaultSymbol = "BTCUSDT" }) {
  const [snapshot, setSnapshot] = useState(null);
  const [order, setOrder] = useState({ symbol: defaultSymbol, side: "buy", quantity: "0.001" });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    try { setSnapshot(await getPaperAccount()); setError(""); }
    catch (requestError) { setError(requestError.message); }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => { setOrder((current) => ({ ...current, symbol: defaultSymbol })); }, [defaultSymbol]);

  const submit = async (event) => {
    event.preventDefault(); setBusy(true);
    try {
      const response = await placePaperOrder({ ...order, symbol: order.symbol.toUpperCase(), quantity: Number(order.quantity), bot_id: botId || null });
      setResult(response); await load();
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  const reset = async () => {
    if (!window.confirm("Resetear cuenta paper a USD 10,000? El ledger historico se conserva.")) return;
    setBusy(true);
    try { setSnapshot(await resetPaperAccount({ initial_balance: 10000, reason: "Manual reset from Bot Forge" })); setResult(null); setError(""); }
    catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  if (!snapshot) return <section className="exchange-panel paper-panel"><div className="chart-state">{error || "Cargando cuenta paper desde SQLite..."}</div></section>;
  return <>
    {error && <div className="error-box">{error}</div>}
    <section className="paper-account-strip">
      {[["Equity", money(snapshot.equity)], ["Cash", money(snapshot.account.cash_balance)], ["Market value", money(snapshot.market_value)], ["PnL realizado", money(snapshot.account.realized_pnl)], ["PnL no realizado", money(snapshot.unrealized_pnl)], ["Drawdown", `${Number(snapshot.drawdown_pct).toFixed(2)}%`]].map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong></article>)}
    </section>
    <section className="paper-workspace">
      <form className="exchange-panel paper-order-ticket" onSubmit={submit}>
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Paper order</p><h2>Market ticket</h2></div><span>RISK GATED</span></div>
        <label>Symbol<input value={order.symbol} onChange={(event) => setOrder((current) => ({ ...current, symbol: event.target.value.toUpperCase() }))} /></label>
        <label>Side<select value={order.side} onChange={(event) => setOrder((current) => ({ ...current, side: event.target.value }))}><option value="buy">Buy</option><option value="sell">Sell</option></select></label>
        <label>Quantity<input type="number" min="0" step="0.000001" value={order.quantity} onChange={(event) => setOrder((current) => ({ ...current, quantity: event.target.value }))} /></label>
        <button type="submit" disabled={busy || Number(order.quantity) <= 0}>{busy ? "Validando..." : "Enviar a Risk Engine"}</button>
        <small>Precio: último market_snapshot real. Fee paper: 0.10%. No se conecta a exchanges.</small>
        {result && <div className={`paper-result ${result.status}`}><strong>{result.status.toUpperCase()}</strong><span>{result.reason || `Order #${result.order_id} · fill #${result.fill_id}`}</span></div>}
      </form>
      <section className="exchange-panel paper-positions">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Portfolio</p><h2>Posiciones abiertas</h2></div><button type="button" onClick={load}>Refrescar</button></div>
        {snapshot.positions.length ? snapshot.positions.map((position) => <article key={position.symbol}><div><strong>{position.symbol}</strong><span>{position.quantity} units</span></div><div><span>Avg {money(position.average_price)}</span><b className={position.unrealized_pnl >= 0 ? "positive" : "negative"}>{money(position.unrealized_pnl)}</b></div></article>) : <div className="chart-state">Sin posiciones abiertas.</div>}
      </section>
    </section>
    <section className="exchange-panel paper-orders">
      <div className="exchange-panel-head compact"><div><p className="eyebrow">Audit</p><h2>Ordenes recientes</h2></div><button type="button" onClick={reset} disabled={busy}>Reset account</button></div>
      <div className="backtest-trades-wrap"><table><thead><tr><th>ID</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th><th>Status</th><th>Risk ID</th></tr></thead><tbody>{snapshot.orders.map((item) => <tr key={item.id}><td>#{item.id}</td><td>{item.symbol}</td><td>{item.side}</td><td>{item.quantity}</td><td>{money(item.fill_price || item.reference_price)}</td><td className={item.status === "filled" ? "positive" : "negative"}>{item.status}</td><td>#{item.risk_validation_id}</td></tr>)}</tbody></table>{!snapshot.orders.length && <div className="chart-state">Sin ordenes paper.</div>}</div>
    </section>
  </>;
}
