const API_BASE = import.meta.env.VITE_ABRAXAS_API_BASE || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export function getHealth() {
  return request("/api/health");
}

export function getRadar() {
  return request("/api/radar");
}

export function getMarketUniverse(category, refresh = false) {
  const params = new URLSearchParams({ category, refresh: String(refresh) });
  return request(`/api/markets/universe?${params}`);
}

export function getMarketOverview(refresh = false) {
  const params = new URLSearchParams({ refresh: String(refresh) });
  return request(`/api/markets/overview?${params}`);
}

export function updateRadar() {
  return request("/api/radar/update", { method: "POST" });
}

export function getCandles(symbol = "BTCUSDT", interval = "15m", limit = 200) {
  const params = new URLSearchParams({ symbol, interval, limit: String(limit) });
  return request(`/api/candles?${params}`);
}

export function getOrderBook(symbol = "BTCUSDT", limit = 20) {
  const params = new URLSearchParams({ symbol, limit: String(limit) });
  return request(`/api/order-book?${params}`);
}

export function getStatistics({
  symbol = "BTCUSDT",
  interval = "15m",
  limit = 300,
  horizonSteps = 48,
  paths = 700,
} = {}) {
  const params = new URLSearchParams({
    symbol,
    interval,
    limit: String(limit),
    horizon_steps: String(horizonSteps),
    paths: String(paths),
  });
  return request(`/api/statistics?${params}`);
}

export function getStatisticsSummary({ symbol = "BTCUSDT", interval = "15m", limit = 300 } = {}) {
  const params = new URLSearchParams({
    symbol,
    interval,
    limit: String(limit),
  });
  return request(`/api/statistics/summary?${params}`);
}

export function getMonteCarlo({
  symbol = "BTCUSDT",
  interval = "15m",
  limit = 300,
  horizonSteps = 48,
  paths = 700,
} = {}) {
  const params = new URLSearchParams({
    symbol,
    interval,
    limit: String(limit),
    horizon_steps: String(horizonSteps),
    paths: String(paths),
  });
  return request(`/api/statistics/monte-carlo?${params}`);
}

export function getStatisticsRuns({ symbol = "", timeframe = "", runType = "", limit = 20 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (symbol) params.set("symbol", symbol);
  if (timeframe) params.set("timeframe", timeframe);
  if (runType) params.set("run_type", runType);
  return request(`/api/statistics/runs?${params}`);
}

export function getRegime({ symbol = "BTCUSDT", timeframe = "15m", limit = 120, refresh = false } = {}) {
  const params = new URLSearchParams({
    symbol,
    timeframe,
    limit: String(limit),
    refresh: String(refresh),
  });
  return request(`/api/regime?${params}`);
}

export function getRegimeSnapshots({ symbol = "", timeframe = "", limit = 20 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (symbol) params.set("symbol", symbol);
  if (timeframe) params.set("timeframe", timeframe);
  return request(`/api/regime/snapshots?${params}`);
}

export function getFeatures({ symbol = "", timeframe = "", limit = 20 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (symbol) params.set("symbol", symbol);
  if (timeframe) params.set("timeframe", timeframe);
  return request(`/api/features?${params}`);
}

export function buildFeatures({ symbol = "BTCUSDT", timeframe = "15m", limit = 300 } = {}) {
  const params = new URLSearchParams({
    symbol,
    timeframe,
    limit: String(limit),
  });
  return request(`/api/features/build?${params}`, { method: "POST" });
}

export function getBots(limit = 100) {
  const params = new URLSearchParams({ limit: String(limit) });
  return request(`/api/bots?${params}`);
}

export function createBot(payload) {
  return request("/api/bots", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getBot(botId) {
  return request(`/api/bots/${botId}`);
}

export function createBotVersion(botId, payload) {
  return request(`/api/bots/${botId}/versions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getBotBacktests(botId, limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) });
  return request(`/api/bots/${botId}/backtests?${params}`);
}

export function getBacktests(limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) });
  return request(`/api/bots/backtests?${params}`);
}

export function getBacktest(backtestId) {
  return request(`/api/bots/backtests/${backtestId}`);
}

export function runBotBacktest(botId, payload = {}) {
  return request(`/api/bots/${botId}/backtests`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getLiveMapEvents({ refresh = false, limit = 250, types = "" } = {}) {
  const params = new URLSearchParams({ refresh: String(refresh), limit: String(limit) });
  if (types) params.set("types", types);
  return request(`/api/live-map/events?${params}`);
}

export function getLiveMapNews({ refresh = false, limit = 160 } = {}) {
  const params = new URLSearchParams({ refresh: String(refresh), limit: String(limit) });
  return request(`/api/live-map/news?${params}`);
}

export function getLiveMapAlerts({ refresh = false, limit = 160 } = {}) {
  const params = new URLSearchParams({ refresh: String(refresh), limit: String(limit) });
  return request(`/api/live-map/alerts?${params}`);
}

export function getLiveMapHealth() {
  return request("/api/live-map/health");
}

export function getDataCatalog() {
  return request("/api/data/catalog");
}

export function getDataSources() {
  return request("/api/data/sources");
}

export function getDataHealth() {
  return request("/api/data/health");
}

export function getDataDatasets() {
  return request("/api/data/datasets");
}

export function getBackendRoutes() {
  return request("/api/data/routes");
}

export function getDatasetPreview(datasetId, limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) });
  return request(`/api/data/datasets/${datasetId}/preview?${params}`);
}

export function datasetExportUrl(datasetId, limit = 5000) {
  const params = new URLSearchParams({ limit: String(limit) });
  return `${API_BASE}/api/data/export/${datasetId}.csv?${params}`;
}

export function getRiskProfile(auditLimit = 20) {
  return request(`/api/risk?audit_limit=${auditLimit}`);
}

export function updateRiskLimits(payload) {
  return request("/api/risk/limits", { method: "PUT", body: JSON.stringify(payload) });
}

export function updateKillSwitch(payload) {
  return request("/api/risk/kill-switch", { method: "POST", body: JSON.stringify(payload) });
}

export function validateRiskIntent(payload) {
  return request("/api/risk/validate", { method: "POST", body: JSON.stringify(payload) });
}

export function getPaperAccount() {
  return request("/api/paper");
}

export function placePaperOrder(payload) {
  return request("/api/paper/orders", { method: "POST", body: JSON.stringify(payload) });
}

export function resetPaperAccount(payload) {
  return request("/api/paper/reset", { method: "POST", body: JSON.stringify(payload) });
}

export function getExchangeRegistry() {
  return request("/api/exchanges");
}

export function getExchangeTicker(exchangeId, symbol) {
  const params = new URLSearchParams({ symbol });
  return request(`/api/exchanges/${exchangeId}/ticker?${params}`);
}

export function getExchangeOrderBook(exchangeId, symbol, limit = 20) {
  const params = new URLSearchParams({ symbol, limit: String(limit) });
  return request(`/api/exchanges/${exchangeId}/order-book?${params}`);
}
