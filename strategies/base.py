"""Strategy interface, plus the moving-average helper."""
from dataclasses import dataclass, fields
from typing import Iterator, Optional

BUY = "BUY"
SELL = "SELL"

# One bar of input: (date, close). One bar of output: (date, close, signal|None).
Bar = tuple[str, float]
Signal = tuple[str, float, Optional[str]]


@dataclass
class Strategy:
    """Base class. Subclasses are dataclasses whose fields are the tunable parameters,
    which is what lets a command-line spec like "moving-average:20,50" be parsed without any
    per-strategy code.

    Class attributes (not dataclass fields):
      key  - short name used on the command line, e.g. "moving-average"
      doc  - one-line description shown by --list
    """
    key = ""
    doc = ""

    @property
    def warmup(self) -> int:
        """Bars needed before the strategy can emit its first signal."""
        return 0

    def signals(self, prices: list[Bar]) -> Iterator[Signal]:
        raise NotImplementedError

    def label(self) -> str:
        """Same form as a command-line spec, e.g. "moving-average:20,50", so it can be pasted back in."""
        params = ",".join(str(getattr(self, f.name)) for f in fields(self))
        return f"{self.key}:{params}" if params else self.key

    @classmethod
    def param_help(cls) -> str:
        return ", ".join(f"{f.name}={f.default}" for f in fields(cls))

    @classmethod
    def from_args(cls, args: list[str]) -> "Strategy":
        """Build from positional string args, e.g. ["20", "50"], converting via the field types."""
        fs = fields(cls)
        if len(args) > len(fs):
            raise ValueError(f"{cls.key} takes at most {len(fs)} parameter(s): {cls.param_help()}")
        kwargs = {}
        for f, raw in zip(fs, args):
            try:
                kwargs[f.name] = f.type(raw)
            except ValueError:
                raise ValueError(f"{cls.key}: parameter {f.name} must be {f.type.__name__}, got {raw!r}")
        return cls(**kwargs)


def rolling_mean(values: list[float], window: int) -> list[Optional[float]]:
    """Simple moving average; None until `window` values are available. O(n)."""
    out: list[Optional[float]] = [None] * len(values)
    total = 0.0
    for i, v in enumerate(values):
        total += v
        if i >= window:
            total -= values[i - window]
        if i + 1 >= window:
            out[i] = total / window
    return out
