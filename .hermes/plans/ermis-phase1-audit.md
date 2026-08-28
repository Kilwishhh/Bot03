# ERMIS Phase 1 — Implementation Audit

## Existing Architecture

### Frontend Stack (3 UIs today)
| UI | Route | Tech | Status |
|----|-------|------|--------|
| Landing page | `/` | `index.html` | Static HTML + `/static/app.js` |
| Mobile dashboard | `/mobile` | `mobile.html` | HTML table + polling |
| Admin panel | `/admin` | `admin.html` | HTML table + polling |
| Streamlit dashboard | `streamlit_app.py` | Python | Not integrated into FastAPI |
| Flutter mobile app | `mobile/flutter_app/` | Flutter/Dart | APK at `build/app/outputs/flutter-apk/app-release.apk` |

### Backend Stack
| Component | File | Notes |
|-----------|------|-------|
| API server | `app/api/server.py` (FastAPI) | 492 lines |
| Control router | `app/api/control.py` | Start/stop, thread-based daemon |
| Auth | `app/api/auth.py` | Bearer + X-Token headers |
| Security | `app/api/security.py` | Rate limit, headers, audit logger |
| WebSocket | `app/api/ws.py` | Read-only |
| Static assets | `app/api/static/app.js`, `styles.css` | Shared client helpers |

### Key Business Logic
| Module | File | Gap vs PRD |
|--------|------|-----------|
| Strategy registry | `app/strategy/factory.py` | ✅ Built-in (5) + user auto-load. No per-strategy config DB. |
| Signal engine | `app/signals/signal_engine.py` | ✅ Health-gated. No follow-up model. |
| Signal model | `app/signals/models.py` | Signal has: symbol/side/confidence/timestamp/reason/strategy_name/metadata. Missing: TP1/TP2/SL levels, mode, publish status, follow-up timeline. |
| Order manager | `app/execution/order_manager.py` | ✅ Risk-gated. Fixed-notional paper mode. |
| Risk manager | `app/risk/risk_manager.py` | ✅ Emergency stop, confidence gate, daily loss, max positions. |
| Binance Square | `app/notifications/binance_square.py` | ✅ Queue + daily limit. Missing: configurable limit behavior (stop/continue/queue). |
| Telegram | `app/notifications/telegram.py` | ✅ Deduplicating publisher chain. |
| Exchange factory | `app/exchange/factory.py` | ✅ Paper/Binance/Hyperliquid/WalletConnect. |
| Database | `app/database/repository.py` | ✅ Thread-safe SQLite. No Strategy table. |
| Health/monitoring | `app/monitoring/health.py` | ✅ Exchange + market data health. |
| Alerts | `app/monitoring/alerts.py` | ✅ Failure threshold + cooldown. |
| Audit log | `app/api/security.py` | ✅ JSONL. Actor/action/detail/result. |

## Gaps vs PRD

### P0 — Critical (missing entirely)
1. **Strategy lifecycle model** — No DB table for strategy configs. Lifecycle (BACKTEST → PAPER → TESTNET → LIVE) is purely env-driven, not per-strategy.
2. **Signal follow-ups** — No follow-up data model or timeline. Signal has no TP/SL/entry fields.
3. **Automation rules engine** — No structured rules. Signals → publisher chain is hardcoded in `control.py`.
4. **User/Admin separation** — Single-token auth. No multi-user, no user roles, no user-specific data.
5. **Emergency pause** — `RiskManager.emergency_stop` exists but not exposed via API. No admin emergency endpoint.
6. **Per-strategy configuration** — All settings are global. Cannot configure pair/timeframe/leverage per strategy.
7. **Audit log for admin actions** — `server.py` has audit calls but no structured audit for strategy pause/deploy/emergency.

### P1 — Core UX (partial or missing)
1. **Signals list** — `/signals` endpoint returns raw rows. No filtering (All/Active/Follow-ups/Published).
2. **Strategy Builder UI** — No create/edit strategy UI. No visual rule builder.
3. **Strategy Lab** — No backtest/paper/testnet/live stage UI.
4. **Mode badges** — None in mobile.html/admin.html beyond a simple pill.
5. **Binance Square limit UX** — Status shown in admin but not the 3-way behavior config (stop/continue/queue).
6. **Connections screen** — No UI for managing Binance/Telegram/Square connections.
7. **On-demand charts** — No drawer/panel. No lazy-load.
8. **Admin System Health** — No API endpoint exposing: API / Signal Engine / Trading Engine / Database / Job Queue / Telegram / Binance / Square.
9. **Follow-up timeline** — No data model or API for follow-up events.

### P2 — Enhancement
1. Analytics screen
2. Activity/Logs UI (admin)
3. User management UI (admin)
4. DEX integration UX beyond scaffold

## PRD-Compatible Reuse

