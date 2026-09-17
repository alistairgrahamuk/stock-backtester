import argparse
import datetime as dt
import sys

import strategies
from portfolio import Costs
from run import DEFAULT_SYMBOLS, DEFAULT_YEARS, RunConfig, costs_from_percentages, run
from simulate import BacktestResult


def iso_date(text: str) -> str:
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {text!r}")


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Backtest one or more strategies over the same symbols and compare them.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python main.py                                      # default strategies on default symbols\n"
            "  python main.py -s moving-average:10,30 -s moving-average:20,50 -s bh   # MA variants vs buy-and-hold\n"
            "  python main.py --symbols AAPL,AMZN -s breakout:55,20 --trades\n"
            "  python main.py --fee 0.15 --slippage 0.03 --interest 3.8   # with trading costs and interest on cash\n"
            "\navailable strategies:\n" + strategies.describe_all()
        ),
    )
    p.add_argument("-s", "--strategy", action="append", metavar="SPEC",
                   help="strategy spec, name[:p1,p2,...]; repeatable (default: %s)" % " ".join(strategies.DEFAULT_SPECS))
    p.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), metavar="SYM,SYM",
                   help="comma-separated tickers (default: %(default)s)")
    p.add_argument("--start", type=iso_date, metavar="YYYY-MM-DD",
                   help="first date of price history to use (default: %d years before --end)" % DEFAULT_YEARS)
    p.add_argument("--end", type=iso_date, metavar="YYYY-MM-DD",
                   help="last date of price history to use (default: yesterday, the last complete bar)")
    p.add_argument("--cash", type=float, default=10_000.0, help="starting cash (default: %(default)s)")
    c = p.add_argument_group("costs", "all default to zero")
    c.add_argument("--fee", type=float, default=0.0, metavar="PCT",
                   help="percentage charge per buy and per sell, e.g. 0.15")
    c.add_argument("--slippage", type=float, default=0.0, metavar="PCT",
                   help="fill worse than the close by this percent per side")
    c.add_argument("--interest", type=float, default=0.0, metavar="PCT",
                   help="annual interest paid on uninvested cash, e.g. 3.8")
    p.add_argument("--trades", action="store_true", help="print the trade log for each strategy")
    p.add_argument("--list", action="store_true", help="list available strategies, then exit")
    return p.parse_args(argv)


def fmt_pct(x, signed=True):
    if x is None:
        return "  n/a"
    return f"{x * 100:+.1f}%" if signed else f"{x * 100:.1f}%"


def print_summary(results: list[BacktestResult], symbols: list[str], cash: float, costs: Costs):
    r0 = results[0]
    bar = "=" * 106
    print()
    print(bar)
    print(f"Window   : {r0.start_date}  ->  {r0.end_date}   ({len(r0.equity)} trading days)")
    print(f"Symbols  : {', '.join(symbols)}")
    print(f"Cash     : {cash:,.2f}   (equal-weight sizing on current portfolio value)")
    print(f"Costs    : {costs.describe()}")
    print(bar)
    print(f"{'Strategy':<28s} {'Return':>8s} {'Final':>12s} {'Max DD':>8s} {'Trades':>7s} {'Win%':>7s} "
          f"{'In mkt':>7s} {'Fees':>9s} {'Interest':>8s}")
    print("-" * 106)
    for r in sorted(results, key=lambda r: r.total_return, reverse=True):
        print(
            f"{r.strategy.label():<28s} {fmt_pct(r.total_return):>8s} {r.final_value:>12,.2f} "
            f"{fmt_pct(r.max_drawdown):>8s} {r.trade_count:>7d} "
            f"{fmt_pct(r.win_rate, signed=False):>7s} {fmt_pct(r.time_in_market, signed=False):>7s} "
            f"{r.fees_paid:>9,.2f} {r.interest_earned:>8,.2f}"
        )
    print(bar)


def print_trades(r: BacktestResult):
    print()
    print(f"--- {r.strategy.label()}: {r.trade_count} trades ---")
    for tx in r.portfolio.transactions:
        fee = f"  fee {tx.fee:>6.2f}" if tx.fee else ""
        print(f"  {tx.date}  {tx.action:5s}{tx.qty:>6d} {tx.symbol:<6s} @ {tx.price:>8.2f}{fee}"
              f"   cash={tx.cash_after:>10,.2f}")
    held = r.portfolio.positions
    print("  Final positions:" if held else "  Final positions: (none, all in cash)")
    for sym, pos in held.items():
        last = r.final_prices[sym]
        mkt = pos.qty * last
        print(f"    {sym:<6s} {pos.qty:>6d} sh  avg {pos.avg_cost:>8.2f}  last {last:>8.2f}  "
              f"value {mkt:>10,.2f}  pnl {mkt - pos.qty * pos.avg_cost:>+10,.2f}")


def main(argv=None):
    args = parse_args(argv)
    if args.list:
        print("strategies:")
        print(strategies.describe_all())
        return 0

    try:
        config = RunConfig(
            symbols=args.symbols.split(","),
            start=args.start,
            end=args.end,
            strategies=args.strategy or strategies.DEFAULT_SPECS,
            cash=args.cash,
            costs=costs_from_percentages(args.fee, args.slippage, args.interest),
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        out = run(config)
    except (RuntimeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if out.uneven:
        latest = max(r.end_date for r in out.results)
        lagging = ", ".join(f"{s} ends {d}" for s, d in sorted(out.uneven.items()))
        print(f"warning: uneven history, latest bar is {latest} but {lagging}", file=sys.stderr)

    print_summary(out.results, config.symbols, config.cash, config.costs)
    if args.trades:
        for r in out.results:
            print_trades(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
