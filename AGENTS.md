# AGENTS.md — Operating rules for Bot03 / MK TRADER

This file is the contract any AI coding agent must follow when working in
this repository. It exists because the project is a money-moving system:
a bad change can produce real losses, not just bugs.

If instructions in a chat, prompt, or PRD conflict with the rules below,
the rules below win. Always.

---

## 1. Safety rules (highest priority)

- **Live trading MUST stay disabled** during all development, testing, and
  PR work. Verify `mode: "paper"` and `live_trading_enabled: false` in
  `.env` and `GET /health` before doing anything that exercises the bot.
- Never flip `live_trading_enabled` to `true` as part of a code change,
  even if the change "needs" it. If a real-trade path is required for
  verification, the user must explicitly enable it after the PR merges.
- Never use real funds, real exchange credentials outside of paper mode,
  or testnet-only funds in a way that affects a live account.
- Risk engine, emergency stop, and position-limits code is load-bearing.
  Treat any change to `app/risk/`, `app/execution/`, or the protection
  modules as a red-flag diff that needs explicit justification.

## 2. Before you change anything

- **Inspect the existing code first.** Read the file you intend to change,
  plus the callers and the tests that exercise it. Do not guess the shape
  of an API or import.
- **Find the root cause before applying a fix.** A symptom patch that
  papers over a bug (e.g. `age = max(age, 0)`) is forbidden. Trace the
  data back to its source. If the bug is in candle timestamps, fix the
  timestamp, not the age math.
- **Work on ONE task at a time.** Do not combine two PRDs, two P0s, or
  one P0 plus a refactor into a single commit. Each task is a separate
  commit with a separate rationale.
- **Do not make unrelated refactors.** Drive-by renames, reformatting,
  or "while I'm here" cleanups are not allowed in a feature commit.
- **Do not create duplicate functionality.** If a helper, dataclass, or
  function already does what you need, use it. Don't add a parallel API.

## 3. Candle and market-data integrity

