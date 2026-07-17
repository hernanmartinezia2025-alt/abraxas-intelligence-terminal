import React, { useEffect, useMemo, useRef, useState } from "react";
import { CandlestickSeries, ColorType, createChart, createSeriesMarkers, HistogramSeries, LineSeries } from "lightweight-charts";
import {
  archiveChartIndicatorPreset,
  computeChartIndicators,
  getCandles,
  getChartIndicatorPresets,
  getPaperAccount,
  saveChartIndicatorPreset,
  updatePaperProtection,
} from "../../api/client.js";

const DEFAULT_INDICATORS = [
  { id: "sma-20", kind: "sma", period: 20, deviation: 2, color: "#dfc079", line_width: 2, label: "SMA 20", visible: true },
];

const INDICATOR_COLORS = { sma: "#dfc079", ema: "#7aa7ff", bollinger: "#9a8cff" };

function normalizeCandles(candles) {
  return candles.map((candle) => ({
    time: Math.floor(Number(candle.timestamp) / 1000),
    open: Number(candle.open),
    high: Number(candle.high),
    low: Number(candle.low),
    close: Number(candle.close),
    volume: Number(candle.volume || 0),
  }));
}

export default function MarketChart({ symbol = "BTCUSDT", interval = "15m", expanded = false }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const overlaysRef = useRef({});
  const indicatorSeriesRef = useRef([]);
  const markersRef = useRef(null);
  const [candles, setCandles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [paper, setPaper] = useState(null);
  const [showLevels, setShowLevels] = useState(true);
  const [indicatorConfigs, setIndicatorConfigs] = useState(DEFAULT_INDICATORS);
  const [indicatorWorkspace, setIndicatorWorkspace] = useState(null);
  const [indicatorDraft, setIndicatorDraft] = useState({ kind: "ema", period: 55, deviation: 2, color: INDICATOR_COLORS.ema });
  const [presets, setPresets] = useState([]);
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [presetName, setPresetName] = useState("Mi workspace");
  const [indicatorMessage, setIndicatorMessage] = useState("");
  const [indicatorLoading, setIndicatorLoading] = useState(false);
  const [protectionDraft, setProtectionDraft] = useState({ stop_loss_price: "", take_profit_price: "", trailing_distance_pct: "" });
  const [protectionMessage, setProtectionMessage] = useState("");

  const lastCandle = candles[candles.length - 1];
  const previousCandle = candles[candles.length - 2];
  const allocation = (paper?.allocations || []).find((item) => item.symbol === symbol && Number(item.quantity) > 0);
  const move = useMemo(() => {
    if (!lastCandle || !previousCandle) return 0;
    return ((lastCandle.close - previousCandle.close) / previousCandle.close) * 100;
  }, [lastCandle, previousCandle]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");

    getCandles(symbol, interval, 600)
      .then((payload) => {
        if (!alive) return;
        setCandles(normalizeCandles(payload.candles || []));
      })
      .catch((err) => {
        if (!alive) return;
        setError(err.message);
        setCandles([]);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [symbol, interval]);

  useEffect(() => {
    let alive = true;
    getPaperAccount().then((snapshot) => alive && setPaper(snapshot)).catch(() => alive && setPaper(null));
    return () => { alive = false; };
  }, [symbol]);

  useEffect(() => {
    let alive = true;
    setIndicatorMessage("");
    getChartIndicatorPresets({ symbol, timeframe: interval })
      .then((payload) => {
        if (!alive) return;
        const rows = payload.presets || [];
        setPresets(rows);
        if (rows[0]) {
          setIndicatorConfigs(rows[0].indicators || DEFAULT_INDICATORS);
          setSelectedPresetId(String(rows[0].id));
          setPresetName(rows[0].name);
        } else {
          setIndicatorConfigs(DEFAULT_INDICATORS);
          setSelectedPresetId("");
          setPresetName("Mi workspace");
        }
      })
      .catch((err) => alive && setIndicatorMessage(err.message));
    return () => { alive = false; };
  }, [symbol, interval]);

  useEffect(() => {
    let alive = true;
    if (!indicatorConfigs.length) {
      setIndicatorWorkspace(null);
      setIndicatorLoading(false);
      return () => { alive = false; };
    }
    setIndicatorLoading(true);
    const maxPeriod = Math.max(...indicatorConfigs.map((item) => Number(item.period) || 2));
    computeChartIndicators({
      symbol,
      timeframe: interval,
      limit: Math.max(600, maxPeriod + 20),
      indicators: indicatorConfigs,
    })
      .then((payload) => alive && setIndicatorWorkspace(payload))
      .catch((err) => {
        if (!alive) return;
        setIndicatorWorkspace(null);
        setIndicatorMessage(err.message);
      })
      .finally(() => alive && setIndicatorLoading(false));
    return () => { alive = false; };
  }, [symbol, interval, indicatorConfigs]);

  useEffect(() => {
    if (!allocation) return;
    setProtectionDraft({ stop_loss_price: allocation.stop_loss_price || "", take_profit_price: allocation.take_profit_price || "", trailing_distance_pct: allocation.trailing_distance_pct || "" });
  }, [allocation?.id, allocation?.updated_at]);

  function addIndicator() {
    if (indicatorConfigs.length >= 8) {
      setIndicatorMessage("Maximo 8 indicadores por workspace.");
      return;
    }
    const kind = indicatorDraft.kind;
    const period = Math.max(2, Math.min(500, Number(indicatorDraft.period) || 2));
    const base = `${kind}-${period}`;
    let identifier = base;
    let suffix = 2;
    while (indicatorConfigs.some((item) => item.id === identifier)) identifier = `${base}-${suffix++}`;
    const next = {
      id: identifier,
      kind,
      period,
      deviation: Math.max(0.1, Math.min(10, Number(indicatorDraft.deviation) || 2)),
      color: indicatorDraft.color || INDICATOR_COLORS[kind],
      line_width: 2,
      label: `${kind === "bollinger" ? "BB" : kind.toUpperCase()} ${period}`,
      visible: true,
    };
    setIndicatorConfigs((current) => [...current, next]);
    setSelectedPresetId("");
    setIndicatorMessage("Workspace modificado; guardalo para versionarlo.");
  }

  function applyPreset(presetId) {
    const preset = presets.find((item) => String(item.id) === String(presetId));
    setSelectedPresetId(String(presetId));
    if (!preset) return;
    setIndicatorConfigs(preset.indicators || []);
    setPresetName(preset.name);
    setIndicatorMessage(`Preset v${preset.active_version} cargado.`);
  }

  async function savePreset() {
    setIndicatorLoading(true);
    setIndicatorMessage("Guardando preset...");
    try {
      const saved = await saveChartIndicatorPreset({ name: presetName, symbol, timeframe: interval, indicators: indicatorConfigs });
      const payload = await getChartIndicatorPresets({ symbol, timeframe: interval });
      setPresets(payload.presets || []);
      setSelectedPresetId(String(saved.id));
      setIndicatorConfigs(saved.indicators || indicatorConfigs);
      setIndicatorMessage(`Preset v${saved.active_version} persistido en SQLite.`);
    } catch (err) {
      setIndicatorMessage(err.message);
    } finally {
      setIndicatorLoading(false);
    }
  }

  async function archivePreset() {
    if (!selectedPresetId) return;
    setIndicatorLoading(true);
    try {
      await archiveChartIndicatorPreset(selectedPresetId);
      const payload = await getChartIndicatorPresets({ symbol, timeframe: interval });
      const rows = payload.presets || [];
      setPresets(rows);
      setSelectedPresetId(rows[0] ? String(rows[0].id) : "");
      setIndicatorConfigs(rows[0]?.indicators || DEFAULT_INDICATORS);
      setPresetName(rows[0]?.name || "Mi workspace");
      setIndicatorMessage("Preset archivado; el historial de versiones se conserva.");
    } catch (err) {
      setIndicatorMessage(err.message);
    } finally {
      setIndicatorLoading(false);
    }
  }

  async function saveProtection(event) {
    event.preventDefault();
    if (!allocation) return;
    setProtectionMessage("Guardando...");
    try {
      await updatePaperProtection(allocation.id, Object.fromEntries(Object.entries(protectionDraft).map(([key, value]) => [key, value === "" ? null : Number(value)])));
      const next = await getPaperAccount();
      setPaper(next);
      setProtectionMessage("Protección persistida");
    } catch (err) { setProtectionMessage(err.message); }
  }

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#0d0f12" },
        textColor: "rgba(246, 248, 251, 0.68)",
        fontFamily: "JetBrains Mono, Consolas, monospace",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.055)" },
        horzLines: { color: "rgba(255,255,255,0.055)" },
      },
      crosshair: {
        mode: 0,
      },
      rightPriceScale: {
        borderColor: "rgba(255,255,255,0.08)",
        scaleMargins: { top: 0.08, bottom: 0.24 },
      },
      timeScale: {
        borderColor: "rgba(255,255,255,0.08)",
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#25d39b",
      downColor: "#ff6376",
      borderUpColor: "#25d39b",
      borderDownColor: "#ff6376",
      wickUpColor: "#25d39b",
      wickDownColor: "#ff6376",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.78, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;
    markersRef.current = createSeriesMarkers(candleSeries);

    return () => {
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      overlaysRef.current = {};
      indicatorSeriesRef.current = [];
      markersRef.current?.detach();
      markersRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || !chartRef.current) return;

    candleSeriesRef.current.setData(
      candles.map(({ time, open, high, low, close }) => ({ time, open, high, low, close }))
    );
    volumeSeriesRef.current.setData(
      candles.map((candle) => ({
        time: candle.time,
        value: candle.volume,
        color: candle.close >= candle.open ? "rgba(37, 211, 155, 0.36)" : "rgba(255, 99, 118, 0.34)",
      }))
    );
    const ledgerByReference = new Map((paper?.ledger || []).map((item) => [String(item.reference_id), item]));
    const markers = (paper?.fills || []).filter((fill) => fill.symbol === symbol).map((fill) => {
      const ledger = ledgerByReference.get(String(fill.id));
      let trigger = "";
      try { trigger = ledger?.payload_json ? JSON.parse(ledger.payload_json).trigger_reason || "" : ""; } catch { trigger = ""; }
      const exit = fill.side === "sell";
      return { time: Math.floor(new Date(fill.filled_at).getTime() / 1000), position: exit ? "aboveBar" : "belowBar", color: exit ? "#ff6376" : "#25d39b", shape: exit ? "arrowDown" : "arrowUp", text: exit ? (trigger || "EXIT") : "ENTRY" };
    }).filter((marker) => Number.isFinite(marker.time));
    markersRef.current?.setMarkers(markers.sort((a, b) => a.time - b.time));
    const position = (paper?.positions || []).find((item) => item.symbol === symbol);
    const allocation = (paper?.allocations || []).find((item) => item.symbol === symbol && Number(item.quantity) > 0);
    for (const [key, price, color, title] of [
      ["entry", position?.average_price, "#8bd4ff", "Avg entry"],
      ["stop", allocation?.stop_loss_price, "#ff6376", "SL"],
      ["take", allocation?.take_profit_price, "#25d39b", "TP"],
    ]) {
      if (showLevels && price && candles.length) {
        if (!overlaysRef.current[key]) overlaysRef.current[key] = candleSeriesRef.current.createPriceLine({ price, color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title });
        else overlaysRef.current[key].applyOptions({ price, color, title });
      } else if (overlaysRef.current[key]) { candleSeriesRef.current.removePriceLine(overlaysRef.current[key]); delete overlaysRef.current[key]; }
    }
    chartRef.current.timeScale().fitContent();
  }, [candles, showLevels, paper, symbol]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    for (const series of indicatorSeriesRef.current) chart.removeSeries(series);
    indicatorSeriesRef.current = [];
    for (const item of indicatorWorkspace?.indicators || []) {
      const config = item.config;
      const entries = Object.entries(item.series || {});
      entries.forEach(([band, points]) => {
        const isOuterBand = config.kind === "bollinger" && band !== "middle";
        const series = chart.addSeries(LineSeries, {
          color: config.color,
          lineWidth: isOuterBand ? 1 : config.line_width,
          lineStyle: isOuterBand ? 2 : 0,
          priceLineVisible: false,
          lastValueVisible: band === "value" || band === "middle",
          title: config.kind === "bollinger" ? `${config.label} ${band}` : config.label,
        });
        series.setData((points || []).map((point) => ({ time: Math.floor(Number(point.timestamp) / 1000), value: Number(point.value) })));
        indicatorSeriesRef.current.push(series);
      });
    }
  }, [indicatorWorkspace]);

  return (
    <div className={`real-chart-wrap ${expanded ? "expanded" : ""}`}>
      <div className="chart-toolbar">
        <span>{symbol}</span>
        <strong>{interval}</strong>
        {lastCandle && <b className={move >= 0 ? "positive" : "negative"}>{move >= 0 ? "+" : ""}{move.toFixed(2)}%</b>}
        <div className="chart-indicators" aria-label="Indicadores del gráfico">
          <button type="button" className={showLevels ? "active" : ""} onClick={() => setShowLevels((current) => !current)}>Posición / SL / TP</button>
          <span>{indicatorLoading ? "calculando" : `${indicatorConfigs.length} indicadores backend`}</span>
        </div>
      </div>
      <div className={`real-chart ${expanded ? "expanded" : ""}`} ref={containerRef} />
      <section className="chart-workspace-editor">
        <div className="chart-workspace-head">
          <div><span className="eyebrow">Indicator workspace</span><strong>Cálculo backend + presets SQLite</strong></div>
          <small>{indicatorWorkspace?.served_from || "sin cálculo"} · visual only</small>
        </div>
        <div className="chart-preset-row">
          <select aria-label="Preset de indicadores" value={selectedPresetId} onChange={(event) => applyPreset(event.target.value)}>
            <option value="">Workspace sin guardar</option>
            {presets.map((preset) => <option key={preset.id} value={preset.id}>{preset.name} · v{preset.active_version}</option>)}
          </select>
          <input aria-label="Nombre del preset" value={presetName} maxLength={80} onChange={(event) => setPresetName(event.target.value)} />
          <button type="button" disabled={indicatorLoading || !indicatorConfigs.length} onClick={savePreset}>Guardar versión</button>
          <button type="button" className="secondary" disabled={indicatorLoading || !selectedPresetId} onClick={archivePreset}>Archivar</button>
        </div>
        <div className="chart-indicator-builder">
          <label>Tipo<select value={indicatorDraft.kind} onChange={(event) => setIndicatorDraft((current) => ({ ...current, kind: event.target.value, color: INDICATOR_COLORS[event.target.value] }))}><option value="sma">SMA</option><option value="ema">EMA</option><option value="bollinger">Bollinger</option></select></label>
          <label>Período<input type="number" min="2" max="500" value={indicatorDraft.period} onChange={(event) => setIndicatorDraft((current) => ({ ...current, period: event.target.value }))} /></label>
          {indicatorDraft.kind === "bollinger" && <label>Desvío<input type="number" min="0.1" max="10" step="0.1" value={indicatorDraft.deviation} onChange={(event) => setIndicatorDraft((current) => ({ ...current, deviation: event.target.value }))} /></label>}
          <label>Color<input type="color" value={indicatorDraft.color} onChange={(event) => setIndicatorDraft((current) => ({ ...current, color: event.target.value }))} /></label>
          <button type="button" disabled={indicatorLoading || indicatorConfigs.length >= 8} onClick={addIndicator}>Agregar indicador</button>
        </div>
        <div className="chart-indicator-list">
          {indicatorConfigs.map((item) => <button type="button" key={item.id} style={{ "--indicator-color": item.color }} onClick={() => { setIndicatorConfigs((current) => current.filter((row) => row.id !== item.id)); setSelectedPresetId(""); setIndicatorMessage("Workspace modificado; guardalo para versionarlo."); }}><i />{item.label}<small>{item.kind === "bollinger" ? `x${item.deviation}` : item.kind.toUpperCase()}</small><b>×</b></button>)}
          {!indicatorConfigs.length && <span>Agrega al menos un indicador para calcular y guardar el workspace.</span>}
        </div>
        {indicatorMessage && <p className="chart-workspace-message">{indicatorMessage}</p>}
      </section>
      {allocation && <form className="chart-protection-editor" onSubmit={saveProtection}>
        <span className="eyebrow">Protección paper · asignación #{allocation.id}</span>
        <label>SL <input type="number" step="any" value={protectionDraft.stop_loss_price} onChange={(e) => setProtectionDraft((v) => ({ ...v, stop_loss_price: e.target.value }))} placeholder="precio" /></label>
        <label>TP <input type="number" step="any" value={protectionDraft.take_profit_price} onChange={(e) => setProtectionDraft((v) => ({ ...v, take_profit_price: e.target.value }))} placeholder="precio" /></label>
        <label>Trailing % <input type="number" step="0.01" min="0" max="50" value={protectionDraft.trailing_distance_pct} onChange={(e) => setProtectionDraft((v) => ({ ...v, trailing_distance_pct: e.target.value }))} placeholder="opcional" /></label>
        <button type="submit">Guardar niveles</button><small>{protectionMessage}</small>
      </form>}
      {loading && <div className="chart-state">Loading candles</div>}
      {error && <div className="chart-state error">Chart error: {error}</div>}
      {!loading && !error && candles.length === 0 && <div className="chart-state">No candles</div>}
    </div>
  );
}
