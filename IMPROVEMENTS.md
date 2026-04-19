# Training Optimization Report

## Summary
The provided logs are evaluation/PnL traces rather than classical ML trainer logs, so the useful optimization signals are run PnL trajectory, drawdown, time-to-profit, per-product contribution, and terminal inventory. Based on those signals, the trading algorithm in `ROUND_2/Solution/trader.py` was improved in four areas: adaptive pepper warmup, tiered inventory control, end-of-session de-risking, and one-sided-book fallback handling.

The strongest measured historical A/B in the logs remains `295207` -> `295471`: final profit improved from `1315.16` to `2364.22` (+79.8%), max drawdown fell from `195.94` to `136.39` (-30.4%), and time-to-first-positive PnL improved from `10.2k` ticks to `0.6k` ticks (-94.1%). The newly implemented logic extends those same ideas further and is expected to add another `+5% to +12%` PnL, reduce drawdown by `15% to 30%`, and improve time-to-profit by `5% to 15%` versus the previous `ROUND_2/Solution/trader.py`.

## Key Issues Identified
- Issue 1: Pepper cold-start bias causes long early instability.
  - Log evidence: `294631.graphLog` moves from `"0;0.0"` to `"9000;-434.9375"` and does not turn positive until `"38000;11.0390625"`.
  - Probable cause: `294631.py` hardcodes `self.pepper_ema = 11981.0`, while the first live pepper mid is `"1;0;INTARIAN_PEPPER_ROOT;12993;9;12990;25;;;13007;9;13010;25;;;13000.0;0.0"`. The initial fair value is about 19 ticks low, so the EMA spends a long time correcting.
- Issue 2: Fixed symmetric edges pin the strategy near short limits.
  - Log evidence: `295207` closes with positions `ASH_COATED_OSMIUM=-16`, `INTARIAN_PEPPER_ROOT=-19`, and its curve stalls around `"95200;1315.890625"` before dipping to `"97200;1301.671875"`.
  - Log evidence: after adding asymmetric inventory relief in `295471`, pepper PnL at the same late regime is far higher: `"1;97200;INTARIAN_PEPPER_ROOT;13101;7;13090;11;13087;17;13104;11;;;;;13102.5;368.0"` in `295207` versus `"1;97200;INTARIAN_PEPPER_ROOT;13090;11;13087;17;;;13104;11;13108;17;;;13097.0;1416.59375"` in `295471`.
- Issue 3: End-of-run carry leaks PnL.
  - Log evidence: `295471.graphLog` peaks at `"93200;2434.5625"` but the run closes at `2364.21875`.
  - Log evidence: `295471` still ends with near-limit short inventory: `ASH_COATED_OSMIUM=-20`, `INTARIAN_PEPPER_ROOT=-19`.
- Issue 4: One-sided books currently freeze the model/quoting loop.
  - Log evidence: `295207.activitiesLog` contains `"1;5500;INTARIAN_PEPPER_ROOT;;;;;;;;;;;;;0.0;59.0"`.
  - Log evidence: `295471.activitiesLog` contains `"1;11600;INTARIAN_PEPPER_ROOT;;;;;;;;;;;;;0.0;190.599609375"`.
  - Probable cause: the loop exits on missing sides (`if not best_bid or not best_ask: continue`), so fair value and inventory relief stop updating exactly when liquidity is sparse.

## Recommended Improvements

### 1. Adaptive Pepper Warmup
- Problem:
  - The pepper model was sensitive to startup conditions. In the bad historical variant `294631`, a poor prior caused a `-434.94` early drawdown by tick `9000` and the strategy did not turn positive until tick `38000`.
- Solution:
  - Implemented `self.pepper_updates` and a short warmup schedule with higher early EMA alpha.
  - Added a temporary blend between live `micro_price` and EMA fair value for the first `12` pepper updates.
  - Kept the initialization fully adaptive; no hardcoded prior was reintroduced.
- Modification:
  - Added adaptive EMA warmup in `trader.py` for `INTARIAN_PEPPER_ROOT`.
  - The fair price now transitions smoothly from observed live price to steady-state EMA instead of jumping directly into slow EMA-only mode.
- Why it helps:
  - This reduces early bias, shortens cold-start stabilization time, and avoids the slow recovery pattern visible in the weakest logged run.
- Expected Impact:
  - Speed: +0%
  - Convergence: +5% to +12%
  - Accuracy: +2% to +5%

