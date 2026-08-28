# ERMIS — Target Architecture Map

## Vision
A multi-user trading automation platform. Backend-first, with Strategy Lifecycle + Automation Engine + Multi-user + Live Trading Safety as the four critical foundations. UI on top, but UI cannot be the source of truth for any of these.

## New Layered Architecture
```
┌──────────────────────────────────────────────────────────────────────┐
│  PRESENTATION                                                        │
│  ├─ /app/*  (Vite + React SPA, user app)                              │
│  └─ /admin/* (Vite + React SPA, admin app)                           │
│       ↓ HTTPS + Bearer token (per-user)                              │
├──────────────────────────────────────────────────────────────────────┤
│  API GATEWAY (FastAPI)                                               │
│  ├─ Auth middleware (user identity, role, scope)                      │
│  ├─ Rate limit (existing)                                            │
│  ├─ CORS (existing)                                                 │
│  └─ Audit middleware (every privileged action)                       │
│       ↓                                                              │
├──────────────────────────────────────────────────────────────────────┤
│  DOMAIN SERVICES (NEW)                                               │
│  ├─ user_service             — user/profile/role/scope               │
│  ├─ strategy_service         — CRUD + lifecycle state machine        │
│  ├─ strategy_lifecycle       — server-side state transition guard    │
│  ├─ signal_service           — signal creation + status              │
│  ├─ followup_service         — TP1/TP2/SL events, timeline           │
│  ├─ automation_engine        — TRIGGER→CONDITION→ACTION pipeline     │
│  ├─ trading_engine           — wraps existing OrderManager per-user  │
│  ├─ publishing_service       — Telegram + Square, queue, limits      │
│  ├─ connection_service       — exchange/DEX/Telegram credentials     │
│  ├─ health_service           — system health aggregation             │
│  └─ emergency_service        — pause/resume at 3 scopes              │
│       ↓                                                              │
├──────────────────────────────────────────────────────────────────────┤
│  PERSISTENCE (SQLite for dev, PostgreSQL-ready schema)               │
│  ├─ users                                                         │
│  ├─ user_roles                                                    │
│  ├─ strategies                       (NEW — per-user persistent)   │
│  ├─ strategy_versions                (NEW — config history)        │
│  ├─ strategy_lifecycle_events        (NEW — audit trail)           │
│  ├─ signals                          (EXTEND — add fields)         │
│  ├─ signal_followups                 (NEW — TP/SL timeline)        │
│  ├─ automation_rules                 (NEW — per-strategy rules)    │
│  ├─ automation_events                (NEW — fired events)          │
│  ├─ exchange_connections             (NEW — encrypted secrets)     │
│  ├─ publishing_configs               (NEW — per-user Square config)│
│  ├─ publications                     (NEW — posts sent)            │
│  ├─ audit_log                        (EXTEND — add actor user_id)  │
│  └─ [legacy tables preserved: orders, trades, balances, positions]  │
│       ↓                                                              │
├──────────────────────────────────────────────────────────────────────┤
│  WORKER / QUEUE (existing pattern, generalized)                       │
│  ├─ signal_worker          — runs strategy cycles                    │
│  ├─ followup_worker        — monitors positions, emits follow-ups    │
│  ├─ publishing_worker      — drains Square queue                     │
│  └─ job_queue              — in-process FIFO + persistence           │
└──────────────────────────────────────────────────────────────────────┘
```

## New Database Schema (additive, no destructive changes)

### users
```
id              TEXT PK            (uuid)
email           TEXT UNIQUE NOT NULL
password_hash   TEXT NOT NULL      (bcrypt/argon2)
display_name    TEXT
role            TEXT NOT NULL      ('user' | 'admin')
status          TEXT NOT NULL      ('active' | 'suspended')
created_at      TEXT NOT NULL
updated_at      TEXT NOT NULL
```

### user_sessions
```
id              TEXT PK            (token)
user_id         TEXT FK -> users.id
expires_at      TEXT NOT NULL
created_at      TEXT NOT NULL
last_used_at    TEXT
```

