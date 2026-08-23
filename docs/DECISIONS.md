# Architecture Decision Records

This file records significant architecture decisions. Each ADR states context, decision, and
consequences. Decisions are written so they can be revisited deliberately, not accidentally.

## ADR-001: React Native + Expo for the mobile app

**Context.** We need a mobile-first client for Android (first target) and iOS. Native apps for both
platforms are expensive to maintain; web-only does not satisfy mobile-first.

**Decision.** Use React Native with the Expo managed workflow and TypeScript.

**Consequences.**
- One codebase for Android and iOS; Expo simplifies builds, updates, and device testing.
- Charting and WebSocket libraries for React Native are mature.
- The mobile app is a thin client, so cross-platform UI work is simpler than a native trading engine.
- EAS builds can be deferred until later; the app can also run as a web target for quick preview.

## ADR-002: FastAPI for the backend API

**Context.** The backend needs a typed, async, testable HTTP API that shares domain models with
trading workers.

**Decision.** Use FastAPI with Pydantic v2, SQLAlchemy 2.0 (async), and Alembic.

**Consequences.**
- Pydantic models double as API schemas and validation for strategy parameters.
- FastAPI native async + WebSocket support fits the real-time dashboard requirement.
- Auto-generated OpenAPI docs speed up mobile client development.
- Proven by the FastAPI full-stack template (MIT) for auth/config/testing patterns.

## ADR-003: PostgreSQL as the database

**Context.** We need a transactional, SQL source of truth for strategies, bots, orders, trades, PnL,
and (later) multi-tenant SaaS data.

**Decision.** Use PostgreSQL (via SQLAlchemy 2.0 + Alembic).

**Consequences.**
- JSONB columns store strategy parameters, so schema stays stable while parameters evolve.
- Enforces transactional integrity for order/trade state and PnL updates.
- Scales to multi-tenant SaaS without changing the storage engine.
- SQL (rather than Redis) remains the source of truth for permanent trading records.

## ADR-004: Redis for queues, pub/sub, locks, cache

**Context.** Backtests and bot execution must run as background jobs; the API must push real-time
events; only one worker may run a given bot; dashboards should be fast.

**Decision.** Use Redis for Arq job queues, pub/sub event bus, distributed locks
(`bot:{id}:lock`), cache, and temporary bot status. Permanent records never live only in Redis.

**Consequences.**
- Arq is an async-first Redis job queue — lighter and more natural for an asyncio codebase than Celery.
- Pub/sub decouples workers from the API; workers publish events, the API forwards them over WebSocket.
- Distributed locks make horizontal scaling of workers safe.
- Requires careful key-lifecycle management; ephemeral state is reconstructable from the DB.

## ADR-005: Modular monolith + separate workers (no microservices)

**Context.** The PRD explicitly warns against a giant monolith and against premature microservices.

**Decision.** Build a modular monolith: three deployable units (API, Trading Worker, Backtest Worker)
from one repository, sharing `packages/trading-core` and `packages/exchange`. Split further only
when actual scale requires it.

**Consequences.**
- Heavy backtests run in worker processes, so they never block API requests or bot loops.
- Shared packages prevent code duplication between API and workers.
- Deployment stays simple (one Docker Compose project).
- The trading worker can run independently of the API process, satisfying "bot keeps running".

## ADR-006: Pluggable strategy plugin architecture

**Context.** The most important requirement: replace a strategy without rewriting the engine;
change parameters from mobile without editing Python code.

**Decision.** Strategies are registered plugin classes in `trading-core/strategy/` that are pure
functions of (market data, validated parameters) → `Signal`. They never import the exchange,
database, or UI. Parameters live in the database as JSONB validated by a per-strategy Pydantic
config schema; every change creates an immutable `strategy_version`.

