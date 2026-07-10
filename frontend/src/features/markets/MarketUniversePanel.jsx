import React, { useState } from "react";

const UNIVERSES = [
  ["crypto", "Crypto", "online", "Binance + Alternative.me", "12 activos rastreados en el radar actual."],
  ["indices", "Índices", "planned", "Fuente macro pendiente", "S&P 500, Nasdaq, DAX, Nikkei y otros índices."],
  ["equities", "Acciones", "planned", "Fuente macro pendiente", "Acciones y sectores sensibles a narrativa."],
  ["fx", "Divisas", "planned", "Fuente macro pendiente", "DXY y pares FX para contexto de riesgo."],
  ["commodities", "Commodities", "planned", "Fuente macro pendiente", "Oro, petróleo, gas y metales."],
];

export default function MarketUniversePanel() {
  const [selected, setSelected] = useState("crypto");
  const active = UNIVERSES.find(([key]) => key === selected) || UNIVERSES[0];
  return (
    <section className="market-universe-panel exchange-panel">
      <div className="exchange-panel-head compact">
        <div><p className="eyebrow">Asset Universe</p><h2>Mercados por categoría</h2></div>
        <span>fuentes reales por conectar</span>
      </div>
      <div className="universe-tabs" role="tablist" aria-label="Universo de activos">
        {UNIVERSES.map(([key, label, status]) => <button key={key} type="button" className={selected === key ? "active" : ""} onClick={() => setSelected(key)} role="tab" aria-selected={selected === key}>{label}<small>{status}</small></button>)}
      </div>
      <div className={`universe-detail ${active[2]}`}>
        <span>{active[2] === "online" ? "ONLINE" : "PLANNED"}</span>
        <strong>{active[1]}</strong>
        <p>{active[4]}</p>
        <small>{active[3]}</small>
      </div>
    </section>
  );
}
