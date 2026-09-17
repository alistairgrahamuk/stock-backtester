from dataclasses import dataclass, field


@dataclass
class Costs:
    """Trading costs and cash treatment. All rates are fractions (0.0015 = 0.15%)."""

    fee_pct: float = 0.0        # percentage charge on each buy and each sell
    slippage_pct: float = 0.0   # fill worse than the close by this much: buys higher, sells lower (models the spread)
    interest_rate: float = 0.0  # annual simple interest paid on uninvested cash, accrued daily

    def describe(self) -> str:
        parts = []
        if self.fee_pct:
            parts.append(f"{self.fee_pct * 100:g}% fee per side")
        if self.slippage_pct:
            parts.append(f"{self.slippage_pct * 100:g}% slippage per side")
        if self.interest_rate:
            parts.append(f"{self.interest_rate * 100:g}% interest on cash")
        return ", ".join(parts) or "none"


@dataclass
class Position:
    symbol: str
    qty: int = 0
    avg_cost: float = 0.0  # per share, including buy-side costs


@dataclass
class Transaction:
    date: str
    symbol: str
    action: str
    qty: int
    price: float  # fill price after slippage
    fee: float
    cash_after: float


@dataclass
class Portfolio:
    cash: float
    costs: Costs = field(default_factory=Costs)
    positions: dict = field(default_factory=dict)
    transactions: list = field(default_factory=list)
    round_trip_pnl: list = field(default_factory=list)  # realised P&L per closed position, net of all costs
    fees_paid: float = 0.0
    interest_earned: float = 0.0

    def holds(self, symbol: str) -> bool:
        return symbol in self.positions

    def invested(self) -> bool:
        return bool(self.positions)

    def buy(self, date: str, symbol: str, price: float, budget: float) -> bool:
        """Open a position, spending up to `budget` (fees included). Returns False if nothing affordable."""
        if self.holds(symbol):
            return False
        fill = price * (1.0 + self.costs.slippage_pct)
        qty = int(budget / (fill * (1.0 + self.costs.fee_pct)))  # most whole shares the budget covers, fee included
        if qty <= 0:
            return False
        gross = qty * fill
        fee = gross * self.costs.fee_pct
        self.cash -= gross + fee
        self.fees_paid += fee
        self.positions[symbol] = Position(symbol=symbol, qty=qty, avg_cost=(gross + fee) / qty)
        self.transactions.append(Transaction(date, symbol, "BUY", qty, fill, fee, self.cash))
        return True

    def sell_all(self, date: str, symbol: str, price: float) -> bool:
        """Close the whole position and record the round trip's P&L, net of all costs."""
        pos = self.positions.get(symbol)
        if pos is None:
            return False
        fill = price * (1.0 - self.costs.slippage_pct)
        gross = pos.qty * fill
        fee = gross * self.costs.fee_pct
        self.cash += gross - fee
        self.fees_paid += fee
        self.round_trip_pnl.append(gross - fee - pos.qty * pos.avg_cost)
        self.transactions.append(Transaction(date, symbol, "SELL", pos.qty, fill, fee, self.cash))
        del self.positions[symbol]
        return True

    def accrue_interest(self, days: int) -> None:
        """Credit simple interest on the cash balance for `days` calendar days."""
        if self.costs.interest_rate and self.cash > 0 and days > 0:
            earned = self.cash * self.costs.interest_rate * days / 365.0
            self.cash += earned
            self.interest_earned += earned

    def value(self, current_prices: dict) -> float:
        equity = sum(pos.qty * current_prices.get(sym, 0.0) for sym, pos in self.positions.items())
        return self.cash + equity
