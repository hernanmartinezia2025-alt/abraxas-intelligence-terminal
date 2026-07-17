from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


class DepthSequenceGap(RuntimeError):
    pass


@dataclass
class LocalOrderBook:
    symbol: str
    last_update_id: int
    bids: dict[float, float]
    asks: dict[float, float]

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "LocalOrderBook":
        return cls(
            symbol=str(snapshot["symbol"]).upper(),
            last_update_id=int(snapshot["last_update_id"]),
            bids={float(item["price"]): float(item["quantity"]) for item in snapshot.get("bids", [])},
            asks={float(item["price"]): float(item["quantity"]) for item in snapshot.get("asks", [])},
        )

    def apply(self, event: dict) -> bool:
        first_id = int(event["first_update_id"])
        final_id = int(event["final_update_id"])
        expected = self.last_update_id + 1
        if final_id < expected:
            return False
        if first_id > expected:
            raise DepthSequenceGap(
                f"{self.symbol} expected update {expected}, received {first_id}-{final_id}."
            )
        if not (first_id <= expected <= final_id):
            return False
        for side, changes in ((self.bids, event["bid_changes"]), (self.asks, event["ask_changes"])):
            for price_raw, quantity_raw in changes:
                price = float(price_raw)
                quantity = float(quantity_raw)
                if quantity == 0:
                    side.pop(price, None)
                else:
                    side[price] = quantity
        self.last_update_id = final_id
        return True

    def snapshot_payload(self, limit: int = 100, fetched_at: str | None = None) -> dict:
        bid_rows = sorted(self.bids.items(), reverse=True)[:limit]
        ask_rows = sorted(self.asks.items())[:limit]

        def levels(rows: list[tuple[float, float]]) -> list[dict]:
            return [
                {"price": price, "quantity": quantity, "notional": price * quantity}
                for price, quantity in rows
            ]

        bids = levels(bid_rows)
        asks = levels(ask_rows)
        best_bid = bids[0]["price"] if bids else None
        best_ask = asks[0]["price"] if asks else None
        spread = best_ask - best_bid if best_bid is not None and best_ask is not None else None
        mid = (best_ask + best_bid) / 2 if spread is not None else None
        return {
            "symbol": self.symbol,
            "source": "binance_depth_stream_local_book",
            "last_update_id": self.last_update_id,
            "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "spread_percent": spread / mid * 100 if spread is not None and mid else None,
            "mid_price": mid,
            "bids": bids,
            "asks": asks,
        }
