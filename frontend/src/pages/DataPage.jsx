import React from "react";
import DataApiCenter from "../features/data/DataApiCenter.jsx";

export default function DataPage({ selectedSymbol }) {
  return (
    <section className="page-stack">
      <DataApiCenter selectedSymbol={selectedSymbol} />
    </section>
  );
}