### 2. Tiered Inventory Management And Quote Sizing
- Problem:
  - The previous logic could still lean into inventory saturation. The logs show repeated late short inventory pressure, including `ASH_COATED_OSMIUM=-16` and `INTARIAN_PEPPER_ROOT=-19` in `295207`, with weakened incremental gains late in the run.
- Solution:
  - Implemented `_target_abs_position`, `_inventory_relief`, and `_quote_size`.
  - Inventory relief is now tiered by position magnitude instead of only reacting near the limit.
  - Passive quote size now shrinks when already loaded on one side, instead of always refilling aggressively to the full position band.
- Modification:
  - Added progressive edge tightening and asymmetric quoting based on both current position and time remaining.
  - Reduced inventory targets into the close.
- Why it helps:
  - This prevents repeated inventory pinning, reduces adverse inventory carry, and preserves more capital for favorable fills.
- Expected Impact:
  - Speed: +0%
  - Convergence: +5% to +10%
  - Accuracy: +3% to +7%

### 3. End-Of-Session Risk Reduction
- Problem:
  - Late-session PnL leakage was visible even in the best logged run. `295471` peaked at `2434.56` at tick `93200` but closed at `2364.22`, while still holding near-limit short inventory (`-20/-19`).
- Solution:
  - Implemented `_close_phase` and used it to penalize fair value in the direction opposite current inventory.
  - After `97000`, the strategy actively takes top-of-book liquidity to reduce excess inventory.
  - After `98500`, quoting for further accumulation is effectively disabled by collapsing the target inventory toward zero.
- Modification:
  - Added explicit time-dependent de-risking to both products.
  - Added late-session hard-flatten behavior for excess exposure.
- Why it helps:
  - This directly attacks the observed giveback pattern near the end of the session and reduces tail risk from carrying inventory too long.
- Expected Impact:
  - Speed: +0%
  - Convergence: +0% to +4%
  - Accuracy: +2% to +6%

### 4. Sparse / One-Sided Book Fallback Handling
- Problem:
  - When one side of the order book disappeared, the previous logic skipped the product entirely, freezing state updates and quote generation.
- Solution:
  - Implemented `_market_view` with fallback bid/ask reconstruction using the last valid top-of-book and spread.
  - Pepper micro-price now remains defined even with one missing side by blending the live side with the synthetic opposite side.
  - Internal state continues updating deterministically instead of freezing.
- Modification:
  - Added stored `last_best_bid`, `last_best_ask`, `last_spread`, and `last_fair`.
  - Removed the full stop caused by one-sided books in the main decision loop.
- Why it helps:
  - This improves continuity during sparse liquidity, avoids stale EMA state, and preserves control over inventory when the market is temporarily incomplete.
- Expected Impact:
  - Speed: +0% to +1%
  - Convergence: +2% to +6%
  - Accuracy: +1% to +4%

## Before vs After (Estimated)
| Metric              | Before | After | Improvement |
|--------------------|--------|-------|------------|
| Training Time      | Not logged | Not logged | +0% |
| Epochs to Converge | 33.0k ticks to +500 PnL (historical proxy, `295207`) | 25.4k ticks to +500 PnL (historical proxy, `295471`) | -23.0% |
| Accuracy           | 1315.16 final PnL (historical proxy, `295207`) | 2364.22 final PnL (historical proxy, `295471`) | +79.8% |

Implemented-code estimate versus previous `ROUND_2/Solution/trader.py`:

| Metric              | Before | After | Improvement |
|--------------------|--------|-------|------------|
| Training Time      | Not logged | Not logged | +0% |
| Epochs to Converge | Current strategy baseline | Patched strategy | -5% to -15% |
| Accuracy           | Current strategy baseline | Patched strategy | +5% to +12% |

## Additional Notes
- Assumptions made:
  - The logs are evaluation traces, not SGD/Adam training logs, so `convergence` is proxied by ticks to positive PnL / ticks to `+500` PnL.
  - `Accuracy` is proxied by final PnL because no validation metric is logged.
  - The `+79.8%` figure is measured from the historical logged A/B (`295207` -> `295471`), while the `+5% to +12%` figure is the expected incremental gain from the newly implemented patch over the last solution file.
  - `Speed` is estimated from algorithmic complexity only; no batch time, epoch time, throughput, or hardware telemetry is present.
- Risks or trade-offs:
  - Stronger inventory relief can increase adverse selection if the book trends through the fair value.
  - End-of-session flattening reduces tail risk but may give up some last-minute spread-capture opportunities.
  - One-sided-book fallback pricing is intentionally conservative; if set too aggressively it can trade on stale implied values.
  - Logging behavior is unchanged: no log statements, schemas, field names, or triggers were modified by the code patch.
