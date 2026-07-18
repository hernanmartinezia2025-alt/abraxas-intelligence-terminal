export function initialChartSize(container, fallbackHeight = 320) {
  return {
    width: Math.max(1, Math.floor(container.clientWidth)),
    height: Math.max(1, Math.floor(container.clientHeight || fallbackHeight)),
  };
}

export function observeChartSize(container, chart) {
  let frame = 0;
  let disposed = false;
  const observer = new ResizeObserver(([entry]) => {
    if (disposed || !entry) return;
    const { width, height } = entry.contentRect;
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      if (!disposed) chart.applyOptions({ width: Math.max(1, Math.floor(width)), height: Math.max(1, Math.floor(height)) });
    });
  });
  observer.observe(container);
  return () => {
    disposed = true;
    observer.disconnect();
    cancelAnimationFrame(frame);
  };
}
