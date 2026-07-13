from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

Environment = Literal["backtest", "paper", "live"]
OrderAction = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class OrderIntent:
    id: str
    environment: Environment
    adapter: str
    symbol: str
    action: OrderAction
    order_type: OrderType
    quantity: float
    limit_price: float | None
    bot_id: int | None
    bot_version_id: int | None
    strategy_hash: str | None
    signal_evaluation_id: int | None
    proposal_id: int | None
    created_at: str

    @classmethod
    def paper_market(cls, payload: dict) -> "OrderIntent":
        symbol = str(payload["symbol"]).strip().upper()
        action = str(payload["side"]).strip().lower()
        quantity = float(payload["quantity"])
        if action not in {"buy", "sell"}:
            raise ValueError(f"Unsupported order action: {action}")
        if quantity <= 0:
            raise ValueError("Order quantity must be greater than zero")
        return cls(
            id=f"paper-proposal-{int(payload['proposal_id'])}" if payload.get("proposal_id") else str(uuid4()),
            environment="paper",
            adapter="paper_market_snapshot",
            symbol=symbol,
            action=action,
            order_type="market",
            quantity=quantity,
            limit_price=None,
            bot_id=payload.get("bot_id"),
            bot_version_id=payload.get("bot_version_id"),
            strategy_hash=payload.get("strategy_hash"),
            signal_evaluation_id=payload.get("signal_evaluation_id"),
            proposal_id=payload.get("proposal_id"),
            created_at=utc_now_iso(),
        )

    def to_dict(self) -> dict:
        return asdict(self)