**Consequences.**
- Adding a strategy = adding one module and registering it; no engine changes.
- Backtests, paper, testnet, and live all reuse the same strategy code.
- Versioning makes results reproducible; a running bot always uses the version it started with.
- Confidence scoring stays strategy-specific (never hardcoded in the risk engine).

## ADR-007: Exchange adapter abstraction (CCXT behind a thin interface)

**Context.** The strategy layer must not know Binance exists; Binance-specific code must not spread
through the app; Bybit/OKX/Coinbase may be added later.

**Decision.** Define our own `ExchangeAdapter` interface (balance, positions, orders, market data,
order placement/cancel, leverage, exchange info). Implement it once for Binance USD-M Futures using
CCXT (`binanceusdm`, MIT), and once as `PaperAdapter` for paper trading.

**Consequences.**
- Strategy/risk/execution code is exchange-agnostic.
- CCXT handles the messy Binance specifics and gives us multi-exchange headroom; the adapter layer
  isolates TP/SL and leverage semantics (the main cross-exchange divergence points).
- Avoids python-binance, which would couple us to a single venue and contradict the multi-exchange goal.

## ADR-008: Mobile app does not run the trading engine

**Context.** The product rule: bots must keep running when the phone is closed; the phone is a
control/monitoring client.

**Decision.** All trading logic runs in the Trading Worker on the backend. The mobile app only calls
the API and subscribes to WebSockets.

**Consequences.**
- Bots are resilient to network/phone state; the backend owns execution.
- Execution, risk, and credentials are centralized (more secure).
- Offline phone → bot continues; reconnecting the app resyncs from REST + WS.
- Implies a backend round-trip for every action (acceptable; keeps logic testable server-side).

## ADR-009: Live trading disabled by default

**Context.** Live trading is dangerous; the PRD requires multiple safeguards and default-off.

**Decision.** `LIVE_TRADING_ENABLED=false` by default. LIVE mode requires an explicit flag plus an
explicit per-account confirmation step (UI shows "REAL MONEY MODE" and requires typed
acknowledgement). MVP ships BACKTEST, PAPER, and TESTNET.

**Consequences.**
- Accidental real-money orders are structurally hard to produce.
- Audit log records live-mode enablement.
- Live uses the same code path as testnet, so the only difference is the endpoint and the gate.

## ADR-010: Arq over Celery for background jobs

**Context.** Redis is already in the stack; the codebase is async-native (FastAPI + asyncio workers).

**Decision.** Use Arq for job queues.

**Consequences.**
- No additional broker; async-native; simple function-based jobs.
- Celery is heavier and sync-oriented; not justified at this scale.
- If job semantics grow complex (cron, retries, priorities), we can migrate to Celery without changing the interface.

## ADR-011: Single repo, local package layout (no polyrepo)

**Context.** API, workers, and mobile share domain concepts; the PRD prescribes an
`apps/ packages/ infrastructure/` layout.

**Decision.** One repository with `apps/` (api, worker, mobile), `packages/` (trading-core, exchange),
`infrastructure/` (docker, migrations), `tests/`, `docs/`. Python packages are installed as local
editable packages.

**Consequences.**
- Atomic changes across API/worker/trading-core land in one PR.
- Simpler CI, simpler local dev with Docker Compose.
- Keeps mobile separate (own toolchain) but inside the same repo for coherent versioning.

## ADR-012: Domain-scoped packages + dependency-injected auth

**Context.** SaaS-readiness requires clean boundaries and tenant isolation by construction.

**Decision.** Follow the `fastapi-best-practices`/full-stack-template pattern: each domain owns
`router.py`, `schemas.py`, `models.py`, `dependencies.py`, `service.py`; auth and tenancy are
enforced by chained FastAPI dependencies (`get_current_user` → `valid_owned_*`). Never trust
client-supplied IDs; derive identity from the token.

**Consequences.**
- Cross-user access is prevented structurally, not by remembering WHERE clauses.
- Tests can override dependencies to simulate users and assert isolation.
