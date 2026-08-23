# Implementation Plan

Development is broken into phases. Each phase is self-contained: it compiles, has tests, and meets
its acceptance criteria before the next phase starts. The trading engine continues running when the
mobile app is closed (workers, not the phone, execute trading).

Global rules (PRD sections 73, 84):
- Never silently skip a requirement. Never claim a feature complete if it is mocked.
- Never rewrite an existing file unless necessary; reuse existing components and mature libraries.
- No live trading by default. No copying external code without license checks.
- After every phase: run tests, list changed files, list known issues, update docs.

## Phase 0 — Architecture (this document set)

- **Objective:** Architecture, ADRs, security model, dependency plan, third-party notices, and this
  implementation plan. No application code.
- **Deliverables:** `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/SECURITY.md`,
  `docs/THIRD_PARTY_NOTICES.md`, `docs/DEPENDENCIES.md`, `docs/IMPLEMENTATION_PLAN.md`.
- **Acceptance criteria:** The plan and structure are committed; no trading/auth/UI code exists.
- **Risks:** None (documentation only).

---

## Phase 1 — Backend foundation

- **Objective:** Project skeleton, Docker Compose, PostgreSQL + Redis, FastAPI app, config, health,
  base database models, Alembic migrations, logging. Monorepo layout with local packages.
- **Files/modules:** `infrastructure/docker/` (compose, Dockerfiles), `apps/api/app/main.py`,
  `apps/api/app/core/config.py`, `apps/api/app/database/` (session, base), `infrastructure/migrations/`,
  `apps/api/app/api/routes/health.py`, `pyproject.toml` (root + packages), `packages/trading-core/pyproject.toml`,
  `packages/exchange/pyproject.toml`, `.env.example`, `README.md`.
- **Dependencies:** Phase 1: none beyond FastAPI, SQLAlchemy 2.0 async, Alembic, pydantic-settings,
  asyncpg, redis, arq, structlog/uvicorn.
- **Database changes:** `users` (id, email, hashed_password, is_active, timestamps);
  `organizations` + `memberships` (empty scaffolding, SaaS prep). Alembic initial migration.
- **APIs:** `GET /health` (API, DATABASE, REDIS status).
- **Tests:** App boots, health endpoint returns 200, DB session works, migration applies cleanly.
- **Acceptance criteria:** `docker compose up` brings up api/postgres/redis; `/health` green;
  Alembic migrates a fresh database.
- **Risks:** Environment/version mismatch for asyncpg/psycopg; resolved via Docker pinning.

## Phase 2 — Authentication

- **Objective:** Register, login, logout, refresh token, password hashing (Argon2), email-verification
  and password-reset architecture (signed tokens, local maildev in dev).
- **Files/modules:** `apps/api/app/auth/` (router, schemas, service, dependencies, security),
  `apps/api/app/users/`, `apps/api/app/api/routes/auth.py`, token utils.
- **Dependencies:** pwdlib, PyJWT (or python-jose), itsdangerous (signed links), argon2-bcrypt.
- **Database changes:** no new tables (tokens are signed/JWT, not stored); add
  `users.is_email_verified`, `users.verification_token_hash`, `users.password_reset_token_hash`.
- **APIs:** `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/refresh`,
  `GET /auth/verify-email`, `POST /auth/password-reset`, `GET /users/me`.
- **Tests:** register→login→me; wrong password rejected; refresh rotation; expired token rejected;
  cross-user me isolation.
- **Acceptance criteria:** User can register and log in from a client; tokens are secure; logout
  invalidates refresh.
- **Risks:** Token storage on mobile (Keychain/Keystore) — deferred to mobile phase; document now.

## Phase 3 — Mobile foundation

- **Objective:** Expo + TypeScript app skeleton: navigation (bottom tabs HOME/BOTS/STRATEGIES/TRADES/
  SETTINGS), API client, auth screens wired to backend, stores (state), theme, error handling.
- **Files/modules:** `apps/mobile/` (App.tsx, `src/screens/`, `src/components/`, `src/navigation/`,
  `src/services/`, `src/stores/`, `src/hooks/`, `src/types/`), `apps/mobile/app.json`, package.json.
