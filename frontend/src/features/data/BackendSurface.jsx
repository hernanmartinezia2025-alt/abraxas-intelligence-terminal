import React, { useEffect, useMemo, useState } from "react";
import {
  buildFeatures,
  getBacktests,
  getBackendRoutes,
  getFeatures,
  getBots,
  getLiveMapAlerts,
  getLiveMapHealth,
  getLiveMapNews,
  getOrderBook,
  getBotBacktests,
  getRegimeSnapshots,
  getStatisticsRuns,
  getRiskProfile,
  getPaperAccount,
  getChartIndicatorPresets,
  getSpotPortfolio,
  getSpotDcaPlans,
  getSpotAllocationPolicies,
} from "../../api/client.js";

const UI_ROUTE_SURFACES = [
  ["/api/radar", "markets", "Markets"],
  ["/api/markets", "markets", "Markets"],
  ["/api/candles", "trade", "Trade"],
  ["/api/order-book", "trade", "Trade"],
  ["/api/chart-indicators", "trade", "Trade / Indicators"],
  ["/api/statistics", "research", "Research"],
  ["/api/regime", "research", "Research"],
  ["/api/features", "research", "Research"],
  ["/api/live-map", "map", "Map"],
  ["/api/bots", "bots", "Bots"],
  ["/api/paper", "bots", "Bots / Paper"],
  ["/api/spot-portfolio", "portfolio", "Portfolio / Spot"],
  ["/api/risk", "risk", "Risk"],
  ["/api/exchanges", "data", "Data"],
  ["/api/data", "data", "Data"],
  ["/api/health", "data", "Data"],
];

function uiSurfaceFor(path) {
  const match = UI_ROUTE_SURFACES.find(([prefix]) => path === prefix || path.startsWith(`${prefix}/`));
  return match ? { page: match[1], label: match[2] } : null;
}

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
  const [routeCatalog, setRouteCatalog] = useState({ count: 0, routes: [] });

  const routeCoverage = useMemo(() => {
    const routes = routeCatalog.routes.map((route) => ({ ...route, uiSurface: uiSurfaceFor(route.path) }));
    const exposed = routes.filter((route) => route.uiSurface).length;
    return { routes, exposed, backendOnly: routes.length - exposed };
  }, [routeCatalog.routes]);

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
      {
        label: "Chart Indicator Presets",
        method: "GET",
        path: "/api/chart-indicators/presets",
        description: "Workspaces versionados de SMA, EMA y Bollinger calculados por backend.",
        call: () => getChartIndicatorPresets({ symbol: selectedSymbol, timeframe: "15m" }),
        rows: ["presets"],
      },
      {
        label: "Risk Engine",
        method: "GET",
        path: "/api/risk",
        description: "Limites, kill switch y auditoria persistidos en SQLite.",
        call: () => getRiskProfile(12),
        rows: ["audit_log"],
      },
      {
        label: "Paper Trading",
        method: "GET",
        path: "/api/paper",
        description: "Cuenta, posiciones, fills y perfiles ROI por bot bajo Risk Engine.",
        call: () => getPaperAccount(),
        rows: ["orders", "positions", "bot_performance"],
      },
      {
        label: "Spot Portfolio",
        method: "GET",
        path: "/api/spot-portfolio",
        description: "Ciclos, holdings, equity persistida y ledger patrimonial spot simulado.",
        call: () => getSpotPortfolio(),
        rows: ["holdings", "equity_history", "ledger"],
      },
      {
        label: "Spot DCA Plans",
        method: "GET",
        path: "/api/spot-portfolio/dca-plans",
        description: "Planes, vencimientos e intentos DCA auditables sin scheduler ni live execution.",
        call: () => getSpotDcaPlans(),
        rows: ["plans", "executions"],
      },
      {
        label: "Spot Allocation",
        method: "GET",
        path: "/api/spot-portfolio/allocation-policies",
        description: "Políticas versionadas y runs de rebalanceo en dos fases, sin ejecución live.",
        call: () => getSpotAllocationPolicies(),
        rows: ["policies", "runs"],
      },
    ],
    [selectedSymbol]
  );

  async function loadSurface({ silent = false } = {}) {
    if (!silent) setLoading(true);
    setError("");
    const [results, routesResult] = await Promise.all([
      Promise.all(
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
      ),
      getBackendRoutes().catch((err) => ({ count: 0, routes: [], error: err.message })),
    ]);
    setSurface(results);
    setRouteCatalog(routesResult);
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
  }, [requests]);

  return (
    <section className="exchange-panel data-panel backend-surface">
      <div className="exchange-panel-head compact">
        <div>
          <p className="eyebrow">Backend Surface</p>
          <h2>Funciones reales expuestas</h2>
          <small>Auditoria bajo demanda para evitar llamadas externas innecesarias.</small>
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

      <section className="route-catalog">
        <div className="exchange-panel-head compact">
          <div><p className="eyebrow">FastAPI registry</p><h2>{routeCatalog.count} rutas descubiertas</h2></div>
          <span>AUTO-DISCOVERED</span>
        </div>
        <div className="route-coverage-summary">
          <article><span>CON SUPERFICIE UI</span><strong>{routeCoverage.exposed}</strong></article>
          <article className={routeCoverage.backendOnly ? "attention" : "complete"}>
            <span>SOLO BACKEND</span><strong>{routeCoverage.backendOnly}</strong>
          </article>
          <p>El registro se compara con las consolas declaradas. Una ruta sin superficie queda marcada para no perder motores backend.</p>
        </div>
        {routeCatalog.error && <div className="error-box">{routeCatalog.error}</div>}
        <div className="route-catalog-list">
          {routeCoverage.routes.map((route) => <article className={route.uiSurface ? "ui-exposed" : "backend-only"} key={`${route.methods.join("-")}-${route.path}`}>
            <div>{route.methods.map((method) => <b className={method.toLowerCase()} key={method}>{method}</b>)}</div>
            <code>{route.path}</code>
            {route.uiSurface
              ? <a href={`#${route.uiSurface.page}`}>UI · {route.uiSurface.label}</a>
              : <span>SOLO BACKEND</span>}
          </article>)}
        </div>
      </section>

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
