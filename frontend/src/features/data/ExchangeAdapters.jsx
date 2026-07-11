import React, { useEffect, useMemo, useState } from "react";
import { getExchangeOrderBook, getExchangeRegistry, getExchangeTicker } from "../../api/client.js";

const price = (value) => value == null ? "--" : Number(value).toLocaleString(undefined, { maximumFractionDigits: 8 });

export default function ExchangeAdapters() {
  const [registry, setRegistry] = useState(null);
  const [exchangeId, setExchangeId] = useState("kraken");
  const [symbol, setSymbol] = useState("BTC/USD");
  const [ticker, setTicker] = useState(null);
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getExchangeRegistry().then(setRegistry).catch((requestError) => setError(requestError.message));
  }, []);

  const selected = useMemo(() => registry?.exchanges?.find((row) => row.id === exchangeId), [registry, exchangeId]);
  const selectExchange = (value) => {
    const next = registry.exchanges.find((row) => row.id === value);
    setExchangeId(value); setSymbol(next?.default_symbol || "BTC/USD"); setTicker(null); setBook(null); setError("");
  };
  const query = async () => {
    setLoading(true); setError("");
    try {
      const [tickerResult, bookResult] = await Promise.all([getExchangeTicker(exchangeId, symbol), getExchangeOrderBook(exchangeId, symbol, 20)]);
      setTicker(tickerResult); setBook(bookResult);
    } catch (requestError) { setError(requestError.message); }
    finally { setLoading(false); }
  };

  return <section className="exchange-adapters-page">
    <section className="panel-accent data-command">
      <div><p className="eyebrow">CCXT Public Adapter</p><h2>Exchange data console</h2><span>Consultas publicas normalizadas. Sin credenciales, balances ni ejecucion.</span></div>
      <strong>READ ONLY</strong>
    </section>
    {error && <div className="error-box">{error}</div>}
    <section className="exchange-panel exchange-adapter-controls">
      <label>Exchange<select value={exchangeId} onChange={(event) => selectExchange(event.target.value)}>{(registry?.exchanges || []).map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
      <label>Unified symbol<input value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} /></label>
      <button type="button" onClick={query} disabled={loading || !registry}>{loading ? "Consultando..." : "Consultar mercado"}</button>
      <div><span>PUBLIC</span><b>{selected?.capabilities?.join(" / ") || "cargando"}</b></div>
      <div><span>PRIVATE API</span><b className="negative">{registry?.private_api || "blocked"}</b></div>
    </section>
    <section className="exchange-adapter-grid">
      <article className="exchange-panel exchange-ticker-card">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Unified ticker</p><h2>{ticker?.symbol || symbol}</h2></div><span>{ticker?.exchange || exchangeId}</span></div>
        {ticker ? <div className="exchange-ticker-metrics">{[["Last", price(ticker.last)], ["Bid", price(ticker.bid)], ["Ask", price(ticker.ask)], ["24h %", ticker.percentage == null ? "--" : `${Number(ticker.percentage).toFixed(2)}%`], ["High", price(ticker.high)], ["Low", price(ticker.low)]].map(([label, value]) => <span key={label}><small>{label}</small><strong>{value}</strong></span>)}</div> : <div className="chart-state">Consulta un mercado para ver datos reales.</div>}
      </article>
      <article className="exchange-panel exchange-book-card">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Unified order book</p><h2>Top 20</h2></div><span>{book?.exchange || exchangeId}</span></div>
        {book ? <div className="exchange-book-columns"><div><b>ASKS</b>{book.asks.slice().reverse().map((row, index) => <span key={`a-${index}`} className="negative"><i>{price(row[0])}</i><em>{price(row[1])}</em></span>)}</div><div><b>BIDS</b>{book.bids.map((row, index) => <span key={`b-${index}`} className="positive"><i>{price(row[0])}</i><em>{price(row[1])}</em></span>)}</div></div> : <div className="chart-state">Sin profundidad consultada.</div>}
      </article>
    </section>
    <div className="ops-warning"><strong>No execution surface.</strong><p>Esta consola no expone createOrder, claves, balances privados ni metodos autenticados. Cada consulta registra health y latencia en SQLite.</p></div>
  </section>;
}
