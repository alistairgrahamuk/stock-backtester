from dataclasses import dataclass

from .base import BUY, SELL, Strategy


@dataclass
class Breakout(Strategy):
    key = "breakout"
    doc = "Donchian: buy on a close above the prior N-bar high, sell on a close below the prior M-bar low"

    # Window lengths in trading days, settable from the command line as "breakout:entry,exit".
    entry: int = 20  # buy when today's close beats the highest close of the previous `entry` bars
    exit: int = 10   # sell when it falls below the lowest close of the previous `exit` bars; shorter, to cut losers fast

    @property
    def warmup(self) -> int:
        return max(self.entry, self.exit) + 1

    def signals(self, prices):
        closes = [c for _, c in prices]
        for i, (date, close) in enumerate(prices):
            signal = None
            if i >= self.entry and close > max(closes[i - self.entry:i]):
                signal = BUY
            elif i >= self.exit and close < min(closes[i - self.exit:i]):
                signal = SELL
            yield date, close, signal