- **Never evaluate an unfinished / future / in-progress candle.** A candle
  is closed only when `now >= candle.close_time` (Binance `close_time` is
  the EXCLUSIVE end of the interval, equal to the next candle's open).
- The scanner must call `_select_last_closed_candle()` (or equivalent)
  and never blindly take `candles[-1]` from a market-data response.
- **Verify candle timestamp, timeframe, freshness, and closed status**
  before any indicator or condition is evaluated. The four questions are
  not optional.
- The scanner must reject candles with negative age, future close_time,
  or staleness past the configured threshold (default 5 minutes).
- Timeframes must be matched across strategy config, exchange kline
  request, and indicator calculation. Do not silently re-aggregate
  from a different timeframe.
- **Never use fake / synthetic / mock market data when real market-data
  behavior is being tested.** Tests for candle selection, age, freshness,
  and indicator evaluation must use constructed `Candle` objects that
  mirror real Binance semantics, not invented numbers. Mocked adapters
  are only acceptable for unrelated pipeline plumbing.

## 4. Condition evaluation and confidence

- **Never hardcode a fixed number of indicators or conditions** such as
  10, 8, 5, etc. The number of conditions in a strategy is data-driven:
  sum `len(conditions)` across the strategy's `conditions_config.groups`.
- The same rule applies to the indicator list: compute it from config,
  do not hardcode `range(10)`, `[:10]`, or similar.
- **Confidence must be reported as X/Y format**, e.g. `6/10`, `5/8`,
  `8/13` — where X is the number of conditions that passed in the
  current cycle and Y is the total number of conditions evaluated for
  that strategy at that moment. The Y denominator is dynamic.
- The confidence number is stored as two integer columns
  `confidence_hits` and `confidence_total` in the `signals` table, plus
  a derived `confidence` float. Display in the UI as `N/M`.
- Do not change the underlying indicator math (RSI, EMA, MACD, Bollinger)
  as part of a confidence or wiring change. Those calculations are stable.

## 5. Logging and observability

- **Do not spam logs with every failed condition.** Per-symbol DEBUG
  noise is not acceptable for a multi-symbol scanner. Aggregate per cycle
  and emit a single summary line.
- Per-symbol DEBUG logs are still allowed for **structural** events
  (candle selection, indicator error, empty data response) but not for
  "this condition did not pass" on every symbol on every cycle.
- Use the existing structured `[SCAN]`, `[DATA]`, `[EVAL]`, `[RISK]`
  prefixes when adding new log lines. Keep them grep-friendly.
- Never silently swallow exceptions in scanner, risk, or execution
  paths. Either log with context or re-raise. Bare `except Exception: pass`
  is a code-review blocker.

## 6. Signal and trade history integrity

- **Preserve immutable signal / condition snapshots for historical
  analysis.** Once a signal is persisted, its condition values, indicator
  values, and confidence must not be retroactively edited. Corrections
  go in a new column or a new event row.
- The same rule applies to `signal_followups` and trade outcomes. The
  `id TEXT PK UUID` row, once written, is read-only for analysis.
- Do not claim an indicator "caused" a profit. The system reports
  **observed relationships** between condition matches and outcomes, not
  causation. Never word a log or UI label as if a specific indicator
  produced the PnL.

## 7. Paper / testnet / live separation

- The three trading modes are defined in `app/config/settings.py` and
  the exchange factory. Do not collapse them or auto-promote a paper
  strategy to live.
- The exchange factory in `app/exchange/factory.py` chooses
  `PaperTradingAdapter` for `paper` and `backtest` modes. Do not change
  this routing.
- The `live_trading_enabled` flag in settings is the master switch.
  Code that submits orders must check it on every call, not cache the
  result at startup.
- `paper_config.json` and live config must remain separate files. Do
  not move live credentials into the paper config or vice versa.

## 8. Risk controls and emergency stop

- The risk engine, max position size, max daily loss, max drawdown, and
  the `/admin/risk/{action}` endpoints are protected code paths. Any
  change must be reviewed against the original PRD section and must
  come with a regression test that exercises the protection.
- Emergency stop must be reachable in one HTTP call and must not depend
  on the scanner being healthy. Do not introduce a "stuck running" state
  by removing the stale-state reconciliation in `app/api/control.py` or
  `app/api/routes/admin_routes.py`.
- The control-state machine in `app/api/control.py` (start, pause,
  resume, stop) is the source of truth for "is the bot running". Do
  not introduce a second source of truth.

## 9. Testing rules

- **Test every code change.** A change without a test is a draft, not a
  deliverable.
- **Run targeted tests first**, then the relevant full test suite:
  `pytest <test_file>::<test_name> -v`, then `pytest tests/<area> -v`,
  then `pytest --tb=short -q` for the full suite.
- Use `make test` as the canonical full-run command, or
  `pytest --tb=short -q` if the Makefile target is unavailable.
- **Never weaken a test to make it pass.** If a test breaks, the code
  is wrong, not the test. Add a new test that captures the new
  expected behavior, then change the code.
- **Never claim completion from unit tests alone** for changes that
  affect scanner, risk, or execution paths. Perform runtime verification
  with the live scanner (`GET /admin/scanner/diagnostics`,
  `GET /admin/audit/tail`) before reporting done.
- Test data must reflect Binance semantics: 1m candle starting at
  `18:36:00` has `open_time=18:36:00` and `close_time=18:37:00`
  (exclusive). A candle at `18:36:52` is in-progress.

## 10. Database rules

- Schema changes go through `app/database/migrations/`. The manifest in
  `app/database/migrations/_manifest.py` and the runner in
  `app/database/migration_runner.py` are the source of truth.
- Each migration gets its own numbered file (e.g. `016_xxx.sql`) and
  is added to the manifest list in order.
- Migrations must be **idempotent** — running them twice must not fail
  or duplicate. Use `IF NOT EXISTS`, `ADD COLUMN` with a check, or
  programmatic schema introspection in `migration_runner.py`.
- Never hand-edit the live `trading.db` in production-style code paths.
  For local drift, use `repair_migrations.py` or a one-off script and
  commit the script separately.
- Backfills run as part of the migration that introduces the column, not
  as a separate ad-hoc job.

## 11. API rules

- FastAPI routes live in `app/api/routes/`. Add a new route file only
  if the area is genuinely new; otherwise extend the existing file.
- Public APIs return JSON with stable keys. Renaming a response key is
  a breaking change — bump the route, do not silently rename.
- Admin endpoints are gated by `X-Admin-Token` (NOT `Authorization: Bearer`).
  Do not change the auth header.
- Error responses follow FastAPI's `HTTPException` model. Do not return
  bare 500s with stack traces. Include a `detail` field with a stable
  error code where possible.
- WebSocket endpoints (`/ws`, `/admin/ws`) must remain connection-safe:
  no shared mutable state between handlers.

## 12. Frontend rules

- The admin SPA lives in `admin-spa/` (Vite + React + TypeScript). Build
  output goes to `admin-spa/dist/` and is served by the FastAPI server.
- After any SPA change, run `cd admin-spa && npm run build` and restart
  the backend so the new bundle is served.
- Do not introduce a new UI framework or state library. The project uses
  React + plain `useState` / `useEffect` and a thin `api()` wrapper.
- Do not change unrelated UI. Feature work touches the relevant page only.
- Style additions go in `admin-spa/src/styles.css` as classes, not inline
  styles, unless the element is dynamic.

## 13. Performance and scanning

- The multi-symbol scanner evaluates hundreds of symbols per cycle.
  Avoid per-symbol database writes inside the hot loop. Use the
  in-cycle diagnostics counters and the `_seen` dedup set.
- Do not introduce a per-symbol HTTP call. Fetch candles in batch where
  the exchange supports it; otherwise reuse the existing `AdapterMarketDataProvider`.
- Indicator calculation must be done once per (symbol, strategy, cycle)
  and reused for condition evaluation. Do not recompute on every
  condition check.
- Diagnostics counters (`ScannerDiagnostics`) are per-cycle and reset
  on each `scan_once`. Lifetime stats live in `self._stats`.

## 14. Runtime verification

Before claiming a scanner, risk, or execution change is done, verify:

- `curl -s http://localhost:8000/health` returns
  `{"healthy":true,"mode":"paper","live_trading_enabled":false}`.
- `curl -s -H "X-Admin-Token: $ADMIN_API_TOKEN"
  http://localhost:8000/admin/scanner/diagnostics` shows
  `fresh_candles > 0`, no `STALE_CANDLE` errors, and
  `symbols_without_candles` count matches the empty-data expectation.
- `curl -s -H "X-Admin-Token: $ADMIN_API_TOKEN" http://localhost:8000/admin/audit/tail`
  shows the cycle summary, not per-symbol spam.
- Restart the server after backend code changes so the new code is
  loaded: kill port 8000, then `uvicorn app.api.server:app --host 0.0.0.0 --port 8000`.

## 15. Git and commits

- **Check `git diff` before committing.** `git status`, `git diff`, and
  `git diff --stat` are part of the commit ritual.
- **Do not commit unrelated changes.** If the diff contains more than
  the task requires, split it or revert the noise.
- Commit messages follow `type(scope): summary`:
  - `fix(scanner): ...` for bug fixes
  - `feat(signals): ...` for new features
  - `chore(scanner): ...` for audits, refactors with no behavior change
  - `test(scanner): ...` for test-only changes
- Each task is a separate commit. PRs may bundle several commits if they
  form one logical unit, but a single commit must not span two PRDs.
- Never commit secrets. `.env` is gitignored; `paper_config.json`
  contains no live keys. If a secret leaks, rotate it and amend.
- Push to `Kilwishhh/Bot03 master` only after the full test suite is
  green. Never push a failing test.

## 16. Reporting

When a task is done, report:

1. **Root cause** (one paragraph, plain language).
2. **Files changed** (list with line counts).
3. **Tests added or updated** (file names + count).
4. **Test results** (`pytest` output summary line).
5. **Runtime verification** (the curl commands and their relevant fields).
6. **Commit hashes** (local short + pushed remote).
7. **Live trading** (`live_trading_enabled: false` confirmed).
8. **Unrelated changes** ("None" or explicit list).

If a step is skipped, say why. Do not claim verification you did not
perform.

---

## 17. Out of scope for AGENTS.md

- Specific PRD task breakdowns live in `audit/*.md`. Each PRD is its own
  document; AGENTS.md does not duplicate them.
- Deployment specifics live in `DEPLOYMENT_ROADMAP.md` and
  `docker-compose.yml`.
- Style and lint rules live in `pyproject.toml` (`[tool.ruff]`).

If a future agent or human wants to amend these rules, the change is
made in this file, with its own commit, and noted in the PR description.

---

## 18. Persistent project maintenance record

This section is the durable project history for future Hermes/Copilot agents.
Read it before changing existing behavior. Preserve the safety rules above,
the beginner-friendly UX decisions, and the exchange-style position behavior
unless the user explicitly changes the requirements.

### Application purpose

Bot03 / MK TRADER is a FastAPI trading application with a React/Vite admin
SPA. It scans configured market symbols using Binance Futures market data,
evaluates user-created strategies, persists signals and trade history in
SQLite, routes accepted signals through the execution bridge, and manages
paper, testnet, or live positions with risk controls. Development and
verification must remain paper-only.

### Architecture and data flow

The normal flow is:

1. Strategy records are loaded by `app/database/repository.py`. Strategy
   configuration contains symbols, timeframe, direction, enabled indicators,
   indicator parameters, permissions, and `minimum_hits`.
2. `app/strategy/scanner.py` requests candles through the configured market
   data adapter, selects the last closed Binance candle, validates timestamp,
   timeframe, freshness, and closed status, and calculates indicators once per
   symbol/strategy/cycle.
3. The scanner evaluates either the legacy condition groups or the
   indicator-voting configuration. Voting returns LONG, SHORT, or NEUTRAL per
   enabled indicator. A signal is valid only when the selected direction has
   at least `minimum_hits` votes and is allowed by the strategy direction.
4. Valid signals are persisted as immutable snapshots in the `signals` table,
   including `confidence_hits`, `confidence_total`, derived confidence,
   indicator/condition results, entry, stop loss, take profit, strategy, and
   signal time.
5. `app/runtime.py` connects scanner output immediately to
   `app/execution/scanner_bridge.py`. The bridge performs mode checks, risk
   checks, sizing, order submission through the exchange adapter, and saves
   order/trade/position records. The bridge is the scanner-to-OrderManager
   handoff; do not reintroduce a polling-only gap.
6. `app/execution/position_watcher.py` polls Binance Futures public ticker
   prices (`https://fapi.binance.com/fapi/v1/ticker/price`), updates mark
   price and unrealized P&L, persists `updated_at`, and processes conditional
   TP/SL orders. Paper positions use the same watcher semantics as the
   exchange-facing flow.
7. `app/exchange/paper.py` simulates fills and maintains conditional orders.
   `app/exchange/binance_futures.py` sends actual Futures orders for testnet or
   live mode. `app/exchange/factory.py` routes paper and backtest to
   `PaperTradingAdapter`.
8. Full close removes the position snapshot and cancels remaining TP/SL
   orders. Partial fills reduce only the requested quantity and resize
   remaining brackets.

Important modules:

- `app/config/settings.py`: mode, credentials, risk, and
  `live_trading_enabled` settings.
- `app/exchange/base.py`: exchange-neutral order/cancellation contract.
- `app/exchange/models.py`: order, position, and trade models.
- `app/strategy/indicators.py`: stable indicator calculations and
  `compute_indicator_votes()`.
- `app/strategy/condition_engine.py`: legacy condition-group evaluation.
- `app/database/migrations/`: ordered, idempotent schema changes; migrations
  016 and 017 repair signal fields and add/backfill `positions.opened_at`.
- `app/database/repository.py`: persistence for strategies, signals, orders,
  trades, positions, and runtime snapshots.
- `app/api/control.py`: source of truth for start/pause/resume/stop state.
- `app/api/routes/admin_routes.py`: authenticated admin APIs, including
  strategy, signal, trade, position, reset, diagnostics, and lifecycle APIs.
- `admin-spa/src/pages/Strategies.tsx`: guided strategy builder.
- `admin-spa/src/pages/Signals.tsx`: persisted signal results and explanation
  drawer.
- `admin-spa/src/pages/Positions.tsx`: exchange-style position management.
- `admin-spa/src/utils/time.ts`: shared relative timestamp formatting.

### Strategy Builder and Signals UX

The builder intentionally uses a simple mental model: select indicators,
configure them, choose LONG/SHORT permissions, choose how many enabled
indicators must agree, preview the result, and save. It must not regress into
raw expressions, nested rule trees, or a separate confusing “entry rules”
system.

The six initial core indicators are RSI, MACD, EMA Crossover, Volume,
Bollinger Bands, and Stochastic. Defaults are visible and editable:

- RSI: period 14, oversold 30, overbought 70.
- MACD: fast 12, slow 26, signal 9.
- EMA Crossover: fast 20, slow 50.
- Volume: period 20.
- Bollinger Bands: period 20, standard deviation 2.
- Stochastic: %K 14, %D 3, smooth 3.

Every enabled indicator has independent LONG and SHORT permissions. Strategy
direction supports LONG + SHORT, LONG ONLY, or SHORT ONLY. The builder
computes the enabled indicator count dynamically: with M enabled indicators,
minimum rules is always 1 of M through M of M. Never restore a hard-coded 2,
6, 7, or another fixed count.

The preview explains LONG/SHORT/NEUTRAL votes and shows hits as `N/M`.
The Signals tab shows the actual persisted result, not a generic label:
symbol, timeframe, direction, confidence, agreeing indicators, entry, SL,
TP, strategy, signal time, and status. Indicator results must describe
observed agreement, not claim that an indicator caused profit.

### Positions UX and bracket behavior

The Positions tab is intentionally modeled after an exchange position screen.
Each open position shows symbol, side, entry, current Binance Futures mark
price, remaining quantity, unrealized P&L, position age, updated time, and
TP/SL status. Relative timestamps such as “1 min ago” are used throughout
the SPA instead of raw browser-local date strings.

Supported real controls are:

- **Close Position**: closes only the selected position.
- **Close All**: closes every currently open position through the existing
  execution adapter; it is not a demo action.
- **Partial Close / Book Profit**: accepts an absolute quantity or a
  percentage of the current position.
- **TP1/TP2/TP3**: each has its own trigger price and quantity percentage.
- **SL**: one protective stop for the remaining position.

The APIs are in `app/api/routes/admin_routes.py`:
`POST /admin/positions/{symbol}/close`,
`POST /admin/positions/close-all`,
`POST /admin/positions/{symbol}/partial-close`, and
`POST /admin/positions/{symbol}/brackets`.

TP/SL behavior is Binance-style for both LONG and SHORT. A triggered TP closes
only its allocation, then remaining TP/SL orders are resized to the remaining
position. Allocations over the current position are rejected. A full manual,
TP, or SL close cancels all sibling conditional orders. Conditional orders
must retain their requested quantity; storing zero quantity was a fixed bug
that previously caused triggers to cancel without reducing paper positions.

### Paper, Testnet, and Live

`TRADING_MODE=paper` and `live_trading_enabled=false` are the required
development defaults. Paper and backtest use `PaperTradingAdapter`; testnet
and live use `BinanceFuturesAdapter` with their appropriate endpoints and
credentials. Order submission must check the current master switch on every
call. Never copy live credentials into `paper_config.json`, and never enable
live trading for validation. Position-management endpoints use the running
execution bridge, so the bot runner must be active.

### Important configuration and defaults

- Default candle freshness threshold is 5 minutes.
- Binance candle `close_time` is exclusive; a candle is closed only when
  `now >= close_time`.
- Confidence is integer `confidence_hits` / `confidence_total`, displayed as
  `N/M`; do not replace it with a percentage-only setting.
- Position age is based on persisted `positions.opened_at`.
- Admin APIs require `X-Admin-Token` (session Bearer authentication also
  remains supported by the existing auth flow).
- The SPA is served by FastAPI, with `/` redirecting to `/admin` and nested
  admin routes using the SPA fallback.

### Problems found and fixes already completed

#### Scanner signals were not traded

The scanner was generating and logging database signals, but the runtime did
not immediately pass those results to OrderManager/execution. The
scanner-to-execution bridge was wired into `app/runtime.py` and
`app/execution/scanner_bridge.py`; signal persistence and execution decisions
are now observable through diagnostics. This was verified in paper mode.

#### `minimum_hits` was defeated by condition groups

The old condition-group path used an `all()`-style gate, so one failed
condition could prevent signal creation even when the configured minimum
number of hits was satisfied. Dynamic hit counting and minimum-hit gating were
implemented in `app/strategy/scanner.py` and covered by regression tests.

#### Strategy rule count was hard-coded

The Signals/Strategy UI previously exposed a hard-coded minimum value of 2
and did not stay valid when indicators were added or removed. The builder now
derives M from enabled indicator configuration and clamps minimum hits to the
current 1..M range.

#### Strategy configuration was too technical

The builder exposed confusing condition concepts and lacked a clear direction
model. It was replaced with six configurable core indicator cards, beginner
help text, editable defaults, explicit LONG/SHORT permissions, direction
presets, and a live vote preview. Backend voting in
`compute_indicator_votes()` ensures controls affect real signal generation.

#### Positions were too generic

The previous Positions screen did not provide exchange-style partial exits or
multi-level brackets. Real close, close-all, partial-close, and bracket APIs
were added, with paper conditional fills, remaining-order resizing, and
automatic sibling cancellation. The UI controls call these APIs rather than
simulating state locally.

#### Other repaired operational issues

- Idempotent migration handling fixed “failed to fetch” startup failures.
- Signal/trade persistence and frontend authentication were repaired.
- Exit-price propagation and closed-trade P&L persistence were corrected.
- Paper long/short unrealized P&L and watcher persistence were added.
- Binance Futures public ticker prices replaced stale/non-exchange mark prices.
- `opened_at` migration and relative timestamps were added.
- Reset Data now supports paper, testnet, live, or all with explicit
  confirmation query handling.
- Root/nested SPA routing, Settings health fields, restart, Dashboard stop,
  pause/resume, synchronization, and status reporting were repaired.

### Current limitations and pending work

- Full end-to-end bracket behavior should continue to be tested with a
  controlled paper position after any execution change; testnet/live should
  never be used with real funds for development verification.
- Position listing is currently based on persisted local snapshots enriched
  with running-bridge bracket orders. A future reconciliation feature may
  compare persisted rows with exchange-side testnet/live positions.
- Bracket metadata is primarily represented by exchange conditional orders;
  if configuration must survive a process restart independently of open orders,
  add an explicit idempotent migration and immutable event/history design.
- `Close All` should eventually return per-symbol success/failure details
  rather than stopping at the first exception.
- Existing local debug files are not project documentation and must not be
  committed if they contain tokens, credentials, or runtime logs.

### Verification record

The following work was completed and pushed in separate logical commits
through `6191956` (position management is the latest):

- Full suite passed at `507 passed` before the final position edits.
- Position watcher/execution targeted tests passed: `16 passed` after the
  final position edits.
- Admin SPA production build passed after the final position edits.
- Python diagnostics were clean after the final position edits.
- Runtime health was verified in paper mode with
  `healthy: true`, `mode: paper`, and `live_trading_enabled: false`.
- Scanner runtime and paper execution were started and inspected through
  admin diagnostics. A Close All smoke test intentionally closed the local
  paper positions present at that time.

For future validation, use targeted tests first, then the relevant area, then
the full suite:

```powershell
pytest tests/test_scanner_execution_pipeline.py -v
pytest tests/test_condition_confidence.py -v
pytest tests -v
pytest --tb=short -q
Set-Location admin-spa
npm run build
```

For scanner/execution changes, also verify:

```powershell
curl -s http://localhost:8000/health
curl -s -H "X-Admin-Token: $env:ADMIN_API_TOKEN" http://localhost:8000/admin/scanner/diagnostics
curl -s -H "X-Admin-Token: $env:ADMIN_API_TOKEN" http://localhost:8000/admin/audit/tail
```

### Change log protocol for future agents

Whenever a feature, bug fix, architecture change, or important decision is
made, append a dated entry here containing:

- Date
- Problem or feature
- Root cause or reason
- Change made
- Files/modules affected
- Tests performed
- Current status
- Important future considerations

The current record date is **2026-09-04**. The latest committed feature is
`6191956 feat(positions): add exchange-style position management`.
