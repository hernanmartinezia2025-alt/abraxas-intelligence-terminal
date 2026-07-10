import React, { useState } from "react";
import PageSubtabs from "../components/PageSubtabs.jsx";
import ContextPlaceholder from "../features/context/ContextPlaceholder.jsx";
import RegimeEngine from "../features/regime/RegimeEngine.jsx";
import ResearchArchive from "../features/research/ResearchArchive.jsx";
import StatisticalIntelligence from "../features/statistics/StatisticalIntelligence.jsx";

export default function ResearchPage({ selectedSymbol }) {
  const [activeTab, setActiveTab] = useState("intelligence");
  return (
    <section className="page-stack">
      <PageSubtabs
        tabs={[
          ["intelligence", "Intelligence", "statistics + regime"],
          ["archive", "Archive", "runs persistidos"],
          ["context", "Context", "macro context lab"],
        ]}
        activeTab={activeTab}
        onChange={setActiveTab}
      />
      {activeTab === "intelligence" && (
        <>
          <StatisticalIntelligence selectedSymbol={selectedSymbol} />
          <RegimeEngine selectedSymbol={selectedSymbol} />
        </>
      )}
      {activeTab === "archive" && <ResearchArchive selectedSymbol={selectedSymbol} />}
      {activeTab === "context" && <ContextPlaceholder />}
    </section>
  );
}
