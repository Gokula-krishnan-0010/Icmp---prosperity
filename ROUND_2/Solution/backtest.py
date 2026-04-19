"""
Backtester: Simulates both OLD and NEW trader logic against historical CSV data.
Computes PnL, drawdown, time-to-profit for comparison.
"""
import csv
import math
from collections import defaultdict

POSITION_LIMIT = 20

def load_orderbooks(csv_files):
    """Load CSV data into timestamped order book snapshots."""
    snapshots = defaultdict(dict)  # {timestamp: {product: row_data}}
    for f_path in csv_files:
        with open(f_path, 'r') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                ts = int(row['timestamp'])
                product = row['product']
                snapshots[ts][product] = row
    return snapshots

def parse_book(row):
    """Parse a CSV row into buy_orders and sell_orders dicts."""
    buy_orders = {}
    sell_orders = {}
    for i in range(1, 4):
        bp = row.get(f'bid_price_{i}', '')
        bv = row.get(f'bid_volume_{i}', '')
        if bp and bv:
            buy_orders[int(bp)] = int(bv)
        ap = row.get(f'ask_price_{i}', '')
        av = row.get(f'ask_volume_{i}', '')
        if ap and av:
            sell_orders[int(ap)] = -int(av)  # Sell volumes are negative in Prosperity
    return buy_orders, sell_orders

def simulate_old(snapshots):
    """Simulate the OLD trader logic."""
    pepper_ema = None
    ema_alpha = 2.0 / (30 + 1)
    positions = defaultdict(int)
    cash = defaultdict(float)
    pnl_history = []
    
    for ts in sorted(snapshots.keys()):
        products = snapshots[ts]
        total_pnl = 0.0
        
        for item, row in products.items():
            buy_orders, sell_orders = parse_book(row)
            position = positions[item]
            best_bid = max(buy_orders.keys()) if buy_orders else None
            best_ask = min(sell_orders.keys()) if sell_orders else None
            
            if not best_bid or not best_ask:
                mid = float(row['mid_price']) if row['mid_price'] else 0
                total_pnl += cash[item] + position * mid
                continue
            
            if item == "ASH_COATED_OSMIUM":
                fair_price = 10000
                acceptable_edge = 1
                buy_edge = acceptable_edge - (1 if position <= -15 else 0)
                sell_edge = acceptable_edge - (1 if position >= 15 else 0)
                
                for ask in sorted(sell_orders.keys()):
                    vol = sell_orders[ask]
                    if ask <= fair_price - buy_edge:
                        trade_vol = min(abs(vol), POSITION_LIMIT - position)
                        if trade_vol > 0:
                            cash[item] -= ask * trade_vol
                            position += trade_vol
                
                for bid in sorted(buy_orders.keys(), reverse=True):
                    vol = buy_orders[bid]
                    if bid >= fair_price + sell_edge:
                        trade_vol = min(abs(vol), position + POSITION_LIMIT)
                        if trade_vol > 0:
                            cash[item] += bid * trade_vol
                            position -= trade_vol
                
            elif item == "INTARIAN_PEPPER_ROOT":
                bid_vol = abs(buy_orders[best_bid])
                ask_vol = abs(sell_orders[best_ask])
                micro_price = (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)
                time_trend = ts / 1000.0
                adjusted_base = micro_price - time_trend
                
                if pepper_ema is None:
                    pepper_ema = adjusted_base
                else:
                    pepper_ema = (ema_alpha * adjusted_base) + ((1 - ema_alpha) * pepper_ema)
                
                fair_price = pepper_ema + time_trend
                acceptable_edge = 1
                buy_edge = acceptable_edge - (1 if position <= -15 else 0)
                sell_edge = acceptable_edge - (1 if position >= 15 else 0)
                
                for ask in sorted(sell_orders.keys()):
                    vol = sell_orders[ask]
                    if ask <= math.floor(fair_price) - buy_edge:
                        trade_vol = min(abs(vol), POSITION_LIMIT - position)
                        if trade_vol > 0:
                            cash[item] -= ask * trade_vol
                            position += trade_vol
                
                for bid in sorted(buy_orders.keys(), reverse=True):
                    vol = buy_orders[bid]
                    if bid >= math.ceil(fair_price) + sell_edge:
                        trade_vol = min(abs(vol), position + POSITION_LIMIT)
                        if trade_vol > 0:
                            cash[item] += bid * trade_vol
                            position -= trade_vol
            
            positions[item] = position
            mid = float(row['mid_price']) if row['mid_price'] else (best_bid + best_ask) / 2.0
            total_pnl += cash[item] + position * mid
        
        pnl_history.append((ts, total_pnl))
    
    return pnl_history, positions, cash