| What to KEEP | Why |
|-------------|-----|
| `app/api/server.py` (all endpoints + auth + security + middleware) | Solid FastAPI foundation. Extend, don't replace. |
| `app/api/auth.py` | Dual-header auth works. Extend for multi-user later. |
| `app/database/repository.py` | Thread-safe SQLite. Add new tables, don't rewrite. |
| `app/strategy/factory.py` | Registry is clean. Add strategy config DB on top. |
| `app/signals/models.py` | Extend Signal dataclass with new fields. |
| `app/signals/signal_engine.py` | Health-gating is correct. Add follow-up pipeline. |
| `app/execution/order_manager.py` | Working. Add TP/SL fields. |
| `app/risk/risk_manager.py` | Emergency stop is already there. Wire to API. |
| `app/notifications/binance_square.py` | Queue + limit logic is solid. Add 3-way behavior config. |
| `app/notifications/signal_publisher.py` | Publisher chain is clean. Add follow-up types. |
| `app/monitoring/health.py` | Extend for system-wide health. |
| `app/api/security.py` | Audit logger stays. |
| `app/api/static/app.js` | Utility helpers. Drop-in to new pages. |
| `app/api/static/styles.css` | Design tokens are reasonable. Can extend or replace per PRD. |

## Implementation Roadmap

### Phase 2 — Design System (shared, no feature logic)
- [ ] Define CSS variables: dark navy base, cyan accent, purple secondary, badge colors, font stack
- [ ] Build reusable components: ModeBadge (PAPER/TESTNET/LIVE), StatusDot, MetricCard, SignalCard
- [ ] Shared layout primitives: Sidebar nav, header, main content area, right drawer/panel slot
- [ ] Shared utilities: formatCurrency, formatTime, relativeTime, confidenceBar
- [ ] Apply to all 3 existing HTML pages (landing stays minimal; admin + mobile get full redesign)

### Phase 3a — Backend Extensions (before frontend)
- [ ] Add Strategy DB table + CRUD endpoints
- [ ] Add StrategyVersion/Backtest/PaperSession tables
- [ ] Extend Signal model: entry_price, tp1, tp2, sl, mode, published_channels, follow_up_status
- [ ] Add SignalFollowUp model + API
- [ ] Add system health API endpoint (`GET /admin/system-health`)
- [ ] Add emergency pause API endpoint (`POST /admin/emergency-pause`, `POST /admin/emergency-resume`)
- [ ] Add automation rules table + API (signal rules, TP/SL follow-up rules)
- [ ] Extend Binance Square: 3-way limit behavior config + API
- [ ] Add admin audit log view endpoint
- [ ] Strategy lifecycle enforcement: server-side gate for LIVE deployment

### Phase 3b — New Admin UI (Phase 4 PRD)
- Replace `admin.html` with new sidebar-based admin app
- Routes: `/admin` → Overview, `/admin/users`, `/admin/users/:id`, `/admin/strategies`, `/admin/executions`, `/admin/integrations`, `/admin/system-health`, `/admin/logs`, `/admin/alerts`, `/admin/settings`
- Health grid: API / Signal Engine / Trading Engine / DB / Job Queue / Telegram / Binance / Square
- Emergency controls with confirmation + audit log

### Phase 3c — New User App (Phase 3 PRD)
- New `/app` route serving the user-facing SPA
- Sidebar nav matching PRD: Overview, Strategies, Signals, Automation, Positions, Portfolio, Activity, Analytics, Connections, Settings
- Strategy Builder: structured form → save to DB → start backtest
- Strategy Lab: lifecycle stage display + progress
- Signal list: All/Active/Follow-ups/Published filters + on-demand detail drawer
- Automation rules editor
- Mode badges everywhere

### Phase 3d — Flutter Mobile App (Phase 3 PRD)
- Apply same design system (dark navy + cyan)
- Restructure screens: Overview, Strategies, Signals, Automation, Positions, Portfolio, Settings
- On-demand chart drawer
- Emergency pause button in header

## Frontend Technology Decision

The PRD says "rebuild frontend information architecture". The existing HTML files use vanilla JS + shared `app.js`. The Flutter app is separate.

**Recommendation: Keep vanilla HTML/JS for admin + user web apps, apply new design system.**

Rationale:
- No build step required (works alongside existing FastAPI)
- FastAPI serves static files already
- Flutter is the mobile target (not web)
- Adding React/Vue creates a separate frontend server requirement
- New HTML + JS pages can be served from `app/api/static/user/` and `app/api/static/admin/`
- Flutter app rebuild uses existing Flutter SDK

Alternative: if the user wants React or Vue, that's a separate build pipeline to set up. Recommend vanilla JS to start and migrate later if needed.

## Strategy: Which approach for Phase 2 (Design System)?

Option A — **Extend existing `styles.css`** (quick, works)
- Add new CSS variables for the PRD design language
- Build new components in the same file
- Drop into the existing HTML shells
- Fastest path to visual coherence

Option B — **New `ermis.css` design system file** (cleaner)
- Separate from existing `styles.css` so the legacy pages can keep the old look
- New pages import only `ermis.css`
- Gradual migration without breaking existing pages

**Decision: Option B** — new design system, applied to new pages. Legacy `admin.html` and `mobile.html` get redesigned as new pages. `index.html` stays minimal.
