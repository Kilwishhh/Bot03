# Rollback Runbook

This document describes how to roll back the three mutable components of a MK TRADER deployment: configuration, Docker image, and the SQLite database.

---

## 1. Configuration rollback

Configuration lives in environment variables and `.env` files. There is no "apply a previous version" mechanism — you restore by reverting the `.env` or the env vars in your container orchestrator.

### Before changing config, snapshot:

```bash
# Save a named snapshot of the current .env
cp .env .env.backup-$(date +%Y%m%d-%H%M%S)
```

### To roll back:

1. Stop the container/process.
2. Restore the last known-good `.env`:
   ```bash
   cp .env.backup-<timestamp> .env
   ```
3. Restart the container/process.

### If using Docker Compose, roll back the env var snapshot via your orchestrator (Helm rollback, Terraform, etc.) or just `docker compose down && docker compose up -d`.

---

## 2. Docker image rollback

MK TRADER is deployed as a Docker image. Every CI run on `main` / `master` that passes produces a tagged image.

### Image tags produced by CI

| Tag | Meaning |
|-----|---------|
| `mktrader:latest` | The most recent CI pass on main/master |
| Commit SHA (`mktrader:<sha>`) | Immutable, every CI run |

### To roll back to a known-good image:

```bash
# 1. Find the SHA of the last good commit
git log --oneline -10

# 2. Pull (or rebuild from that commit)
docker pull mktrader:ci   # if you've pushed it to a registry
# OR rebuild from the old commit
git checkout <old-sha>
docker build -t mktrader:ci .
git checkout master

# 3. Restart containers with the old image
docker compose down
docker compose up -d
```

### If using a container registry (ECR, GCR, Docker Hub):

```bash
docker pull <registry>/mktrader:<last-good-tag>
# Update docker-compose.yml or your helm values to point to that tag
docker compose up -d
```

---

## 3. Database rollback (SQLite)

MK TRADER uses SQLite by default (`DATABASE_PATH`). SQLite appends data — there is no native "undo last N transactions." Rollback means restoring from a snapshot.

### Before risky operations (live trading, mass order cancellation), snapshot:

```bash
cp /path/to/trading.db /path/to/trading.db.backup-$(date +%Y%m%d-%H%M%S)
```

### To restore a snapshot:

```bash
# 1. Stop the bot
docker compose down   # or kill the Python process

# 2. Restore
cp /path/to/trading.db.backup-<timestamp> /path/to/trading.db

# 3. Restart
docker compose up -d
```

### What data is lost on restore

A snapshot restore discards all writes that happened after the snapshot was taken. Specifically:

| Table | What is lost |
|-------|-------------|
| `orders` | Orders placed after snapshot |
| `trades` | Fills executed after snapshot |
| `positions` | Position changes after snapshot |
| `signals` | Signals generated after snapshot |
| `risk_events` | Risk events after snapshot |

There is **no** "incremental rollback" — it is a full-file restore. Keep multiple snapshots for fine-grained recovery.

### Scheduled snapshots

The `scripts/backup_db.py` script creates a timestamped snapshot:

```bash
python scripts/backup_db.py
# Output: backup_trading_20260827_120000.db
```

Add it to a cron job for automated snapshots:

```cron
0 */6 * * * cd /app && python scripts/backup_db.py
```
*(every 6 hours — adjust to your risk tolerance)*

### Retention

Keep the last N snapshots and prune older ones:

```bash
# Keep last 7 daily snapshots, delete the rest
ls -t backup_trading_*.db | tail -n +8 | xargs rm -f
```

---

## 4. Emergency stop checklist

If something goes wrong in production:

```
[ ] 1. Stop the trading process / container
       docker compose down   or   pkill -f "app.main"
[ ] 2. Preserve the current database (do NOT overwrite the backup)
       cp $DATABASE_PATH $DATABASE_PATH.corrupt-$(date +%s)
[ ] 3. Restore the last known-good DB snapshot
[ ] 4. Verify .env / env vars are correct
[ ] 5. Restart with the previous image
       docker compose up -d
[ ] 6. Check /health and /status before re-enabling live trading
[ ] 7. Notify via Telegram/Square if notifications are configured
[ ] 8. Document the incident (what failed, when, what was done)
```

---

## 5. Quick reference

| Component | Rollback method | Data loss |
|-----------|---------------|-----------|
| Config | Restore `.env` from snapshot | Config changes since snapshot |
| Docker image | `docker pull` previous tag / rebuild old SHA | Container process restart |
| SQLite DB | `cp` backup file | All writes after snapshot time |
