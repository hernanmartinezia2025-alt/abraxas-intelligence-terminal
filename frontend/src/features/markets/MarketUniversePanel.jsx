import React, { useEffect, useState } from "react";
import { getMarketUniverse } from "../../api/client.js";

const UNIVERSES = [
  ["crypto", "Crypto", "online"],
  ["indices", "Índices", "online"],
  ["equities", "Acciones", "planned"],
  ["fx", "Divisas", "online"],
  ["commodities", "Commodities", "online"],
  ["rates", "Tasas", "online"],
];

function formatValue(value) {
  if (value === null || value === undefined) return "--";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function MiniLine({ points = [], positive }) {
  const values = points.map((point) => Number(point.value)).filter(Number.isFinite);
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const range = Math.max(...values) - min || 1;
  const line = values.map((item, index) => `${(index / (values.length - 1)) * 100},${25 - ((item - min) / range) * 22}`).join(" ");
  return <svg className={`universe-spark ${positive ? "positive" : "negative"}`} viewBox="0 0 100 28" preserveAspectRatio="none"><polyline points={line} vectorEffect="non-scaling-stroke" /></svg>;
}

export default function MarketUniversePanel({ selected, onChange }) {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const selectedMeta = UNIVERSES.find(([key]) => key === selected) || UNIVERSES[0];

  async function load(refresh = false) {
    if (selected === "crypto" || selectedMeta[2] !== "online") { setPayload(null); return; }
    setLoading(true);
    setError("");
    try { setPayload(await getMarketUniverse(selected, refresh)); } catch (err) { setError(err.message); setPayload(null); } finally { setLoading(false); }
  }

  useEffect(() => { load(false); }, [selected]);

  return (
    <section className="market-universe-panel exchange-panel">
      <div className="exchange-panel-head compact">
        <div><p className="eyebrow">Asset Universe</p><h2>Mercados por categoría</h2></div>
        <button type="button" onClick={() => load(true)} disabled={loading || selected === "crypto" || selectedMeta[2] !== "online"}>{loading ? "Actualizando..." : "Actualizar fuente"}</button>
      </div>
      <div className="universe-tabs" role="tablist" aria-label="Universo de activos">
        {UNIVERSES.map(([key, label, status]) => <button key={key} type="button" className={selected === key ? "active" : ""} onClick={() => onChange(key)} role="tab" aria-selected={selected === key}>{label}<small>{status}</small></button>)}
      </div>
      {error && <div className="stat-error">Fuente macro no disponible: {error}</div>}
      {selected === "crypto" && <div className="universe-detail online"><span>ONLINE</span><strong>Crypto</strong><p>Binance, Fear & Greed, régimen y snapshots locales.</p><small>Los gráficos crypto continúan debajo.</small></div>}
      {selectedMeta[2] === "planned" && <div className="universe-detail planned"><span>PLANNED</span><strong>{selectedMeta[1]}</strong><p>Esta categoría todavía no tiene una fuente aprobada.</p><small>No se muestran números inventados.</small></div>}
      {selected !== "crypto" && selectedMeta[2] === "online" && (
        <div className="universe-market-grid">
          {(payload?.items || []).map((item) => {
            const positive = Number(item.change_pct || 0) >= 0;
            return <article className={positive ? "positive" : "negative"} key={item.series_id}><div><span>{item.symbol}</span><small>{item.name}</small></div><strong>{formatValue(item.latest)}</strong><b>{positive ? "+" : ""}{formatValue(item.change_pct)}%</b><MiniLine points={item.observations} positive={positive} /><footer>{item.unit} · {payload.source}</footer></article>;
          })}
          {!loading && !payload?.items?.length && <div className="map-empty"><strong>Sin series disponibles</strong><span>La fuente no devolvió observaciones para esta categoría.</span></div>}
        </div>
      )}
    </section>
  );
}
