# MOBILE-FIRST CRYPTO STRATEGY LAB & TRADING SAAS

## Master PRD + Implementation Specification for Claude Code / Cursor / Codex / Gemini Coding Agents

---

# 0. BUILD PHILOSOPHY

Build a mobile-first crypto trading research and paper-trading platform that can later become a multi-user SaaS.

The first objective is NOT profitability.

The first objective is:

* reliable architecture
* strategy experimentation
* backtesting
* paper trading
* Binance Testnet execution
* risk management
* accurate PnL
* mobile monitoring
* strategy versioning
* clean modularity
* SaaS-ready multi-tenancy

Do NOT build a giant monolithic trading bot.

The system must separate:

MARKET DATA
STRATEGY
SIGNALS
RISK
POSITION SIZING
EXECUTION
EXCHANGE
PORTFOLIO
DATABASE
BACKTESTING
NOTIFICATIONS
API
MOBILE UI

A strategy must be replaceable without rewriting the trading engine.

---

# 1. PRODUCT VISION

The product is a mobile-first application where a user can:

1. Create an account.
2. Create a strategy.
3. Configure strategy parameters.
4. Run historical backtests.
5. Analyze results.
6. Run paper trading.
7. Run Binance Testnet.
8. Monitor positions and PnL live.
9. Stop/start bots from mobile.
10. Change strategy parameters.
11. Compare multiple strategies.
12. View complete trade history.
13. Receive notifications.

Later:

14. Connect Binance live account.
15. Invite friends.
16. Support multiple users.
17. Add subscriptions.
18. Launch as SaaS.

---

# 2. CRITICAL PRODUCT RULE

The mobile application is NOT the trading engine.

Never run the actual trading engine only inside a mobile phone.

Architecture:

Mobile App
↓
Backend API
↓
Trading Engine
↓
Exchange Adapter
↓
Binance

The mobile app is a control/monitoring client.

The backend is responsible for:

* strategies
* market data
* bot execution
* risk
* positions
* orders
* PnL
* databases
* notifications

This allows the bot to continue running when the mobile app is closed.

---

# 3. PRODUCT MODES

The system must support:

## MODE 1 — BACKTEST

Historical data only.

No real orders.

## MODE 2 — PAPER

Simulated wallet and simulated execution.

No exchange order is created.

## MODE 3 — TESTNET

Real Binance Testnet API orders.

No real funds.

## MODE 4 — LIVE

Real Binance account.

Disabled by default.

Live mode must require explicit confirmation.

---

# 4. FIRST RELEASE SCOPE

The first release MUST focus on:

* user authentication
* mobile dashboard
* strategy management
* backtesting
* paper trading
* Binance Testnet
* basic Binance Futures support
* risk management
* trade history
* PnL
* notifications
* bot start/stop
* strategy parameter editing

Do NOT build billing initially.

However, the database and architecture MUST be SaaS-ready.

---

# 5. REFERENCE PROJECTS

Use the following projects as architectural references.

## Existing user-selected projects

1. KhushiThakur-AI/Crypto-Trading-Bot

   * indicator strategy
   * risk concepts
   * monitoring/logging

2. l0ller/binance-futures-bot

   * Binance Futures order handling
   * positions/orders
   * CLI interaction

3. frostyalce000/paper-trading-binance

   * Testnet paper-trading foundation
   * simple signal → order flow

## Additional references

4. Freqtrade

   * strategy architecture
   * dry-run
   * backtesting
   * persistence
   * strategy optimization concepts

5. Hummingbot

   * modular trading architecture
   * connectors
   * executors
   * strategy/controller separation

6. CCXT

   * exchange abstraction
   * normalized exchange interfaces

7. FastAPI SaaS starter patterns

   * authentication
   * organizations
   * RBAC
   * tenant isolation

8. Hummingbot API

   * API-controlled trading engine architecture

IMPORTANT:

Do NOT blindly merge these repositories.

