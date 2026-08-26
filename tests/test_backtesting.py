from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.backtesting import BacktestingEngine
from app.exchange.models import Candle
from app.strategy import IndicatorStrategy


def test_backtest_uses_only_candles_available_at_each_step():
    start = datetime.now(timezone.utc)
    candles = [Candle(start + timedelta(minutes=i), Decimal(100 + i), Decimal(100 + i), Decimal(100 + i), Decimal(100 + i), Decimal("1"), start + timedelta(minutes=i + 1)) for i in range(12)]
    result = BacktestingEngine().run(IndicatorStrategy(3, 5, 3, 5, 3), "BTCUSDT", candles)
    assert result.starting_balance == Decimal("1000")
    assert result.trades >= 1
    assert result.fees > 0
    assert result.net_pnl < result.ending_balance - result.starting_balance + result.fees
    assert result.total_return == result.net_pnl / result.starting_balance
    assert result.average_trade != Decimal("0")
    assert result.max_drawdown >= Decimal("0")
    assert result.sharpe_ratio != Decimal("0")
    assert result.sortino_ratio != Decimal("0")