### strategies (NEW, persistent per-user)
```
id              TEXT PK
user_id         TEXT FK -> users.id NOT NULL
name            TEXT NOT NULL
description     TEXT
version         INT NOT NULL DEFAULT 1
lifecycle_state TEXT NOT NULL DEFAULT 'draft'
                -- 'draft' | 'backtest' | 'paper' | 'testnet' | 'live_eligible' | 'live' | 'paused' | 'stopped'
execution_mode  TEXT NOT NULL      -- 'paper' | 'testnet' | 'live'
execution_venue TEXT NOT NULL      -- 'binance' | 'hyperliquid' | 'walletconnect'
market          TEXT NOT NULL      -- e.g. 'BTCUSDT'
timeframe       TEXT NOT NULL      -- '1m'|'5m'|'15m'|'1h'|'4h'
entry_config    TEXT NOT NULL      (JSON: conditions, indicators)
exit_config     TEXT NOT NULL      (JSON: TP1, TP2, SL, trailing)
risk_config     TEXT NOT NULL      (JSON: per_trade, daily, leverage, exposure)
automation_id   TEXT FK -> automation_rules.id
template_name   TEXT              (registry name: 'ema_crossover', 'macd_crossover', etc.)
template_params TEXT              (JSON)
created_at      TEXT NOT NULL
updated_at      TEXT NOT NULL
```

### strategy_lifecycle_events
```
id              INTEGER PK AUTOINCREMENT
strategy_id     TEXT FK NOT NULL
from_state      TEXT
to_state        TEXT NOT NULL
actor_user_id   TEXT FK -> users.id
actor_role      TEXT NOT NULL      -- 'user' | 'admin' | 'system'
reason          TEXT
created_at      TEXT NOT NULL
```

### strategy_versions
```
id              TEXT PK
strategy_id     TEXT FK NOT NULL
version         INT NOT NULL
config_snapshot TEXT NOT NULL      (JSON — full strategy state at this version)
created_at      TEXT NOT NULL
```

### backtests
```
id              TEXT PK
strategy_id     TEXT FK NOT NULL
user_id         TEXT FK NOT NULL
status          TEXT NOT NULL      -- 'queued' | 'running' | 'completed' | 'failed'
result_summary  TEXT              (JSON)
started_at      TEXT
completed_at    TEXT
error_message   TEXT
```

### signals (EXTEND existing table — additive migration)
```
-- existing columns preserved
+ id              TEXT PK            (uuid; existing rows get backfilled)
+ user_id         TEXT FK -> users.id
+ strategy_id     TEXT FK -> strategies.id
+ entry_price     TEXT
+ tp1             TEXT
+ tp2             TEXT
+ stop_loss       TEXT
+ mode            TEXT NOT NULL      -- 'paper' | 'testnet' | 'live'
+ signal_status   TEXT NOT NULL DEFAULT 'active'
                  -- 'active' | 'entry_confirmed' | 'tp1_hit' | 'tp2_hit' | 'sl_hit' | 'closed' | 'cancelled'
+ trading_status  TEXT NOT NULL DEFAULT 'pending'
                  -- 'pending' | 'placed' | 'rejected' | 'filled' | 'closed'
+ telegram_status TEXT NOT NULL DEFAULT 'pending'
+ square_status   TEXT NOT NULL DEFAULT 'pending'
+ created_at      TEXT
+ updated_at      TEXT
```

### signal_followups (NEW)
```
id              TEXT PK
signal_id       TEXT FK -> signals.id NOT NULL
event_type      TEXT NOT NULL      -- 'entry_confirmed' | 'tp1_hit' | 'tp2_hit' | 'sl_hit' | 'stop_moved' | 'position_closed' | 'cancelled'
event_data      TEXT              (JSON: price, time, pnl, etc.)
publishing_status TEXT NOT NULL DEFAULT 'pending'  -- JSON: {telegram, square, errors}
execution_status  TEXT NOT NULL DEFAULT 'pending'
created_at      TEXT NOT NULL
```

### automation_rules (NEW)
```
id              TEXT PK
user_id         TEXT FK -> users.id NOT NULL
strategy_id     TEXT FK -> strategies.id (NULL = global)
name            TEXT NOT NULL
trigger         TEXT NOT NULL      -- 'signal_generated' | 'tp1_hit' | 'tp2_hit' | 'sl_hit' | 'stop_moved' | 'position_closed'
conditions      TEXT NOT NULL      (JSON: array of conditions)
actions         TEXT NOT NULL      (JSON: array of {type: 'telegram'|'square'|'trade'|'close'|'move_sl', params: {...}})
enabled         INTEGER NOT NULL DEFAULT 1
created_at      TEXT NOT NULL
updated_at      TEXT NOT NULL
```