Inspect architecture and reuse only code/components that are:

* technically compatible
* properly licensed
* actually useful
* maintained enough for the intended purpose

If a repository has no clear compatible license, do NOT copy its code.

Use its architecture as reference only.

---

# 6. LICENSE POLICY

Before copying any external code:

1. Find LICENSE.
2. Record license.
3. Verify compatibility with this project.
4. Preserve required copyright/license notices.
5. Add THIRD_PARTY_NOTICES.md.

If license is unclear:

DO NOT COPY CODE.

Architecture and ideas can be independently reimplemented.

Prefer MIT / Apache-2.0 compatible components where practical.

---

# 7. RECOMMENDED TECH STACK

## Mobile

Use:

React Native + Expo

or another mature cross-platform mobile framework.

Prefer TypeScript.

Mobile targets:

* Android
* iOS

The first development target should be Android.

---

# 8. BACKEND

Use:

Python
FastAPI
Pydantic
SQLAlchemy
Alembic
PostgreSQL

Use Redis for:

* caching
* job queues
* pub/sub
* real-time bot events

Use WebSockets for:

* live dashboard updates
* bot status
* PnL
* signals
* order updates

---

# 9. TRADING ENGINE

The trading engine should be a separate Python module/service.

Recommended conceptual architecture:

Trading Engine
├── Market Data
├── Strategy Engine
├── Signal Engine
├── Risk Engine
├── Position Sizer
├── Execution Engine
├── Position Manager
├── Portfolio Manager
└── Reconciliation Engine

The FastAPI backend controls this engine.

---

# 10. DATABASE

Use PostgreSQL.

Every user-owned trading object must include:

user_id

and where applicable:

workspace_id / organization_id

Core tables:

users
organizations
memberships
strategies
strategy_versions
strategy_parameters
bots
bot_runs
exchange_accounts
exchange_credentials
market_data_sources
signals
orders
positions
trades
balances
pnl_snapshots
backtests
backtest_trades
backtest_metrics
notifications
audit_logs

---

# 11. MULTI-TENANCY

Implement SaaS-ready tenant isolation from day one.

Every user must only be able to access their own:

* strategies
* bots
* trades
* API credentials
* backtests
* PnL
* positions
* notifications

Never trust a client-provided user_id.

Always derive identity from authenticated session/token.

All queries must be tenant/user scoped.

Add automated tests attempting cross-user access.

Those tests must fail safely.

---

# 12. AUTHENTICATION

Implement:

* registration
* login
* logout
* refresh token
* password hashing
* password reset architecture
* email verification architecture

Optional later:

* Google login
* Apple login
* 2FA

Use secure token handling.

Do not store plaintext passwords.

---

# 13. USER ROLES

Initially:

USER

Later:

OWNER
ADMIN
MEMBER

Design RBAC so it can be enabled later without restructuring the database.

---

# 14. EXCHANGE ACCOUNT MANAGEMENT

Users should be able to add:

Binance

Later:

Bybit
OKX
Coinbase
etc.

Do not make Binance-specific code spread throughout the application.

Create:

ExchangeAdapter

Interface.

Example:

get_balance()
get_positions()
get_open_orders()
get_market_data()
place_order()
cancel_order()
get_order()
set_leverage()
get_exchange_info()

Implement:

BinanceFuturesAdapter

Later:

PaperTradingAdapter

---

# 15. API CREDENTIAL SECURITY

Never store raw API secrets in normal database columns.

Encrypt credentials at rest.

Use application-level encryption.

The encryption master key must come from environment/secret management.

Never:

* return secret values to frontend
* log secret values
* send secrets to analytics
* expose them through API responses

Allow users to revoke/delete credentials.

---

# 16. BINANCE SUPPORT

Initial target:

Binance USDⓈ-M Futures Testnet.

Support:

* market data
* account balance
* positions
* orders
* market order
* limit order
* stop-market
* take-profit-market
* leverage
* position information
* order status
* cancellation

