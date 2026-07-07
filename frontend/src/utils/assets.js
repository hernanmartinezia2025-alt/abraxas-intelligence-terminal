export const ASSET_ORDER = [
  "BTCUSDT",
  "ETHUSDT",
  "SOLUSDT",
  "BNBUSDT",
  "XRPUSDT",
  "ADAUSDT",
  "DOGEUSDT",
  "AVAXUSDT",
  "LINKUSDT",
  "TONUSDT",
  "DOTUSDT",
  "MATICUSDT",
];

export function sortAssets(rows) {
  return [...rows].sort((a, b) => {
    const left = ASSET_ORDER.indexOf(a.symbol);
    const right = ASSET_ORDER.indexOf(b.symbol);
    if (left !== -1 || right !== -1) return (left === -1 ? 999 : left) - (right === -1 ? 999 : right);
    return a.symbol.localeCompare(b.symbol);
  });
}

export function latestRows(rows) {
  const grouped = rows.reduce((acc, row) => {
    if (!acc[row.symbol]) acc[row.symbol] = row;
    return acc;
  }, {});
  return sortAssets(Object.values(grouped));
}
