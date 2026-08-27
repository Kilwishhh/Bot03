"""Run a small local backtest demonstration without network access."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.backtesting import BacktestingEngine
from app.exchange.models import Candle
from app.strategy import IndicatorStrategy


def main() -> None:
    start = datetime.now(UTC)
    prices = [100, 101, 102, 103, 104, 105, 104, 103, 102, 101, 100, 101, 102]
    candles = [Candle(start + timedelta(minutes=i), Decimal(price), Decimal(price), Decimal(price), Decimal(price), Decimal("1"), start + timedelta(minutes=i + 1)) for i, price in enumerate(prices)]
    result = BacktestingEngine().run(IndicatorStrategy(3, 5, 3, 5, 3), "BTCUSDT", candles)
    print(f"trades={result.trades} wins={result.wins} win_rate={result.win_rate:.2%}")
    print(f"fees={result.fees} net_pnl={result.net_pnl} total_return={result.total_return:.2%}")
    print(f"max_drawdown={result.max_drawdown} sharpe={result.sharpe_ratio:.4f} sortino={result.sortino_ratio:.4f}")
    print("Performance not yet validated.")


if __name__ == "__main__":
    main()