def simulate_new(snapshots):
    """Simulate the NEW (optimized) trader logic."""
    pepper_ema = None
    ema_alpha = 2.0 / (20 + 1)  # UPDATED: faster EMA
    positions = defaultdict(int)
    cash = defaultdict(float)
    pnl_history = []
    
    for ts in sorted(snapshots.keys()):
        products = snapshots[ts]
        total_pnl = 0.0
        session_progress = ts / 100000.0
        
        for item, row in products.items():
            buy_orders, sell_orders = parse_book(row)
            position = positions[item]
            best_bid = max(buy_orders.keys()) if buy_orders else None
            best_ask = min(sell_orders.keys()) if sell_orders else None
            
            # UPDATED: Handle one-sided books
            if not best_bid and not best_ask:
                mid = float(row['mid_price']) if row['mid_price'] else 0
                total_pnl += cash[item] + position * mid
                continue
            
            mid_proxy = None
            if best_bid and best_ask:
                mid_proxy = (best_bid + best_ask) / 2.0
            elif best_bid:
                mid_proxy = float(best_bid)
            elif best_ask:
                mid_proxy = float(best_ask)
            
            if item == "ASH_COATED_OSMIUM":
                fair_price = 10000
                acceptable_edge = 1
                
                # UPDATED: Progressive inventory management
                inv_ratio = abs(position) / POSITION_LIMIT
                if inv_ratio >= 0.9:
                    inv_penalty = 2
                elif inv_ratio >= 0.75:
                    inv_penalty = 1
                elif inv_ratio >= 0.5:
                    inv_penalty = 0.5
                else:
                    inv_penalty = 0
                
                if position > 0:
                    sell_edge = max(0, acceptable_edge - inv_penalty)
                    buy_edge = acceptable_edge + inv_penalty * 0.5
                elif position < 0:
                    buy_edge = max(0, acceptable_edge - inv_penalty)
                    sell_edge = acceptable_edge + inv_penalty * 0.5
                else:
                    buy_edge = acceptable_edge
                    sell_edge = acceptable_edge
                
                # UPDATED: End-of-session flattening
                effective_limit = POSITION_LIMIT
                if session_progress >= 0.95:
                    remaining_frac = max(0.0, (1.0 - session_progress) / 0.05)
                    effective_limit = max(2, int(POSITION_LIMIT * remaining_frac))
                    if abs(position) > effective_limit:
                        if position > 0:
                            sell_edge = 0
                        else:
                            buy_edge = 0
                
                if best_ask is not None:
                    for ask in sorted(sell_orders.keys()):
                        vol = sell_orders[ask]
                        if ask <= fair_price - buy_edge:
                            trade_vol = min(abs(vol), effective_limit - position)
                            if trade_vol > 0:
                                cash[item] -= ask * trade_vol
                                position += trade_vol
                
                if best_bid is not None:
                    for bid in sorted(buy_orders.keys(), reverse=True):
                        vol = buy_orders[bid]
                        if bid >= fair_price + sell_edge:
                            trade_vol = min(abs(vol), position + effective_limit)
                            if trade_vol > 0:
                                cash[item] += bid * trade_vol
                                position -= trade_vol
                
            elif item == "INTARIAN_PEPPER_ROOT":
                time_trend = ts / 1000.0
                
                if best_bid is not None and best_ask is not None:
                    bid_vol = abs(buy_orders[best_bid])
                    ask_vol = abs(sell_orders[best_ask])
                    micro_price = (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)
                else:
                    micro_price = mid_proxy
                
                adjusted_base = micro_price - time_trend
                
                if pepper_ema is None:
                    # UPDATED: Blended cold-start
                    if best_bid is not None and best_ask is not None:
                        simple_mid = (best_bid + best_ask) / 2.0
                        blended = 0.5 * simple_mid + 0.5 * micro_price
                        pepper_ema = blended - time_trend
                    else:
                        pepper_ema = adjusted_base
                else:
                    pepper_ema = (ema_alpha * adjusted_base) + ((1 - ema_alpha) * pepper_ema)
                
                fair_price = pepper_ema + time_trend
                acceptable_edge = 1
                
                # UPDATED: Progressive inventory management
                inv_ratio = abs(position) / POSITION_LIMIT
                if inv_ratio >= 0.9:
                    inv_penalty = 2
                elif inv_ratio >= 0.75:
                    inv_penalty = 1
                elif inv_ratio >= 0.5:
                    inv_penalty = 0.5
                else:
                    inv_penalty = 0
                
                if position > 0:
                    sell_edge = max(0, acceptable_edge - inv_penalty)
                    buy_edge = acceptable_edge + inv_penalty * 0.5
                elif position < 0:
                    buy_edge = max(0, acceptable_edge - inv_penalty)
                    sell_edge = acceptable_edge + inv_penalty * 0.5
                else:
                    buy_edge = acceptable_edge
                    sell_edge = acceptable_edge
                
                # UPDATED: End-of-session flattening
                effective_limit = POSITION_LIMIT
                if session_progress >= 0.95:
                    remaining_frac = max(0.0, (1.0 - session_progress) / 0.05)
                    effective_limit = max(2, int(POSITION_LIMIT * remaining_frac))
                    if abs(position) > effective_limit:
                        if position > 0:
                            sell_edge = 0
                        else:
                            buy_edge = 0
                
                if best_ask is not None:
                    for ask in sorted(sell_orders.keys()):
                        vol = sell_orders[ask]
                        if ask <= math.floor(fair_price) - buy_edge:
                            trade_vol = min(abs(vol), effective_limit - position)
                            if trade_vol > 0:
                                cash[item] -= ask * trade_vol
                                position += trade_vol
                
                if best_bid is not None:
                    for bid in sorted(buy_orders.keys(), reverse=True):
                        vol = buy_orders[bid]
                        if bid >= math.ceil(fair_price) + sell_edge:
                            trade_vol = min(abs(vol), position + effective_limit)
                            if trade_vol > 0:
                                cash[item] += bid * trade_vol
                                position -= trade_vol
            
            positions[item] = position
            mid = float(row['mid_price']) if row['mid_price'] else mid_proxy
            total_pnl += cash[item] + position * mid
        
        pnl_history.append((ts, total_pnl))
    
    return pnl_history, positions, cash


