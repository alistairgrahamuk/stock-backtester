"""One run of the backtester: validate the config, make sure prices are cached, compare the strategies."""
import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import strategies
from db import init_db
from fetcher import ensure_prices, load_prices
from portfolio import Costs
from simulate import BacktestResult, compare

DEFAULT_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]
DEFAULT_YEARS = 3  # window length when start is not given


def default_end() -> str:
    return (dt.date.today() - dt.timedelta(days=1)).isoformat()  # yesterday: the last complete bar


def default_start(end: str) -> str:
    e = dt.date.fromisoformat(end)
    return e.replace(year=e.year - DEFAULT_YEARS).isoformat()


@dataclass
class RunConfig:
    symbols: list[str] = field(default_factory=lambda: list(DEFAULT_SYMBOLS))
    start: Optional[str] = None
    end: Optional[str] = None
    strategies: list[str] = field(default_factory=lambda: list(strategies.DEFAULT_SPECS))
    cash: float = 10_000.0
    costs: Costs = field(default_factory=Costs)

    def __post_init__(self):
        self.symbols = [s.strip().upper() for s in self.symbols if s.strip()]
        if not self.symbols:
            raise ValueError("no symbols given")
        self.end = self.end or default_end()
        self.start = self.start or default_start(self.end)
        for d in (self.start, self.end):
            dt.date.fromisoformat(d)  # raises ValueError on a bad date
        if self.start >= self.end:
            raise ValueError(f"start {self.start} must be before end {self.end}")
        self.strategy_objs = [strategies.parse_spec(s) for s in self.strategies]
        if not self.strategy_objs:
            raise ValueError("no strategies given")


def costs_from_percentages(fee: float = 0.0, slippage: float = 0.0, interest: float = 0.0) -> Costs:
    """Build Costs from the user-facing percentages (0.15 means 0.15%)."""
    return Costs(fee_pct=fee / 100.0, slippage_pct=slippage / 100.0, interest_rate=interest / 100.0)


@dataclass
class RunOutput:
    config: RunConfig
    results: list[BacktestResult]
    uneven: dict  # symbol -> last date, for symbols ending before the latest


def run(config: RunConfig) -> RunOutput:
    """Fetch whatever the cache is missing, then run every strategy over the same prices."""
    init_db()
    ensure_prices(config.symbols, config.start, config.end)

    symbol_prices = {s: load_prices(s, config.start, config.end) for s in config.symbols}
    ends = {s: bars[-1][0] for s, bars in symbol_prices.items() if bars}
    latest = max(ends.values(), default=None)
    uneven = {s: d for s, d in ends.items() if d != latest}

    results = compare(config.strategy_objs, symbol_prices, config.cash, costs=config.costs)
    return RunOutput(config=config, results=results, uneven=uneven)
