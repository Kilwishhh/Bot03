# ERMIS — Migration Plan

## Guiding Principles
1. **Additive only** — never break the running system mid-migration
2. **Migrations on startup** — `migration_runner.py` runs at app start, idempotent
3. **Legacy endpoints deprecated, not removed** — existing `/admin/data`, `/signals`, `/orders`, `/trades` etc. keep working for one release
4. **Two-track users** — legacy "single token" still works (treated as a system user); new per-user auth runs alongside
5. **Commit per logical chunk** — small, reviewable, reversible
6. **Tests for new code path required** before merging
7. **DB back-up script** before each destructive migration

## Migration Order

### Stage 0 — Pre-flight (no code change)
- [ ] `cp trading.db trading.db.pre-ermis` — backup
- [ ] Document current API contracts in `docs/legacy-api.md`

### Stage 1 — Database foundation (B)
| Change | Files | BC impact | Tests |
|--------|-------|-----------|-------|
| Create `app/database/migrations/` with `001_init.sql` for all new tables | new | none (additive) | `test_migrations.py` |
| Add `app/database/migration_runner.py` to apply on startup | new | none | `test_migration_runner.py` |
| Modify `app/database/repository.py` to add new methods (no changes to existing) | modified | none | existing tests pass + `test_repository_new.py` |
| Backfill script: `002_extend_signals.sql` adds new columns to `signals` with NULL/defaults | new | existing `/signals` endpoint now returns extra fields; clients that ignore unknown fields are fine | `test_signal_backfill.py` |
| Backfill script: `003_backfill.sql` populates `user_id='system'` and `strategy_id` derived from `strategy` column on legacy signal rows | new | none | `test_backfill.py` |

**Done when:** All new tables exist, legacy tables intact, all 180 existing tests still pass.

### Stage 2 — Core (auth, audit, errors) (C)
| Change | Files | BC impact | Tests |
|--------|-------|-----------|-------|
| Add `app/core/auth.py` (bcrypt/argon2, session tokens) | new | none (no router yet) | `test_auth.py` |
| Add `app/core/rbac.py` (role check helpers) | new | none | `test_rbac.py` |
| Add `app/core/audit.py` (structured audit writer) | new | none | `test_audit.py` |
| Add `app/core/crypto.py` (Fernet-based secret encryption) | new | none | `test_crypto.py` |
| Add `app/core/errors.py` (domain exceptions) | new | none | `test_errors.py` |
| Modify `app/api/auth.py` to ALSO accept user session tokens (fall through to existing token auth) | modified | none | existing + new tests |

**Done when:** Core utilities exist, no UI changes yet, all 180 existing tests pass.

### Stage 3 — User domain + auth API (C + D)
| Change | Files | BC impact | Tests |
|--------|-------|-----------|-------|
| Add `app/domain/user.py` (dataclasses) | new | none | `test_user_domain.py` |
| Add `app/services/user_service.py` (CRUD) | new | none | `test_user_service.py` |
| Add `app/api/routes/user_routes.py` (`POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /me`) | new | none | `test_user_routes.py` |
| Modify `app/api/server.py` to include the new router | modified | new endpoints added | existing + new |

**Done when:** `/auth/login` returns a session token; `/me` returns the current user. Legacy auth still works.

### Stage 4 — Strategy domain + lifecycle + APIs (B + C + D)
| Change | Files | BC impact | Tests |
|--------|-------|-----------|-------|
| Add `app/domain/strategy.py` | new | none | `test_strategy_domain.py` |
| Add `app/services/strategy_service.py` (CRUD, version snapshotting) | new | none | `test_strategy_service.py` |
| Add `app/services/strategy_lifecycle.py` (state machine, transition validation) | new | none | `test_strategy_lifecycle.py` |
| Add `app/api/routes/strategy_routes.py` (`/strategies/*` with create/get/list/update/delete/transition) | new | none | `test_strategy_routes.py` |
| Update `app/api/server.py` to mount | modified | new endpoints | existing tests still pass |

