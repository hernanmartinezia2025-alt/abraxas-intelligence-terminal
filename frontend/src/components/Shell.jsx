import React from "react";
import GlobalAssetSelector from "./GlobalAssetSelector.jsx";

const NAV_ITEMS = [
  ["markets", "Markets", "overview"],
  ["trade", "Trade", "spot desk"],
  ["map", "Map", "live world"],
  ["research", "Research", "strategy"],
  ["data", "Data", "sources"],
  ["bots", "Bots", "forge"],
  ["risk", "Risk", "limits"],
];

const ROADMAP_ITEMS = [
  ["Charts", "live"],
  ["Stats", "next"],
  ["Regime", "next"],
  ["Backtest", "next"],
  ["Bots", "visible"],
  ["Risk", "visible"],
];

export default function Shell({
  activePage = "markets",
  children,
  loading,
  onRefresh,
  pageEyebrow = "Market desk",
  pageTitle = "ABRAXAS Market Radar",
  snapshotCount = 0,
  lastUpdated = "--",
  assetOptions = [],
  selectedSymbol = "BTCUSDT",
  onAssetChange,
}) {
  return (
    <div className="terminal-frame">
      <aside className="side-rail">
        <div className="brand-block">
          <img className="brand-mark" src="/abraxas-emblem.png" alt="ABRAXAS emblem" />
          <div>
            <strong>ABRAXAS</strong>
            <small>local intelligence</small>
          </div>
        </div>
        <nav className="rail-nav" aria-label="Primary modules">
          {NAV_ITEMS.map(([key, label, meta]) => (
            <a className={activePage === key ? "active" : ""} href={`#${key}`} key={key}>
              <span>{label}</span>
              <small>{meta}</small>
            </a>
          ))}
        </nav>
        <div className="rail-crest" aria-hidden="true">
          <img src="/abraxas-emblem.png" alt="" />
        </div>
        <div className="rail-module-card">
          <span>Recovery path</span>
          <div>
            {ROADMAP_ITEMS.map(([label, status]) => (
              <b className={status} key={label}>
                {label}
                <small>{status}</small>
              </b>
            ))}
          </div>
        </div>
        <div className="rail-status-card">
          <span>Selected</span>
          <strong>{selectedSymbol}</strong>
          <small>{snapshotCount} snapshots stored</small>
        </div>
        <div className="rail-footer">
          <span>Local mode</span>
          <strong>SQLite</strong>
        </div>
      </aside>

      <main className="shell">
        <header className="topbar">
          <div className="title-stack">
            <p className="eyebrow">{pageEyebrow}</p>
            <h1>{pageTitle}</h1>
          </div>
          <div className="command-strip">
            {assetOptions.length > 0 && (
              <GlobalAssetSelector assets={assetOptions} onChange={onAssetChange} selectedSymbol={selectedSymbol} />
            )}
            <div className="system-chip">
              <span>Snapshots</span>
              <strong>{snapshotCount}</strong>
            </div>
            <div className="system-chip">
              <span>Updated</span>
              <strong>{lastUpdated}</strong>
            </div>
            <button className="primary-action" onClick={onRefresh} disabled={loading}>
              {loading ? "Actualizando" : "Actualizar"}
            </button>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
