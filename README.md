# stock-backtester

A small command-line backtester. It replays a few trading strategies over the
same stocks and the same dates, and shows how each would have done against
simply buying and holding.

Daily prices come from [Twelve Data](https://twelvedata.com/) and are cached
in a local SQLite file. Plain Python: the only dependencies are `requests`
and `python-dotenv`.

## Set up a virtual environment (Ubuntu)

Ubuntu's system Python refuses a bare `pip install` (the
"externally-managed-environment" error), so install into a `.venv` in the
project folder. The `venv` module is packaged separately on Ubuntu:

```
sudo apt update
sudo apt install python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
```

The prompt now starts with `(.venv)`, and `python` and `pip` point into
`.venv`. Run `source .venv/bin/activate` again in each new terminal, and
`deactivate` to leave. To start over, delete the `.venv` folder and recreate it.

## Run it

```
pip install -r requirements.txt
echo "TWELVEDATA_API_KEY=your_key" > .env     # a free key is enough
python main.py
```

```
python main.py -s moving-average:10,30 -s moving-average:20,50 -s bh   # MA variants vs buy-and-hold
python main.py --symbols AAPL,AMZN -s breakout:55,20 --trades
python main.py --fee 0.15 --slippage 0.03 --interest 3.8
python main.py --help                                  # every option, and the strategy list
```

```
Window   : 2023-11-28  ->  2026-09-15   (701 trading days)
Symbols  : AAPL, MSFT, GOOGL, NVDA, TSLA
Cash     : 10,000.00   (equal-weight sizing on current portfolio value)
Costs    : 0.15% fee per side, 0.03% slippage per side, 3.8% interest on cash
Strategy                       Return        Final   Max DD  Trades    Win%  In mkt      Fees Interest
bh                            +125.2%    22,524.98   -33.1%       5     n/a  100.0%     14.51    34.78
moving-average:20,50           +58.4%    15,840.32   -17.8%      76   50.0%   86.0%    298.53   643.06
breakout:20,10                 +58.4%    15,837.45   -11.9%     161   40.5%   82.5%    658.26   856.21
```

## How it works

`main.py` parses the command line, `run.py` validates the config and loads
prices, `simulate.py` walks the dates and trades through `portfolio.py`.
Each symbol gets an equal share of the portfolio. Trades fill at the day's
close, in whole shares.

Two design choices worth knowing about:

- **Strategies are plugins.** A strategy is a dataclass in `strategies/` with
  one method, `signals()`, that turns a price series into BUY/SELL signals.
  Its dataclass fields are its parameters, so `moving-average:20,50` on the
  command line is parsed from the field list with no per-strategy code. Adding
  a strategy is one small file and one line in the registry. Strategies only emit
  signals; sizing, cash and costs all live in the simulator, so every
  strategy is compared on the same terms.
- **The price cache is incremental.** A `coverage` table records the date
  range already requested for each symbol, and only the gaps either side are
  fetched. Coverage is stored rather than inferred from the bars because
  weekends and holidays have no bar, so the bars alone can't say whether a
  range has been fetched.

## Limits

Dividends are ignored, which understates buy-and-hold a little. There is no
shorting, leverage or intraday data.
