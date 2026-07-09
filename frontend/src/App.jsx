import React, { useEffect, useMemo, useState } from "react";
import { getRadar, updateRadar } from "./api/client.js";
import Shell from "./components/Shell.jsx";
import BotsPage from "./pages/BotsPage.jsx";
import DataPage from "./pages/DataPage.jsx";
import LiveMapPage from "./pages/LiveMapPage.jsx";
import MarketsPage from "./pages/MarketsPage.jsx";
import ResearchPage from "./pages/ResearchPage.jsx";
import RiskPage from "./pages/RiskPage.jsx";
import TradePage from "./pages/TradePage.jsx";
import { latestRows } from "./utils/assets.js";

const PAGE_META = {
  markets: ["Market overview", "Markets"],
  trade: ["Spot desk", "Trade"],
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
      setRadar({ latest_snapshots: result.rows || [] });
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
      setRadar({ latest_snapshots: result.rows || [] });
      setLastUpdated(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadRadar();
    const timer = window.setInterval(() => {
      silentRefreshRadar();
    }, 60000);
    return () => window.clearInterval(timer);
  }, []);

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
      {activePage === "markets" && <MarketsPage rows={rows} />}
      {activePage === "trade" && <TradePage rows={rows} selectedSymbol={selectedSymbol} onSelectSymbol={setSelectedSymbol} />}
      {activePage === "map" && <LiveMapPage />}
      {activePage === "research" && <ResearchPage selectedSymbol={selectedSymbol} />}
      {activePage === "data" && <DataPage selectedSymbol={selectedSymbol} />}
      {activePage === "bots" && <BotsPage />}
      {activePage === "risk" && <RiskPage />}
    </Shell>
  );
}