**Done when:** A user can create a strategy, transition through states, get rejected for invalid transitions, see an audit trail.

### Stage 5 — Signal domain + service + APIs (B + C + D)
| Change | Files | BC impact | Tests |
|--------|-------|-----------|-------|
| Extend `app/domain/signal.py` with TP/SL/mode/status fields | new | none | `test_signal_domain.py` |
| Add `app/services/signal_service.py` (create from engine, update status) | new | none | `test_signal_service.py` |
| Extend `app/signals/models.py` Signal dataclass with new fields | modified | existing code that constructs Signal must add defaults; check usages | `test_signal_compat.py` |
| Modify `TradingCycle` to call the new signal_service instead of `repository.save_signal` directly | modified | signal data shape changes (extra fields NULL for now) | existing tests still pass; new tests |
| Add `app/api/routes/signal_routes.py` (`/signals/*` with filtering: All/Active/Follow-ups/Published) | new | none (new endpoints) | `test_signal_routes.py` |

**Done when:** Signals carry the new fields, signal list endpoint supports filters, old `/signals` endpoint still works.

### Stage 6 — Follow-up model + service + APIs (B + C + D)
| Change | Files | BC impact | Tests |
|--------|-------|-----------|-------|
| Add `app/domain/followup.py` | new | none | `test_followup_domain.py` |
| Add `app/services/followup_service.py` (record event, get timeline) | new | none | `test_followup_service.py` |
| Add `app/api/routes/followup_routes.py` (`/signals/:id/followups`, `/followups/:id`) | new | none | `test_followup_routes.py` |
| Add follow-up emission hook into the trading cycle / position reconciliation | modified | adds side effects to trading cycle | new tests + existing pass |

**Done when:** A signal can have a timeline of follow-up events visible via API.

### Stage 7 — Automation engine (B + C + D)
| Change | Files | BC impact | Tests |
|--------|-------|-----------|-------|
| Add `app/domain/automation.py` | new | none | `test_automation_domain.py` |
| Add `app/services/automation_engine.py` (TRIGGER→CONDITIONS→ACTIONS, idempotent, async) | new | none | `test_automation_engine.py` |
| Add `app/api/routes/automation_routes.py` (`/automation/rules/*`) | new | none | `test_automation_routes.py` |
| Wire automation engine to fire on signal creation, follow-up creation, etc. | modified | adds side effects | new tests + existing pass |

**Done when:** A user can create an automation rule and see it fire when its trigger condition is met.

### Stage 8 — Connections + Publishing (B + C + D)
| Change | Files | BC impact | Tests |
|--------|-------|-----------|-------|
| Add `app/domain/connection.py` | new | none | `test_connection_domain.py` |
| Add `app/domain/publishing.py` | new | none | `test_publishing_domain.py` |
| Add `app/services/connection_service.py` (encrypted credential storage) | new | none | `test_connection_service.py` |
| Add `app/services/publishing_service.py` (3-way Square limit behavior, dedup, queue) | new | none | `test_publishing_service.py` |
| Add `app/api/routes/connection_routes.py`, `publishing_routes.py` | new | none | `test_*_routes.py` |
| Update existing `BinanceSquarePoster` to delegate to `PublishingService` for limit checks | modified | publishing behavior preserved | existing tests + new |

**Done when:** A user can store an encrypted exchange key, configure Telegram + Square with limit behavior, and see queue + status.

### Stage 9 — Health, Emergency, Admin APIs (C + D)
| Change | Files | BC impact | Tests |
|--------|-------|-----------|-------|
| Add `app/services/health_service.py` (aggregates 8 service checks) | new | none | `test_health_service.py` |
| Add `app/services/emergency_service.py` (3 scope levels: strategy/user/platform) | new | none | `test_emergency_service.py` |
| Add `app/api/routes/health_routes.py` (`/health/system`) | new | adds a new endpoint | `test_health_routes.py` |
| Add `app/api/routes/emergency_routes.py` (`/emergency/pause`, `/resume`, `/status`) | new | adds new endpoints | `test_emergency_routes.py` |
| Add `app/api/routes/admin_routes.py` (users list/detail, audit tail, system health, integrations) | new | adds new endpoints | `test_admin_routes.py` |

