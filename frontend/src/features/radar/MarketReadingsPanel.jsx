import React, { useMemo, useState } from "react";
import { latestRows } from "../../utils/assets.js";

function formatPercent(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function formatCompact(value) {
  return Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 0, notation: "compact" });
}

function riskRank(value) {
  const risk = String(value || "NORMAL");
  if (risk.startsWith("HIGH")) return 2;
  if (risk === "VOLATILITY") return 1;
  return 0;
}

function riskLabel(value) {
  const risk = String(value || "NORMAL");
  if (risk === "HIGH_EUPHORIA_RISK") return "EUPHORIA";
  if (risk === "HIGH_FEAR_RISK") return "FEAR";
  if (risk === "HIGH_VOLATILITY") return "VOLATILITY";
  return "NORMAL";
}

export default function MarketReadingsPanel({ rows = [], sentiment }) {
  const [lens, setLens] = useState("all");
  const [sort, setSort] = useState("change");
  const assets = latestRows(rows);

  const summary = sentiment?.market_breadth;
  const visibleAssets = useMemo(() => {
    const filtered = assets.filter((asset) => {
      const change = Number(asset.change_24h || 0);
      if (lens === "winners") return change > 0;
      if (lens === "losers") return change < 0;
      if (lens === "risk") return riskRank(asset.risk_level) > 0;
      return true;
    });
    return [...filtered].sort((left, right) => {
      if (sort === "volume") return Number(right.volume_24h || 0) - Number(left.volume_24h || 0);
      if (sort === "risk") return riskRank(right.risk_level) - riskRank(left.risk_level);
      return Number(right.change_24h || 0) - Number(left.change_24h || 0);
    });
  }, [assets, lens, sort]);

  return (
    <section className="exchange-panel market-readings-panel">
      <div className="exchange-panel-head compact">
        <div>
          <p className="eyebrow">Market Command</p>
          <h2>Amplitud y focos de mercado</h2>
        </div>
        <span>{assets.length} activos · SQLite / radar</span>
      </div>

      <div className="market-overview-strip">
        <article><span>Amplitud</span><strong>{summary ? `${summary.positive} / ${summary.tracked_assets}` : "--"}</strong><small>activos positivos</small></article>
        <article><span>Promedio 24h</span><strong>{summary ? formatPercent(summary.average_change_24h) : "--"}</strong><small>cambio ponderado simple</small></article>
        <article><span>Volumen 24h</span><strong>{summary ? `$${formatCompact(summary.total_volume_24h)}` : "--"}</strong><small>universo rastreado</small></article>
        <article><span>Riesgo alto</span><strong>{summary?.high_risk ?? "--"}</strong><small>activos con alerta</small></article>
      </div>

      <div className="market-lens-toolbar" role="toolbar" aria-label="Filtros de mercado">
        <div>
          {[['all', 'Todos'], ['winners', 'Suben'], ['losers', 'Bajan'], ['risk', 'Riesgo']].map(([value, label]) => (
            <button key={value} type="button" className={lens === value ? "active" : ""} onClick={() => setLens(value)}>{label}</button>
          ))}
        </div>
        <label>
          Ordenar
          <select value={sort} onChange={(event) => setSort(event.target.value)}>
            <option value="change">Cambio 24h</option>
            <option value="volume">Volumen</option>
            <option value="risk">Riesgo</option>
          </select>
        </label>
      </div>

      <div className="market-readings-grid">
        {visibleAssets.map((asset, index) => {
          const change = Number(asset.change_24h || 0);
          const tone = change >= 0 ? "positive" : "negative";
          return (
            <article key={asset.symbol} className={tone}>
              <div className="market-reading-head"><b>{String(index + 1).padStart(2, "0")} · {asset.symbol}</b><em>{riskLabel(asset.risk_level)}</em></div>
              <strong className={tone}>{formatPercent(change)}</strong>
              <span>{asset.abraxas_reading || "Lectura no disponible."}</span>
              <small>Vol. ${formatCompact(asset.volume_24h)}</small>
            </article>
          );
        })}
        {!visibleAssets.length && (
          <div className="map-empty"><strong>Sin activos en este foco</strong><span>Prueba otra lente o actualiza el radar.</span></div>
        )}
      </div>
    </section>
  );
}
