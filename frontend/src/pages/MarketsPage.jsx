import React, { useState } from "react";
import PageSubtabs from "../components/PageSubtabs.jsx";
import MarketIntelligenceBrief from "../features/markets/MarketIntelligenceBrief.jsx";
import MarketUniversePanel from "../features/markets/MarketUniversePanel.jsx";
import RadarPanel from "../features/radar/RadarPanel.jsx";
import MarketReadingsPanel from "../features/radar/MarketReadingsPanel.jsx";

export default function MarketsPage({ rows, sentiment, selectedSymbol = "BTCUSDT", onSelectSymbol }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [universe, setUniverse] = useState("crypto");
  function openTrade(symbol) {
    onSelectSymbol?.(symbol);
    window.location.hash = "trade";
  }
  return (
    <>
      <PageSubtabs
        tabs={[["overview", "Overview", "radar + sentimiento"], ["assets", "Asset focus", "amplitud + filtros"]]}
        activeTab={activeTab}
        onChange={setActiveTab}
      />
      {activeTab === "overview" ? (
        <>
          <MarketUniversePanel selected={universe} onChange={setUniverse} />
          {universe === "crypto" && <><MarketIntelligenceBrief selectedSymbol={selectedSymbol} /><RadarPanel rows={rows} sentiment={sentiment} onOpenTrade={openTrade} /></>}
        </>
      ) : <MarketReadingsPanel rows={rows} sentiment={sentiment} />}
    </>
  );
}