**Done when:** `/health/system` shows 8 services, `/emergency/pause` works at 3 scopes, `/admin/users` lists users.

### Stage 10 — Worker / queue refactor (C)
| Change | Files | BC impact | Tests |
|--------|-------|-----------|-------|
| Add `app/queue/job_queue.py` (FIFO, persistent) | new | none | `test_job_queue.py` |
| Modify `app/runtime.py` to push follow-up and automation events into the queue | modified | trading cycle still works | existing + new |
| Modify `app/worker.py` to consume from the queue | modified | worker still runs | existing + new |

**Done when:** Trades still execute; automation events fire asynchronously; dedup works.

### Stage 11 — Flutter app update (E, partial)
- Re-skin with the new design system
- Add User App screens: Overview, Strategies, Signals, Automation, Positions, Portfolio, Activity, Connections, Settings
- Add Admin App: Overview, Users, Strategies, System Health, Emergency, Logs
- Build new APK

**Done when:** APK builds, connects to the new APIs.

### Stage 12 — Vite + React web UIs (E + F) [PARALLEL to Stage 11]
| Track | User App | Admin App |
|-------|----------|-----------|
| Phase 2A | Vite + React setup, routing, auth, design system, app shell, sidebar | Same |
| Phase 2B | Overview, Strategies list, Create, Lab, Detail | Admin Overview, Users |
| Phase 2C | Signals list + detail drawer, Automation editor | Strategy monitoring, Executions, Integrations, System Health |
| Phase 2D | Connections, Positions, Portfolio, Activity, Analytics, Settings | Logs, Alerts, Admin Settings |

**Done when:** Both SPAs are functional, dark navy + cyan, real APIs.

### Stage 13 — Integration + testing (G + H)
- End-to-end flows: register → create strategy → backtest → paper → testnet → live-eligible
- Multi-user permission tests
- Live deployment rejection tests (missing confirmation, no exchange connection, etc.)
- Emergency pause tests
- Automation engine integration tests
- Binance Square limit behavior tests
- Flutter app build + smoke test

**Done when:** All flows work in browser, all tests pass.

## Compatibility Matrix

| Component | Pre-ERMIS | Post-ERMIS | Strategy |
|-----------|-----------|------------|----------|
| `/admin/data` | Returns existing payload | Still returns existing payload + new fields (additive) | Keep, deprecate slowly |
| `/signals` | Raw rows | Raw rows + new fields | Keep, deprecate slowly |
| `/control/*` | Single bot daemon | Per-strategy workers | New `/strategies/:id/control/*` endpoints added; old kept for global bot |
| Auth | Single token | Token OR user session | Token still works as "system user" |
| DB | 9 tables | 9 + 13 new tables | New tables; no destructive ALTER on existing |

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Migration script breaks production DB | Each migration idempotent + reversible; `migration_runner` runs in dry-run mode first; backup before each apply |
| New schema adds columns that legacy code ignores | All reads from new code go through repository methods; new columns are NULL by default; existing code paths unaffected |
| Per-user bot workers overload server | Workers are bounded per-user; default max 5 active workers per user; admin can override |
| Secrets leak in audit log | `audit.detail` never includes values matching `*_key`, `*_secret`, `password`, `token`; explicit allow-list in `app/core/audit.py` |
| Cross-user access | Every query in services enforces `user_id`; admin routes have explicit allow-list; integration tests assert 404 on cross-user requests |
| Live deployment by bypass | `strategy_lifecycle.transition('live')` is the ONLY entry point; checked at server level; no way to set `lifecycle_state='live'` directly via repository without going through the service |
