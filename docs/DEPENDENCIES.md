# Dependency Plan

Every dependency is listed with its purpose, why it is needed, its license, and whether it is
essential or optional. **Avoid dependency bloat**: we prefer few, mature, MIT/Apache-2.0
dependencies and reuse them across API, workers, and mobile. Dependencies are added in the phase
where they are first needed (see `docs/IMPLEMENTATION_PLAN.md`), not all up front.

## Backend (Python — shared)

| Dependency | Purpose | Why | License | Essential? |
|------------|---------|-----|---------|------------|
| fastapi | HTTP API framework | Async, typed, WebSocket support | MIT | Essential |
| uvicorn[standard] | ASGI server | Runs FastAPI; websockets support | BSD-3-Clause | Essential |
| pydantic v2 + pydantic-settings | Validation, settings, strategy param schemas | Single validation model for API and strategy config | MIT | Essential |
| SQLAlchemy 2.0 (async) | ORM | Database models + async sessions | MIT | Essential |
| alembic | Migrations | Schema versioning | MIT | Essential |
| asyncpg | PostgreSQL async driver | Async DB access | Apache-2.0 | Essential |
| redis (redis-py) + arq | Job queue, pub/sub, locks, cache | Bot/backtest jobs, real-time events, distributed locks | MIT | Essential |
| pwdlib | Password hashing (Argon2/bcrypt) | Secure password storage with transparent hash upgrade | MIT (wrappers) / BSD (argon2) | Essential (Phase 2) |
| PyJWT (or python-jose) | JWT access tokens | Auth tokens | MIT | Essential (Phase 2) |
| cryptography | Fernet/AES encryption of credentials | Encrypt exchange API keys at rest | Apache-2.0 / BSD | Essential (Phase 8) |
| structlog (or stdlib logging) | Structured logging | Observability/audit-friendly logs | MIT / Apache-2.0 | Essential |
| slowapi (or redis limiter) | Rate limiting | Brute-force and abuse protection | MIT | Optional (Phase 12; can hand-roll a Redis limiter) |

## Trading (Python — packages/trading-core + packages/exchange)

| Dependency | Purpose | Why | License | Essential? |
|------------|---------|-----|---------|------------|
| ccxt | Exchange abstraction (binanceusdm) | Unified multi-exchange API; MIT; first-class Binance USD-M Futures; async + ccxt.pro WebSockets | MIT | Essential (Phase 8) |
| pandas | OHLCV handling, indicator computation | Strategy/backtest engine operates on DataFrames | BSD-3-Clause | Essential |
| numpy | Numeric computation | Indicator/math backend for pandas | BSD-3-Clause | Essential |
| pandas-ta (or `ta`) | Technical indicators (EMA, RSI, MACD, ADX, Bollinger) | Avoid hand-writing indicators; isolated behind one module | MIT | Essential (isolate for swapability) |
| cryptography | (listed above) | Credential encryption for adapters | Apache-2.0 | Essential (Phase 8) |
| python-json-logger / msgspec | (optional) faster serialization | Not needed at MVP | — | Optional — skip |

## Mobile (React Native + Expo)

| Dependency | Purpose | Why | License | Essential? |
|------------|---------|-----|---------|------------|
| expo | App framework (managed workflow) | Cross-platform dev/build pipeline | MIT | Essential |
| react-navigation (bottom tabs + native stack) | Navigation | 5-tab structure (HOME/BOTS/STRATEGIES/TRADES/SETTINGS) | MIT | Essential |
| axios (or fetch wrapper) | HTTP client | REST API calls with interceptors/tokens | MIT | Essential |
| react-query | Server state/caching | Dashboard/backtest data caching, retries | MIT | Essential |
| zustand | Client state | Lightweight stores (auth, current bot) | MIT | Essential |
| react-native-keychain | Secure token storage | Access/refresh tokens in Keychain/Keystore | MIT | Essential |
| react-native-svg | Vector graphics | Chart drawing primitives | MIT | Essential (charts) |
| lightweight-charts (via react-native-webview) | Candlestick/equity charts | Mature TradingView-style charting without building charts from scratch | Apache-2.0 | Recommended — evaluate vs victory-native |
| victory-native (or react-native-gifted-charts) | Metric/area charts | Alternative charting | MIT | Optional (choose one chart lib, not both) |
| expo-notifications | Push notifications | Bot/signal/order notifications | MIT | Optional (Phase 10) |

**Charting decision (ADR noted in DEPENDENCIES):** use a mature library, not hand-built charts.
Primary recommendation: `lightweight-charts` in a WebView for candlesticks + equity curves; if the
WebView approach causes integration pain, fall back to `victory-native` (SVG). Pick exactly one to
avoid two chart stacks.

## Database & Infrastructure

| Dependency | Purpose | Why | License | Essential? |
|------------|---------|-----|---------|------------|
| PostgreSQL | Primary database | Transactional source of truth; JSONB for params; SaaS-ready | PostgreSQL License | Essential |
| Redis | Queue/pub-sub/locks/cache | Arq jobs, WS event bus, bot locks, dashboard cache | BSD-3-Clause | Essential |
| Docker + Docker Compose | Dev/deploy | Consistent env; api/worker/postgres/redis | Apache-2.0 (engine) | Essential |
| GitHub Actions | CI | lint, typecheck, unit tests, builds | — | Essential |

## Testing & Quality

| Dependency | Purpose | Why | License | Essential? |
|------------|---------|-----|---------|------------|
| pytest + pytest-asyncio | Unit/integration/security tests | Test strategy, risk, sizing, PnL, isolation | MIT | Essential |
| httpx | Async test client for FastAPI | `TestClient`-style integration tests with dependency overrides | BSD-3-Clause | Essential |
| ruff | Python lint + format | Fast, modern linter | MIT | Essential |
| mypy | Python type checking | Static types across API/worker/trading-core | MIT | Essential |
| factory-boy (optional) | Test fixtures | Cleaner test data | MIT | Optional |
| TypeScript + eslint + prettier | Mobile typecheck/lint | Mobile quality gates | MIT | Essential (mobile) |

## Explicitly NOT chosen (avoid bloat)

- **Celery** — Arq is async-native and Redis-based; revisit only if job semantics demand it.
- **python-binance** — Binance-only; CCXT already covers Binance + future exchanges (ADR-007).
- **Vendored Freqtrade/Hummingbot code** — license-incompatible or unnecessary (see THIRD_PARTY_NOTICES).
- **Streamlit/Web dashboard (Hummingbot Dashboard)** — mobile-first; no web dashboard in MVP.
- **Stripe SDK** — deferred to Phase 14 (behind `BILLING_ENABLED=false`).

## Version pinning

All backend deps pinned in `pyproject.toml` (or `requirements/` lock files); mobile deps locked by
Expo (`package-lock.json`/`yarn.lock`). Indicator library (pandas-ta/ta) pinned and isolated behind
`packages/trading-core/indicators.py` so it can be swapped without touching strategies.
