"""Simple script to copy the SQLite trading DB to backups with timestamp."""
import shutil
from datetime import datetime
from pathlib import Path

DB = Path('trading.db')
BACKUP_DIR = Path('backups')
BACKUP_DIR.mkdir(exist_ok=True)
if not DB.exists():
    print('No trading.db found to backup')
else:
    ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    dest = BACKUP_DIR / f'trading_{ts}.db'
    shutil.copy2(DB, dest)
    print(f'Backed up {DB} -> {dest}')