- **Dependencies:** expo, react-native, react-navigation, axios (or fetch wrapper), zustand (state),
  react-query (server state), react-native-keychain, react-native-svg (charts later).
- **Database changes:** none.
- **APIs:** uses Phase 2 auth endpoints.
- **Tests:** `tsc --noEmit`, eslint; component tests for auth flow if feasible.
- **Acceptance criteria:** User can log in on the app and see the (empty) dashboard; app builds for
  Android; TypeScript passes.
- **Risks:** Expo SDK version drift with RN packages; lock versions.

## Phase 4 — Strategy engine

- **Objective:** Pluggable strategy system with `Signal` model and a demo EMA/RSI/MACD/ADX/Bollinger
  strategy. Strategy code fully decoupled from exchange/DB/UI.
- **Files/modules:** `packages/trading-core/strategy/` (base.py, registry.py, signals.py,
  demo_momentum.py), `packages/trading-core/schemas/` (Signal, Side, params pydantic models),
  `packages/trading-core/indicators.py` (thin wrapper around pandas-ta/ta).
- **Dependencies:** pandas, numpy, pandas-ta (or `ta`) for indicators.
- **Database changes:** `strategies`, `strategy_versions`, `strategy_parameters` (JSONB).
- **APIs:** `GET/POST /strategies`, `POST /strategies/{id}/versions`, `GET /strategies/{id}/versions/{v}`.
- **Tests:** deterministic signals from fixed candles; parameter validation; registry lookup;
  strategy purity (no IO imports).
- **Acceptance criteria:** Historical candles produce deterministic signals; parameters editable
  via API without code changes; version immutability.
- **Risks:** pandas-ta maintenance — pin and isolate behind one module so it is swappable.

## Phase 5 — Backtesting

- **Objective:** Backtest worker consuming jobs: OHLCV history, candle-loop simulation, fees,
  slippage, metrics, equity curve, no look-ahead (`.shift(1)`), out-of-sample split.
- **Files/modules:** `packages/trading-core/backtesting/` (engine.py, simulation.py, metrics.py,
  assumptions.py), `apps/worker/backtest_worker/` (jobs.py, app.py), `apps/api/app/backtests/`.
- **Dependencies:** arq, pandas, numpy; chart data serialized to JSON for mobile.
- **Database changes:** `backtests`, `backtest_trades`, `backtest_metrics`.
- **APIs:** `POST /strategies/{id}/backtest` (enqueue), `GET /backtests/{id}` (status/results).
- **Tests:** known-strategy PnL matches hand-computed values; look-ahead guard (shift); fee/slippage
  applied; out-of-sample split labels.
- **Acceptance criteria:** A strategy can be backtested from the API (mobile later) and results are
  stored; heavy computation runs in the worker, never in the request.
- **Risks:** Assumption realism (spread/slippage) — documented in results and compared to paper later.

## Phase 6 — Paper trading

- **Objective:** `PaperAdapter` implementing `ExchangeAdapter` with simulated wallet, fills, fees,
  slippage, balance, positions, TP/SL, PnL. Bot runs without any exchange credentials.
- **Files/modules:** `packages/exchange/base.py` (ExchangeAdapter ABC), `packages/exchange/paper.py`,
  `packages/trading-core/execution/` (order.py, position.py), `packages/trading-core/portfolio/`.
- **Dependencies:** none new (uses trading-core + market data feed).
- **Database changes:** `exchange_accounts` (type=PAPER), `orders`, `positions`, `trades`,
  `balances`, `pnl_snapshots`, `bots`, `bot_runs`.
- **APIs:** `GET/POST /exchange-accounts`, `POST /bots`, `POST /bots/{id}/start|stop|pause`,
  `GET /bots/{id}`, `GET /positions`, `GET /orders`, `GET /trades`, `GET /pnl`.
- **Tests:** `PaperExchange` fill semantics (limit fill vs not, slippage, fees), wallet math,
  TP/SL lifecycle, PnL accuracy with Decimal.
- **Acceptance criteria:** A bot can run for hours in PAPER mode with no credentials; positions and
  PnL are tracked end-to-end.
- **Risks:** Slippage model fidelity — keep assumptions configurable and labeled.

