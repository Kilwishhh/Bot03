"""Chronological train/validation/test splitting for out-of-sample work."""

from dataclasses import dataclass

from app.exchange.models import Candle


@dataclass(frozen=True)
class WalkForwardSplit:
    train: list[Candle]
    validation: list[Candle]
    test: list[Candle]


def split_candles(candles: list[Candle], train_ratio: float = 0.6, validation_ratio: float = 0.2) -> WalkForwardSplit:
    if not candles or train_ratio <= 0 or validation_ratio <= 0 or train_ratio + validation_ratio >= 1:
        raise ValueError("ratios must be positive and leave room for an out-of-sample test set")
    train_end = int(len(candles) * train_ratio)
    validation_end = train_end + int(len(candles) * validation_ratio)
    if train_end < 1 or validation_end >= len(candles):
        raise ValueError("not enough candles for all periods")
    return WalkForwardSplit(candles[:train_end], candles[train_end:validation_end], candles[validation_end:])
