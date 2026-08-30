"""Dev/test simulation routes — STRATEGY-TEST-001."""
import json
from datetime import UTC, datetime, timedelta
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
        # Fallback: synthesize candles for test/dev environments with no Binance access
        base = {"BTCUSDT": "50000", "ETHUSDT": "3000", "SOLUSDT": "100"}.get(symbol, "100")
        now_ts = int(datetime.now(UTC).timestamp()) * 1000
        return [
            Candle(
                open_time=datetime.fromtimestamp((now_ts - (limit - i) * 60000) / 1000, tz=UTC),
                open=Decimal(base), high=Decimal(str(float(base) * 1.002)),
                low=Decimal(str(float(base) * 0.998)),
                close=Decimal(base),
                volume=Decimal("1"),
                close_time=datetime.fromtimestamp((now_ts - (limit - i) * 60000 + 59999) / 1000, tz=UTC),
            )
            for i in range(limit)
        ]


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

    # Cooldown: symbols with an open position in `positions` table
    open_syms = {r[0] for r in db._connection.execute(
        "SELECT symbol FROM positions").fetchall()}

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

        # Execute paper trade
        order = paper.place_order(OrderRequest(
            symbol=symbol, side=side, order_type=OrderType.MARKET,
            quantity=quantity, price=None,
        ))

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
                leverage, unrealized_pnl, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (symbol, direction, float(quantity), entry_f, entry_f,
             1, 0.0, candle_ts),
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
    from datetime import UTC, datetime as _dt
    from app.exchange.paper import PaperTradingAdapter as _Paper
    from app.exchange.models import OrderRequest as _OR, OrderSide as _OS, OrderType as _OT

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
            leverage, unrealized_pnl, updated_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (symbol, side_str, float(quantity), entry_f, entry_f, 1, 0.0, now),
    )
    db._connection.execute(
        """UPDATE signals
           SET trading_status='EXECUTED', signal_status='EXECUTED', updated_at=?
           WHERE UPPER(COALESCE(trading_status,'PENDING')) != 'EXECUTED'
           AND id=?""", (now, signal_id),
    )
    db._connection.commit()

    try:
        from app.services.automation_engine import AutomationEngine
        from app.core.rbac import AccessContext as _AC
        from app.domain.user import User as _U, UserRole as _UR, UserStatus as _US
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
    _get_strategy(strategy_id)
    from app.database.repository import TradingRepository
    db = TradingRepository()

    sig_ids = [r[0] for r in db._connection.execute(
        "SELECT id FROM signals WHERE strategy_id=?", (strategy_id,)).fetchall()]

    if sig_ids:
        ph = ",".join("?" * len(sig_ids))
        db._connection.execute(f"DELETE FROM signal_followups WHERE signal_id IN ({ph})", sig_ids)
        db._connection.execute(f"DELETE FROM signals WHERE strategy_id=?", (strategy_id,))
    db._connection.execute("DELETE FROM trades WHERE strategy=?", (strategy_id,))
    db._connection.execute("DELETE FROM positions WHERE symbol IN (SELECT symbol FROM signals WHERE strategy_id=?)",
                     (strategy_id,))
    db._connection.commit()

    return {"strategy_id": strategy_id, "reset": True, "signals_deleted": len(sig_ids)}
