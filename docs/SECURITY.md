# Security

Security requirements for the crypto trading platform. This document describes how credentials,
authentication, tenancy, and live trading are protected. It is the reference for Phase 11
(security hardening) and every phase that touches credentials or execution.

## 1. API Key Storage

- Exchange API keys/secrets are **never stored in plaintext** database columns.
- Stored encrypted at rest using application-level encryption (Fernet, symmetric AES-256).
- The encryption **master key** comes only from environment/secret management
  (`CREDENTIALS_ENCRYPTION_KEY`), never from the repository.
- Decryption happens only inside the Trading Worker process at the moment of order execution;
  secrets are never returned to the frontend, logged, or sent to analytics.
- Users can add, revoke, and delete credentials at any time. Deletion must remove or invalidate
  the stored ciphertext.
- Binance guidance: request **read + futures trading** permissions only; never request withdrawal
  access. Show this guidance to users in the exchange-account UI.

## 2. Encryption

- TLS everywhere (API behind HTTPS/TLS; WebSocket `wss://`).
- Passwords hashed with Argon2 (pwdlib), with transparent upgrade to bcrypt for legacy hashes.
- Credentials-at-rest encrypted with a key derived from the master key in environment secrets.
- In transit, no secrets in query strings; only in authenticated request bodies over TLS.

## 3. Authentication

- Registration, login, logout, refresh token, password hashing.
- JWT access token (short-lived) + refresh token (rotated; stored in secure storage; mobile keeps
  it in Keychain/Keystore, web in httpOnly+Secure cookie).
- Token identity is the **only** source of user identity. Never trust client-supplied `user_id`.
- Password reset and email verification are implemented with single-use signed tokens.
- Optional later: Google/Apple OAuth, TOTP 2FA. Design the auth dependency so these can be added
  without restructuring.

## 4. Authorization / Tenant Isolation

- Every user-owned table carries `user_id` (and `organization_id`/`workspace_id`, nullable, for
  future SaaS).
- Chained FastAPI dependencies enforce ownership by construction:
  `get_current_user` → resource-scoped `valid_owned_<resource>` (e.g., `valid_owned_bot`).
- Resource queries are always filtered by the authenticated user.
- Cross-user access attempts return **404** (not 403) to avoid leaking the existence of objects.
- Automated tests assert User A cannot read/modify User B's bots, strategies, trades, credentials,
  backtests, positions, notifications.
- Live/Testnet operations additionally verify the exchange account belongs to the requesting user.

## 5. Secret Handling

- `.env` files are gitignored; only `.env.example` with placeholders is committed.
- Encryption master key, JWT signing key, DB/Redis URLs live in environment/secret management.
- pydantic-settings `BaseSettings` fails fast on default placeholder secrets in production.
- No secrets in logs: the logging formatter redacts credential-like values.
- Credentials obtained for third-party services (none in MVP) must also be encrypted and gated.

## 6. Live Trading Safeguards

- `LIVE_TRADING_ENABLED=false` in all environments by default.
- Enabling LIVE requires:
  1. Environment flag flipped to `true` by the operator.
  2. Explicit per-account confirmation in the UI ("REAL MONEY MODE").
  3. Required typed acknowledgement (e.g., "I UNDERSTAND") before the bot can enter LIVE.
  4. An audit-log entry recording who/when.
- All the paper/testnet safeguards (risk engine, reconciliation, TP/SL protection, max leverage
  defaults) apply identically to LIVE.
- Emergency stop endpoint and daily-loss circuit breaker stop new entries automatically.
- Default risk posture for futures: ISOLATED margin, conservative leverage (never default to
  50x/100x/125x). Liquidation-distance monitoring halts entries and notifies when unsafe.

## 7. Audit Logs

- Structured `audit_logs` table records: login, registration, strategy created/changed, bot
  started/stopped, risk settings changed, exchange account added/removed, order placed/cancelled,
  live mode enabled, credentials rotated/deleted.
- Entries include user, action, target type/id, timestamp, IP (where available), result.
- Audit logs are append-only and tenant-scoped (visible to owner/admin later).

## 8. Rate Limiting

- API-level rate limiting per authenticated user and per IP (slowapi/Redis-backed).
- Stricter limits on auth endpoints (login, register, password reset) to slow brute force.
- Exchange-facing requests respect exchange rate limits (CCXT built-in rate limiters + our own
  per-exchange quota) to avoid bans and to avoid hammering endpoints from background loops.

## 9. API Security

- Every endpoint enforces authentication (except public auth endpoints: register, login, refresh,
  password-reset request).
- Standard auth flow: bearer access token; WebSocket connects authenticate via token (query param
  only over TLS, or subprotocol header).
- Validation: Pydantic schemas for all inputs; OpenAPI-driven.
- CORS restricted to configured origins; mobile app uses native networking, CORS applies to the
  web target only.
- Idempotency: order placement uses client order IDs; on timeout the system queries the existing
  order before re-submitting (never blind duplicate).
- No sensitive data in URL paths/query strings; IDs are opaque and ownership-checked.
- Security headers, structured logging, and a `/health` endpoint that leaks no internals.

## 10. Threat Model (summary)

| Asset | Primary threat | Mitigation |
|-------|----------------|------------|
| Exchange API keys | Theft/exfiltration | Encrypted at rest, never returned to clients, no withdrawal perms, not logged |
| User data (strategies, PnL) | Cross-tenant access | Ownership deps, 404 on foreign IDs, automated isolation tests |
| Orders/funds | Duplicate/erroneous orders | Idempotency keys, reconciliation, risk engine gating |
| Credentials in transit | Interception | TLS, no secrets in query strings |
| Auth tokens | Theft | Short-lived access + rotated refresh tokens, secure storage |
| Live trading | User error / runaway risk | Default-off LIVE, confirmations, circuit breakers, conservative defaults |
| Rate-limit abuse | Account ban / DoS | Per-user + per-IP rate limits, exchange quotas |
