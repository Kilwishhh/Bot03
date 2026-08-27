"""Scan all available Binance Futures symbols through a market-data provider."""

import logging

from app.market_data.base import MarketDataProvider
from app.signals import SignalEngine
from app.signals.models import Signal, SignalSide

logger = logging.getLogger(__name__)


class FuturesSignalScanner:
    def __init__(self, exchange, market_data: MarketDataProvider, signal_engine: SignalEngine, publisher=None) -> None:
        self._exchange = exchange
        self._market_data = market_data
        self._signal_engine = signal_engine
        self._publisher = publisher

    def scan(self, timeframe: str, limit: int = 200, symbols: list[str] | None = None) -> list[Signal]:
        symbols_to_scan = symbols if symbols is not None else self._exchange.get_symbols()
        signals: list[Signal] = []
        for symbol in symbols_to_scan:
            try:
                candles = self._market_data.candles(symbol, timeframe, limit)
                signal = self._signal_engine.generate(symbol, candles)
                signals.append(signal)
                if self._publisher is not None and signal.side is not SignalSide.HOLD:
                    try:
                        self._publisher.publish(signal)
                    except Exception as error:
                        logger.warning("signal publication failed for %s: %s", symbol, error)
            except Exception as error:
                logger.warning("symbol scan failed for %s: %s", symbol, error)
        return signals
