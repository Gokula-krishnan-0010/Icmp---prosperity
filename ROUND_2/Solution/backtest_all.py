"""Multi-day backtest runner."""
from backtest import load_orderbooks, simulate_old, simulate_new, compute_metrics

days = [
    (['../prices_round_2_day_-1.csv'], 'Day -1'),
    (['../prices_round_2_day_0.csv'], 'Day 0'),
    (['../prices_round_2_day_1.csv'], 'Day 1'),
]

results = []
for day_file, day_name in days:
    snaps = load_orderbooks(day_file)
    old_pnl, old_pos, _ = simulate_old(snaps)
    new_pnl, new_pos, _ = simulate_new(snaps)
    om = compute_metrics(old_pnl)
    nm = compute_metrics(new_pnl)
    dd_red = ((om['max_drawdown'] - nm['max_drawdown']) / om['max_drawdown'] * 100) if om['max_drawdown'] else 0
    results.append((day_name, om, nm, old_pos, new_pos, dd_red))
    print(f"=== {day_name} ===")
    print(f"  OLD: PnL={om['final_pnl']:.0f}, DD={om['max_drawdown']:.0f}, MinPnL={om['min_pnl']:.0f}")
    print(f"  NEW: PnL={nm['final_pnl']:.0f}, DD={nm['max_drawdown']:.0f}, MinPnL={nm['min_pnl']:.0f}")
    print(f"  DD Reduction: {dd_red:+.1f}%")
    print(f"  OLD final pos: {dict(old_pos)}")
    print(f"  NEW final pos: {dict(new_pos)}")
    print()

# Summary
print("=" * 60)
print("AGGREGATE SUMMARY")
print("=" * 60)
old_total = sum(r[1]['final_pnl'] for r in results)
new_total = sum(r[2]['final_pnl'] for r in results)
old_dd_avg = sum(r[1]['max_drawdown'] for r in results) / len(results)
new_dd_avg = sum(r[2]['max_drawdown'] for r in results) / len(results)
print(f"  Total OLD PnL: {old_total:.0f}")
print(f"  Total NEW PnL: {new_total:.0f}")
print(f"  Avg OLD DD: {old_dd_avg:.0f}")
print(f"  Avg NEW DD: {new_dd_avg:.0f}")
print(f"  Avg DD Reduction: {((old_dd_avg - new_dd_avg) / old_dd_avg * 100):+.1f}%")
