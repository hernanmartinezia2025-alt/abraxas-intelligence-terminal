import React from "react";
import { latestRows } from "../../utils/assets.js";

export default function MarketReadingsPanel({ rows = [] }) {
  const assets = latestRows(rows);

  return (
    <section className="exchange-panel market-readings-panel">
      <div className="exchange-panel-head compact">
        <div>
          <p className="eyebrow">Market Tape</p>
          <h2>Lecturas por activo</h2>
        </div>
        <span>SQLite / radar</span>
      </div>
      <div className="market-readings-grid">
        {assets.map((asset) => (
          <article key={asset.symbol}>
            <b>{asset.symbol}</b>
            <span>{asset.abraxas_reading || "Lectura no disponible."}</span>
          </article>
        ))}
        {!assets.length && (
          <div className="map-empty">
            <strong>Sin lecturas persistidas</strong>
            <span>Actualiza Markets para cargar snapshots reales.</span>
          </div>
        )}
      </div>
    </section>
  );
}
