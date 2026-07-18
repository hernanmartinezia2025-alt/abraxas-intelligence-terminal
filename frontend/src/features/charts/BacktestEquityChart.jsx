import React, { useEffect, useMemo, useRef } from "react";
import { AreaSeries, ColorType, createChart, LineSeries } from "lightweight-charts";
import { initialChartSize, observeChartSize } from "./chartSize.js";

function normalizePoints(points) {
  const byTime = new Map();
  for (const point of points || []) {
    const timestamp = Math.floor(Number(point.timestamp) / 1000);
    const equity = Number(point.equity);
    if (!Number.isFinite(timestamp) || !Number.isFinite(equity)) continue;
    byTime.set(timestamp, {
      time: timestamp,
      equity,
      benchmark: point.benchmark_equity === null || point.benchmark_equity === undefined
        ? null
        : Number(point.benchmark_equity),
    });
  }
  return [...byTime.values()].sort((left, right) => left.time - right.time);
}

export default function BacktestEquityChart({ points = [] }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const equitySeriesRef = useRef(null);
  const benchmarkSeriesRef = useRef(null);
  const normalized = useMemo(() => normalizePoints(points), [points]);
  const hasBenchmark = normalized.some((point) => Number.isFinite(point.benchmark));
  const chartLabel = normalized.length
    ? `Curva de equity con ${normalized.length} puntos; ${hasBenchmark ? "incluye benchmark buy and hold" : "sin benchmark disponible"}.`
    : "Sin puntos de equity para este run.";

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const chart = createChart(container, {
      ...initialChartSize(container),
      layout: {
        background: { type: ColorType.Solid, color: "#0d0f12" },
        textColor: "rgba(246, 248, 251, 0.68)",
        fontFamily: "JetBrains Mono, Consolas, monospace",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.055)" },
        horzLines: { color: "rgba(255,255,255,0.055)" },
      },
      crosshair: { mode: 0 },
      rightPriceScale: {
        borderColor: "rgba(255,255,255,0.08)",
        scaleMargins: { top: 0.12, bottom: 0.12 },
      },
      timeScale: {
        borderColor: "rgba(255,255,255,0.08)",
        timeVisible: true,
        secondsVisible: false,
      },
    });

    equitySeriesRef.current = chart.addSeries(AreaSeries, {
      lineColor: "#dfc07a",
      topColor: "rgba(223, 192, 122, 0.34)",
      bottomColor: "rgba(223, 192, 122, 0.025)",
      lineWidth: 2,
      title: "Strategy",
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    benchmarkSeriesRef.current = chart.addSeries(LineSeries, {
      color: "#78a6ff",
      lineWidth: 2,
      lineStyle: 2,
      title: "Buy & Hold",
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    chartRef.current = chart;
    const disconnectResize = observeChartSize(container, chart);

    return () => {
      disconnectResize();
      chartRef.current = null;
      equitySeriesRef.current = null;
      benchmarkSeriesRef.current = null;
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!chartRef.current || !equitySeriesRef.current || !benchmarkSeriesRef.current) return;
    equitySeriesRef.current.setData(normalized.map((point) => ({ time: point.time, value: point.equity })));
    benchmarkSeriesRef.current.setData(
      normalized
        .filter((point) => Number.isFinite(point.benchmark))
        .map((point) => ({ time: point.time, value: point.benchmark }))
    );
    chartRef.current.timeScale().fitContent();
  }, [normalized]);

  return (
    <div className="backtest-chart-wrap">
      <div className="backtest-chart-legend">
        <span><i className="strategy" /> Strategy equity</span>
        {hasBenchmark && <span><i className="benchmark" /> Buy &amp; hold</span>}
      </div>
      <div className="backtest-chart" ref={containerRef} role="img" aria-label={chartLabel} />
      {!normalized.length && <div className="chart-state">Sin puntos de equity para este run</div>}
    </div>
  );
}
