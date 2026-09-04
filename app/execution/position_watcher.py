"""Position watcher: poll Binance public ticker to close paper positions via TP/SL.

The PaperTradingAdapter places STOP_MARKET / TAKE_PROFIT_MARKET orders that
fire when update_market_price() is called. This watcher polls each open
position's Binance ticker every N seconds and calls update_market_price() on
the shared paper adapter — which triggers the conditional order engine inside
the adapter.

Lifecycle:
  signal → entry MARKET order → position opened → TP+SL orders placed
  → PositionWatcher polls ticker → price crosses TP/SL threshold
  → update_market_price() fires the conditional order
  → position closed, P&L recorded, sibling orders cancelled

Reuses: existing PaperTradingAdapter.update_market_price()
         existing PaperTradingAdapter.place_order() STOP_MARKET path
No new TP/SL logic invented.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.exchange.paper import PaperTradingAdapter

logger = logging.getLogger(__name__)


class PositionWatcher:
    """Poll Binance public ticker for open paper positions and update prices.

    Args:
        paper_adapter:  The shared PaperTradingAdapter (same instance used by
                        OrderManager so positions/orders are visible).
        poll_interval:  Seconds between ticker polls. Default 5s.
        on_position_closed:  Optional callback(position, pnl, exit_price) when a position closes.
        on_position_updated: Optional callback(position) after an open position is marked.
    """

    def __init__(
        self,
        paper_adapter: "PaperTradingAdapter",
        poll_interval: float = 5.0,
        on_position_closed=None,
        on_position_updated=None,
    ) -> None:
        self._adapter = paper_adapter
        self._interval = max(0.5, float(poll_interval))
        self._on_closed = on_position_closed
        self._on_updated = on_position_updated
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ── lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="position-watcher", daemon=True)
        self._thread.start()
        logger.info("position_watcher started interval=%.1fs", self._interval)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("position_watcher stopped")

    # ── internal ─────────────────────────────────────────────────────────

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:
                logger.debug("position_watcher tick error: %s", exc)
            # Sleep in chunks so stop responds quickly
            waited = 0.0
            while waited < self._interval and not self._stop.is_set():
                time.sleep(min(0.5, self._interval - waited))
                waited += 0.5

    def _tick(self) -> None:
        positions = self._adapter._positions  # dict[str, Position]
        if not positions:
            return

        for symbol, position in list(positions.items()):
            if position.quantity <= 0:
                continue
            try:
                price = self._fetch_ticker(symbol)
                if price is None:
                    continue
                pos_before = self._adapter.get_position(symbol)
                self._adapter.update_market_price(symbol, price)
                pos_after = self._adapter.get_position(symbol)

                # If position disappeared or quantity shrank, it was closed by TP/SL
                if pos_after is None or pos_after.quantity < pos_before.quantity:
                    pnl = self._compute_pnl(symbol, position, price)
                    if self._on_closed is not None:
                        try:
                            self._on_closed(position, pnl, price)
                        except Exception as exc:
                            logger.debug("on_position_closed callback error: %s", exc)
                    logger.info(
                        "position_closed symbol=%s side=%s entry=%.6f exit=%.6f pnl=%s",
                        symbol,
                        position.side.value,
                        position.entry_price,
                        price,
                        pnl,
                    )
                elif self._on_updated is not None and pos_after is not None:
                    self._on_updated(pos_after)
            except Exception as exc:
                logger.debug("position_watcher price update for %s failed: %s", symbol, exc)

    def _fetch_ticker(self, symbol: str) -> Decimal | None:
        """Fetch the live Binance public ticker price for symbol."""
        try:
            import urllib.request
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
            return Decimal(data["price"])
        except Exception:
            return None

    def _compute_pnl(
        self, symbol: str, position, exit_price: Decimal
    ) -> Decimal:
        """Compute realized P&L for a closed position."""
        qty = Decimal(str(position.quantity))
        entry = Decimal(str(position.entry_price))
        lev = Decimal(str(position.leverage))
        diff = exit_price - entry
        if position.side.value == "SELL":
            diff = -diff
        return diff * qty * lev
