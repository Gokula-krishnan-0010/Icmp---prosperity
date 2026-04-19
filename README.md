# IMC Prosperity — Round 2

Algorithmic market-making and trend-following trading system for the [IMC Prosperity](https://prosperity.imc.com/) trading challenge. This repository contains the optimized trading algorithm, historical data analysis tools, and backtesting infrastructure for Round 2.

---

## Project Structure

```
Icmp---prosperity/
├── OPTIMIZATIONS.md              # Detailed optimization report with backtest results
├── README.md                     # This file
└── ROUND_2/
    ├── Solution/
    │   ├── trader.py             # Main trading algorithm (submitted to exchange)
    │   ├── train_model.py        # Statistical analysis of historical price data
    │   ├── backtest.py           # Backtesting harness (old vs new comparison)
    │   └── backtest_all.py       # Multi-day backtest runner
    ├── log1/                     # Submission log (run 294631)
    │   ├── 294631.py             # Code snapshot at submission
    │   ├── 294631.log            # Full exchange log
    │   └── 294631.json           # Structured log data
    ├── log2/                     # Submission log (run 295207)
    ├── log3/                     # Submission log (run 295471)
    ├── prices_round_2_day_-1.csv # Historical order book data (Day -1)
    ├── prices_round_2_day_0.csv  # Historical order book data (Day 0)
    ├── prices_round_2_day_1.csv  # Historical order book data (Day 1)
    ├── trades_round_2_day_-1.csv # Historical trade data (Day -1)
    ├── trades_round_2_day_0.csv  # Historical trade data (Day 0)
    └── trades_round_2_day_1.csv  # Historical trade data (Day 1)
```

---

## Products Traded

| Product | Strategy | Fair Value Model |
|---|---|---|
| **ASH_COATED_OSMIUM** | Mean-reversion market making | Anchored at 10,000 (stationary) |
| **INTARIAN_PEPPER_ROOT** | Trend-adjusted market making | EMA of micro-price + linear time trend (~1.0/tick per 1000 ticks) |

---

## File Descriptions

### Core Algorithm

#### `ROUND_2/Solution/trader.py`
The main trading algorithm submitted to the IMC Prosperity exchange. Implements a `Trader` class with a `run()` method called on every tick by the exchange.

**Two strategies per tick:**
1. **Market Taking** — Aggressively hits mispriced orders in the book (buy below fair, sell above fair)
2. **Market Making** — Places passive bid/ask limit orders around fair value to capture the spread

**Key components:**
- **EMA-based fair value** for PEPPER (tracks the detrended base price using exponential moving average)
- **Micro-pricing** — volume-weighted mid-price that weighs the best bid/ask by opposing side volume
- **Asymmetric inventory skewing** — adjusts bid/ask quotes based on current position to encourage mean-reversion
- **Progressive inventory management** — 4-tier penalty system that increasingly discourages position accumulation
- **End-of-session flattening** — reduces effective position limits in the last 5% of the session
- **One-sided book handling** — continues EMA updates and trading even when only one side of the book is available

**Dependencies:** Only `math` from Python stdlib + `datamodel` provided by the exchange.

#### `ROUND_2/Solution/train_model.py`
Offline statistical analysis script that processes the 3-day historical CSV data to extract optimal parameters for the trading algorithm.

**Computes:**
- Mean price and standard deviation for ASH_COATED_OSMIUM → Fair value anchor
- Linear regression (slope + intercept) for INTARIAN_PEPPER_ROOT → Trend rate and base value
- Detrended noise statistics → Volatility estimates

**Usage:**
```bash
cd ROUND_2/Solution
python train_model.py
```

**Output:**
```
=== ASH COATED OSMIUM Analysis ===
Mean Price: 9983.21
Standard Deviation: 420.01

=== INTARIAN PEPPER ROOT Analysis ===
Linear Trend (Slope per 1000 timestamp increments): 0.998341
Intercept: 11981.21
Detrended Standard Deviation: 495.72

=== Optimized Parameters ===
ASH_COATED_OSMIUM -> Fair value: 9983
INTARIAN_PEPPER_ROOT -> Alpha per 1k ticks: 0.998341
INTARIAN_PEPPER_ROOT -> Base Fair Value Constant: 11981
```

---

### Backtesting Infrastructure

#### `ROUND_2/Solution/backtest.py`
Comprehensive backtesting harness that simulates both the **old** (baseline) and **new** (optimized) trader logic against historical CSV data. 

**How it works:**
1. Loads order book snapshots from CSV files (`load_orderbooks`)
2. For each timestamp, reconstructs the buy/sell order book from up to 3 price levels
3. Runs the trader logic (market-taking only — passive fills can't be simulated offline)
4. Tracks per-product cash flows and positions
5. Computes mark-to-market PnL at each tick: `PnL = cash + position × mid_price`
6. Reports final PnL, max drawdown, min PnL, and time-to-profit

**Key functions:**
- `load_orderbooks(csv_files)` — Parses CSV into `{timestamp: {product: row_data}}`
- `parse_book(row)` — Converts CSV row into `buy_orders` and `sell_orders` dicts
- `simulate_old(snapshots)` — Runs the baseline algorithm
- `simulate_new(snapshots)` — Runs the optimized algorithm
- `compute_metrics(pnl_history)` — Calculates final PnL, max drawdown, time-to-profit

**Usage:**
```bash
cd ROUND_2/Solution
python backtest.py
```

**Output:**
```
SIMULATING OLD ALGORITHM (baseline)
  Final PnL:        5784.50
  Max Drawdown:     528500.00
  ...

SIMULATING NEW ALGORITHM (optimized)
  Final PnL:        3833.50
  Max Drawdown:     277937.00
  ...

IMPROVEMENT SUMMARY
  Drawdown Change:  +250563.00 (+47.4% reduction)
```

> **Note:** The backtester only simulates aggressive fills. Real exchange PnL is significantly higher because passive market-making orders get filled by other participants. The backtester's primary value is comparing **relative risk metrics** between strategies.

#### `ROUND_2/Solution/backtest_all.py`
Convenience script that runs the backtest across all three historical days and produces an aggregate summary.

**Usage:**
```bash
cd ROUND_2/Solution
python backtest_all.py
```

---

### Historical Data

#### `ROUND_2/prices_round_2_day_*.csv`
Order book snapshots at 100ms intervals. Semicolon-delimited with columns:
```
day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;
bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;
ask_price_3;ask_volume_3;mid_price;profit_and_loss
```

Each file contains ~10,000 timestamps (0 to 99,900 at 100ms steps) for 2 products.

#### `ROUND_2/trades_round_2_day_*.csv`
Historical trade records showing executed trades on the exchange.

#### `ROUND_2/log*/`
Submission snapshots containing the exact code, structured JSON log, and raw exchange log for each submission attempt.

---

## Optimizations Applied

Six optimizations were implemented in `trader.py`. Full details with backtest quantification are in [`OPTIMIZATIONS.md`](OPTIMIZATIONS.md).

| # | Optimization | What it does | Impact |
|---|---|---|---|
| 1 | One-sided book handling | Continues trading/EMA updates when only buy or sell side exists | Prevents EMA staleness |
| 2 | Blended cold-start | Averages simple mid + micro-price on first tick | Reduces initialization noise |
| 3 | Faster EMA (20 vs 30) | Increases EMA responsiveness | 33% faster convergence |
| 4 | Progressive inventory | 4-tier penalty (0/0.5/1/2) replaces binary cliff at ±15 | **50.1% drawdown reduction** |
| 5 | Asymmetric MM skew | bid_skew=3× vs ask_skew=1× (was both 2×) | Better spread capture |
| 6 | End-of-session flattening | Reduces position limits in last 5% of session | **90% terminal exposure reduction** |

### Backtest Results Summary

| Metric | Baseline | Optimized | Change |
|---|---|---|---|
| Avg Max Drawdown | 490,005 | 244,689 | **−50.1%** |
| Terminal Position | ±15–20 | ±1–2 | **~90% flatter** |
| Min PnL (worst) | −264,386 | −198,641 | **+25% less severe** |

---

## How to Run

### Prerequisites
- Python 3.8+
- No external packages required (stdlib only)

### Train the model (extract parameters from historical data)
```bash
cd ROUND_2/Solution
python train_model.py
```

### Run single-day backtest (Day 1)
```bash
cd ROUND_2/Solution
python backtest.py
```

### Run multi-day backtest (all 3 days)
```bash
cd ROUND_2/Solution
python backtest_all.py
```