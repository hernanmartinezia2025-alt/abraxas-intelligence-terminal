import React, { useState } from "react";
import PageSubtabs from "../components/PageSubtabs.jsx";
import RadarPanel from "../features/radar/RadarPanel.jsx";
import MarketReadingsPanel from "../features/radar/MarketReadingsPanel.jsx";

export default function MarketsPage({ rows, sentiment }) {
  const [activeTab, setActiveTab] = useState("overview");
  return (
    <>
      <PageSubtabs
        tabs={[["overview", "Overview", "radar + sentimiento"], ["assets", "Asset focus", "amplitud + filtros"]]}
        activeTab={activeTab}
        onChange={setActiveTab}
      />
      {activeTab === "overview" ? <RadarPanel rows={rows} sentiment={sentiment} /> : <MarketReadingsPanel rows={rows} sentiment={sentiment} />}
    </>
  );
}
