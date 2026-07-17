import React, { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { getRadar, updateRadar } from "./api/client.js";
import Shell from "./components/Shell.jsx";
import { latestRows } from "./utils/assets.js";

const MarketsPage = lazy(() => import("./pages/MarketsPage.jsx"));
const TradePage = lazy(() => import("./pages/TradePage.jsx"));
const SpotPortfolioPage = lazy(() => import("./pages/SpotPortfolioPage.jsx"));
const LiveMapPage = lazy(() => import("./pages/LiveMapPage.jsx"));
const ResearchPage = lazy(() => import("./pages/ResearchPage.jsx"));
const DataPage = lazy(() => import("./pages/DataPage.jsx"));
const BotsPage = lazy(() => import("./pages/BotsPage.jsx"));
const RiskPage = lazy(() => import("./pages/RiskPage.jsx"));

const PAGE_META = {
  markets: ["Market overview", "Markets"],
  trade: ["Spot desk", "Trade"],
  portfolio: ["Long-term spot", "Portfolio"],
  map: ["World vectors", "Live Map"],
  research: ["Research desk", "Research"],
  data: ["Data layer", "Data"],
  bots: ["Bot Forge", "Bots"],
  risk: ["Risk engine", "Risk"],
};

const VALID_PAGES = Object.keys(PAGE_META);

function pageFromHash() {
  const value = window.location.hash.replace("#", "");
  return VALID_PAGES.includes(value) ? value : "markets";
}

export default function App() {
  const [radar, setRadar] = useState({ latest_snapshots: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState("--");
  const [activePage, setActivePage] = useState(pageFromHash);
  const [selectedSymbol, setSelectedSymbol] = useState("BTCUSDT");

  const rows = radar.latest_snapshots || [];
  const snapshotCount = rows.length;
  const assetOptions = useMemo(() => latestRows(rows), [rows]);

  const latestTime = useMemo(() => {
    const timestamp = rows[0]?.timestamp;
    if (!timestamp) return lastUpdated;
    return new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }, [rows, lastUpdated]);

  async function loadRadar() {
    setError("");
    try {
      const data = await getRadar();
      setRadar(data);
    } catch (err) {
      setError(err.message);
    }
  }

  async function refreshRadar() {
    setLoading(true);
    setError("");
    try {
      const result = await updateRadar();
      setRadar({ ...result, latest_snapshots: result.latest_snapshots || result.rows || [] });
      setLastUpdated(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function silentRefreshRadar() {
    try {
      const result = await updateRadar();
      setRadar({ ...result, latest_snapshots: result.latest_snapshots || result.rows || [] });
      setLastUpdated(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadRadar();
  }, []);

  useEffect(() => {
    if (!['markets', 'trade'].includes(activePage)) return undefined;
    const refreshIfVisible = () => {
      if (document.visibilityState === 'visible') silentRefreshRadar();
    };
    const timer = window.setInterval(refreshIfVisible, 60000);
    document.addEventListener('visibilitychange', refreshIfVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', refreshIfVisible);
    };
  }, [activePage]);

  useEffect(() => {
    if (!window.location.hash) window.history.replaceState(null, "", "#markets");
    const handleHashChange = () => setActivePage(pageFromHash());
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const [pageEyebrow, pageTitle] = PAGE_META[activePage] || PAGE_META.markets;

  return (
    <Shell
      activePage={activePage}
      onRefresh={refreshRadar}
      loading={loading}
      snapshotCount={snapshotCount}
      lastUpdated={latestTime}
      pageEyebrow={pageEyebrow}
      pageTitle={pageTitle}
      assetOptions={assetOptions}
      selectedSymbol={selectedSymbol}
      onAssetChange={setSelectedSymbol}
    >
      {error && <div className="error-box">{error}</div>}
      <Suspense fallback={<section className="page-loading-state"><span>ABRAXAS</span><strong>Cargando modulo operativo...</strong></section>}>
        {activePage === "markets" && <MarketsPage rows={rows} sentiment={radar.sentiment} selectedSymbol={selectedSymbol} onSelectSymbol={setSelectedSymbol} />}
        {activePage === "trade" && <TradePage rows={rows} selectedSymbol={selectedSymbol} onSelectSymbol={setSelectedSymbol} />}
        {activePage === "portfolio" && <SpotPortfolioPage selectedSymbol={selectedSymbol} />}
        {activePage === "map" && <LiveMapPage />}
        {activePage === "research" && <ResearchPage selectedSymbol={selectedSymbol} />}
        {activePage === "data" && <DataPage selectedSymbol={selectedSymbol} />}
        {activePage === "bots" && <BotsPage selectedSymbol={selectedSymbol} />}
        {activePage === "risk" && <RiskPage />}
      </Suspense>
    </Shell>
  );
}