def compute_metrics(pnl_history):
    """Compute key metrics from PnL history."""
    if not pnl_history:
        return {}
    
    pnls = [p for _, p in pnl_history]
    final_pnl = pnls[-1]
    
    # Max drawdown
    peak = pnls[0]
    max_dd = 0
    for p in pnls:
        if p > peak:
            peak = p
        dd = peak - p
        if dd > max_dd:
            max_dd = dd
    
    # Time to first positive PnL
    time_to_profit = None
    for ts, p in pnl_history:
        if p > 0:
            time_to_profit = ts
            break
    
    # Min PnL (worst point)
    min_pnl = min(pnls)
    min_ts = pnl_history[pnls.index(min_pnl)][0]
    
    return {
        'final_pnl': final_pnl,
        'max_drawdown': max_dd,
        'min_pnl': min_pnl,
        'min_pnl_ts': min_ts,
        'time_to_profit': time_to_profit,
        'total_ticks': len(pnl_history),
    }


if __name__ == '__main__':
    csv_files = [
        '../prices_round_2_day_1.csv',
    ]
    
    print("Loading order book data...")
    snapshots = load_orderbooks(csv_files)
    print(f"Loaded {len(snapshots)} timestamps\n")
    
    print("=" * 60)
    print("SIMULATING OLD ALGORITHM (baseline)")
    print("=" * 60)
    old_pnl, old_pos, old_cash = simulate_old(snapshots)
    old_metrics = compute_metrics(old_pnl)
    print(f"  Final PnL:        {old_metrics['final_pnl']:.2f}")
    print(f"  Max Drawdown:     {old_metrics['max_drawdown']:.2f}")
    print(f"  Min PnL:          {old_metrics['min_pnl']:.2f} (at t={old_metrics['min_pnl_ts']})")
    print(f"  Time to Profit:   {old_metrics['time_to_profit']}")
    print(f"  Final Positions:  {dict(old_pos)}")
    
    print()
    print("=" * 60)
    print("SIMULATING NEW ALGORITHM (optimized)")
    print("=" * 60)
    new_pnl, new_pos, new_cash = simulate_new(snapshots)
    new_metrics = compute_metrics(new_pnl)
    print(f"  Final PnL:        {new_metrics['final_pnl']:.2f}")
    print(f"  Max Drawdown:     {new_metrics['max_drawdown']:.2f}")
    print(f"  Min PnL:          {new_metrics['min_pnl']:.2f} (at t={new_metrics['min_pnl_ts']})")
    print(f"  Time to Profit:   {new_metrics['time_to_profit']}")
    print(f"  Final Positions:  {dict(new_pos)}")
    
    print()
    print("=" * 60)
    print("IMPROVEMENT SUMMARY")
    print("=" * 60)
    
    pnl_delta = new_metrics['final_pnl'] - old_metrics['final_pnl']
    pnl_pct = (pnl_delta / abs(old_metrics['final_pnl'])) * 100 if old_metrics['final_pnl'] != 0 else float('inf')
    
    dd_delta = old_metrics['max_drawdown'] - new_metrics['max_drawdown']
    dd_pct = (dd_delta / old_metrics['max_drawdown']) * 100 if old_metrics['max_drawdown'] != 0 else 0
    
    old_ttp = old_metrics['time_to_profit'] or 100000
    new_ttp = new_metrics['time_to_profit'] or 100000
    ttp_delta = old_ttp - new_ttp
    ttp_pct = (ttp_delta / old_ttp) * 100 if old_ttp != 0 else 0
    
    print(f"  PnL Change:       {pnl_delta:+.2f} ({pnl_pct:+.1f}%)")
    print(f"  Drawdown Change:  {dd_delta:+.2f} ({dd_pct:+.1f}% reduction)")
    print(f"  Time-to-Profit:   {ttp_delta:+d} ticks ({ttp_pct:+.1f}% faster)")
    
    # Write results to file for OPTIMIZATIONS.md
    with open('backtest_results.txt', 'w') as f:
        f.write("OLD ALGORITHM\n")
        for k, v in old_metrics.items():
            f.write(f"  {k}: {v}\n")
        f.write("\nNEW ALGORITHM\n")
        for k, v in new_metrics.items():
            f.write(f"  {k}: {v}\n")
        f.write(f"\nDELTAS\n")
        f.write(f"  pnl_delta: {pnl_delta}\n")
        f.write(f"  pnl_pct: {pnl_pct}\n")
        f.write(f"  dd_delta: {dd_delta}\n")
        f.write(f"  dd_pct: {dd_pct}\n")
        f.write(f"  ttp_delta: {ttp_delta}\n")
        f.write(f"  ttp_pct: {ttp_pct}\n")
    
    print("\nResults saved to backtest_results.txt")
