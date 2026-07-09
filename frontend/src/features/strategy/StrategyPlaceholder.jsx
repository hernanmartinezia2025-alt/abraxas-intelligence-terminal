import React from "react";

export default function StrategyPlaceholder() {
  return (
    <section className="module-panel" id="strategy">
      <div className="section-head">
        <div>
          <p className="eyebrow">Strategy Lab</p>
          <h2>Pipeline pendiente</h2>
        </div>
        <span>lab only</span>
      </div>
      <div className="panel-body">
        <div className="module-list stacked">
          <span><b>1</b> Rules</span>
          <span><b>2</b> Backtest engine</span>
          <span><b>3</b> Report</span>
        </div>
      </div>
    </section>
  );
}
