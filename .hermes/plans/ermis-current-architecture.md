# ERMIS — Current Architecture Map

## Project Layout
```
C:\Users\AMD\MK TRADER\
├── app/                          Python backend (FastAPI)
│   ├── api/                      HTTP layer
│   │   ├── server.py             Main FastAPI app (492 lines, 25+ endpoints)
│   │   ├── auth.py               Bearer + X-Token header auth
│   │   ├── control.py            Bot start/stop (thread-based daemon)
│   │   ├── security.py           Rate limit, headers, audit logger
│   │   ├── prometheus.py         Prometheus metrics
│   │   ├── ws.py                 WebSocket (read-only)
│   │   ├── index.html            Landing page
│   │   ├── admin.html            Admin dashboard
│   │   ├── mobile.html           Mobile dashboard
│   │   └── static/               Shared CSS + JS helpers
│   ├── config/                   Pydantic settings
│   ├── database/repository.py    Thread-safe SQLite repo
│   ├── strategy/                 Strategy registry + 5 built-in + user auto-load
│   ├── signals/                  Signal model + engine
│   ├── exchange/                 Paper / Binance / Hyperliquid / WalletConnect
│   ├── execution/                OrderManager, RiskManager, DEX gate
│   ├── risk/                     Position sizer, stop loss, take profit
│   ├── market_data/              Candle providers, health checks
│   ├── notifications/            Telegram + Binance Square + dedup publisher chain
│   ├── monitoring/               Health, alerts, retry
│   ├── backtesting/              Engine + walk-forward
│   ├── portfolio/                PnL
│   ├── dex/                      WalletConnect scaffold
│   ├── dashboard/                Streamlit (not integrated with FastAPI)
│   ├── runtime.py                TradingCycle + BotRunner
│   ├── worker.py                 Persistent worker
│   └── main.py                   CLI entry
├── mobile/flutter_app/           Flutter mobile app (1701 LOC)
├── tests/                        61 test files, 180/182 passing (2 pre-existing EMA failures)
├── scripts/                      DB maintenance, smoke tests, etc.
└── docs/                         MkDocs
```

## Existing Database Schema (SQLite + WAL)
```
signals        (symbol, side, confidence, timestamp, strategy, reason)
orders         (order_id, symbol, status, quantity, average_price, created_at)
trades         (trade_id, symbol, side, quantity, entry_price, exit_price, realized_pnl, fees, strategy, entry_time, exit_time)
daily_pnl      (trade_date, realized_pnl, fees)
bot_events     (event_id, event_type, message, created_at)
errors         (error_id, error_type, message, created_at)
balances       (asset, wallet_balance, available_balance, updated_at)
positions      (symbol, side, quantity, entry_price, mark_price, leverage, unrealized_pnl, updated_at)
control_state  (id=1, desired_state, heartbeat_at, updated_at)
```

**No tables for:** users, strategies, signal follow-ups, automation rules, audit events, lifecycle state, publications.

## Existing API Routes
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | none | Liveness |
| GET | `/status` | none | Mode + provider |
| GET | `/summary` | none | High-level state |
| GET | `/ready` | none | Readiness |
| GET | `/metrics` | none | DB row counts |
| GET | `/orders` | none | Recent orders |
| GET | `/signals` | none | Recent signals (raw rows) |
| GET | `/trades` | none | Recent trades |
| GET | `/balances` | none | Wallet balances |
| GET | `/positions` | none | Open positions |
| GET | `/events` | none | Bot events |
| GET | `/errors` | none | Errors |
| GET | `/admin/status` | admin | Bot control state |
| GET | `/admin/summary` | admin | Full summary |
| GET | `/admin/data` | admin | All data in one payload |
| GET/POST | `/admin/dex/*` | admin | DEX preview/approve/place |
| GET/POST | `/admin/square/*` | admin | Square toggle/enqueue/flush/status |
| GET | `/admin/audit/tail` | admin | Audit log tail |
| GET/POST | `/control/status\|start\|stop` | control | Bot lifecycle |
| WS | `/ws` | none | Real-time events (read-only) |
| GET | `/` | none | Landing page |
| GET | `/mobile` | none | Mobile dashboard HTML |
| GET | `/admin` | none | Admin HTML |
| GET | `/docs` | none | Swagger UI |

## Existing Auth
- **Single token per role**, configured via env (`ADMIN_API_TOKEN`, `CONTROL_API_TOKEN`)
- Header support: `Authorization: Bearer <token>` AND `X-Admin-Token` / `X-Control-Token`
- No user identity, no roles, no user scoping
- Audit logger exists (JSONL) but only for admin endpoints (DEX, Square, control)

## Existing Strategy Engine
- Registry: `app/strategy/factory.py` — 5 built-in + user file auto-load
- Built-in: `IndicatorStrategy`, `EMACrossoverStrategy`, `MACDCrossoverStrategy`, `BollingerStrategy`, `RSIMeanReversionStrategy`
- Each registered with a name + builder function
- No persistence — strategies are pure classes, no DB record
- No per-strategy config: all settings are global in `.env`

## Existing Signal Engine
- `app/signals/models.py`: `Signal(symbol, side, confidence, timestamp, reason, strategy_name, metadata)`
- `app/signals/signal_engine.py`: Health-gated, calls `strategy.generate_signal(symbol, candles)`
- No persistence of follow-ups
- No signal_status / trading_status / publishing_status fields

## Existing Exchange Adapters
| Adapter | File | State |
|---------|------|-------|
| `PaperTradingAdapter` | `exchange/paper.py` | Working, configurable balance + notional |
| `BinanceFuturesAdapter` | `exchange/binance_futures.py` | Working (testnet + live) |
| `HyperliquidAdapter` | `exchange/hyperliquid.py` | Working |
| `WalletConnectAdapter` | `exchange/walletconnect.py` | Scaffold |
| `DexOrderGate` | `execution/dex_gate.py` | Preview/approve/place enforcement |

## Existing Risk Engine
- `app/risk/risk_manager.py`: `RiskManager.approve(...)` returns `RiskDecision(approved, reason)`
- Checks: emergency_stop, min_confidence, daily_loss, max_positions, leverage_cap, max_exposure, consecutive_losses
- Emergency stop exists but is in-memory only and not exposed via API

## Existing WebSocket
- Read-only event stream at `/ws`
- Pushes: signal events, order events, bot events
- No reconnection, no auth

## Existing Notifications
- Telegram: `app/notifications/telegram.py` — `TelegramNotifier` + `TelegramSignalPublisher`
- Binance Square: `app/notifications/binance_square.py` — `BinanceSquarePoster` with queue + daily limit (default 95)
- Publisher chain: `DeduplicatingPublisher → CompositePublisher → [Telegram, Square]`
- Square has hardcoded daily limit behavior — no 3-way config

## Existing Control Mechanism
- `app/api/control.py` — single-thread-based daemon
- `TradingCycle.run_once()` → `BotRunner.run(max_cycles)` in a thread
- Started by `POST /control/start`, stopped by `POST /control/stop`
- One global bot instance (no per-user, no per-strategy)
- `control_state` DB table persists desired state across restarts

## Existing Tests
- 61 test files, 180/182 passing
- 2 pre-existing failures in `test_strategies.py` (EMA crossover — pre-existing, not related to ERMIS)
- Tests use `:memory:` SQLite via `tests/conftest.py`
