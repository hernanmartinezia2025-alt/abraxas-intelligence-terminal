import React, { useEffect, useMemo, useRef, useState } from "react";
import { CandlestickSeries, ColorType, createChart, HistogramSeries } from "lightweight-charts";
import { getCandles } from "../../api/client.js";

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
  const [candles, setCandles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const lastCandle = candles[candles.length - 1];
  const previousCandle = candles[candles.length - 2];
  const move = useMemo(() => {
    if (!lastCandle || !previousCandle) return 0;
    return ((lastCandle.close - previousCandle.close) / previousCandle.close) * 100;
  }, [lastCandle, previousCandle]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");

    getCandles(symbol, interval, 240)
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

    return () => {
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
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
    chartRef.current.timeScale().fitContent();
  }, [candles]);

  return (
    <div className={`real-chart-wrap ${expanded ? "expanded" : ""}`}>
      <div className="chart-toolbar">
        <span>{symbol}</span>
        <strong>{interval}</strong>
        {lastCandle && <b className={move >= 0 ? "positive" : "negative"}>{move >= 0 ? "+" : ""}{move.toFixed(2)}%</b>}
      </div>
      <div className={`real-chart ${expanded ? "expanded" : ""}`} ref={containerRef} />
      {loading && <div className="chart-state">Loading candles</div>}
      {error && <div className="chart-state error">Chart error: {error}</div>}
      {!loading && !error && candles.length === 0 && <div className="chart-state">No candles</div>}
    </div>
  );
}
