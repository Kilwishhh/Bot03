# Third-Party Notices

This document records the license and reuse assessment for every external repository studied
during Phase 0 (architecture research). Per the PRD license policy: if a repository has no clear
compatible license, its code is **not** copied — its architecture is used as inspiration only.

Our reuse policy:
- **Prefer MIT / Apache-2.0 compatible components.**
- **Dependencies** (pip/npm packages) are used under their own licenses, listed in
  `docs/DEPENDENCIES.md`.
- **Copied/vendored code** must preserve the original copyright and license header and be listed
  here. Currently we copy **no** code from the repositories below; we only reuse mature libraries.

## 1. Freqtrade — https://github.com/freqtrade/freqtrade

| Field | Value |
|-------|-------|
| License | GNU GPL v3.0 |
| Code reuse | **Not copied.** GPL-3.0 is incompatible with our closed-source SaaS licensing. |
| Legal note | Copying code would obligate derivative work to be GPL. Keeping Freqtrade as a separate GPL process behind an API is possible but not planned. |
| Architecture inspiration | Strategy ABC (`populate_indicators`/entry/exit), declarative parameters, `.shift(1)` look-ahead avoidance, fill-checked order simulation, in-memory vs persisted trade split, dry-run wallet derived from DB, Trade/Order state machines, trailing-stop / ROI / protections concepts. |
| Verdict | Inspiration only |

## 2. Hummingbot — https://github.com/hummingbot/hummingbot

| Field | Value |
|-------|-------|
| License | Apache-2.0 (core repo; individual files may carry headers — verify before vendoring) |
| Code reuse | **Not copied in Phase 0.** Apache-2.0 permits reuse with attribution if we later vendor small components. |
| Architecture inspiration | v2 controller/executor split (intent queue, `ExecutorAction`), triple-barrier `PositionExecutor`, `ControllerConfigBase` (Pydantic, `is_updatable` fields), paper-trading via live order book + simulated fills, event-driven connector design. |
| Verdict | Inspiration; Apache-2.0 reuse allowed with attribution if needed later |

## 3. Hummingbot API — https://github.com/hummingbot/hummingbot-api

| Field | Value |
|-------|-------|
| License | MIT |
| Code reuse | Not copied. MIT permits reuse with attribution if needed. |
| Architecture inspiration | Backend/frontend separation: FastAPI control plane + real-time event plane + PostgreSQL + independent bot worker containers + web dashboard. |
| Verdict | Inspiration; MIT reuse allowed with attribution if needed later |

## 4. CCXT — https://github.com/ccxt/ccxt

| Field | Value |
|-------|-------|
| License | MIT (Copyright © 2024 Igor Kroitor) |
| Code reuse | Used as a **dependency** (PyPI package `ccxt`) for exchange connectivity. |
| Legal note | MIT permits commercial use with preservation of the copyright notice (handled by the package license). |
| Architecture value | Unified exchange abstraction; `binanceusdm` futures support; async + ccxt.pro WebSockets; normalized methods (fetch_balance, fetch_positions, create_order, fetch_order, cancel_order, fetch_ohlcv). |
| Verdict | Dependency (MIT) — primary exchange connectivity path |

## 5. KhushiThakur-AI/Crypto-Trading-Bot — https://github.com/KhushiThakur-AI/Crypto-Trading-Bot

| Field | Value |
|-------|-------|
| License | MIT (verified LICENSE file, Copyright 2025 Khushi Thakur) |
| Code reuse | Not copied. MIT permits reuse with attribution. |
| Assessment | Hobby-grade (stale, no tests, committed `.env`). Its per-coin config schema (SL/TP/TSL), confidence-scoring idea, and risk-guard concepts are reference patterns only; we implement our own with Pydantic + modern APIs. |
| Verdict | Reference patterns (MIT); no code copied |

## 6. l0ller/binance-futures-bot — https://github.com/l0ller/binance-futures-bot

| Field | Value |
|-------|-------|
| License | **None.** README claims MIT but no LICENSE file exists (GitHub API reports no license). Default: all rights reserved. |
| Code reuse | **Not permitted / not copied.** |
| Assessment | Single-file CLI order manager; OCO (TP+SL) workflow is a useful conceptual model. Uses python-binance (which we are not using as primary). |
| Verdict | Inspiration only (order-type workflows); no code copied |

## 7. frostyalce000/paper-trading-binance — https://github.com/frostyalce000/paper-trading-binance

| Field | Value |
|-------|-------|
| License | **None.** (Repo README itself notes the absence of a LICENSE.) Default: all rights reserved. |
| Code reuse | **Not permitted / not copied.** |
| Assessment | ~50-line script; **hardcoded Testnet API keys committed** (security anti-pattern to avoid). LOT_SIZE precision rounding is standard practice. Nothing worth salvaging. |
| Verdict | Skip; inspiration only. Anti-pattern to avoid |

## 8. zhanymkanov/fastapi-best-practices — https://github.com/zhanymkanov/fastapi-best-practices

| Field | Value |
|-------|-------|
| License | No LICENSE file (guide repository). Patterns, not copyable code. |
| Code reuse | Not copied. |
| Architecture inspiration | Domain-scoped packages (router/schemas/models/dependencies/service per module), SQLAlchemy 2.0 async, chained ownership dependencies, Alembic naming conventions, pydantic-settings per domain, "BackgroundTasks only for <1s work; use a queue otherwise". |
| Verdict | Inspiration only |

## 9. fastapi/full-stack-fastapi-template — https://github.com/fastapi/full-stack-fastapi-template

| Field | Value |
|-------|-------|
| License | MIT |
| Code reuse | Not copied in Phase 0; patterns are adopted (auth via pwdlib Argon2, pydantic-settings config, Docker Compose layout, tests). MIT permits reuse with attribution if we later adopt files. |
| Architecture inspiration | OAuth2 password flow, refresh token handling, pwdlib password hashing, `BaseSettings` fail-fast on default secrets, Alembic setup, compose.yml structure. |
| Verdict | Reference (MIT); patterns adopted, no wholesale copying |

---

## Summary

| Repository | License | Verdict |
|------------|---------|---------|
| Freqtrade | GPL-3.0 | Inspiration only (license-incompatible to copy) |
| Hummingbot | Apache-2.0 | Inspiration; reuse allowed with attribution if needed |
| Hummingbot API | MIT | Inspiration; reuse allowed with attribution if needed |
| CCXT | MIT | **Dependency** — primary exchange connectivity |
| KhushiThakur Crypto-Trading-Bot | MIT | Reference patterns; no code copied |
| l0ller binance-futures-bot | none | Inspiration only; no code copied |
| frostyalce000 paper-trading-binance | none | Skip; no code copied |
| zhanymkanov fastapi-best-practices | none (guide) | Inspiration only |
| fastapi full-stack-fastapi-template | MIT | Reference; patterns adopted |

**Current reused code:** none vendored from the above. All reuse is through mature pip/npm
dependencies (see `docs/DEPENDENCIES.md`). If any code is copied later, this document and the
license headers must be updated before merging.
