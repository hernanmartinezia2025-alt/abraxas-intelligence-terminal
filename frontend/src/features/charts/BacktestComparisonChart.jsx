import React, { useEffect, useMemo, useRef } from "react";
import { ColorType, createChart, LineSeries } from "lightweight-charts";
import { initialChartSize, observeChartSize } from "./chartSize.js";

function normalizedReturnSeries(run) {
  const initialEquity = Number(run?.initial_equity);
  if (!Number.isFinite(initialEquity) || initialEquity <= 0) return [];

  const byTime = new Map();
  for (const point of run?.equity_curve || []) {
    const timestamp = Math.floor(Number(point.timestamp) / 1000);
    const equity = Number(point.equity);
    if (!Number.isFinite(timestamp) || !Number.isFinite(equity)) continue;
    byTime.set(timestamp, {
      time: timestamp,
      value: ((equity / initialEquity) - 1) * 100,
    });
  }
  return [...byTime.values()].sort((left, right) => left.time - right.time);
}

export default function BacktestComparisonChart({ runA, runB }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesARef = useRef(null);
  const seriesBRef = useRef(null);
  const seriesA = useMemo(() => normalizedReturnSeries(runA), [runA]);
  const seriesB = useMemo(() => normalizedReturnSeries(runB), [runB]);
  const chartLabel = `Comparacion de retorno normalizado: run ${runA?.id || "A"} con ${seriesA.length} puntos y run ${runB?.id || "B"} con ${seriesB.length} puntos.`;

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
      localization: {
        priceFormatter: (value) => `${Number(value).toFixed(2)}%`,
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

    seriesARef.current = chart.addSeries(LineSeries, {
      color: "#dfc07a",
      lineWidth: 2,
      title: "Run A",
      priceFormat: { type: "custom", minMove: 0.01, formatter: (value) => `${value.toFixed(2)}%` },
    });
    seriesBRef.current = chart.addSeries(LineSeries, {
      color: "#78a6ff",
      lineWidth: 2,
      lineStyle: 2,
      title: "Run B",
      priceFormat: { type: "custom", minMove: 0.01, formatter: (value) => `${value.toFixed(2)}%` },
    });
    chartRef.current = chart;
    const disconnectResize = observeChartSize(container, chart);

    return () => {
      disconnectResize();
      chartRef.current = null;
      seriesARef.current = null;
      seriesBRef.current = null;
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!chartRef.current || !seriesARef.current || !seriesBRef.current) return;
    seriesARef.current.setData(seriesA);
    seriesBRef.current.setData(seriesB);
    chartRef.current.timeScale().fitContent();
  }, [seriesA, seriesB]);

  return (
    <div className="backtest-chart-wrap comparison-chart-wrap">
      <div className="backtest-chart-legend">
        <span><i className="strategy" /> Run #{runA?.id} · A</span>
        <span><i className="benchmark" /> Run #{runB?.id} · B</span>
        <b>Retorno normalizado</b>
      </div>
      <div className="backtest-chart" ref={containerRef} role="img" aria-label={chartLabel} />
    </div>
  );
}
