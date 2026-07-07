import React from "react";

export default function ChartPlaceholder() {
  return (
    <section className="module-panel chart-module" id="charts">
      <div className="section-head">
        <div>
          <p className="eyebrow">Charts</p>
          <h2>Market Structure</h2>
        </div>
        <span>queued</span>
      </div>
      <div className="panel-body">
        <div className="chart-surface">
          <div className="chart-grid-lines" aria-hidden="true" />
          <div className="fake-candles" aria-hidden="true">
            {Array.from({ length: 34 }).map((_, index) => (
              <i key={index} style={{ height: `${28 + ((index * 17) % 80)}px` }} />
            ))}
          </div>
        </div>
        <div className="chart-caption">
          <span>EMA / Volume / RSI</span>
          <b>local module</b>
        </div>
      </div>
    </section>
  );
}
