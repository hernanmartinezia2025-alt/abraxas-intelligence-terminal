import React, { useEffect, useMemo, useState } from "react";
import { datasetExportUrl, getDataCatalog, getDataHealth, getDatasetPreview } from "../../api/client.js";
import BackendSurface from "./BackendSurface.jsx";

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

export default function DataApiCenter({ selectedSymbol = "BTCUSDT" }) {
  const [catalog, setCatalog] = useState(null);
  const [health, setHealth] = useState(null);
  const [selectedDataset, setSelectedDataset] = useState("market_candles");
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
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

  async function loadPreview(datasetId = selectedDataset) {
    setPreviewLoading(true);
    try {
      const payload = await getDatasetPreview(datasetId, 20);
      setPreview(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setPreviewLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    const timer = window.setInterval(() => {
      loadData({ silent: true });
    }, 90000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    loadPreview(selectedDataset);
  }, [selectedDataset]);

  const datasets = useMemo(() => health?.datasets || catalog?.datasets || [], [catalog, health]);
  const sources = catalog?.sources || [];
  const summary = health?.summary || {};
  const database = health?.database || {};
  const assetFeaturesReady = datasets.some(
    (dataset) => dataset.dataset_id === "asset_features" && dataset.exists && dataset.row_count > 0
  );
  const exportableDatasets = datasets.filter((dataset) => dataset.exists && dataset.powerbi_ready);
  const previewRows = preview?.rows || [];
  const availablePreviewColumns = previewRows[0] ? Object.keys(previewRows[0]) : [];
  const preferredPreviewColumns = preview?.dataset?.preview_columns || [];
  const previewColumns = preferredPreviewColumns.length
    ? preferredPreviewColumns.filter((column) => availablePreviewColumns.includes(column))
    : availablePreviewColumns.slice(0, 8);

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

      <BackendSurface selectedSymbol={selectedSymbol} />

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
              <span className="dataset-actions">
                <button type="button" disabled={!dataset.exists} onClick={() => setSelectedDataset(dataset.dataset_id)}>
                  Preview
                </button>
                {dataset.exists && dataset.powerbi_ready ? (
                  <a href={datasetExportUrl(dataset.dataset_id)} target="_blank" rel="noreferrer">
                    CSV
                  </a>
                ) : (
                  <em>CSV</em>
                )}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="exchange-panel data-panel">
        <div className="exchange-panel-head compact">
          <div>
            <p className="eyebrow">Dataset Preview</p>
            <h2>{selectedDataset}</h2>
          </div>
          <div className="dataset-toolbar">
            <select value={selectedDataset} onChange={(event) => setSelectedDataset(event.target.value)}>
              {datasets.map((dataset) => (
                <option key={dataset.dataset_id} value={dataset.dataset_id}>
                  {dataset.label}
                </option>
              ))}
            </select>
            <button type="button" onClick={() => loadPreview()} disabled={previewLoading}>
              {previewLoading ? "Leyendo..." : "Refrescar preview"}
            </button>
          </div>
        </div>
        <div className="preview-wrap">
          <div className="export-strip">
            {exportableDatasets.map((dataset) => (
              <a key={dataset.dataset_id} href={datasetExportUrl(dataset.dataset_id)} target="_blank" rel="noreferrer">
                {dataset.dataset_id}.csv
              </a>
            ))}
          </div>
          {previewRows.length ? (
            <div className="preview-table">
              <div className="preview-row header">
                {previewColumns.map((column) => (
                  <span key={column}>{column}</span>
                ))}
              </div>
              {previewRows.map((row, index) => (
                <div className="preview-row" key={`${selectedDataset}-${index}`}>
                  {previewColumns.map((column) => (
                    <span key={column}>{String(row[column] ?? "").slice(0, 80)}</span>
                  ))}
                </div>
              ))}
            </div>
          ) : (
            <div className="map-empty">
              <strong>Sin filas para mostrar</strong>
              <span>Este dataset existe pero todavia no tiene registros, o esta planificado para una fase posterior.</span>
            </div>
          )}
        </div>
      </section>
    </section>
  );
}
