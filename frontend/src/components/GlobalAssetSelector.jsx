import React from "react";

export default function GlobalAssetSelector({ assets = [], selectedSymbol = "BTCUSDT", onChange }) {
  return (
    <label className="global-asset-selector">
      <span>Asset</span>
      <select value={selectedSymbol} onChange={(event) => onChange?.(event.target.value)}>
        {assets.map((asset) => (
          <option key={asset.symbol} value={asset.symbol}>
            {asset.symbol}
          </option>
        ))}
      </select>
    </label>
  );
}