Use official/current Binance APIs or a well-maintained compatible library.

Do not depend on outdated Binance libraries simply because one old repository uses them.

---

# 17. EXCHANGE ABSTRACTION

The Strategy layer MUST NOT know Binance exists.

Bad:

strategy.py → Binance API

Correct:

strategy.py
↓
Signal
↓
Risk
↓
Execution
↓
ExchangeAdapter
↓
Binance

This is mandatory.

---

# 18. MARKET DATA

Support:

OHLCV
ticker
orderbook
trades

Initial candle timeframes:

1m
5m
15m
30m
1h
4h
1d

Make everything configurable.

Avoid requesting excessive data.

Cache historical candles.

Use WebSockets for real-time updates where practical.

Handle:

* reconnect
* stale data
* missing candles
* duplicate candles
* API rate limits
* timestamp mismatch

---

# 19. STRATEGY SYSTEM

This is the MOST IMPORTANT part.

Strategy must be a plugin.

Interface:

Strategy

Methods:

initialize()
calculate_indicators()
generate_signal()
validate_signal()

Output:

Signal

Signal contains:

symbol
timeframe
side
confidence
timestamp
strategy_id
strategy_version
reason
metadata

Possible signal:

BUY
SELL
HOLD

---

# 20. STRATEGY EDITING

The user should NOT need to edit Python code for normal parameter changes.

Example:

EMA Fast = 20
EMA Slow = 50
RSI Period = 14
RSI Buy Threshold = 55
RSI Sell Threshold = 45
Stop Loss = 1%
Take Profit = 2%

These should be editable from the mobile app.

Store strategy parameters in database.

Every parameter change creates a new strategy version.

NEVER silently modify an existing strategy version used by a running bot.

---

# 21. STRATEGY VERSIONING

Example:

MyStrategy v1
MyStrategy v2
MyStrategy v3

Each version stores:

* parameters
* strategy code/version identifier
* created_at
* author
* notes
* backtest results
* paper-trading results

A bot run must reference an immutable strategy version.

This makes results reproducible.

---

# 22. INITIAL DEMO STRATEGY

Create an example technical-analysis strategy.

Indicators:

EMA
RSI
MACD
ADX
Bollinger Bands

This is NOT claimed to be profitable.

Purpose:

test the entire platform.

Example:

BUY if:

EMA fast > EMA slow
AND RSI > threshold
AND MACD bullish
AND ADX > threshold

SELL if inverse conditions occur.

HOLD otherwise.

All thresholds configurable.

---

# 23. SIGNAL CONFIDENCE

Support a confidence score:

0.0 → 1.0

Example:

EMA = +0.20
RSI = +0.20
MACD = +0.20
ADX = +0.20
Bollinger = +0.20

Total:

0.80

The confidence calculation must be strategy-specific.

Do NOT hardcode confidence logic into the risk engine.

---

# 24. RISK ENGINE

Every signal MUST pass through RiskEngine.

RiskEngine checks:

* account balance
* risk per trade
* daily loss
* max drawdown
* max open positions
* max symbol exposure
* leverage
* minimum confidence
* cooldown
* duplicate position
* maximum notional
* available margin

If rejected:

NO ORDER.

Record rejection reason.

---

# 25. POSITION SIZING

Never use fixed quantity by default.

Use risk-based position sizing.

Example:

risk_amount =
equity × risk_per_trade

position_size =
risk_amount / stop_distance

Then validate:

* min quantity
* step size
* tick size
* min notional
* available margin
* leverage

Always use Decimal where financial precision matters.

---

# 26. FUTURES RISK

Support:

* isolated margin
* leverage
* long
* short

Initially default to:

ISOLATED

with conservative leverage.

Never default to 50x/100x/125x.

Add liquidation-distance monitoring.

If liquidation risk becomes unsafe:

* stop new entries
* notify user
* optionally reduce/close according to configured emergency policy

---

