import React from "react";
import RadarPanel from "../features/radar/RadarPanel.jsx";
import MarketReadingsPanel from "../features/radar/MarketReadingsPanel.jsx";

export default function MarketsPage({ rows, sentiment }) {
  return (
    <>
      <RadarPanel rows={rows} sentiment={sentiment} />
      <MarketReadingsPanel rows={rows} />
    </>
  );
}
