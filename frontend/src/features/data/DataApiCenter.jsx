import React, { useEffect, useMemo, useState } from "react";
import { getDataCatalog, getDataHealth } from "../../api/client.js";

function formatTime(value) {
  if (!value) return "sin registro";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
}

function statusTone(status) {
  if (status === "ready" || status === "active") return "ready";
  if (status === "degraded_possible" || status === "empty") return "warn";
  if (status === "planned" || status === "missing") return "planned";
  return "neutral";
}

export default function DataApiCenter() {
  const [catalog, setCatalog] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadData({ silent = false } = {}) {
    if (!silent) setLoading(true);
    setError("");
    try {
      const [catalogPayload, healthPayload] = await Promise.all([getDataCatalog(), getDataHealth()]);
      setCatalog(catalogPayload);
      setHealth(healthPayload);
    } catch (err) {
      setError(err.message);
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    const timer = window.setInterval(() => {
      loadData({ silent: true });
    }, 90000);
    return () => window.clearInterval(timer);
  }, []);

  const datasets = useMemo(() => health?.datasets || catalog?.datasets || [], [catalog, health]);
  const sources = catalog?.sources || [];
  const summary = health?.summary || {};
  const database = health?.database || {};
  const assetFeaturesReady = datasets.some(
    (dataset) => dataset.dataset_id === "asset_features" && dataset.exists && dataset.row_count > 0
  );

  return (
    <section className="data-center-page">
      <section className="panel-accent data-command">
        <div>
          <p className="eyebrow">Data API Center</p>
          <h2>APIs, datasets y feature pipeline</h2>
          <span>{catalog?.principle || "APIs externas -> SQLite/cache -> datasets analiticos -> frontend/bots/PowerBI"}</span>
        </div>
        <button type="button" onClick={() => loadData()} disabled={loading}>
          {loading ? "Leyendo..." : "Refrescar health"}
        </button>
      </section>

      {error && <div className="error-box">{error}</div>}

      <section className="data-kpi-grid">
        <article>
          <span>SQLite</span>
          <strong>{database.exists ? "ONLINE" : "MISSING"}</strong>
          <small>{formatBytes(database.size_bytes)}</small>
        </article>
        <article>
          <span>Datasets</span>
          <strong>{summary.datasets_existing ?? "--"}/{summary.datasets_total ?? "--"}</strong>
          <small>existentes / catalogados</small>
        </article>
        <article>
          <span>PowerBI-ready</span>
          <strong>{datasets.filter((dataset) => dataset.powerbi_ready && dataset.exists).length}</strong>
          <small>tablas legibles hoy</small>
        </article>
        <article>
          <span>Bot feature store</span>
          <strong>{assetFeaturesReady ? "READY" : "PLANNED"}</strong>
          <small>features numericas para bots</small>
        </article>
      </section>

      <section className="data-grid">
        <article className="exchange-panel data-panel">
          <div className="exchange-panel-head compact">
            <div>
              <p className="eyebrow">Sources</p>
              <h2>API registry</h2>
            </div>
            <span>{sources.length} fuentes</span>
          </div>
          <div className="data-source-list">
            {sources.map((source) => (
              <article key={source.source_id} className={`data-source-card ${statusTone(source.status)}`}>
                <div>
                  <strong>{source.name}</strong>
                  <span>{source.type}</span>
                </div>
                <p>{source.purpose}</p>
                <small>{source.datasets.join(" / ")}</small>
              </article>
            ))}
          </div>
        </article>

        <article className="exchange-panel data-panel">
          <div className="exchange-panel-head compact">
            <div>
              <p className="eyebrow">Health</p>
              <h2>Live sources</h2>
            </div>
            <span>{health?.sources?.length || 0} checks</span>
          </div>
          <div className="data-health-list">
            {(health?.sources || []).map((source) => (
              <article key={source.source} className={source.ok ? "ok" : "down"}>
                <div>
                  <strong>{source.source}</strong>
                  <b>{source.ok ? "OK" : "DOWN"}</b>
                </div>
                <span>{source.event_count} eventos | {source.latency_ms} ms</span>
                <small>{source.error || `ultimo exito ${formatTime(source.last_success_at)}`}</small>
              </article>
            ))}
            {!health?.sources?.length && (
              <div className="map-empty">
                <strong>Sin health todavia</strong>
                <span>El mapa o las fuentes todavia no registraron checks en SQLite.</span>
              </div>
            )}
          </div>
        </article>
      </section>

      <section className="exchange-panel data-panel">
        <div className="exchange-panel-head compact">
          <div>
            <p className="eyebrow">Datasets</p>
            <h2>Analytical catalog</h2>
          </div>
          <span>{formatTime(health?.generated_at)}</span>
        </div>
        <div className="dataset-table">
          <div className="dataset-row header">
            <span>Dataset</span>
            <span>Status</span>
            <span>Rows</span>
            <span>Last timestamp</span>
            <span>PowerBI</span>
            <span>Bots</span>
          </div>
          {datasets.map((dataset) => (
            <div className="dataset-row" key={dataset.dataset_id}>
              <span>
                <b>{dataset.label}</b>
                <small>{dataset.description}</small>
              </span>
              <span>
                <i className={statusTone(dataset.status)}>{dataset.status}</i>
              </span>
              <span>{dataset.row_count}</span>
              <span>{formatTime(dataset.last_timestamp)}</span>
              <span>{dataset.powerbi_ready && dataset.exists ? "ready" : dataset.powerbi_ready ? "pending data" : "planned"}</span>
              <span>{dataset.bot_ready && dataset.exists && dataset.row_count > 0 ? "ready" : dataset.dataset_id === "asset_features" ? "next" : "no"}</span>
            </div>
          ))}
        </div>
      </section>
    </section>
  );
}
