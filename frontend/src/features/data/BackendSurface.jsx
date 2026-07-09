import React, { useEffect, useMemo, useState } from "react";
import {
  buildFeatures,
  getBacktests,
  getFeatures,
  getBots,
  getLiveMapAlerts,
  getLiveMapHealth,
  getLiveMapNews,
  getOrderBook,
  getBotBacktests,
  getRegimeSnapshots,
  getStatisticsRuns,
} from "../../api/client.js";

function countRows(payload, keys) {
  for (const key of keys) {
    if (Array.isArray(payload?.[key])) return payload[key].length;
  }
  return 0;
}

function latestLabel(payload, keys) {
  for (const key of keys) {
    const rows = payload?.[key];
    if (Array.isArray(rows) && rows.length) {
      const row = rows[0];
      return row.symbol || row.source || row.title || row.regime_label || row.run_type || row.price || row.id || "registro";
    }
  }
  return "sin filas";
}

function SurfaceCard({ item }) {
  const ok = item.status === "online";
  return (
    <article className={`surface-card ${ok ? "online" : "down"}`}>
      <div>
        <span>{item.method}</span>
        <strong>{item.label}</strong>
      </div>
      <code>{item.path}</code>
      <p>{item.description}</p>
      <footer>
        <b>{ok ? "ONLINE" : "ERROR"}</b>
        <small>{item.metric}</small>
      </footer>
    </article>
  );
}

export default function BackendSurface({ selectedSymbol = "BTCUSDT" }) {
  const [surface, setSurface] = useState([]);
  const [featureBuild, setFeatureBuild] = useState(null);
  const [loading, setLoading] = useState(false);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState("");

  const requests = useMemo(
    () => [
      {
        label: "Feature Store",
        method: "GET",
        path: "/api/features",
        description: "Features numericas listas para estadistica, regimen y bots.",
        call: () => getFeatures({ symbol: selectedSymbol, timeframe: "15m", limit: 12 }),
        rows: ["features", "rows"],
      },
      {
        label: "Statistics Runs",
        method: "GET",
        path: "/api/statistics/runs",
        description: "Historial persistido de calculos estadisticos y Monte Carlo.",
        call: () => getStatisticsRuns({ symbol: selectedSymbol, limit: 12 }),
        rows: ["runs", "rows"],
      },
      {
        label: "Regime Snapshots",
        method: "GET",
        path: "/api/regime/snapshots",
        description: "Lecturas historicas del motor de regimen por activo/timeframe.",
        call: () => getRegimeSnapshots({ symbol: selectedSymbol, limit: 12 }),
        rows: ["snapshots", "rows"],
      },
      {
        label: "Live Map Health",
        method: "GET",
        path: "/api/live-map/health",
        description: "Estado de fuentes GDELT, USGS y GDACS.",
        call: () => getLiveMapHealth(),
        rows: ["sources"],
      },
      {
        label: "Live News",
        method: "GET",
        path: "/api/live-map/news",
        description: "Noticias geolocalizadas normalizadas y cacheadas.",
        call: () => getLiveMapNews({ limit: 12 }),
        rows: ["events", "news"],
      },
      {
        label: "Live Alerts",
        method: "GET",
        path: "/api/live-map/alerts",
        description: "Eventos severos y market-relevant ordenados por impacto.",
        call: () => getLiveMapAlerts({ limit: 12 }),
        rows: ["events", "alerts"],
      },
      {
        label: "Bot Forge",
        method: "GET",
        path: "/api/bots",
        description: "Bots guardados en SQLite con versiones de estrategia auditables.",
        call: () => getBots(12),
        rows: ["bots"],
      },
      {
        label: "Backtest Runs",
        method: "GET",
        path: "/api/bots/backtests",
        description: "Resultados persistidos de simulaciones de bots contra market_candles.",
        call: () => getBacktests(12),
        rows: ["runs"],
      },
      {
        label: "Order Book",
        method: "GET",
        path: "/api/order-book",
        description: "Profundidad real Binance Spot para la mesa Trade.",
        call: () => getOrderBook(selectedSymbol, 20),
        rows: ["bids"],
      },
    ],
    [selectedSymbol]
  );

  async function loadSurface({ silent = false } = {}) {
    if (!silent) setLoading(true);
    setError("");
    const results = await Promise.all(
      requests.map(async (item) => {
        try {
          const payload = await item.call();
          const rowCount = countRows(payload, item.rows);
          return {
            ...item,
            status: "online",
            metric: `${rowCount} filas | ${latestLabel(payload, item.rows)}`,
          };
        } catch (err) {
          return {
            ...item,
            status: "down",
            metric: err.message,
          };
        }
      })
    );
    setSurface(results);
    if (!silent) setLoading(false);
  }

  async function handleBuildFeatures() {
    setBuilding(true);
    setError("");
    try {
      const payload = await buildFeatures({ symbol: selectedSymbol, timeframe: "15m", limit: 300 });
      setFeatureBuild(payload);
      await loadSurface({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBuilding(false);
    }
  }

  useEffect(() => {
    loadSurface();
    const timer = window.setInterval(() => {
      loadSurface({ silent: true });
    }, 120000);
    return () => window.clearInterval(timer);
  }, [requests]);

  return (
    <section className="exchange-panel data-panel backend-surface">
      <div className="exchange-panel-head compact">
        <div>
          <p className="eyebrow">Backend Surface</p>
          <h2>Funciones reales expuestas</h2>
        </div>
        <div className="dataset-toolbar">
          <button type="button" onClick={() => loadSurface()} disabled={loading}>
            {loading ? "Auditando..." : "Auditar endpoints"}
          </button>
          <button type="button" onClick={handleBuildFeatures} disabled={building}>
            {building ? "Construyendo..." : `Build features ${selectedSymbol}`}
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="surface-grid">
        {surface.map((item) => (
          <SurfaceCard item={item} key={item.path} />
        ))}
      </div>

      {featureBuild && (
        <div className="surface-result">
          <strong>Feature build ejecutado</strong>
          <span>
            {featureBuild.symbol || selectedSymbol} | {featureBuild.timeframe || "15m"} |{" "}
            {featureBuild.features_saved ?? featureBuild.saved ?? featureBuild.count ?? 0} registros guardados
          </span>
        </div>
      )}
    </section>
  );
}