# 27. STOP LOSS

Support:

1. percentage SL
2. ATR SL
3. structure-based SL
4. strategy-provided SL

Risk engine must validate the resulting stop distance.

---

# 28. TAKE PROFIT

Support:

1. fixed percentage
2. risk/reward ratio
3. multiple TP levels

Example:

TP1 = 1R
TP2 = 2R
TP3 = 3R

Future support:

partial close

---

# 29. TRAILING STOP

Support optional trailing stop.

Parameters:

trailing activation
trailing distance
minimum profit

Trailing stop must never move backwards in a way that increases risk.

---

# 30. ORDER ENGINE

OrderManager handles:

* validation
* submission
* status
* fills
* cancellation
* retries
* reconciliation

Never assume:

API success = order filled.

Always query/receive actual order status.

---

# 31. TP/SL PROTECTION

If exchange does not provide native OCO suitable for the exact futures workflow:

Create a safe order-management mechanism.

When position opens:

1. verify fill
2. calculate TP
3. calculate SL
4. create protection orders
5. verify both
6. monitor

If TP executes:

cancel SL
verify position state

If SL executes:

cancel TP
verify position state

If either protection order fails:

STOP NEW TRADES FOR THAT POSITION
and trigger emergency notification.

Never leave a position silently unprotected.

---

# 32. RECONCILIATION

This is mandatory.

Periodically compare:

LOCAL DATABASE

vs

BINANCE

for:

* positions
* orders
* balances
* fills

If mismatch:

* mark system DEGRADED
* stop new entries
* reconcile
* notify user

Do not blindly continue trading.

---

# 33. PAPER TRADING ENGINE

Implement a realistic paper engine.

It should simulate:

* market orders
* limit orders
* fills
* fees
* slippage
* balance
* positions
* TP
* SL
* PnL

Paper trading must NOT simply assume:

entry price = candle close.

Use configurable execution assumptions.

---

# 34. BACKTESTING ENGINE

Build a backtester inspired by mature systems such as Freqtrade.

Input:

historical OHLCV

Output:

trades
equity curve
metrics

Metrics:

total return
net PnL
gross PnL
fees
win rate
profit factor
expectancy
average win
average loss
max drawdown
Sharpe
Sortino
number of trades
long/short breakdown

---

# 35. BACKTEST REALISM

Backtesting must account for:

* trading fees
* slippage
* spread assumptions
* candle execution limitations

Never use future data.

Avoid look-ahead bias.

Clearly label assumptions.

---

# 36. OUT-OF-SAMPLE TESTING

Support:

TRAIN
VALIDATION
TEST

or:

IN-SAMPLE
OUT-OF-SAMPLE

Never present optimized in-sample results as proof of future profitability.

---

# 37. PAPER VS BACKTEST COMPARISON

Allow user to compare:

Backtest
vs
Paper trading

Metrics:

win rate
PnL
drawdown
trade frequency
average trade
entry/exit difference

This helps identify unrealistic backtest assumptions.

---

# 38. BOT MANAGEMENT

Users can create multiple bots.

Example:

BTC EMA Bot
ETH Momentum Bot
BTC Scalper
Strategy Test #4

Each bot contains:

strategy_version
exchange_account
symbols
timeframes
risk configuration
mode
status

Statuses:

STOPPED
STARTING
RUNNING
PAUSED
ERROR
DEGRADED

---

# 39. MOBILE DASHBOARD

Home screen should show:

Total Equity
Today PnL
Open PnL
Total PnL
Win Rate
Active Bots
Open Positions

Use clear color coding:

green = positive
red = negative
neutral = no change

Avoid clutter.

---

# 40. BOT DETAIL SCREEN

Show:

Bot name
Strategy
Version
Mode
Status
Symbol
Timeframe
Risk
Leverage

Current:

Position
Entry
Mark
SL
TP
PnL

Buttons:

START
STOP
PAUSE

---

# 41. STRATEGY SCREEN

