# Deployment-Ready Roadmap

## Goal
Move the project from a verified internal prototype to a production-ready deployment pipeline with safe defaults, deterministic configuration, and clear operational controls.

## Phase 1 — Stabilize the current application
- Confirm the bot starts in paper mode without secrets.
- Validate every environment mode with explicit safety checks.
- Keep live/testnet execution behind required confirmation gates.
- Ensure all health and status endpoints are idempotent and read-only.
- Document the default mode, credentials, and required config keys for every environment.

## Phase 2 — Production configuration hardening
- Add `.env.example` coverage for all required values.
- Add validation for missing credentials and unsupported mode combinations.
- Enforce secret storage via environment variables or secret managers only.
- Define environment-specific configuration for dev, staging, and production.
- Add startup checks to fail fast on insecure or incomplete deployments.

## Phase 3 — Deployment packaging
- Package the project as a clean installable app via `pip` or a container build.
- Add a canonical Docker configuration for the API and worker runtime.
- Add health checks for the API service and the bot runtime.
- Add container environment variables for mode, provider, credentials, and feature flags.
- Keep database persistence explicit and mounted to a durable volume.

## Phase 4 — Observability and operations
- Add structured logging across API, trading engine, and runtime worker.
- Add metrics export for health checks, cycle counts, order actions, and errors.
- Add alerting for repeated failures, stale signals, or missing market data.
- Add a retention policy for database tables and logs.
- Add admin dashboard actions and status monitoring for runtime health.

## Phase 5 — Security and access control
- Require auth for remote control endpoints.
- Enforce token-based access for admin actions.
- Restrict CORS origins to trusted deployments only.
- Avoid exposing secrets in logs or API responses.
- Validate every external API integration before production exposure.

## Phase 6 — Real exchange integration readiness
- Complete wallet and DEX onboarding for the approved provider.
- Add explicit transaction preview and confirmation flows.
- Require signed-order approval for every live execution.
- Validate chain/network configuration before placing orders.
- Add dry-run simulation for new exchange integrations before prod activation.

## Phase 7 — Feature completion checklist
- Paper mode works end-to-end.
- Testnet mode works with sandbox credentials only.
- Live mode is gated by explicit confirmation and valid credentials.
- DEX mode is gated by wallet approval and chain validation.
- Dashboard shows current runtime health and counts.
- API exposes read-only operational data only.
- Remote control is disabled unless explicitly enabled.

## Phase 8 — Release readiness
- Run regression tests in CI on each change.
- Add a smoke test that validates health endpoints and app startup.
- Add deployment validation for Docket/compose startup scripts.
- Freeze supported Python version and dependency set.
- Prepare rollback steps for config, image, and database points.

## Recommended target release sequence
1. Release as paper-mode API + admin dashboard.
2. Release with sandbox/testnet validation.
3. Release with live safety gates enabled in staging.
4. Release production only after audit and manual approval.

## Hard gates before production
- No secrets in code or commit history.
- No unsigned live orders without explicit approval.
- No unvalidated exchange provider in production config.
- No remote control without token auth.
- No deployment without health checks and rollback plan.

## Suggested deployment targets
- Local development: Docker Compose + SQLite + API.
- Staging: containerized runtime with mocked or sandbox exchange data.
- Production: hardened container deployment with secret manager and persistence.

## Final recommendation
Treat the project as production-ready only after all hard gates are passed, all supported modes are tested, and the runtime is visible through admin tooling and logs. Until then, keep live execution disabled by default.
