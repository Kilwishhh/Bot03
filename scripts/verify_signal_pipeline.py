"""End-to-end pipeline verification for SIGNAL_PIPELINE_TEST.

This script:
  1. Seeds the diagnostic strategy (paper only).
  2. Builds the same scanner the admin /start endpoint builds.
  3. Runs ONE scan cycle against the real Binance Futures API.
  4. Asserts each pipeline stage produced the expected evidence:
     universe loaded, candles fetched, conditions passed, signal created,
     signal persisted, signal visible in the signals table.

It prints a structured [SCAN]/[DATA]/[EVAL]/[SIGNAL] log line per stage
so the failing stage is obvious if the pipeline is broken.

Exits non-zero on any failure.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import warnings
from datetime import UTC, datetime

# Suppress noisy python-binance deprecation on Python 3.11+
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s — %(message)s",
)
logger = logging.getLogger("signal_pipeline_e2e")

# Quiet noisy libraries
for noisy in ("urllib3", "binance", "requests"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.environ.get("DATABASE_PATH", "trading.db"))
    parser.add_argument("--max-symbols", type=int, default=20,
                        help="Cap the universe for fast E2E (default 20). "
                             "Set to 0 for full Binance universe.")
    args = parser.parse_args()

    os.environ["DATABASE_PATH"] = args.db

    # 1. Seed diagnostic strategy
    from app.seed.signal_pipeline_test import seed
    sid = seed()
    print(f"\n[1/6] Strategy seeded: id={sid}")

    # 2. Build scanner
    from app.config import Settings
    from app.database import TradingRepository
    from app.database.repository import get_default_repository
    from app.exchange import create_exchange
    from app.market_data import AdapterMarketDataProvider
    from app.strategy.scanner import StrategyScanner

    settings = Settings()
    exchange = create_exchange(settings)
    repo = get_default_repository()
    market_data = AdapterMarketDataProvider(exchange)
    scanner = StrategyScanner(repo, market_data)

    print(f"\n[2/6] Scanner built: market_data={type(market_data).__name__} "
          f"exchange={type(exchange).__name__}")

    # 3. Run one cycle
    print(f"\n[3/6] Running single scan cycle (max_symbols={args.max_symbols})...")
    t0 = time.time()
    if args.max_symbols > 0:
        # Patch the universe to a small subset for fast verification
        from app.strategy import universe as uni_mod
        orig_get = uni_mod.get_symbols_for_universe

        def capped_get(universe_type, cfg, use_testnet=False):
            syms = orig_get(universe_type, cfg, use_testnet=use_testnet)
            return syms[: args.max_symbols]

        uni_mod.get_symbols_for_universe = capped_get
    signals = scanner.scan_once()
    elapsed = time.time() - t0

    print(f"\n[3/6] Scan finished in {elapsed:.2f}s: signals={len(signals)}")

    # 4. Inspect diagnostics
    diag = scanner.diagnostics.snapshot()
    last_cycle = diag["last_cycle"] or {}
    print(f"\n[4/6] Diagnostics:")
    print(json.dumps(diag, indent=2, default=str))

    # 5. Verify pipeline stages
    print(f"\n[5/6] Verifying pipeline stages...")
    failures: list[str] = []

    if not last_cycle:
        failures.append("no cycle diagnostics produced — scanner did not run")
    else:
        if last_cycle.get("symbols_loaded", 0) == 0:
            failures.append("STAGE: [SCAN] — universe is empty (symbols_loaded=0)")
        if last_cycle.get("symbols_evaluated", 0) == 0:
            failures.append("STAGE: [SCAN] — no symbols evaluated")
        if last_cycle.get("symbols_with_candles", 0) == 0:
            failures.append("STAGE: [DATA] — no candles fetched for any symbol")
        if last_cycle.get("fresh_candles", 0) == 0:
            failures.append("STAGE: [DATA] — no fresh candles (<5 min old)")
        if last_cycle.get("conditions_passed", 0) == 0:
            failures.append("STAGE: [EVAL] — no conditions passed (ALWAYS_TRUE should pass for every fresh candle)")
        if last_cycle.get("signals_created", 0) == 0:
            failures.append("STAGE: [SIGNAL] — no signal created")
        if last_cycle.get("signals_persisted", 0) == 0:
            failures.append("STAGE: [SIGNAL] — signal created but not persisted to DB")

    # 6. Verify the signals are actually in the DB and visible via the API path
    print(f"\n[6/6] Verifying DB + API visibility...")
    sig_count = int(repo.db.execute("SELECT COUNT(*) FROM signals").fetchone()[0])
    print(f"  signals table count: {sig_count}")
    if sig_count == 0:
        failures.append("STAGE: [API] — signals table is empty after a successful scan")

    # Check the most recent signal was emitted by SIGNAL_PIPELINE_TEST
    last_signal = repo.db.execute(
        "SELECT strategy_name, symbol, side, entry, timeframe, created_at, "
        "candle_close_time, mode FROM signals ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if last_signal:
        print(f"  most recent signal: {last_signal}")
        strategy_name = last_signal[0]
        if strategy_name != "SIGNAL_PIPELINE_TEST":
            failures.append(
                f"most recent signal strategy is {strategy_name!r}, expected SIGNAL_PIPELINE_TEST"
            )
    else:
        failures.append("no signal row found in DB after scan")

    # Final report
    print("\n" + "=" * 60)
    if failures:
        print("RESULT: FAILED")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("RESULT: OK — full pipeline verified end-to-end")
    print(f"  strategies_loaded: {last_cycle.get('symbols_loaded', 0)}")
    print(f"  symbols_evaluated: {last_cycle.get('symbols_evaluated', 0)}")
    print(f"  fresh_candles: {last_cycle.get('fresh_candles', 0)}")
    print(f"  conditions_passed: {last_cycle.get('conditions_passed', 0)}")
    print(f"  signals_created: {last_cycle.get('signals_created', 0)}")
    print(f"  signals_persisted: {last_cycle.get('signals_persisted', 0)}")
    print(f"  signals_in_db: {sig_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