Show:

Strategy name
Version
Status

Parameters:

EMA Fast
EMA Slow
RSI
MACD
ADX
Bollinger
SL
TP
Risk

Actions:

SAVE AS NEW VERSION
BACKTEST
PAPER TEST
DEPLOY TO BOT

---

# 42. BACKTEST SCREEN

Inputs:

Strategy
Version
Symbol
Timeframe
Start date
End date
Initial balance
Fees
Slippage

Results:

Net PnL
Return %
Win Rate
Profit Factor
Max Drawdown
Sharpe
Trades

Charts:

Equity Curve
Drawdown
PnL by day
Trade distribution

---

# 43. TRADE HISTORY

Filters:

symbol
bot
strategy
date
side
profit/loss

Show:

entry
exit
quantity
PnL
fees
duration
reason

---

# 44. LIVE SIGNALS

Show:

symbol
strategy
side
confidence
timestamp
reason

Example:

BTCUSDT
BUY
82%

Reasons:

EMA bullish
MACD positive
RSI confirmation

---

# 45. NOTIFICATIONS

Support push notifications.

Notify:

bot started
bot stopped
signal generated
trade opened
trade closed
TP
SL
daily loss limit
API error
reconciliation error
connection lost

Telegram can be added as optional secondary channel.

---

# 46. REAL-TIME COMMUNICATION

Use WebSockets or Server-Sent Events.

Mobile app should receive:

* bot status
* new signal
* order update
* position update
* PnL update

Do not poll every second unnecessarily.

This reduces backend/API load.

---

# 47. API DESIGN

Example:

POST /auth/register
POST /auth/login

GET /me

GET /strategies
POST /strategies
POST /strategies/{id}/versions

POST /strategies/{id}/backtest

GET /bots
POST /bots
POST /bots/{id}/start
POST /bots/{id}/stop

GET /positions
GET /orders
GET /trades
GET /pnl

GET /dashboard

POST /exchange-accounts

GET /signals

GET /notifications

WebSocket:

/ws/dashboard
/ws/bot/{bot_id}

---

# 48. API SECURITY

Every endpoint must enforce authentication.

Every resource must verify ownership.

Example:

GET /bots/123

must NOT return another user's bot.

Return 404 rather than leaking whether another user's object exists.

Add authorization tests.

---

# 49. ADMIN SYSTEM

Prepare architecture for:

Admin dashboard

Admin can later see:

users
active bots
system health
exchange errors
usage
subscriptions

But do NOT build a huge admin panel in MVP.

---

# 50. SAAS PREPARATION

Database must support:

organizations
memberships
plans
subscriptions
usage

But billing can remain disabled.

Later integrate Stripe.

---

# 51. FUTURE BILLING

Design feature flags:

BILLING_ENABLED=false

Later support:

FREE
PRO
PREMIUM

Possible limits:

Free:

1 strategy
1 bot
limited backtests

Pro:

multiple bots
advanced backtests
notifications

Premium:

more bots
advanced analytics
higher execution limits

Do not implement payment logic in MVP.

---

# 52. USAGE METERING

Prepare counters for:

backtests
bot runtime
API calls
market data usage
number of bots
number of strategies

This will make future SaaS billing easier.

---

# 53. PERFORMANCE

Do not run heavy backtests inside normal API request threads.

Use background jobs.

Architecture:

API
↓
Job Queue
↓
Backtest Worker
↓
Database
↓
WebSocket notification

Similarly bot lifecycle operations should be handled by worker/engine processes.

---

# 54. REDIS

Use Redis for:

* job queue
* pub/sub
* cache
* distributed locks
* temporary bot state

Avoid storing permanent trading records only in Redis.

---

# 55. BOT LOCKING

Prevent two workers from accidentally running the same bot.

Use a distributed lock.

Example:

bot:{bot_id}:lock

Only one execution worker can own the bot.

---

# 56. IDEMPOTENCY

