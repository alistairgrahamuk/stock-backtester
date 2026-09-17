"""Strategy registry. Add a strategy by importing it and listing it in ALL."""
from .base import BUY, SELL, Strategy
from .breakout import Breakout
from .buy_hold import BuyAndHold
from .ma_crossover import MACrossover

ALL = [BuyAndHold, MACrossover, Breakout]
REGISTRY: dict[str, type[Strategy]] = {cls.key: cls for cls in ALL}

DEFAULT_SPECS = ["bh", "moving-average:20,50", "breakout"]


def parse_spec(spec: str) -> Strategy:
    """Parse "name" or "name:p1,p2,..." into a strategy instance."""
    name, _, arg_str = spec.strip().partition(":")
    cls = REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"unknown strategy {name!r}; known: {', '.join(REGISTRY)}")
    return cls.from_args([a.strip() for a in arg_str.split(",") if a.strip()])


def describe_all() -> str:
    lines = []
    for cls in ALL:
        params = cls.param_help() or "(no parameters)"
        lines.append(f"  {cls.key:<16s} {cls.doc}\n{'':19s}params: {params}")
    return "\n".join(lines)


__all__ = ["BUY", "SELL", "Strategy", "REGISTRY", "DEFAULT_SPECS", "parse_spec", "describe_all"]
