import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from portfolio import Costs, Portfolio
from strategies import BUY, SELL, Strategy

PriceData = dict[str, list[tuple[str, float]]]  # symbol -> [(date, close), ...] oldest first


@dataclass
class BacktestResult:
    strategy: Strategy
    portfolio: Portfolio
    starting_cash: float
    equity: list  # [(date, portfolio value), ...]
    final_prices: dict
    days_invested: int

    @property
    def start_date(self) -> str:
        return self.equity[0][0]

    @property
    def end_date(self) -> str:
        return self.equity[-1][0]

    @property
    def final_value(self) -> float:
        return self.equity[-1][1]

    @property
    def total_return(self) -> float:
        return self.final_value / self.starting_cash - 1.0

    @property
    def max_drawdown(self) -> float:
        peak, worst = float("-inf"), 0.0
        for _, v in self.equity:
            peak = max(peak, v)
            worst = min(worst, v / peak - 1.0)
        return worst

    @property
    def trade_count(self) -> int:
        return len(self.portfolio.transactions)

    @property
    def win_rate(self) -> Optional[float]:
        closed = self.portfolio.round_trip_pnl
        if not closed:
            return None
        return sum(1 for p in closed if p > 0) / len(closed)

    @property
    def time_in_market(self) -> float:
        return self.days_invested / len(self.equity) if self.equity else 0.0

    @property
    def fees_paid(self) -> float:
        return self.portfolio.fees_paid

    @property
    def interest_earned(self) -> float:
        return self.portfolio.interest_earned


def common_start_date(symbol_prices: PriceData, strategies: list[Strategy]) -> str:
    """First date on which every strategy has finished warming up, so comparisons share a window."""
    warm = max((s.warmup for s in strategies), default=0)
    dates = sorted({d for bars in symbol_prices.values() for d, _ in bars})
    if not dates:
        raise ValueError("no price data loaded")
    return dates[min(warm, len(dates) - 1)]


def backtest(
    strategy: Strategy,
    symbol_prices: PriceData,
    starting_cash: float = 10_000.0,
    start_date: Optional[str] = None,
    costs: Optional[Costs] = None,
) -> BacktestResult:
    """Run one strategy across all symbols with equal-weight sizing on current portfolio value.

    The strategy's BUY/SELL signals decide when it wants to hold each symbol. Each symbol
    gets an equal slot of the portfolio: a position is sized once when bought and then
    left alone until the strategy sells it.
    """
    symbols = list(symbol_prices)
    missing = [s for s in symbols if not symbol_prices[s]]
    if missing:
        raise ValueError(f"no price data for: {', '.join(missing)}")

    timeline: dict[str, dict[str, tuple[float, Optional[str]]]] = defaultdict(dict)
    for symbol in symbols:
        for date, close, signal in strategy.signals(symbol_prices[symbol]):
            timeline[date][symbol] = (close, signal)

    all_dates = sorted(timeline)
    dates = [d for d in all_dates if start_date is None or d >= start_date]
    if not dates:
        raise ValueError("no tradeable dates after warm-up; fetch more history or shorten the windows")

    portfolio = Portfolio(cash=starting_cash, costs=costs or Costs())
    last_close: dict[str, float] = {}
    prev_date: Optional[dt.date] = None
    wants_in = {s: False for s in symbols}  # latest strategy state per symbol
    equity = []
    days_invested = 0

    for date in all_dates:
        day = timeline[date]
        for symbol, (close, _) in day.items():
            last_close[symbol] = close
        if date < dates[0]:
            continue  # warm-up: prices are known but nothing is traded or signalled yet

        today = dt.date.fromisoformat(date)
        if prev_date is not None:
            portfolio.accrue_interest((today - prev_date).days)  # credited overnight, before today's trades
        prev_date = today

        for symbol, (_, signal) in day.items():
            if signal == BUY:
                wants_in[symbol] = True
            elif signal == SELL:
                wants_in[symbol] = False

        # Sells first so freed cash is available for the same day's buys.
        for symbol in symbols:
            if portfolio.holds(symbol) and not wants_in[symbol]:
                portfolio.sell_all(date, symbol, last_close[symbol])

        for symbol in symbols:
            if wants_in[symbol] and not portfolio.holds(symbol) and symbol in day:
                # Equal-weight slot, based on *current* value so gains compound.
                slot = portfolio.value(last_close) / len(symbols)
                budget = min(slot, portfolio.cash)
                portfolio.buy(date, symbol, day[symbol][0], budget)  # no-op if the budget can't cover a share

        equity.append((date, portfolio.value(last_close)))
        if portfolio.invested():
            days_invested += 1

    return BacktestResult(
        strategy=strategy,
        portfolio=portfolio,
        starting_cash=starting_cash,
        equity=equity,
        final_prices=dict(last_close),
        days_invested=days_invested,
    )


def compare(
    strategies: list[Strategy],
    symbol_prices: PriceData,
    starting_cash: float,
    costs: Optional[Costs] = None,
) -> list[BacktestResult]:
    """Run every strategy over the same symbols, costs and post-warm-up window."""
    start = common_start_date(symbol_prices, strategies)
    return [backtest(s, symbol_prices, starting_cash, start_date=start, costs=costs) for s in strategies]
