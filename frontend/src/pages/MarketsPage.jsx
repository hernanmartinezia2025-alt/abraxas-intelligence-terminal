import React, { useState } from "react";
import PageSubtabs from "../components/PageSubtabs.jsx";
import MarketIntelligenceBrief from "../features/markets/MarketIntelligenceBrief.jsx";
import MarketUniversePanel from "../features/markets/MarketUniversePanel.jsx";
import RadarPanel from "../features/radar/RadarPanel.jsx";
import MarketReadingsPanel from "../features/radar/MarketReadingsPanel.jsx";

export default function MarketsPage({ rows, sentiment, selectedSymbol = "BTCUSDT" }) {
  const [activeTab, setActiveTab] = useState("overview");
  return (
    <>
      <PageSubtabs
        tabs={[["overview", "Overview", "radar + sentimiento"], ["assets", "Asset focus", "amplitud + filtros"], ["universe", "Asset universe", "crypto + macro"]]}
        activeTab={activeTab}
        onChange={setActiveTab}
      />
      {activeTab === "overview" ? (
        <>
          <MarketIntelligenceBrief selectedSymbol={selectedSymbol} />
          <RadarPanel rows={rows} sentiment={sentiment} />
        </>
      ) : activeTab === "assets" ? <MarketReadingsPanel rows={rows} sentiment={sentiment} /> : <MarketUniversePanel />}
    </>
  );
}