Order placement is dangerous.

Implement idempotency/client order IDs.

If a request times out:

DO NOT blindly place another order.

First check whether the previous order exists.

---

# 57. DATABASE TRANSACTIONS

Use transactions for:

* trade creation
* order state changes
* strategy version creation
* bot state transitions

Never update PnL partially.

---

# 58. AUDIT LOG

Record important actions:

user login
strategy created
strategy changed
bot started
bot stopped
risk settings changed
exchange account added
exchange account removed
order placed
order cancelled
live mode enabled

This will become important for SaaS.

---

# 59. OBSERVABILITY

Provide:

structured logs
health endpoint
database health
exchange health
worker health

Example:

GET /health

Return:

API
DATABASE
REDIS
EXCHANGE
WORKERS

status.

---

# 60. ERROR RECOVERY

Bot should recover from:

* WebSocket disconnect
* API timeout
* Redis reconnect
* worker restart
* database reconnect

After restart:

1. load bot state
2. query exchange
3. reconcile
4. resume only if state is safe

---

# 61. MOBILE UX

Mobile-first.

Bottom navigation:

HOME
BOTS
STRATEGIES
TRADES
SETTINGS

Keep critical actions within 1–2 taps.

Use confirmation for:

STOP BOT
DELETE STRATEGY
CONNECT EXCHANGE
ENABLE TESTNET
ENABLE LIVE

---

# 62. LIVE TRADING SAFETY

Live trading must have multiple safeguards.

Required:

LIVE_TRADING_ENABLED=false

Even if configuration changes to true, mobile UI must show:

"REAL MONEY MODE"

Require explicit confirmation.

Optionally require typing:

I UNDERSTAND

before enabling.

---

# 63. API KEY PERMISSIONS

For Binance:

Prefer:

read + futures trading

Disable withdrawal permissions.

Never request withdrawal access.

Show security guidance to users.

---

# 64. STRATEGY MARKETPLACE — FUTURE

Do NOT implement now.

But architecture may later support:

public strategies
private strategies
strategy sharing
strategy templates
ratings
strategy cloning

---

# 65. FRIEND/BETA USER SYSTEM

Later allow:

invite user
workspace
shared strategy
shared bot

But initially keep accounts isolated.

---

# 66. TESTING

Use pytest.

Test:

authentication
tenant isolation
strategy
signals
risk
position sizing
precision
orders
PnL
backtesting
paper trading
reconciliation

Critical:

test that user A cannot access user B's:

bots
strategies
trades
credentials
backtests

---

# 67. EXCHANGE MOCKS

Unit tests must not call real Binance.

Create:

FakeExchange
MockExchange
PaperExchange

Use these for tests.

---

# 68. TESTNET INTEGRATION

Create optional integration tests using Binance Testnet.

These tests should be manually enabled.

Never run them automatically in normal CI.

---

# 69. CI/CD

Use GitHub Actions.

Pipeline:

lint
type check
unit tests
build backend
build mobile/web where appropriate

Do not run live trading tests in CI.

---

# 70. DOCKER

Create:

Dockerfile

docker-compose.yml

Services:

api
worker
postgres
redis

Optional:

dashboard

The trading worker should run independently from the API.

---

# 71. PROJECT STRUCTURE

Recommended:

project/

apps/

```
api/
  app/
    api/
    auth/
    users/
    strategies/
    bots/
    backtests/
    trading/
    notifications/
    exchange/
    database/
    websocket/

worker/
  trading_worker/
  backtest_worker/

mobile/
  src/
    screens/
    components/
    navigation/
    services/
    stores/
    hooks/
    types/
```

packages/

```
trading-core/
  strategy/
  signals/
  risk/
  execution/
  portfolio/
  backtesting/

exchange/
  base.py
  binance.py
  paper.py
```

infrastructure/

```
docker/
migrations/
```

tests/

```
unit/
integration/
security/
```

docs/

THIRD_PARTY_NOTICES.md

