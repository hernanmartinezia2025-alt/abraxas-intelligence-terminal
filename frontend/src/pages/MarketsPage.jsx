import React from "react";
import RadarPanel from "../features/radar/RadarPanel.jsx";
import MarketReadingsPanel from "../features/radar/MarketReadingsPanel.jsx";

export default function MarketsPage({ rows }) {
  return (
    <>
      <RadarPanel rows={rows} />
      <MarketReadingsPanel rows={rows} />
    </>
  );
}