## Phase 7 — Risk management

- **Objective:** RiskEngine and risk-based position sizing applied to every signal before any order.
- **Files/modules:** `packages/trading-core/risk/` (engine.py, limits.py, sizing.py, stoploss.py,
  takeprofit.py, trailing.py), emergency-stop + circuit-breaker hooks.
- **Dependencies:** Decimal arithmetic; no new libs.
- **Database changes:** risk config columns on `bots`/`strategy_versions` (JSONB `risk_config`);
  `risk_rejections` (optional logging table).
- **APIs:** risk config exposed via `bots` create/update; `POST /bots/{id}/emergency-stop`.
- **Tests:** reject on balance/daily-loss/max-positions/leverage/cooldown/duplicate/min-confidence;
  sizing formula verified; precision rules (min qty, step, tick, notional) validated.
- **Acceptance criteria:** Unsafe orders are rejected with recorded reasons; sizing is risk-based.
- **Risks:** Edge cases in margin math — property-based tests over parameter space.

## Phase 8 — Binance Testnet

- **Objective:** `CcxtAdapter` for `binanceusdm` testnet: market data, balance, positions, orders,
  market/limit/stop-market/take-profit-market, leverage, order status, cancellation, reconciliation.
- **Files/modules:** `packages/exchange/ccxt_adapter.py`, `apps/worker/trading_worker/exchange_health.py`,
  `apps/api/app/exchange/` (accounts CRUD, credential encryption).
- **Dependencies:** `ccxt` (MIT); credential encryption (cryptography/Fernet).
- **Database changes:** `exchange_credentials` (encrypted), `exchange_accounts` (mode, is_testnet,
  exchange type, leverage/margin config), `orders` fill/reconcile fields.
- **APIs:** `POST /exchange-accounts` (testnet creds), `GET /exchange-accounts/{id}/balance|positions`.
- **Tests:** unit with `MockExchange`/`FakeExchange` (never call real Binance in CI); optional
  opt-in Testnet integration tests (manual).
- **Acceptance criteria:** Testnet trade lifecycle works end-to-end: connect → fetch data → place
  order → verify fill → protection orders → monitor → close → reconcile → store trade → show PnL.
- **Risks:** CCXT param quirks for TP/SL/leverage — isolate in adapter layer; use `fetch_positions`
  as source of truth over WS position streams.

## Phase 9 — Bot workers

- **Objective:** Persistent bot manager: one asyncio task per bot, Redis distributed locks, start/
  stop/pause, restart recovery, reconciliation schedule, DEGRADED state.
- **Files/modules:** `apps/worker/trading_worker/` (app.py, bot_manager.py, market_data.py,
  reconciliation.py), arq worker wiring.
- **Dependencies:** arq, redis (locks via SET NX EX or arq), ccxt async.
- **Database changes:** `bot_runs` (status transitions, timestamps), bot lock keys in Redis.
- **APIs:** existing bot start/stop/pause; `GET /bots/{id}/status`.
- **Tests:** lock prevents double-run (two workers), state recovery after restart, DEGRADED on
  reconciliation mismatch.
- **Acceptance criteria:** Mobile can start/stop a persistent backend bot; restarting the worker
  resumes safe bots.
- **Risks:** Reconnect storms — exponential backoff, market-data dedup/stale handling.

## Phase 10 — Realtime / WebSockets

- **Objective:** Push bot status, signals, order/position/PnL updates to mobile without polling.
  Notifications.
- **Files/modules:** `apps/api/app/websocket/` (manager.py, connections.py), pub/sub bridge in
  worker (`packages/trading-core/events.py`), `apps/mobile/src/services/ws.ts`, notifications UI.
- **Dependencies:** fastapi websockets, redis pub/sub, expo-notifications (push, later).
- **Database changes:** `notifications` table.
- **APIs:** WS `/ws/dashboard`, `/ws/bot/{bot_id}`; `GET /notifications`, `GET /signals`.
- **Tests:** event → WS delivery with two simulated clients; auth on WS connect; reconnect resync.
- **Acceptance criteria:** Mobile dashboard updates live without aggressive polling.
- **Risks:** Connection management at scale — per-user hub pattern; backpressure on slow clients.