README.md

---

# 72. CODE REUSE STRATEGY

To reduce development time and AI token usage:

DO NOT ask the coding agent to recreate mature libraries.

Use existing packages for:

* exchange connectivity
* database ORM
* authentication
* charts
* indicators
* background jobs
* WebSockets

Potential references:

Freqtrade → strategy/backtest ideas

Hummingbot → trading engine architecture

CCXT → exchange abstraction

FastAPI SaaS starters → authentication/multi-tenancy

Use the source repositories as reference when necessary.

Do not copy entire repositories.

Copy only small, clearly licensed, useful components if license permits.

Prefer dependency/package usage over copying code.

---

# 73. TOKEN-SAVING CODING AGENT RULES

The coding agent MUST follow these rules.

1. NEVER rewrite an existing file unless necessary.

2. Before coding, inspect repository structure.

3. Search existing code before creating a new utility.

4. Reuse existing components.

5. Do not regenerate unchanged files.

6. Do not print entire files after every change.

7. Report only:

   * changed files
   * important changes
   * tests

8. Work in phases.

9. Do not implement future features early.

10. Do not create duplicate abstractions.

11. Use existing open-source libraries where appropriate.

12. Do not generate mock functionality pretending to be complete.

13. Do not fabricate API responses.

14. If an external library already solves the problem reliably, use it instead of implementing it from scratch.

---

# 74. CODING AGENT WORKFLOW

Before writing code:

STEP 1:
Inspect repository.

STEP 2:
Create architecture document.

STEP 3:
Identify reusable dependencies.

STEP 4:
Identify files that already exist.

STEP 5:
Create implementation plan.

Then implement one phase at a time.

---

# 75. DEVELOPMENT PHASES

## PHASE 0 — ARCHITECTURE

Create:

docs/ARCHITECTURE.md

docs/DECISIONS.md

docs/SECURITY.md

docs/THIRD_PARTY.md

No major implementation yet.

---

## PHASE 1 — FOUNDATION

Build:

PostgreSQL
Redis
FastAPI
authentication
user model
database migrations
Docker

Acceptance:

User can register/login.

---

## PHASE 2 — MOBILE APP

Build:

login
home
bots
strategies
trades
settings

Connect to API.

Acceptance:

User can log in and view dashboard.

---

## PHASE 3 — STRATEGY ENGINE

Build:

Strategy interface
Signal model
Example EMA/RSI/MACD strategy

Acceptance:

Historical candles produce deterministic signals.

---

## PHASE 4 — BACKTEST

Build:

historical data
simulation
fees
slippage
metrics
equity curve

Acceptance:

A strategy can be backtested from the mobile UI.

---

## PHASE 5 — PAPER TRADING

Build:

PaperExchange
paper wallet
fills
positions
PnL
SL
TP

Acceptance:

Bot can run for hours without exchange credentials.

---

## PHASE 6 — BINANCE TESTNET

Build:

Binance adapter
account
positions
orders
fills
reconciliation

Acceptance:

Testnet trade lifecycle works correctly.

---

## PHASE 7 — RISK

Build:

position sizing
risk per trade
daily loss
max positions
leverage limits
cooldown
emergency stop

Acceptance:

Unsafe orders are rejected.

---

## PHASE 8 — BOT WORKERS

Build:

bot manager
background workers
Redis locks
start/stop
restart/recovery

Acceptance:

Mobile app can start/stop a persistent backend bot.

---

## PHASE 9 — REAL-TIME

Build:

WebSocket
live PnL
position updates
signals
notifications

Acceptance:

Mobile dashboard updates without aggressive polling.

---

## PHASE 10 — STRATEGY VERSIONING

Build:

strategy versions
parameter snapshots
backtest association
bot association

Acceptance:

Running bot always uses immutable strategy version.

---

## PHASE 11 — SECURITY HARDENING

Build:

encrypted credentials
rate limiting
audit logs
tenant isolation
security tests

