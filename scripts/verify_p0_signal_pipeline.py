"""
P0 verification: SIGNAL_PIPELINE_TEST receives real Binance candles and produces a persisted signal.

Run from project root:
  .venv/Scripts/python.exe scripts/verify_p0_signal_pipeline.py
"""
import os
import sys
import time
import json
import logging
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv(".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("p0_verify")

from app.config import Settings
from app.exchange import create_exchange
from app.market_data import AdapterMarketDataProvider
from app.database import TradingRepository
from app.database.repository import get_default_repository
from app.strategy.scanner import StrategyScanner
from app.strategy.diagnostics import ScannerDiagnostics

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def banner(t: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {t}")
    print("=" * 70)


def main() -> int:
    banner("STEP 1 — Settings / mode")
    settings = Settings()
    print(f"TRADING_MODE = {settings.trading_mode.value}")
    print(f"DEFAULT_SYMBOL = {settings.default_symbol}")
    print(f"TIMEFRAME = {settings.timeframe}")
    assert settings.trading_mode.value == "paper", "must be paper mode"

    banner("STEP 2 — Direct candle fetch (Binance spot public API)")
    exchange = create_exchange(settings)
    md = AdapterMarketDataProvider(exchange)
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        c = md.candles(sym, "1m", 5)
        if c:
            last = c[-1]
            print(f"  {sym}: {len(c)} candles | last close={last.close} | volume={last.volume} | close_time={last.close_time}")
            assert len(c) > 0, f"{sym} returned empty"
        else:
            print(f"  {sym}: EMPTY")
            raise SystemExit(f"FIX NOT IN EFFECT — {sym} still empty")

    banner("STEP 3 — Scanner: single cycle over SIGNAL_PIPELINE_TEST")
    repo = get_default_repository()
    scanner = StrategyScanner(repo, md)
    signals = scanner.scan_once()
    print(f"scan_once() returned {len(signals)} signal(s)")

    diag = scanner.diagnostics.snapshot()
    last = diag.get("last_cycle") or {}
    print("--- last cycle diagnostics ---")
    for k, v in last.items():
        print(f"  {k} = {v}")

    banner("STEP 4 — Confirm signal persisted in DB")
    db_signals = repo.list_signals(limit=10)
    print(f"DB now contains {len(db_signals)} signal(s) (top 10)")
    for s in db_signals[:5]:
        print(f"  id={s.get('id','?')[:8]}.. strategy={s.get('strategy_id','?')[:8]}.. symbol={s.get('symbol')} side={s.get('side')} conf={s.get('confidence')}")

    banner("STEP 5 — Acceptance criteria")
    ac = {
        "A. SOLUSDT received real candles": any(md.candles("SOLUSDT", "1m", 5)),
        "B. scanner reports non-zero candle count": (last.get("symbols_with_candles", 0) or 0) > 0,
        "C. SIGNAL_PIPELINE_TEST evaluated": (last.get("symbols_evaluated", 0) or 0) > 0,
        "D. SIGNAL_PIPELINE_TEST created a signal": (last.get("signals_created", 0) or 0) > 0,
        "E. Signal persisted in DB": any(s.get("strategy_id") for s in db_signals),
        "F. signal count > 0": len(db_signals) > 0,
        "I. No live orders (still paper)": settings.trading_mode.value == "paper",
    }
    for k, v in ac.items():
        print(f"  [{'OK' if v else 'FAIL'}] {k}")

    fail = [k for k, v in ac.items() if not v]
    if fail:
        print(f"\nFAILED: {fail}")
        return 1
    print("\nALL ACCEPTANCE CRITERIA PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
