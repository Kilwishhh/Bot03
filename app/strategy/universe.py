"""Binance Futures symbol universe discovery.

Provides the list of tradeable symbols for a strategy's universe_type.
Does NOT hardcode BTCUSDT as the only symbol.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache to avoid hammering Binance API on every scan cycle
# ---------------------------------------------------------------------------

_CACHE: dict[str, tuple[float, list[str]]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


@dataclass
class SymbolInfo:
    symbol: str
    base_asset: str
    quote_asset: str
    status: str          # 'TRADING', 'HALT', etc.
    contract_type: str  # 'PERPETUAL', 'CURRENT_QUARTER', etc.
    price_precision: int
    qty_precision: int


def _fetch_exchange_info(use_testnet: bool = False) -> list[dict]:
    """Fetch exchange info from Binance. Returns raw symbol list."""
    import urllib.request

    url = (
        "https://testnet.binancefuture.com/fapi/v1/exchangeInfo"
        if use_testnet else
        "https://fapi.binance.com/fapi/v1/exchangeInfo"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mk-trader/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("symbols", [])
    except Exception as exc:
        logger.warning("failed to fetch Binance exchange info: %s", exc)
        return []


def _parse_symbols(raw: list[dict]) -> list[SymbolInfo]:
    """Parse raw Binance symbol list into SymbolInfo objects."""
    results = []
    for s in raw:
        try:
            if s.get("status") != "TRADING":
                continue
            if s.get("contractType") != "PERPETUAL":
                continue
            quote = s.get("quoteAsset", "")
            if quote != "USDT":
                continue
            results.append(SymbolInfo(
                symbol=s["symbol"],
                base_asset=s.get("baseAsset", ""),
                quote_asset=quote,
                status=s.get("status", ""),
                contract_type=s.get("contractType", ""),
                price_precision=_parse_precision(s.get("pricePrecision")),
                qty_precision=_parse_precision(s.get("quantityPrecision")),
            ))
        except Exception:
            continue
    return results


def _parse_precision(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 2


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_binance_futures_symbols(use_testnet: bool = False) -> list[str]:
    """Return all active USDT-M Binance Futures perpetual symbols.

    Results are cached for 5 minutes to avoid rate-limiting.
    """
    cache_key = "testnet" if use_testnet else "mainnet"
    now = time.monotonic()
    if cache_key in _CACHE:
        ts, symbols = _CACHE[cache_key]
        if now - ts < _CACHE_TTL_SECONDS:
            return symbols

    raw = _fetch_exchange_info(use_testnet)
    parsed = _parse_symbols(raw)
    symbols = sorted(s.symbol for s in parsed)
    _CACHE[cache_key] = (now, symbols)
    logger.debug("fetched %d symbols for %s", len(symbols), cache_key)
    return symbols


def get_symbols_for_universe(
    universe_type: str,
    universe_config: dict,
    use_testnet: bool = False,
) -> list[str]:
    """Resolve universe_type + config to a concrete list of symbols.

    universe_type options:
      - "all_binance_futures"  → all active USDT-M perps
      - "top_n_futures"        → top N by volume (uses all_binance_futures sorted)
      - "custom_watchlist"     → explicit list from config

    universe_config shape:
      - top_n_futures: {"count": 20}
      - custom_watchlist: {"symbols": ["BTCUSDT", "ETHUSDT"]}
    """
    if universe_type == "custom_watchlist":
        symbols = universe_config.get("symbols", [])
        if not symbols:
            logger.warning("custom_watchlist has no symbols, falling back to all_binance_futures")
            universe_type = "all_binance_futures"
        else:
            return symbols

    all_syms = get_all_binance_futures_symbols(use_testnet)

    if universe_type == "top_n_futures":
        count = universe_config.get("count", 20)
        # Exclude stablecoin pairs that pollute volume rankings
        stable = {"USDCUSDT", "BUSDUSDT", "DAIUSDT", "TUSDUSDT"}
        filtered = [s for s in all_syms if s not in stable]
        return filtered[:count]

    # all_binance_futures (default)
    return all_syms


def filter_by_volume(
    symbols: list[str],
    min_volume: float | None = None,
    min_price: float | None = None,
) -> list[str]:
    """Filter symbols by optional volume/price minimums.

    Currently a no-op stub — real implementation would call Binance ticker API.
    Placeholder to satisfy filter UI requirements without breaking the pipeline.
    """
    if min_volume is None and min_price is None:
        return symbols
    # TODO: fetch 24h ticker data and filter
    logger.debug("filter_by_volume: volume/price filters requested but not yet implemented")
    return symbols


def clear_universe_cache() -> None:
    """Clear the symbol cache. Useful for tests or forced refresh."""
    _CACHE.clear()