Acceptance:

Cross-user access tests pass.

---

## PHASE 12 — LIVE MODE

ONLY after:

paper testing
testnet testing
reconciliation
risk tests
security tests

Implement:

LIVE mode

with multiple confirmations.

---

## PHASE 13 — SAAS

Later:

organizations
invitations
billing
Stripe
plans
usage limits
admin panel

---

# 76. ACCEPTANCE TEST

The final MVP must demonstrate this exact workflow:

USER

↓ login

↓ create strategy

↓ set parameters

↓ save strategy v1

↓ run backtest

↓ see metrics

↓ create bot

↓ select strategy v1

↓ choose PAPER

↓ choose BTCUSDT

↓ choose timeframe

↓ set risk

↓ START

↓ bot receives market data

↓ strategy generates signal

↓ risk validates signal

↓ paper order executes

↓ position opens

↓ SL/TP managed

↓ position closes

↓ PnL calculated

↓ trade stored

↓ mobile dashboard updates

This complete flow must work before claiming MVP completion.

---

# 77. SECOND ACCEPTANCE TEST

Same workflow using:

BINANCE TESTNET

instead of:

PAPER

The system must:

* authenticate
* connect
* fetch data
* place order
* verify fill
* create protection
* monitor
* close
* reconcile
* store trade
* show PnL

---

# 78. THIRD ACCEPTANCE TEST

Create:

Strategy A
Strategy B

Run both independently.

Verify:

Strategy A cannot affect Strategy B.

Change Strategy A parameters.

Strategy B must remain unchanged.

---

# 79. FOURTH ACCEPTANCE TEST — MULTI USER

Create:

User A
User B

User A:

Strategy A
Bot A
Trade A

User B:

Strategy B
Bot B
Trade B

Verify:

A cannot access B's data.

B cannot access A's data.

---

# 80. PERFORMANCE REQUIREMENTS

Mobile dashboard API:

target <500ms for normal cached dashboard requests.

Backtests:

run asynchronously.

Trading worker:

must not depend on mobile app being online.

Database:

must remain source of truth for persistent state.

---

# 81. DESIGN PRINCIPLES

Prefer:

simple
modular
testable
boring
reliable

over:

clever
over-engineered
AI-generated complexity

Do not introduce microservices unless necessary.

Start as a modular monolith + separate workers.

Only split services when actual scale requires it.

---

# 82. IMPORTANT FINANCIAL RULE

Never display:

"Guaranteed Profit"

"AI Guaranteed Returns"

"Safe Trading"

"Risk Free"

Never claim profitability from backtests.

Display:

"Past performance does not guarantee future results."

Backtest results must clearly show assumptions.

---

# 83. FINAL DELIVERABLE

The coding agent must produce:

1. Backend
2. Mobile application
3. Trading engine
4. Strategy engine
5. Risk engine
6. Paper trading
7. Binance Testnet integration
8. Backtesting
9. PostgreSQL database
10. Redis workers
11. Authentication
12. Multi-tenant-ready architecture
13. Strategy versioning
14. Mobile dashboard
15. WebSocket updates
16. Notifications
17. Tests
18. Docker setup
19. CI
20. Documentation

---

# 84. FINAL RULE TO THE CODING AGENT

DO NOT build the entire system in one giant response.

First inspect the repository.

Then create:

docs/IMPLEMENTATION_PLAN.md

Divide the implementation into phases.

Implement only one phase at a time.

After every phase:

* run tests
* show changed files
* show test results
* list known issues
* update documentation

Never silently skip a requirement.

Never claim a feature is complete if it is only mocked.

Never enable live trading by default.

Never copy code from an external repository without checking its license.

The final product should feel like:

"TradingView-style strategy research + paper trading + Binance Testnet execution + mobile bot control"

with the architecture ready to evolve into a SaaS product.

START WITH PHASE 0.
Do not start coding until the repository has been inspected and the architecture plan has been created.