### automation_events (NEW)
```
id              TEXT PK
rule_id         TEXT FK -> automation_rules.id
signal_id       TEXT FK -> signals.id
followup_id     TEXT FK -> signal_followups.id
status          TEXT NOT NULL      -- 'pending' | 'running' | 'completed' | 'failed' | 'retrying'
result          TEXT              (JSON)
attempts        INT NOT NULL DEFAULT 0
created_at      TEXT NOT NULL
completed_at    TEXT
```

### exchange_connections (NEW)
```
id              TEXT PK
user_id         TEXT FK -> users.id NOT NULL
venue           TEXT NOT NULL      -- 'binance' | 'hyperliquid' | 'walletconnect'
label           TEXT
api_key_enc     BLOB NOT NULL      (encrypted with server key)
api_secret_enc  BLOB              (encrypted with server key; null for wallet-based)
wallet_address  TEXT
permissions     TEXT              (JSON: {read, trade, withdraw})
status          TEXT NOT NULL      -- 'connected' | 'disconnected' | 'error'
created_at      TEXT NOT NULL
updated_at      TEXT NOT NULL
```

### publishing_configs (NEW)
```
user_id         TEXT PK FK -> users.id
telegram_token_enc  BLOB
telegram_chat_id    TEXT
telegram_enabled    INTEGER NOT NULL DEFAULT 0
square_api_key_enc  BLOB
square_endpoint     TEXT
square_daily_limit  INTEGER NOT NULL DEFAULT 95
square_limit_behavior TEXT NOT NULL DEFAULT 'queue'
                  -- 'stop_square' | 'telegram_only' | 'queue'
square_enabled      INTEGER NOT NULL DEFAULT 0
updated_at      TEXT NOT NULL
```

### publications (NEW)
```
id              TEXT PK
user_id         TEXT FK -> users.id
signal_id       TEXT FK -> signals.id
channel         TEXT NOT NULL      -- 'telegram' | 'binance_square'
status          TEXT NOT NULL      -- 'pending' | 'sent' | 'failed' | 'rate_limited' | 'duplicate'
posted_at       TEXT
error_message   TEXT
dedup_key       TEXT              (for duplicate prevention)
created_at      TEXT NOT NULL
```

### emergency_pauses (NEW)
```
id              TEXT PK
scope           TEXT NOT NULL      -- 'strategy' | 'user' | 'integration' | 'platform'
scope_target    TEXT              (strategy_id, user_id, venue, or NULL for platform)
actor_user_id   TEXT FK -> users.id NOT NULL
actor_role      TEXT NOT NULL
reason          TEXT NOT NULL
created_at      TEXT NOT NULL
expires_at      TEXT              (NULL = until manually resumed)
```

### audit_log (EXTEND existing append-only JSONL file with structured table mirror)
```
id              INTEGER PK AUTOINCREMENT
actor_user_id   TEXT FK -> users.id
actor_role      TEXT NOT NULL
action          TEXT NOT NULL      -- 'strategy.create' | 'lifecycle.transition' | 'live.deploy' | 'emergency.pause' | ...
target_type     TEXT
target_id       TEXT
detail          TEXT              (JSON, no secrets)
result          TEXT NOT NULL      -- 'ok' | 'rejected' | 'error'
created_at      TEXT NOT NULL
```

## Critical Foundations

### 1. Strategy Lifecycle State Machine (server-enforced)
```
DRAFT ──> BACKTEST ──> PAPER ──> TESTNET ──> LIVE_ELIGIBLE ──> LIVE
                ↑          ↑          ↑              ↑
                └── PAUSED <┴──────────┴── STOPPED <─┘
                              (any state can go to PAUSED/STOPPED)
```

**Transition rules (validated server-side):**
- DRAFT → BACKTEST: user action
- BACKTEST → PAPER: requires completed backtest
- PAPER → TESTNET: requires >= N paper sessions, positive PnL
- TESTNET → LIVE_ELIGIBLE: requires valid exchange connection + risk config + admin approval flag set
- LIVE_ELIGIBLE → LIVE: requires explicit user confirmation string + risk config
- Any → PAUSED: user or admin action (stops NEW actions; does NOT close open positions by default)
- Any → STOPPED: user or admin action (also stops new actions; flag for "close positions on stop" is separate)