## Phase 11 — Strategy versioning

- **Objective:** Full immutable-version workflow: parameter snapshots, backtest association, bot
  association, "save as new version" from mobile, demo "paper vs backtest comparison".
- **Files/modules:** `apps/api/app/strategies/versions.py`, `apps/api/app/comparisons/` (optional),
  mobile strategy screen actions.
- **Database changes:** link `strategy_versions` to `backtests` and `bots`; comparison metrics.
- **APIs:** `POST /strategies/{id}/versions` (copy current params as new version), comparison endpoint.
- **Tests:** a running bot always uses its immutable version; parameter change does not affect it;
  strategy B unaffected by strategy A changes (PRD third acceptance test).
- **Acceptance criteria:** Running bot uses immutable strategy version; results reproducible.
- **Risks:** None significant (schema already designed).

## Phase 12 — Security hardening

- **Objective:** Encrypted credentials verified, rate limiting, audit logs, tenant isolation tests,
  security headers, secret scanning in CI.
- **Files/modules:** `apps/api/app/core/rate_limit.py`, `apps/api/app/audit/`, security test suite
  `tests/security/`.
- **Dependencies:** slowapi (or redis-based limiter), cryptography.
- **Database changes:** `audit_logs`; credential encryption migration.
- **APIs:** rate-limit headers on all endpoints.
- **Tests:** cross-user access matrix (User A vs B for bots/strategies/trades/credentials/backtests/
  positions); 404-not-403; credential never returned.
- **Acceptance criteria:** PRD fourth acceptance test passes; security tests green in CI.
- **Risks:** None — mandatory before any live-adjacent work.

## Phase 13 — Live trading

- **Objective:** LIVE mode gated behind `LIVE_TRADING_ENABLED=false` + explicit confirmations.
  Same code path as Testnet.
- **Files/modules:** `apps/api/app/trading/mode_gate.py`, mobile "REAL MONEY MODE" confirmation UI,
  audit entries for live enablement.
- **Database changes:** none structural.
- **APIs:** `POST /bots/{id}/enable-live` (requires typed confirmation + flag).
- **Tests:** gating unit tests; integration reuses Testnet flow.
- **Acceptance criteria:** Live requires multi-step explicit confirmation; all risk/reconciliation
  safeguards identical to testnet. Only after Phases 6, 8, 9, 12 acceptance.
- **Risks:** Highest-risk phase — keep disabled by default; emergency stop verified under test.

## Phase 14 — SaaS

- **Objective:** organizations/workspaces, memberships, RBAC (OWNER/ADMIN/MEMBER), invitations,
  subscriptions/plans, usage metering, admin surface. Billing flag `BILLING_ENABLED=false`; Stripe later.
- **Files/modules:** `apps/api/app/organizations/`, `apps/api/app/memberships/`, `apps/api/app/billing/`
  (stubs), `apps/api/app/admin/`, `apps/api/app/usage/`.
- **Dependencies:** (later) stripe SDK.
- **Database changes:** `memberships`, `plans`, `subscriptions`, `usage_metering`; tenancy deps switch
  from user-only to user+org scoping.
- **APIs:** org/member management, invite flows, admin read-only endpoints.
- **Tests:** RBAC matrix; org isolation; usage counters.
- **Acceptance criteria:** Multi-user SaaS-ready; billing remains behind flag.
- **Risks:** Migration of tenant scoping — chained dependencies make it a localized change.

---

## Acceptance workflows (PRD 76–79)

1. MVP end-to-end: login → create strategy → set params → save v1 → backtest → metrics → create
   bot → choose PAPER → symbol/timeframe/risk → START → signal → risk → paper fill → position →
   TP/SL → close → PnL → dashboard update.
2. Same workflow on BINANCE TESTNET.
3. Strategy A and B run independently; changing A's params leaves B unchanged.
4. User A and User B fully isolated.

## Performance targets (PRD 80)

- Dashboard API < 500ms for cached requests (Redis-cached aggregates).
- Backtests run asynchronously in workers.
- Trading worker never depends on the mobile app being online.
- PostgreSQL remains source of truth for persistent state.
