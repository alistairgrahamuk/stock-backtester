from dataclasses import dataclass

from .base import BUY, SELL, Strategy, rolling_mean


@dataclass
class MACrossover(Strategy):
    key = "moving-average"
    doc = "Buy when the short Simple Moving Average (SMA) crosses above the long SMA, sell when it crosses below"

    # Averaging windows in trading days, settable from the command line as "moving-average:short,long".
    short: int = 20  # fast average, about a month: follows recent prices closely
    long: int = 50   # slow average, about ten weeks: the trend the fast one is measured against

    @property
    def warmup(self) -> int:
        return self.long + 1

    def signals(self, prices):
        closes = [c for _, c in prices]
        ma_s = rolling_mean(closes, self.short)
        ma_l = rolling_mean(closes, self.long)
        prev_s = prev_l = None
        for i, (date, close) in enumerate(prices):
            s, l = ma_s[i], ma_l[i]
            signal = None
            if s is not None and l is not None and prev_s is not None and prev_l is not None:
                if prev_s <= prev_l and s > l:
                    signal = BUY
                elif prev_s >= prev_l and s < l:
                    signal = SELL
            prev_s, prev_l = s, l
            yield date, close, signal