**LIVE eligibility checks (server-side):**
- exchange connection exists and `status='connected'`
- risk config has: max_per_trade, max_daily_loss, max_open_positions, max_leverage
- automation rules reference valid signal triggers
- user has explicitly set the `LIVE_DEPLOYMENT_CONFIRMED` flag for this strategy
- No active emergency pause on the user/strategy

### 2. Automation Engine
```
TRIGGER (signal_generated, tp1_hit, tp2_hit, sl_hit, stop_moved, position_closed)
  → CONDITIONS (JSON: [{field, op, value}, ...])
  → ACTIONS (JSON: [{type, params}, ...])
```

**Action types:**
- `telegram_publish` (params: template)
- `square_publish` (params: template, category)
- `open_trade` (params: side, qty, leverage, venue)
- `close_position`
- `move_stop` (params: new_stop)
- `notification` (params: severity, message)

**Engine properties:**
- Idempotent: each rule firing gets a `dedup_key`; retries don't double-publish
- Async: rules fire in a worker thread, not in the request path
- Auditable: every firing creates an `automation_events` row
- Per-strategy: rules belong to a strategy (or user, for global rules)

### 3. Multi-user Authorization
- All user-owned resources carry `user_id`
- Middleware: resolves `Bearer <token>` → user_id + role
- Every query scopes by user_id; cross-user access returns 404 (not 403) to avoid info leak
- Admin role: bypasses user scoping BUT cannot read exchange_connections.api_secret_enc (explicit allow-list)
- Admin emergency pause: requires typed confirmation string for LIVE strategies

### 4. Live Trading Safety
- LIVE cannot be enabled by a single toggle
- Must go through `lifecycle.transition(live)` API which:
  1. Validates current state is `LIVE_ELIGIBLE`
  2. Validates exchange connection + risk config + automation rules
  3. Requires `confirm_live: true` AND `confirmation_string: "I_UNDERSTAND_LIVE_RISK"`
  4. Writes audit_log entry
  5. Updates lifecycle_state atomically
- Emergency pause does NOT close positions by default
  - A separate `emergency.close_positions: true` flag is required
  - Default behavior: stop new automated actions; leave open positions to user
- Admin cannot deploy to live on behalf of a user (must be the user themselves)

## File Layout (new)
```
app/
├── core/                            NEW — cross-cutting concerns
│   ├── auth.py                      user identity, password hashing, sessions
│   ├── rbac.py                      role checks, scoping helpers
│   ├── audit.py                     structured audit log
│   ├── crypto.py                    encrypt/decrypt for secrets at rest
│   └── errors.py                    domain exceptions
├── domain/                          NEW — business entities
│   ├── user.py
│   ├── strategy.py
│   ├── signal.py
│   ├── followup.py
│   ├── automation.py
│   ├── connection.py
│   └── publishing.py
├── services/                        NEW — orchestration
│   ├── user_service.py
│   ├── strategy_service.py
│   ├── strategy_lifecycle.py        state machine
│   ├── signal_service.py
│   ├── followup_service.py
│   ├── automation_engine.py
│   ├── connection_service.py
│   ├── publishing_service.py
│   ├── health_service.py
│   └── emergency_service.py
├── api/                             EXTENDED
│   ├── routes/
│   │   ├── user_routes.py           /auth/*  /me
│   │   ├── strategy_routes.py       /strategies/*
│   │   ├── signal_routes.py         /signals/*
│   │   ├── followup_routes.py       /followups/*
│   │   ├── automation_routes.py     /automation/*
│   │   ├── connection_routes.py     /connections/*
│   │   ├── publishing_routes.py     /publishing/*
│   │   ├── health_routes.py         /health/system
│   │   ├── emergency_routes.py      /emergency/*
│   │   └── admin_routes.py          /admin/*
│   ├── legacy_routes.py             the existing endpoints, deprecated but kept
│   ├── server.py                    mounts the new routers + keeps legacy
│   └── dependencies.py              auth deps
├── database/
│   ├── repository.py                EXTENDED — new methods, no breaking changes
│   ├── migrations/
│   │   ├── 001_init.sql             creates the new tables
│   │   ├── 002_extend_signals.sql   adds the new columns to signals
│   │   └── 003_backfill.sql         backfills user_id=strategy_name etc. for legacy rows
│   └── migration_runner.py          applies migrations on startup
└── [existing app/* preserved]
```
