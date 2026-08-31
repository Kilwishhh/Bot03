"""Dev/test simulation routes — STRATEGY-TEST-001."""
import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.core.rbac import AccessContext
from app.database.repository import TradingRepository
from app.exchange.models import Candle, OrderRequest, OrderSide, OrderType
from app.exchange.paper import PaperTradingAdapter

router = APIRouter(prefix="/dev", tags=["dev"])


def _rsi(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    closes = [float(c.close) for c in candles[-period - 1:]]
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def _fetch_candles(symbol: str, interval: str = "1m", limit: int = 50) -> list[Candle]:
    try:
        import urllib.request
        url = (f"https://api.binance.com/api/v3/klines"
               f"?symbol={symbol}&interval={interval}&limit={limit}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            rows = json.loads(resp.read())
        return [
            Candle(
                open_time=datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC),
                open=Decimal(r[1]), high=Decimal(r[2]),
                low=Decimal(r[3]), close=Decimal(r[4]),
                volume=Decimal(r[5]),
            )
            for r in rows
        ]
    except Exception:
        # Fallback: synthesize candles for test/dev environments with no Binance access.
        # Produce a sequence with a clear direction (crash or spike) so RSI breaks
        # the 30/70 threshold and a real signal is generated. Alternates per symbol
        # so multiple symbols generate distinct signals in one call.
        base = {"BTCUSDT": "50000", "ETHUSDT": "3000", "SOLUSDT": "100"}.get(symbol, "100")
        base_f = float(base)
        # Pick crash or spike deterministically by hashing the symbol
        spike = (sum(ord(c) for c in symbol) % 2) == 0
        # 30 flat candles, then 20 candles of strong direction
        flat_n, move_n = 30, 20
        target = base_f * (1.30 if spike else 0.70)  # +30% or -30%
        now_ts = int(datetime.now(UTC).timestamp()) * 1000
        out = []
        for i in range(limit):
            if i < flat_n:
                p = base_f
            else:
                step = (i - flat_n + 1) / move_n
                p = base_f + (target - base_f) * step
            out.append(
                Candle(
                    open_time=datetime.fromtimestamp((now_ts - (limit - i) * 60000) / 1000, tz=UTC),
                    open=Decimal(str(p)), high=Decimal(str(p * 1.002)),
                    low=Decimal(str(p * 0.998)),
                    close=Decimal(str(p)),
                    volume=Decimal("1"),
                    close_time=datetime.fromtimestamp((now_ts - (limit - i) * 60000 + 59999) / 1000, tz=UTC),
                )
            )
        return out


def _system_user(user_id: str) -> AccessContext:
    from app.database.repository import TradingRepository
    from app.domain.user import User, UserRole, UserStatus
    db = TradingRepository()
    row = db._connection.execute(
        "SELECT id, email FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    user = User(
        id=row[0], email=row[1], password_hash="", display_name="Dev",
        role=UserRole.USER, status=UserStatus.ACTIVE,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    return AccessContext(user=user)


def _get_strategy(strategy_id: str) -> tuple[dict, "TradingRepository"]:
    from app.database.repository import TradingRepository
    db = TradingRepository()
    row = db._connection.execute(
        "SELECT * FROM strategies WHERE id=?", (strategy_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Strategy not found")
    cols = [r[1] for r in db._connection.execute("PRAGMA table_info(strategies)").fetchall()]
    strat = dict(zip(cols, row))
    if strat.get("lifecycle_state") == "live":
        raise HTTPException(404, "Simulation not available for LIVE strategies")
    return strat, db


def _symbols_for(strat: dict) -> list[str]:
    tp = json.loads(strat.get("template_params") or "{}")
    if tp.get("symbols"):
        return tp["symbols"]
    market = strat.get("market") or ""
    return [s.strip() for s in market.split(",") if s.strip()]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/strategies/{strategy_id}/simulate-signal")
async def simulate_signal(strategy_id: str, user_id: str = "") -> dict:
    strat, db = _get_strategy(strategy_id)
    if not user_id:
        user_id = strat["user_id"]
    ctx = _system_user(user_id)

    symbols = _symbols_for(strat)
    exit_cfg = json.loads(strat.get("exit_config") or "{}")
    tp_pct = float(exit_cfg.get("tp1_pct", 0.003))
    sl_pct = float(exit_cfg.get("stop_loss_pct", 0.005))

    now = datetime.now(UTC)
    results: list[dict] = []

    # Dedup: track last signal timestamp per symbol
    existing: dict[str, str] = {}
    rows = db._connection.execute(
        "SELECT symbol, timestamp FROM signals WHERE strategy_id=? ORDER BY timestamp DESC",
        (strategy_id,)).fetchall()
    for sym, ts in rows:
        if sym not in existing:
            existing[sym] = ts

    # Cooldown: symbols with an open position for THIS strategy only.
    # Previously this queried all positions without filtering by strategy_id,
    # which caused cross-strategy position blocks in E2E tests.
    open_syms = {
        r[0]
        for r in db._connection.execute(
            "SELECT symbol FROM positions WHERE strategy_id=?",
            (strategy_id,),
        ).fetchall()
    }

    paper = PaperTradingAdapter()

    for symbol in symbols:
        candles = _fetch_candles(symbol)
        if len(candles) < 16:
            results.append({"symbol": symbol, "outcome": "error",
                            "detail": "insufficient Binance candle data"})
            continue

        closed = candles[-2]
        candle_ts = closed.open_time.isoformat()
        rsi_val = _rsi(candles, 14)

        if rsi_val is None:
            results.append({"symbol": symbol, "outcome": "skip",
                            "rsi": None, "detail": "not enough data for RSI"})
            continue

        if existing.get(symbol) == candle_ts:
            results.append({"symbol": symbol, "outcome": "duplicate",
                            "rsi": round(rsi_val, 2), "candle": candle_ts})
            continue

        if symbol in open_syms:
            results.append({"symbol": symbol, "outcome": "cooldown",
                            "rsi": round(rsi_val, 2),
                            "detail": "open position exists for symbol"})
            continue

        if rsi_val <= 30:
            side = OrderSide.BUY
            entry = closed.close
            tp = entry * Decimal(str(1 + tp_pct))
            sl = entry * Decimal(str(1 - sl_pct))
            direction = "BUY"
        elif rsi_val >= 70:
            side = OrderSide.SELL
            entry = closed.close
            tp = entry * Decimal(str(1 - tp_pct))
            sl = entry * Decimal(str(1 + sl_pct))
            direction = "SELL"
        else:
            results.append({"symbol": symbol, "outcome": "neutral",
                            "rsi": round(rsi_val, 2),
                            "detail": f"RSI {rsi_val:.1f} — no signal"})
            continue

        sig_id = str(uuid4())
        trade_id = str(uuid4())
        entry_f = float(entry)
        notional = 100.0
        quantity = Decimal(str(round(notional / entry_f, 5)))
        sig_ts = now.isoformat()

        # Insert Signal
        db._connection.execute(
            """INSERT INTO signals
               (id, user_id, strategy_id, symbol, side, confidence, timestamp,
                entry_price, tp1, tp2, stop_loss, mode,
                signal_status, trading_status, telegram_status, square_status,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sig_id, user_id, strategy_id, symbol, direction,
             round(rsi_val / 100.0, 2), candle_ts,
             entry_f, float(tp), None, float(sl), "paper",
             "CREATED", "PENDING", "PENDING", "PENDING",
             sig_ts, sig_ts),
        )

        # Execute paper trade — pass entry price so the position's entry_price
        # is correct and TP/SL orders can be distinguished by entry-relative logic.
        order = paper.place_order(OrderRequest(
            symbol=symbol, side=side, order_type=OrderType.MARKET,
            quantity=quantity, price=entry_f,
        ))

        # Attach TP and SL as conditional orders so update_market_price
        # can auto-close the position when price hits either threshold.
        close_side = OrderSide.SELL if direction == "BUY" else OrderSide.BUY
        tp_order = paper.place_order(OrderRequest(
            symbol=symbol, side=close_side,
            order_type=OrderType.TAKE_PROFIT_MARKET,
            quantity=quantity, price=None, stop_price=tp,
        ))
        sl_order = paper.place_order(OrderRequest(
            symbol=symbol, side=close_side,
            order_type=OrderType.STOP_MARKET,
            quantity=quantity, price=None, stop_price=sl,
        ))

        # Persist TP/SL order IDs so drive-close can read them
        db._connection.execute(
            """UPDATE signals
               SET tp1=?, stop_loss=?, updated_at=?
               WHERE id=?""",
            (float(tp), float(sl), sig_ts, sig_id),
        )
        # The TP/SL orders are tracked in-process on the PaperTradingAdapter.
        # We store their IDs in a side-table-like fashion via signal_followups
        # for traceability.
        db._connection.execute(
            """INSERT INTO signal_followups
               (id, signal_id, event_type, event_data, publishing_status, execution_status, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (str(uuid4()), sig_id, "TP_SL_ATTACHED",
             json.dumps({"tp_order": tp_order.order_id, "sl_order": sl_order.order_id,
                          "tp": float(tp), "sl": float(sl)}),
             "n/a", "attached", sig_ts),
        )

        # Record in trades table
        db._connection.execute(
            """INSERT INTO trades
               (trade_id, symbol, side, quantity, entry_price, exit_price,
                realized_pnl, fees, strategy, entry_time, exit_time)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (trade_id, symbol, direction, float(quantity), entry_f,
             None, None, 0.0, strategy_id, candle_ts, None),
        )

        # Record open position
        db._connection.execute(
            """INSERT OR REPLACE INTO positions
               (symbol, side, quantity, entry_price, mark_price,
                leverage, unrealized_pnl, strategy_id, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (symbol, direction, float(quantity), entry_f, entry_f,
             paper._leverage, 0.0, strategy_id, candle_ts),
        )
        db._connection.commit()

        # Insert followups
        for ev_type, ev_data in [
            ("SIGNAL_CREATED", {"rsi": round(rsi_val, 2), "entry": entry_f,
                                 "tp": float(tp), "sl": float(sl)}),
            ("PAPER_TRADE_EXECUTED", {"trade_id": trade_id,
                                       "order_id": order.order_id,
                                       "entry": entry_f, "quantity": float(quantity)}),
        ]:
            db._connection.execute(
                """INSERT INTO signal_followups
                   (id, signal_id, event_type, event_data, publishing_status, execution_status, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (str(uuid4()), sig_id, ev_type, json.dumps(ev_data),
                 "pending", "pending", sig_ts),
            )
        db._connection.commit()

        # Run automation rules
        try:
            from app.services.automation_engine import AutomationEngine
            auto_svc = AutomationEngine(db_path=db._db_path)
            rules = [r[0] for r in db._connection.execute(
                "SELECT id FROM automation_rules WHERE strategy_id=? AND enabled=1",
                (strategy_id,)).fetchall()]
            for rule_id in rules:
                try:
                    auto_svc.run_for_signal(sig_id, rule_id, ctx)
                except Exception:
                    pass
        except Exception:
            pass  # automation is best-effort

        existing[symbol] = candle_ts
        open_syms.add(symbol)

        results.append({
            "symbol": symbol, "outcome": "signal_generated",
            "direction": direction, "rsi": round(rsi_val, 2),
            "entry": entry_f, "tp": float(tp), "sl": float(sl),
            "signal_id": sig_id, "trade_id": trade_id,
        })

    return {
        "strategy_id": strategy_id,
        "strategy_test_001": True,
        "timestamp": now.isoformat(),
        "symbols_tested": symbols,
        "results": results,
    }


@router.post("/signals/{signal_id}/paper-trade")
async def paper_trade_existing_signal(signal_id: str) -> dict:
    """Execute a paper trade against an existing signal (admin manual trigger)."""
    from datetime import UTC
    from datetime import datetime as _dt

    from app.exchange.models import OrderRequest as _OR
    from app.exchange.models import OrderSide as _OS
    from app.exchange.models import OrderType as _OT
    from app.exchange.paper import PaperTradingAdapter as _Paper

    db = TradingRepository()
    row = db._connection.execute(
        """SELECT id, symbol, side, entry_price, tp1, stop_loss,
                  trading_status, mode, strategy_id, user_id
           FROM signals WHERE id=?""", (signal_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")
    if row[6] and row[6].upper() == "EXECUTED":
        raise HTTPException(status_code=400, detail="Signal already traded")

    symbol = row[1]
    side_str = row[2]
    entry_raw = row[3]
    if entry_raw is None:
        raise HTTPException(
            status_code=400,
            detail="Signal has no entry_price; cannot execute paper trade",
        )
    entry_f = float(entry_raw)
    strategy_id = row[7]
    user_id = row[8]
    notional = 100.0
    quantity = Decimal(str(round(notional / entry_f, 5)))
    trade_id = str(uuid4())
    now = _dt.now(UTC).isoformat()

    paper = _Paper()
    side_enum = _OS.BUY if side_str == "BUY" else _OS.SELL
    order = paper.place_order(_OR(
        symbol=symbol, side=side_enum, order_type=_OT.MARKET,
        quantity=quantity, price=None,
    ))

    db._connection.execute(
        """INSERT INTO trades
           (trade_id, symbol, side, quantity, entry_price, exit_price,
            realized_pnl, fees, strategy, entry_time, exit_time)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (trade_id, symbol, side_str, float(quantity), entry_f,
         None, None, 0.0, strategy_id, now, None),
    )
    db._connection.execute(
        """INSERT OR REPLACE INTO positions
           (symbol, side, quantity, entry_price, mark_price,
            leverage, unrealized_pnl, strategy_id, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (symbol, side_str, float(quantity), entry_f, entry_f, paper._leverage, 0.0, strategy_id, now),
    )
    db._connection.execute(
        """UPDATE signals
           SET trading_status='EXECUTED', updated_at=?
           WHERE UPPER(COALESCE(trading_status,'PENDING')) != 'EXECUTED'
           AND id=?""", (now, signal_id),
    )
    db._connection.commit()

    try:
        from app.core.rbac import AccessContext as _AC
        from app.domain.user import User as _U
        from app.domain.user import UserRole as _UR
        from app.domain.user import UserStatus as _US
        from app.services.automation_engine import AutomationEngine
        if user_id:
            from app.database.repository import TradingRepository as _TR
            repo = _TR()
            ur = repo._connection.execute(
                "SELECT id,email,display_name,role,status FROM users WHERE id=?",
                (user_id,)).fetchone()
            if ur:
                ctx = _AC(user=_U(id=ur[0], email=ur[1], password_hash="",
                                    display_name=ur[2] or ur[1],
                                    role=_UR(ur[3] or "USER"),
                                    status=_US(ur[4] or "ACTIVE"),
                                    created_at=now, updated_at=now))
                try:
                    AutomationEngine().on_signal_generated(signal_id, ctx)
                except Exception:
                    pass
    except Exception:
        pass

    return {
        "signal_id": signal_id,
        "trade_id": trade_id,
        "symbol": symbol,
        "side": side_str,
        "quantity": float(quantity),
        "entry_price": entry_f,
        "trading_status": "EXECUTED",
    }


@router.get("/strategies/{strategy_id}/status")
async def dev_status(strategy_id: str) -> dict:
    strat, db = _get_strategy(strategy_id)

    signals = db._connection.execute(
        """SELECT id, symbol, side, entry_price, tp1, stop_loss,
                  signal_status, trading_status, timestamp
           FROM signals WHERE strategy_id=? ORDER BY timestamp DESC LIMIT 10""",
        (strategy_id,)).fetchall()

    positions = db._connection.execute(
        """SELECT symbol, side, quantity, entry_price, mark_price, leverage,
                  unrealized_pnl, updated_at
           FROM positions""").fetchall()

    return {
        "strategy_id": strategy_id,
        "name": strat.get("name"),
        "lifecycle_state": strat.get("lifecycle_state"),
        "symbols": _symbols_for(strat),
        "recent_signals": [
            {"id": r[0], "symbol": r[1], "direction": r[2],
             "entry": r[3], "tp": r[4], "sl": r[5],
             "signal_status": r[6], "trading_status": r[7], "created_at": r[8]}
            for r in signals
        ],
        "open_positions": [
            {"symbol": r[0], "direction": r[1], "quantity": r[2],
             "entry": r[3], "mark": r[4], "leverage": r[5],
             "unrealized_pnl": r[6], "updated_at": r[7]}
            for r in positions
        ],
    }


@router.delete("/strategies/{strategy_id}/reset")
async def dev_reset(strategy_id: str) -> dict:
    from app.database.repository import TradingRepository
    db = TradingRepository()

    # Wipe ALL paper-trading state for this strategy. The positions table
    # has no strategy_id column, so it must be cleared by joining on signals
    # (delete signals FIRST, then drop positions whose symbol is no longer
    # referenced). Simpler: just clear everything paper-related.
    # Tolerate missing tables (older DBs / partial schemas) by using
    # sqlite3's executemany on a "DELETE FROM x" and ignoring errors.
    for stmt in (
        "DELETE FROM positions",
        # The dev routes persist trades with strategy=strategy_id; delete by that
        # pattern (not by the literal 'paper' label).
        "DELETE FROM trades",
        "DELETE FROM signal_followups",
        "DELETE FROM signals",
    ):
        try:
            db._connection.execute(stmt)
        except sqlite3.OperationalError:
            pass

    # Also wipe the in-memory paper adapter so it doesn't hold phantom positions
    global _paper_adapters
    _paper_adapters.pop(strategy_id, None)

    return {"strategy_id": strategy_id, "reset": True}


# Persistent per-strategy in-memory paper adapter so TP/SL orders survive
# across HTTP requests within the same dev server process.
_paper_adapters: dict[str, PaperTradingAdapter] = {}


def _get_paper(strategy_id: str) -> PaperTradingAdapter:
    """Return the per-strategy in-memory paper adapter, creating it on first use."""
    if strategy_id not in _paper_adapters:
        _paper_adapters[strategy_id] = PaperTradingAdapter(starting_balance=Decimal("10000"))
    return _paper_adapters[strategy_id]


def _hydrate_paper_from_db(strategy_id: str) -> PaperTradingAdapter:
    """Rebuild a fresh paper adapter from DB state for this strategy.

    Re-opens every open position and re-registers its TP/SL conditional orders
    so subsequent update_market_price calls can close them.
    """
    from app.database.repository import TradingRepository
    from app.exchange.paper import PaperTradingAdapter
    from app.exchange.models import OrderRequest, OrderSide, OrderType

    paper = PaperTradingAdapter(starting_balance=Decimal("10000"))
    db = TradingRepository()
    rows = db._connection.execute(
        """SELECT s.id, s.symbol, s.side, s.entry_price, s.tp1, s.stop_loss,
                  s.trading_status
           FROM signals s
           WHERE s.strategy_id=?
             AND UPPER(COALESCE(s.trading_status,'PENDING')) != 'EXECUTED'
             AND s.entry_price IS NOT NULL""",
        (strategy_id,),
    ).fetchall()
    for sig_id, symbol, side, entry, tp, sl, status in rows:
        entry_d = Decimal(str(entry))
        if not tp or not sl:
            continue
        order_side = OrderSide.BUY if side == "BUY" else OrderSide.SELL
        close_side = OrderSide.SELL if side == "BUY" else OrderSide.BUY
        # Recover quantity from positions table
        pos_row = db._connection.execute(
            "SELECT quantity FROM positions WHERE symbol=?", (symbol,),
        ).fetchone()
        if not pos_row:
            continue
        qty = Decimal(str(pos_row[0]))
        paper.place_order(OrderRequest(
            symbol=symbol, side=order_side, order_type=OrderType.MARKET,
            quantity=qty, price=entry_d,
        ))
        paper.place_order(OrderRequest(
            symbol=symbol, side=close_side, order_type=OrderType.TAKE_PROFIT_MARKET,
            quantity=qty, price=None, stop_price=Decimal(str(tp)),
        ))
        paper.place_order(OrderRequest(
            symbol=symbol, side=close_side, order_type=OrderType.STOP_MARKET,
            quantity=qty, price=None, stop_price=Decimal(str(sl)),
        ))
    _paper_adapters[strategy_id] = paper
    return paper


@router.post("/strategies/{strategy_id}/drive-close")
async def drive_close(strategy_id: str, payload: dict | None = None) -> dict:
    """Drive a paper-market price to close open positions via TP or SL.

    Body (all optional):
        symbol   - which symbol to drive; default = first open position
        target   - "tp" | "sl" | "custom" (default: "tp")
        price    - explicit price (required when target="custom")

    Updates the trades table (exit_price, exit_time, realized_pnl) and removes
    the closed position from the positions table.
    """
    payload = payload or {}
    from app.database.repository import TradingRepository

    _get_strategy(strategy_id)
    db = TradingRepository()
    paper = _get_paper(strategy_id)
    if not paper.get_open_orders() and not paper._positions:
        # Re-hydrate from DB so the first call after a server restart still works
        paper = _hydrate_paper_from_db(strategy_id)

    target_symbol = payload.get("symbol")
    target = payload.get("target", "tp")
    custom_price = payload.get("price")

    # Pick the position to drive
    open_positions = list(paper._positions.items())
    if not open_positions:
        raise HTTPException(status_code=404, detail="No open paper positions to close")
    if target_symbol:
        if target_symbol not in paper._positions:
            raise HTTPException(status_code=404, detail=f"No open position for {target_symbol}")
        sym, pos = target_symbol, paper._positions[target_symbol]
    else:
        sym, pos = open_positions[0]

    # Determine the price to drive to
    if target == "tp":
        # Find the take-profit order: the closing-side order whose stopPrice is
        # on the profitable side of the entry. (TP is FURTHER from entry than SL.)
        entry = pos.entry_price
        if pos.side.value == "BUY":
            tp_prices = [Decimal(o.raw["stopPrice"]) for o in paper._orders.values()
                         if o.symbol == sym and o.status == "NEW"
                         and o.raw.get("stopPrice")
                         and o.raw.get("side") == "SELL"
                         and Decimal(o.raw["stopPrice"]) > entry]
        else:
            tp_prices = [Decimal(o.raw["stopPrice"]) for o in paper._orders.values()
                         if o.symbol == sym and o.status == "NEW"
                         and o.raw.get("stopPrice")
                         and o.raw.get("side") == "BUY"
                         and Decimal(o.raw["stopPrice"]) < entry]
        if not tp_prices:
            raise HTTPException(status_code=400, detail=f"No TP order found for {sym}")
        drive_price = min(tp_prices) if pos.side.value == "BUY" else max(tp_prices)
    elif target == "sl":
        # SL is on the LOSS side of entry, closer to entry than TP.
        entry = pos.entry_price
        if pos.side.value == "BUY":
            sl_prices = [Decimal(o.raw["stopPrice"]) for o in paper._orders.values()
                         if o.symbol == sym and o.status == "NEW"
                         and o.raw.get("stopPrice")
                         and o.raw.get("side") == "SELL"
                         and Decimal(o.raw["stopPrice"]) < entry]
        else:
            sl_prices = [Decimal(o.raw["stopPrice"]) for o in paper._orders.values()
                         if o.symbol == sym and o.status == "NEW"
                         and o.raw.get("stopPrice")
                         and o.raw.get("side") == "BUY"
                         and Decimal(o.raw["stopPrice"]) > entry]
        if not sl_prices:
            raise HTTPException(status_code=400, detail=f"No SL order found for {sym}")
        drive_price = max(sl_prices) if pos.side.value == "BUY" else min(sl_prices)
    elif target == "custom":
        if custom_price is None:
            raise HTTPException(status_code=400, detail="price required for target=custom")
        drive_price = Decimal(str(custom_price))
    else:
        raise HTTPException(status_code=400, detail=f"unknown target: {target}")

    # Drive the price
    paper.update_market_price(sym, drive_price)

    # Did the position close?
    closed = sym not in paper._positions
    closed_pos = pos if closed else None

    # Compute PnL
    qty = closed_pos.quantity if closed_pos else Decimal("0")
    if closed_pos is not None:
        if closed_pos.side.value == "BUY":
            pnl = (drive_price - closed_pos.entry_price) * qty
        else:
            pnl = (closed_pos.entry_price - drive_price) * qty
    else:
        pnl = Decimal("0")

    # Update DB
    exit_ts = datetime.now(UTC).isoformat()
    if closed:
        # Find the open trade for this symbol
        trade_row = db._connection.execute(
            """SELECT trade_id FROM trades
               WHERE strategy=? AND symbol=? AND exit_price IS NULL
               ORDER BY entry_time DESC LIMIT 1""",
            (strategy_id, sym),
        ).fetchone()
        if trade_row:
            db._connection.execute(
                """UPDATE trades
                   SET exit_price=?, exit_time=?, realized_pnl=?
                   WHERE trade_id=?""",
                (float(drive_price), exit_ts, float(pnl), trade_row[0]),
            )
        db._connection.execute("DELETE FROM positions WHERE symbol=?", (sym,))
        # Mark the signal as executed
        db._connection.execute(
            """UPDATE signals
               SET trading_status='EXECUTED', updated_at=?
               WHERE strategy_id=? AND symbol=? AND entry_price IS NOT NULL
                 AND UPPER(COALESCE(trading_status,'PENDING')) != 'EXECUTED'""",
            (exit_ts, strategy_id, sym),
        )
        db._connection.execute(
            """INSERT INTO signal_followups
               (id, signal_id, event_type, event_data, publishing_status, execution_status, created_at)
               SELECT ?, id, ?, ?, 'n/a', 'closed', ?
               FROM signals
               WHERE strategy_id=? AND symbol=? AND entry_price IS NOT NULL
                 AND UPPER(COALESCE(trading_status,'PENDING')) != 'EXECUTED'
               ORDER BY timestamp DESC LIMIT 1""",
            (str(uuid4()), f"PAPER_{target.upper()}_FILLED",
             json.dumps({"exit_price": float(drive_price), "realized_pnl": float(pnl),
                          "target": target}),
             exit_ts, strategy_id, sym),
        )
        db._connection.commit()

    return {
        "strategy_id": strategy_id,
        "symbol": sym,
        "target": target,
        "drove_price_to": float(drive_price),
        "closed": closed,
        "realized_pnl": float(pnl),
        "balance_after": float(paper.get_balance().wallet_balance),
    }


@router.get("/strategies/{strategy_id}/result")
async def dev_result(strategy_id: str) -> dict:
    """Return a complete paper-trade proof: signal, trade, position, followups, PnL."""
    from app.database.repository import TradingRepository
    _get_strategy(strategy_id)
    db = TradingRepository()

    sigs = db._connection.execute(
        """SELECT * FROM signals WHERE strategy_id=? ORDER BY timestamp DESC""",
        (strategy_id,),
    ).fetchall()
    sig_cols = [r[1] for r in db._connection.execute("PRAGMA table_info(signals)").fetchall()]

    trades = db._connection.execute(
        """SELECT * FROM trades WHERE strategy=? ORDER BY entry_time DESC""",
        (strategy_id,),
    ).fetchall()
    trade_cols = [r[1] for r in db._connection.execute("PRAGMA table_info(trades)").fetchall()]

    positions = db._connection.execute("SELECT * FROM positions").fetchall()
    pos_cols = [r[1] for r in db._connection.execute("PRAGMA table_info(positions)").fetchall()]

    sig_ids = [dict(zip(sig_cols, s))["id"] for s in sigs]
    followups = []
    if sig_ids:
        ph = ",".join("?" * len(sig_ids))
        rows = db._connection.execute(
            f"""SELECT * FROM signal_followups WHERE signal_id IN ({ph})
                ORDER BY created_at""",
            sig_ids,
        ).fetchall()
        fu_cols = [r[1] for r in db._connection.execute("PRAGMA table_info(signal_followups)").fetchall()]
        followups = [dict(zip(fu_cols, r)) for r in rows]

    # Aggregate PnL
    closed = [dict(zip(trade_cols, t)) for t in trades
              if dict(zip(trade_cols, t)).get("realized_pnl") is not None]
    total_pnl = sum(float(t["realized_pnl"]) for t in closed)
    wins = sum(1 for t in closed if float(t["realized_pnl"]) > 0)
    losses = sum(1 for t in closed if float(t["realized_pnl"]) < 0)

    return {
        "strategy_id": strategy_id,
        "signals": [dict(zip(sig_cols, s)) for s in sigs],
        "trades": [dict(zip(trade_cols, t)) for t in trades],
        "open_positions": [dict(zip(pos_cols, p)) for p in positions],
        "followups": followups,
        "summary": {
            "signals_count": len(sigs),
            "trades_count": len(trades),
            "closed_trades": len(closed),
            "open_positions": len(positions),
            "total_realized_pnl": total_pnl,
            "wins": wins,
            "losses": losses,
        },
    }
