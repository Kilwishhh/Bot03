# Bot03

Mobile-first crypto strategy research, paper-trading, Binance Testnet, and future SaaS trading
platform.

The mobile app is a control/monitoring client; the trading engine runs in backend workers and keeps
running when the phone is closed. See `docs/ARCHITECTURE.md` for the full design.

## Repository layout

```
apps/            Deployable units: api, worker (future), mobile (future)
packages/        Shared Python libraries: trading-core, exchange
infrastructure/  Docker, Alembic migrations
tests/           unit / integration / security
docs/            Architecture, decisions, security, plan, dependencies
```

## Requirements

- Python 3.11+
- PostgreSQL 15+ and Redis 7 (or Docker)

## Quick start (Docker)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up --build
# API:   http://localhost:8000
# Docs:  http://localhost:8000/docs
# Health:http://localhost:8000/health
```

The `migrate` service applies Alembic migrations before the API starts.

## Quick start (local)

```bash
cp .env.example .env
pip install -e packages/trading-core -e packages/exchange -e apps/api
pip install pytest pytest-asyncio httpx ruff mypy   # dev tooling

# create the database once
#   su - postgres -c "psql -c \"CREATE USER bot03 WITH PASSWORD 'bot03' SUPERUSER;\" \
#                     -c \"CREATE DATABASE bot03 OWNER bot03;\""

alembic -c infrastructure/migrations/alembic.ini upgrade head
uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000
```

## Tests / quality

```bash
pytest                                   # unit + integration (needs local postgres+redis)
ruff check .                             # lint
mypy apps packages tests                 # type check
```

## Status

Phase 0 (architecture) and Phase 1 (backend foundation) are complete. See
`docs/IMPLEMENTATION_PLAN.md`.
