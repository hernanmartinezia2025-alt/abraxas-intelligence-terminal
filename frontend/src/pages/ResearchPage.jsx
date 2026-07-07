import React from "react";
import ContextPlaceholder from "../features/context/ContextPlaceholder.jsx";
import RegimeEngine from "../features/regime/RegimeEngine.jsx";
import StatisticalIntelligence from "../features/statistics/StatisticalIntelligence.jsx";
import StrategyPlaceholder from "../features/strategy/StrategyPlaceholder.jsx";

export default function ResearchPage({ selectedSymbol }) {
  return (
    <section className="page-stack">
      <StatisticalIntelligence selectedSymbol={selectedSymbol} />
      <RegimeEngine selectedSymbol={selectedSymbol} />
      <StrategyPlaceholder />
      <ContextPlaceholder />
    </section>
  );
}
