from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from time import monotonic, time

import aiohttp

from backend.app.market.binance import fetch_order_book
from backend.app.market.local_order_book import DepthSequenceGap, LocalOrderBook
from backend.app.storage.microstructure import (
    latest_collector_run,
    prune_microstructure,
    reconcile_interrupted_collectors,
    save_aggregate_trades,
    save_order_book_deltas,
    save_order_book_snapshot,
    start_collector_run,
    update_collector_run,
)

STREAM_BASE_URLS = (
    "wss://stream.binance.com:9443/stream",
    "wss://data-stream.binance.vision/stream",
)


def normalize_agg_trade_event(data: dict) -> dict:
    price = float(data["p"])
    quantity = float(data["q"])
    buyer_is_maker = bool(data["m"])
    return {
        "symbol": str(data["s"]).upper(),
        "aggregate_trade_id": int(data["a"]),
        "first_trade_id": int(data["f"]),
        "last_trade_id": int(data["l"]),
        "event_time": int(data["T"]),
        "price": price,
        "quantity": quantity,
        "quote_quantity": price * quantity,
        "buyer_is_maker": buyer_is_maker,
        "aggressor_side": "sell" if buyer_is_maker else "buy",
        "best_price_match": bool(data.get("M", True)),
        "source": "binance_agg_trade_stream",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def normalize_depth_event(data: dict) -> dict:
    return {
        "symbol": str(data["s"]).upper(),
        "event_time": int(data["E"]),
        "first_update_id": int(data["U"]),
        "final_update_id": int(data["u"]),
        "bid_changes": data.get("b") or [],
        "ask_changes": data.get("a") or [],
        "source": "binance_depth_stream",
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


class MicrostructureCollector:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._stop_event: asyncio.Event | None = None
        self._task: asyncio.Task | None = None
        self._run_id: int | None = None
        self._config: dict = {}
        self._state = self._empty_state()

    @staticmethod
    def _empty_state() -> dict:
        return {
            "status": "stopped",
            "symbols": [],
            "messages_received": 0,
            "trades_saved": 0,
            "deltas_saved": 0,
            "snapshots_saved": 0,
            "reconnect_count": 0,
            "sequence_gap_count": 0,
            "last_event_at": None,
            "last_error": None,
            "active_endpoint": None,
        }

    async def start(self, config: dict) -> dict:
        symbols = sorted({str(item).upper().strip() for item in config.get("symbols") or []})
        if not symbols:
            raise ValueError("At least one symbol is required.")
        if len(symbols) > 3:
            raise ValueError("SQLite collector v1 supports at most three simultaneous symbols.")
        normalized = {
            "symbols": symbols,
            "snapshot_interval_seconds": max(5, min(int(config.get("snapshot_interval_seconds", 10)), 60)),
            "trade_retention_days": max(1, min(int(config.get("trade_retention_days", 7)), 30)),
            "delta_retention_hours": max(1, min(int(config.get("delta_retention_hours", 24)), 168)),
            "book_levels": max(20, min(int(config.get("book_levels", 100)), 500)),
        }
        async with self._lock:
            if self._task and not self._task.done():
                raise ValueError("Microstructure collector is already running.")
            self._stop_event = asyncio.Event()
            self._config = normalized
            self._run_id = await asyncio.to_thread(start_collector_run, symbols, normalized)
            self._state = {**self._empty_state(), "status": "starting", "symbols": symbols, "run_id": self._run_id}
            self._task = asyncio.create_task(self._supervise(), name="abraxas-microstructure-collector")
        return self.status()

    async def stop(self, reason: str = "operator_request") -> dict:
        async with self._lock:
            task = self._task
            if not task or task.done():
                return self.status()
            self._state["status"] = "stopping"
            self._state["stop_reason"] = reason
            if self._stop_event:
                self._stop_event.set()
        try:
            await asyncio.wait_for(task, timeout=15)
        except asyncio.TimeoutError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return self.status()

    def status(self) -> dict:
        return {
            "contract": "microstructure_collector_v1",
            **self._state,
            "config": self._config,
            "order_execution_enabled": False,
            "latest_persisted_run": latest_collector_run(),
        }

    async def _supervise(self) -> None:
        self._state["status"] = "running"
        if self._run_id:
            await asyncio.to_thread(update_collector_run, self._run_id, self._state, "running")
        consecutive_failures = 0
        endpoint_index = 0
        try:
            while self._stop_event and not self._stop_event.is_set():
                endpoint = STREAM_BASE_URLS[endpoint_index % len(STREAM_BASE_URLS)]
                self._state["active_endpoint"] = endpoint
                try:
                    await self._stream_once(endpoint)
                    consecutive_failures = 0
                except asyncio.CancelledError:
                    raise
                except DepthSequenceGap as exc:
                    self._state["sequence_gap_count"] += 1
                    self._state["last_error"] = str(exc)
                    consecutive_failures += 1
                except Exception as exc:
                    self._state["last_error"] = f"{type(exc).__name__}: {exc}"
                    consecutive_failures += 1
                endpoint_index += 1
                if self._stop_event.is_set():
                    break
                self._state["reconnect_count"] += 1
                if self._run_id:
                    await asyncio.to_thread(update_collector_run, self._run_id, self._state, "running")
                delay = min(2 ** min(consecutive_failures, 5), 30)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
        finally:
            self._state["status"] = "stopped"
            if self._run_id:
                await asyncio.to_thread(update_collector_run, self._run_id, self._state, "stopped", True)

    async def _stream_once(self, stream_base_url: str) -> None:
        symbols = self._config["symbols"]
        streams = []
        for symbol in symbols:
            streams.extend((f"{symbol.lower()}@aggTrade", f"{symbol.lower()}@depth@100ms"))
        url = f"{stream_base_url}?streams={'/'.join(streams)}"
        trade_buffer: list[dict] = []
        delta_buffer: list[dict] = []
        pending_depth: dict[str, list[dict]] = {symbol: [] for symbol in symbols}
        books: dict[str, LocalOrderBook] = {}
        last_flush = monotonic()
        last_snapshot = monotonic()
        last_prune = monotonic()

        async def flush() -> None:
            nonlocal trade_buffer, delta_buffer, last_flush
            trades, deltas = trade_buffer, delta_buffer
            trade_buffer, delta_buffer = [], []
            if trades:
                self._state["trades_saved"] += await asyncio.to_thread(save_aggregate_trades, trades)
            if deltas:
                self._state["deltas_saved"] += await asyncio.to_thread(save_order_book_deltas, deltas)
            last_flush = monotonic()
            if self._run_id:
                await asyncio.to_thread(update_collector_run, self._run_id, self._state, "running")

        timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=45)
        try:
            # aiohttp prefers aiodns when it is installed. On some Windows
            # networks that resolver cannot reach the configured DNS servers
            # even though the operating-system resolver works. The threaded
            # resolver follows the same path as the REST collectors.
            connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.ws_connect(url, heartbeat=20, autoping=True) as ws:
                    self._state["last_error"] = None
                    snapshot_tasks = {
                        symbol: asyncio.create_task(asyncio.to_thread(fetch_order_book, symbol, 1000))
                        for symbol in symbols
                    }
                    while not all(task.done() for task in snapshot_tasks.values()):
                        try:
                            message = await ws.receive(timeout=0.25)
                        except asyncio.TimeoutError:
                            continue
                        self._route_message(message, trade_buffer, pending_depth)
                    snapshots = {symbol: await task for symbol, task in snapshot_tasks.items()}
                    for symbol, snapshot in snapshots.items():
                        book = LocalOrderBook.from_snapshot(snapshot)
                        for event in pending_depth[symbol]:
                            if book.apply(event):
                                delta_buffer.append(event)
                        books[symbol] = book
                        await asyncio.to_thread(save_order_book_snapshot, book.snapshot_payload(self._config["book_levels"]))
                        self._state["snapshots_saved"] += 1

                    while self._stop_event and not self._stop_event.is_set():
                        try:
                            message = await ws.receive(timeout=1)
                        except asyncio.TimeoutError:
                            message = None
                        if message is not None:
                            depth_event = self._route_message(message, trade_buffer, None)
                            if depth_event is not None:
                                book = books[depth_event["symbol"]]
                                if book.apply(depth_event):
                                    delta_buffer.append(depth_event)
                        now = monotonic()
                        if trade_buffer or delta_buffer:
                            if now - last_flush >= 1 or len(trade_buffer) + len(delta_buffer) >= 500:
                                await flush()
                        if now - last_snapshot >= self._config["snapshot_interval_seconds"]:
                            for book in books.values():
                                await asyncio.to_thread(save_order_book_snapshot, book.snapshot_payload(self._config["book_levels"]))
                                self._state["snapshots_saved"] += 1
                            last_snapshot = now
                        if now - last_prune >= 300:
                            now_ms = int(time() * 1000)
                            for symbol in symbols:
                                await asyncio.to_thread(
                                    prune_microstructure,
                                    symbol,
                                    now_ms - self._config["trade_retention_days"] * 86_400_000,
                                    now_ms - self._config["delta_retention_hours"] * 3_600_000,
                                )
                            last_prune = now
        finally:
            if trade_buffer or delta_buffer:
                await flush()

    def _route_message(
        self,
        message: aiohttp.WSMessage,
        trade_buffer: list[dict],
        pending_depth: dict[str, list[dict]] | None,
    ) -> dict | None:
        if message.type == aiohttp.WSMsgType.ERROR:
            raise RuntimeError(f"WebSocket error: {message.data}")
        if message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING}:
            raise RuntimeError("Binance WebSocket closed the stream.")
        if message.type != aiohttp.WSMsgType.TEXT:
            return None
        payload = message.json()
        data = payload.get("data") or payload
        event_type = data.get("e")
        self._state["messages_received"] += 1
        self._state["last_event_at"] = datetime.now(timezone.utc).isoformat()
        if event_type == "aggTrade":
            trade_buffer.append(normalize_agg_trade_event(data))
            return None
        if event_type == "depthUpdate":
            event = normalize_depth_event(data)
            if pending_depth is not None:
                pending_depth[event["symbol"]].append(event)
                return None
            return event
        return None


collector = MicrostructureCollector()


def reconcile_collector_state() -> int:
    return reconcile_interrupted_collectors()
