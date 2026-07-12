import React, { useEffect, useMemo, useState } from "react";
import { getMarketOverview } from "../../api/client.js";

const number = (value, suffix = "") => value === null || value === undefined
  ? "--"
  : `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`;

export default function MacroContextLab() {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load(refresh = false) {
    setLoading(true);
    setError("");
    try { setPayload(await getMarketOverview(refresh)); }
    catch (requestError) { setError(requestError.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(false); }, []);

  const series = useMemo(() => Object.fromEntries((payload?.items || []).map((item) => [item.series_id, item])), [payload]);
  const vectors = payload ? [
    { key: "growth", label: "Growth", primary: series.SP500, secondary: series.NASDAQCOM, reading: "S&P 500 + Nasdaq" },
    { key: "energy", label: "Energy", primary: series.DCOILWTICO, reading: "WTI crude oil" },
    { key: "rates", label: "Rates", primary: series.DGS10, reading: "U.S. Treasury 10Y" },
    { key: "liquidity", label: "Liquidity", primary: series.DTWEXBGS, reading: "Broad U.S. Dollar" },
  ] : [];

  return <section className="macro-context-lab">
    <section className={`exchange-panel context-command ${payload?.regime || "mixed"}`}>
      <div><p className="eyebrow">Context Lab · SQLite + FRED</p><h2>Macro Context Board</h2><span>{payload?.guidance || "Cargando contexto macro persistido..."}</span></div>
      <div className="context-command-state"><small>REGIME</small><strong>{payload?.regime?.replace("_", " ").toUpperCase() || "--"}</strong><button type="button" onClick={() => load(true)} disabled={loading}>{loading ? "Actualizando..." : "Actualizar fuentes"}</button></div>
    </section>
    {error && <div className="error-box">Fuente macro no disponible: {error}</div>}

    <section className="context-vector-grid">
      {vectors.map((vector) => {
        const change = Number(vector.primary?.change_pct || 0);
        const secondaryChange = vector.secondary ? Number(vector.secondary.change_pct || 0) : null;
        return <article className={change >= 0 ? "positive" : "negative"} key={vector.key}>
          <header><span>{vector.label}</span><b>{change >= 0 ? "UP" : "DOWN"}</b></header>
          <strong>{vector.primary?.symbol || "--"} {number(vector.primary?.latest)}</strong>
          <p>{vector.reading}</p>
          <footer><b>{change >= 0 ? "+" : ""}{number(change, "%")}</b>{secondaryChange !== null && <small>NASDAQ {secondaryChange >= 0 ? "+" : ""}{number(secondaryChange, "%")}</small>}<time>{vector.primary?.as_of || "sin fecha"}</time></footer>
        </article>;
      })}
    </section>

    <section className="context-analysis-grid">
      <article className="exchange-panel context-btc-read">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Cross-asset</p><h2>BTC Macro Read</h2></div><span>{payload?.correlation_reading?.samples || 0} RETURNS</span></div>
        <strong>{payload?.correlation_reading?.dominant_pair || "SIN MUESTRA"} {payload?.correlation_reading?.correlation === undefined ? "" : Number(payload.correlation_reading.correlation).toFixed(2)}</strong>
        <p>{payload?.correlation_reading?.summary || "Sin suficientes datos para interpretar correlaciones."}</p>
        <small>{payload?.correlation_reading?.caveat}</small>
      </article>
      <article className="exchange-panel context-source-audit">
        <div className="exchange-panel-head compact"><div><p className="eyebrow">Source audit</p><h2>Cobertura macro</h2></div><span>REAL DATA</span></div>
        <div><span><b>{payload?.items?.length || 0}</b> series listas</span><span><b>{payload?.correlations?.filter((item) => item.status === "ready").length || 0}</b> correlaciones listas</span><span className="planned"><b>{payload?.missing_sources?.length || 0}</b> fuente pendiente</span></div>
        {(payload?.missing_sources || []).map((source) => <p key={source.asset}><strong>{source.asset}</strong> · {source.reason}</p>)}
      </article>
    </section>

    <section className="exchange-panel context-series-table">
      <div className="exchange-panel-head compact"><div><p className="eyebrow">Normalized observations</p><h2>Series activas</h2></div><span>PowerBI READY</span></div>
      <div className="backtest-trades-wrap"><table><thead><tr><th>Symbol</th><th>Nombre</th><th>Categoría</th><th>Último</th><th>Cambio</th><th>Fecha</th><th>Fuente</th></tr></thead><tbody>{(payload?.items || []).map((item) => <tr key={item.series_id}><td>{item.symbol}</td><td>{item.name}</td><td>{item.category}</td><td>{number(item.latest)}</td><td className={Number(item.change_pct || 0) >= 0 ? "positive" : "negative"}>{Number(item.change_pct || 0) >= 0 ? "+" : ""}{number(item.change_pct, "%")}</td><td>{item.as_of}</td><td>{payload.source}</td></tr>)}</tbody></table></div>
    </section>
  </section>;
}
