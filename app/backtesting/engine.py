"""Minimal look-ahead-safe strategy backtesting engine."""

from dataclasses import dataclass
from decimal import Decimal

from app.exchange.models import Candle
from app.signals.models import SignalSide
from app.strategy.base import Strategy


@dataclass(frozen=True)
class BacktestResult:
    starting_balance: Decimal
    ending_balance: Decimal
    trades: int
    wins: int
    fees: Decimal = Decimal("0")
    trade_pnls: tuple[Decimal, ...] = ()

    @property
    def net_pnl(self) -> Decimal:
        return self.ending_balance - self.starting_balance

    @property
    def total_return(self) -> Decimal:
        return self.net_pnl / self.starting_balance if self.starting_balance else Decimal("0")

    @property
    def win_rate(self) -> Decimal:
        return Decimal(self.wins) / Decimal(self.trades) if self.trades else Decimal("0")

    @property
    def average_trade(self) -> Decimal:
        return sum(self.trade_pnls, Decimal("0")) / Decimal(len(self.trade_pnls)) if self.trade_pnls else Decimal("0")

    @property
    def profit_factor(self) -> Decimal:
        profits = sum((p for p in self.trade_pnls if p > 0), Decimal("0"))
        losses = -sum((p for p in self.trade_pnls if p < 0), Decimal("0"))
        return profits / losses if losses else (Decimal("0") if profits == 0 else Decimal("Infinity"))

    @property
    def max_drawdown(self) -> Decimal:
        peak = self.starting_balance
        equity = self.starting_balance
        drawdown = Decimal("0")
        for pnl in self.trade_pnls:
            equity += pnl
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        return drawdown

    @property
    def sharpe_ratio(self) -> Decimal:
        if len(self.trade_pnls) < 2 or self.starting_balance <= 0:
            return Decimal("0")
        returns = [pnl / self.starting_balance for pnl in self.trade_pnls]
        average = sum(returns, Decimal("0")) / Decimal(len(returns))
        variance = sum((value - average) ** 2 for value in returns) / Decimal(len(returns) - 1)
        return average / variance.sqrt() if variance > 0 else Decimal("0")

    @property
    def sortino_ratio(self) -> Decimal:
        if not self.trade_pnls or self.starting_balance <= 0:
            return Decimal("0")
        returns = [pnl / self.starting_balance for pnl in self.trade_pnls]
        average = sum(returns, Decimal("0")) / Decimal(len(returns))
        downside = [value for value in returns if value < 0]
        if not downside:
            return Decimal("Infinity") if average > 0 else Decimal("0")
        deviation = (sum(value ** 2 for value in downside) / Decimal(len(downside))).sqrt()
        return average / deviation if deviation > 0 else Decimal("0")


class BacktestingEngine:
    def run(self, strategy: Strategy, symbol: str, candles: list[Candle], starting_balance: Decimal = Decimal("1000"), fee_rate: Decimal = Decimal("0.0004")) -> BacktestResult:
        if starting_balance <= 0 or fee_rate < 0:
            raise ValueError("starting balance must be positive and fee rate cannot be negative")
        balance = starting_balance
        trades = 0
        wins = 0
        fees = Decimal("0")
        trade_pnls: list[Decimal] = []
        entry: Decimal | None = None
        entry_side: SignalSide | None = None
        for index in range(len(candles)):
            signal = strategy.generate_signal(symbol, candles[: index + 1])
            price = candles[index].close
            if entry is None and signal.side in (SignalSide.BUY, SignalSide.SELL):
                entry = price
                entry_side = signal.side
                trades += 1
            elif entry is not None and signal.side in (SignalSide.BUY, SignalSide.SELL):
                change = price - entry if entry_side is SignalSide.BUY else entry - price
                trade_fee = (entry + price) * fee_rate
                balance += change - trade_fee
                fees += trade_fee
                trade_pnl = change - trade_fee
                trade_pnls.append(trade_pnl)
                wins += int(trade_pnl > 0)
                entry = None
                entry_side = None
        if entry is not None:
            exit_price = candles[-1].close
            change = exit_price - entry if entry_side is SignalSide.BUY else entry - exit_price
            trade_fee = (entry + exit_price) * fee_rate
            balance += change - trade_fee
            fees += trade_fee
            trade_pnls.append(change - trade_fee)
        return BacktestResult(starting_balance, balance, trades, wins, fees, tuple(trade_pnls))
