from dataclasses import dataclass

from .base import BUY, Strategy


@dataclass
class BuyAndHold(Strategy):
    key = "bh"
    doc = "Buy on the first tradeable day and never sell (benchmark)"

    def signals(self, prices):
        # Emit BUY every bar; the simulator ignores BUY while a position is held,
        # so this buys once on the first eligible day and holds to the end.
        for date, close in prices:
            yield date, close, BUY
