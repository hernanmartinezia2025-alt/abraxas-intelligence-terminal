import React, { useEffect, useState } from "react";
import GlobalAssetSelector from "./GlobalAssetSelector.jsx";

const NAV_ITEMS = [
  ["markets", "Markets", "overview", "◈"],
  ["trade", "Trade", "spot desk", "⌁"],
  ["map", "Map", "live world", "◎"],
  ["research", "Research", "strategy", "∿"],
  ["data", "Data", "sources", "▦"],
  ["bots", "Bots", "forge", "◆"],
  ["risk", "Risk", "limits", "△"],
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
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [railCollapsed, setRailCollapsed] = useState(() => window.localStorage.getItem("abraxas-rail-collapsed") === "true");
  const [railDensity, setRailDensity] = useState(() => window.localStorage.getItem("abraxas-rail-density") || "comfortable");

  useEffect(() => {
    document.documentElement.dataset.railDensity = railDensity;
    window.localStorage.setItem("abraxas-rail-density", railDensity);
  }, [railDensity]);

  useEffect(() => {
    window.localStorage.setItem("abraxas-rail-collapsed", String(railCollapsed));
  }, [railCollapsed]);

  return (
    <div className={`terminal-frame ${railCollapsed ? "rail-collapsed" : ""}`}>
      <aside className="side-rail">
        <div className="brand-block">
          <img className="brand-mark" src="/abraxas-emblem.png" alt="ABRAXAS emblem" />
          <div>
            <strong>ABRAXAS</strong>
            <small>local intelligence</small>
          </div>
          <button className="rail-collapse-button" type="button" onClick={() => setRailCollapsed((current) => !current)} aria-label={railCollapsed ? "Abrir rail" : "Colapsar rail"} title={railCollapsed ? "Abrir rail" : "Colapsar rail"}>
            {railCollapsed ? "»" : "«"}
          </button>
        </div>
        <nav className="rail-nav" aria-label="Primary modules">
          {NAV_ITEMS.map(([key, label, meta, icon]) => (
            <a className={activePage === key ? "active" : ""} href={`#${key}`} key={key}>
              <b aria-hidden="true">{icon}</b>
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
        <div className="rail-bottom">
          <div className="rail-status-card">
            <span>Selected</span>
            <strong>{selectedSymbol}</strong>
            <small>{snapshotCount} snapshots stored</small>
          </div>
          {settingsOpen && (
            <div className="rail-settings">
              <span>Terminal settings</span>
              <label>
                Densidad del rail
                <select value={railDensity} onChange={(event) => setRailDensity(event.target.value)}>
                  <option value="comfortable">Confortable</option>
                  <option value="compact">Compacta</option>
                </select>
              </label>
              <small>Preferencia local persistida en este navegador.</small>
            </div>
          )}
          <div className="rail-footer">
            <span>Local mode</span>
            <strong>SQLite</strong>
          </div>
          <button
            className="rail-settings-button"
            type="button"
            onClick={() => setSettingsOpen((current) => !current)}
            aria-expanded={settingsOpen}
            aria-label="Abrir configuracion del terminal"
            title="Configuracion del terminal"
          >
            ⚙
          </button>
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
