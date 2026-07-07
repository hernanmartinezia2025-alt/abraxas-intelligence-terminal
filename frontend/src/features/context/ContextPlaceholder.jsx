import React from "react";

export default function ContextPlaceholder() {
  return (
    <section className="module-panel" id="context">
      <div className="section-head">
        <div>
          <p className="eyebrow">Context</p>
          <h2>Macro Board</h2>
        </div>
        <span>manual</span>
      </div>
      <div className="panel-body">
        <div className="vector-row">
          <b>AI</b>
          <b>Energy</b>
          <b>Rates</b>
          <b>Liquidity</b>
        </div>
      </div>
    </section>
  );
}
