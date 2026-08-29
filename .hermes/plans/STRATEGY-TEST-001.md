# STRATEGY-TEST-001: RSI Reversion 1M Paper Test

## Goal
End-to-end test fixture for the new per-user Strategy/Signal/FollowUp/Automation/Publishing pipeline. NOT a production profitability strategy.

## Current state (inspected)
- `RSIMeanReversionStrategy` already exists in `app/strategy/rsi_mean_reversion.py`
- Per-user `strategies` table + `StrategyService` + `StrategyLifecycle` all in place
- Per-user `signals` table + `SignalService` in place
- `signal_followups` table + `FollowupService` in place
- `automation_rules` + `AutomationEngine` with thread pool, dedup_key, async actions
- `PublishingService` with Telegram + Binance Square + 3-way limit behavior
- `PaperTradingAdapter` (deterministic, no network)
- `AuditModule` for audit logging
- `EmergencyService` for pause
- All 22 DB tables created, 182 tests passing

## Phase 1: Seed script + test user (single Python module)
**File:** `app/seed/rsi_reversion_test.py`

- Idempotent: safe to run multiple times
- Creates test user `test@local.dev` (skips if exists, looks up password)
- Creates Strategy record with config:
  - name="RSI Reversion 1M Test"
  - type=mean_reversion, environment=test
  - timeframe=1m, market=BTCUSDT (primary)
  - execution_mode=paper, execution_venue=binance
  - entry_config: indicators=[rsi(14)], conditions=[rsi<=30 LONG, rsi>=70 SHORT]
  - exit_config: tp1_pct=0.003, tp2_pct=None, stop_loss_pct=0.005
  - risk_config: cooldown_seconds=180, max_open_positions_per_symbol=1
  - template_name=rsi_reversion_1m_test
- Seeds 3 automation rules:
  - signal_generated → create_paper_trade + publish_telegram + publish_square
  - tp1_hit → create_followup + publish_telegram
  - sl_hit → create_followup + publish_telegram
- Seeds publishing config:
  - telegram_enabled=false (no token in test env)
  - square_enabled=true
  - square_daily_limit=10
  - square_limit_behavior=telegram_only
- Returns: `{user_id, strategy_id, rule_ids: [...]}`

## Phase 2: Dev simulation endpoint
**File:** `app/api/routes/dev_routes.py`

- `POST /dev/strategies/{strategy_id}/simulate-signal`
- Body: `{symbol: "BTCUSDT", direction: "long|short", entry_price: 50000, candle_time: "..."}`
- Creates a real Signal record with:
  - mode=PAPER, signal_status=CREATED
  - trading_status=PENDING, telegram_status=PENDING, square_status=PENDING
  - entry_price, tp1=entry*(1±0.003), stop_loss=entry*(1∓0.005)
  - candle_id = candle_time (idempotency key)
- Duplicate check: if signal with same strategy_id+symbol+candle_id exists → return existing
- Fires `automation_engine.on_signal_generated()` — this calls automation rules
- Rules execute: create_paper_trade (via signal → order_manager) + publish_telegram + publish_square
- PAPER-only safety: if `payload.get("force_live", false) == true` → 403
- Dev-only: rejects when `ENVIRONMENT` env is `production`

## Phase 3: Backend tests (pytest)
**File:** `tests/test_rsi_reversion_1m_test.py`

Tests A–I from the spec:
- A: LONG signal at RSI<=30 → persists, paper trade attempted, audit logged
- B: SHORT signal at RSI>=70 → persists, paper trade attempted
- C: RSI=50 → no signal
- D: Same candle twice → exactly 1 signal, exactly 1 paper trade
- E: LONG TP hit → position closes, followup=TP, status=CLOSED, P&L recorded
- F: LONG SL hit → position closes, followup=SL
- G: SHORT TP at lower price → closes successfully
- H: Square limit=1, first=PUBLISHED, second=SKIPPED_LIMIT, Telegram still attempted
- I: Attempt transition to LIVE for this strategy → 400 LifecycleError

## Phase 4: Paper-only safety
- The seeded strategy has `lifecycle_state=paper` initially
- `_validate_live_requirements()` in `strategy_lifecycle.py` requires:
  - exchange_connection (none exists for test user)
  - risk_config
  - no_active_pause
  - confirm_live=true + "I_UNDERSTAND_LIVE_RISK"
- Without exchange connection, the test strategy can NEVER reach LIVE
- This is enforced by `StrategyLifecycle.transition()` — no new code needed

## Phase 5: Wire to UI (no hardcoded strategy page)
- The seeded strategy is just a row in the strategies table
- The existing dashboard `StrategiesPage` + `StrategyDetailPage` + `SignalsPage` will show it
- No new React components

## What I will NOT do
- ❌ Create new React pages
- ❌ Modify the existing signal/paper/followup engines (they already work)
- ❌ Add new DB tables (all required tables exist)
- ❌ Add Telegram/Square API key persistence
- ❌ Run the live bot continuously (paper only, manual test)

## Verification
- 182 existing tests + ~9 new tests = 191 tests
- Manual: run `python -m app.seed.rsi_reversion_test` → confirm strategy in DB
- Manual: POST `/dev/strategies/{id}/simulate-signal` → confirm signal + followup created
- Manual: attempt LIVE transition → 400
