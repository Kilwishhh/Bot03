# Scanner Candle Timestamp Flow — Audit (P0-01)

## Timestamp semantics

- Binance kline API returns:
  - `row[0]` = open_time (ms epoch, inclusive)
  - `row[6]` = close_time (ms epoch, **exclusive** — start of next candle)
- `app/exchange/paper.py` PaperTradingAdapter.get_candles() reads raw row[0] and row[6] and constructs `Candle(open_time, close_time)`.
- For a 1m candle starting at 18:36:00, Binance returns `close_time = 18:37:00.000`, NOT 18:36:59.999.

## Candle flow

```
Binance kline API
    ↓ (row[0]=open, row[6]=close_exclusive)
PaperTradingAdapter.get_candles() builds Candle(open_time, close_time)
    ↓
AdapterMarketDataProvider.candles() returns list[Candle] in ascending open_time order
    ↓
StrategyScanner._get_candles_for_timeframe() (aggregates 1m→N m if needed)
    ↓
StrategyScanner._scan_symbol() picks candles[-1] as "latest candle"
    ↓
_candle_age_seconds(candles[-1]) = (now_utc - close_time).total_seconds()
    ↓
is_fresh = age < 300   # accept if within 5 min
```

## What timestamp means

- `Candle.close_time` is the EXCLUSIVE end of the candle interval (Binance semantics).
- A candle is "closed" only when `now >= close_time`.
- A candle is "in-progress" when `now < close_time` (negative age).
- A candle is "future" when `close_time > now` by a large margin (clock skew or wrong data).

## Why negative candle_age occurs

- At `now=18:36:52`, latest 1m candle's `close_time=18:37:00.000`.
- `age = (18:36:52 - 18:37:00) = -8 seconds`.
- The current scanner code accepts this candle because `is_fresh = age < 300` is true (negative < 300).
- It then evaluates conditions on a still-forming candle — unsafe.

## Scanner picks latest candle

- `candles[-1]` (Python list last element) = most recent open_time.
- For ascending-sorted Binance data, this is the in-progress candle.

## Candle age calculation

- `now = datetime.now(UTC)`
- `ct = candle.close_time`
- If `ct.tzinfo is None`, replace with UTC (defensive)
- `age = (now - ct).total_seconds()`
- Result CAN be negative when candle is in-progress.

## Timezone handling

- PaperTradingAdapter: uses `datetime.fromtimestamp(ms/1000, UTC)` — tz-aware.
- Scanner: defensive `if ct.tzinfo is None: ct = ct.replace(tzinfo=UTC)` — handles both.
- All comparisons use UTC.

## Reference clock

- `datetime.now(UTC)` — system clock, not Binance server time.
- For 1m candles, the small drift is acceptable.
- No per-symbol network time request.

## Findings

1. ✅ Timestamps are timezone-aware (UTC).
2. ✅ Timestamps are unambiguous (open_time + close_time).
3. ❌ Scanner accepts in-progress candles (negative age) because `age < 300` test passes for negative values.
4. ❌ Scanner does not check whether the candle is closed before evaluating conditions.
5. ❌ No timeframe-integrity check between strategy `timeframe` and actual candle interval.
6. ❌ "Empty candle" and "all conditions failed" are treated differently in code but same log severity.
7. ❌ Per-symbol debug log spam (every symbol gets a [DATA] log even when normal).

## Files involved

- `app/exchange/paper.py` — `PaperTradingAdapter.get_candles()`
- `app/market_data/adapter_provider.py` — `AdapterMarketDataProvider.candles()`
- `app/strategy/scanner.py` — `_candle_age_seconds`, `_scan_symbol`, `_get_candles_for_timeframe`
- `app/exchange/models.py` — `Candle` dataclass

## Decision

Treat `Candle.close_time` as the EXCLUSIVE end of the candle interval.
A candle is closed when `now >= close_time` (or `age >= 0`).
A candle is in-progress when `now < close_time` (age < 0).
A candle is future when `close_time > now + tolerance` (clock skew).

In-progress and future candles must be SKIPPED.
Use the last CLOSED candle for evaluation.
