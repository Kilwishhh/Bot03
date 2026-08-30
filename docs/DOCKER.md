# Docker / Deployment

## Stack

Modular monolith: `backend` (FastAPI) + `worker` (bot runner) + `redis` (optional, for future pub/sub) + SQLite (persistent volume).

```
docker compose
  ├── backend   (FastAPI, port 8000)
  ├── worker    (app.worker, polls DB control_state)
  ├── redis     (redis:7-alpine, persistent, no public port)
  └── db        (alpine stub holding the sqlite volume)

volumes:
  - mktrader_sqlite_data  → /app/data    (trading.db survives restart/recreate)
  - mktrader_redis_data   → /data        (redis persistence)
```

## Why no PostgreSQL

The current codebase uses `sqlite3` directly via `app.database.repository.TradingRepository`. Migrating to PostgreSQL would require rewriting every SQL string, the migration runner, and all tests. Per the PRD (no large new architecture, no functional changes), the design keeps SQLite on a persistent named volume. PostgreSQL is pre-wired via the `DATABASE_URL` env var in `.env.example` for future migration.

## Why no separate scheduler

The `worker` itself runs the polling loop (`app.worker.main` — control state check every second, runs one bot cycle per tick). Adding a separate scheduler would create a duplicate tick source. The PRD explicitly forbids duplicate schedulers.

## Commands

### Build
```bash
docker compose build
```

### Start
```bash
docker compose up -d
```

### Status
```bash
docker compose ps
```

### Logs
```bash
docker compose logs -f
docker compose logs -f backend
docker compose logs -f worker
```

### Restart a service
```bash
docker compose restart worker
```

### Stop
```bash
docker compose down              # keep volumes
docker compose down -v           # also remove volumes (loses DB)
```

### With dashboard
```bash
docker compose --profile dashboard up -d
# Streamlit at http://localhost:8501
```

## Healthchecks

- `redis`: `redis-cli ping`
- `backend`: HTTP GET `/health` on port 8000
- `db`: volume stub (always started; backend reads from mounted volume)
- `worker`: no HTTP endpoint (polls DB); relies on `backend` healthy + volume mounted

`/health` endpoint is provided by the existing FastAPI app (`app.api.server`).

## Networking

All inter-container communication uses **Compose service names**, not `localhost`:

- `backend` → `redis://redis:6379/0`
- `worker`  → reads `/app/data/trading.db` (same volume)
- No `localhost` in any env var, Dockerfile, or compose file.

Only `backend` (8000) and optional `dashboard` (8501) are exposed to the host. Redis and the database volume are not publicly accessible.

## Restart policy

`restart: unless-stopped` is set on `backend`, `worker`, `redis`. The `db` volume container uses the same policy so the volume persists.

## Secrets

No real credentials in the repository. `.env.example` is the template; copy to `.env` and fill in real values for your deploy:

```bash
cp .env.example .env
# edit .env
```

`.env` should be added to `.gitignore` if not already.

## Production checklist

- [ ] Set `APP_SECRET` to a strong random value
- [ ] Set `ADMIN_API_TOKEN` to a strong random value
- [ ] Set `BINANCE_API_KEY` / `BINANCE_API_SECRET` for testnet/live
- [ ] `API_REQUIRE_HTTPS=true` if fronted by TLS proxy
- [ ] Configure nginx reverse proxy in `deploy/nginx/` (existing config)
- [ ] Configure log rotation (Docker default is `json-file` with no rotation)
- [ ] Set up backup of `mktrader_sqlite_data` volume
- [ ] Set `ENABLE_LIVE_TRADING=true` ONLY when ready to trade real money

## Persistence test

```bash
docker compose down            # stops containers, keeps volume
docker compose up -d           # restart
docker compose exec backend ls /app/data/trading.db  # DB still there
```

## Failure recovery test

```bash
docker compose restart redis   # redis temporarily down
docker compose ps              # backend/worker restart until redis healthy
docker compose logs -f backend # shows retry on connection until redis ready
```

## Migration procedure

The application uses a migration runner (`app.database.migration_runner`). To add a new migration:

1. Create a new SQL file under `app/database/migrations/`
2. The runner picks it up on next `backend` or `worker` start

To back up the database:
```bash
docker compose exec backend sqlite3 /app/data/trading.db ".backup '/app/data/backup.db'"
docker compose cp backend:/app/data/backup.db ./backup-$(date +%F).db
```
