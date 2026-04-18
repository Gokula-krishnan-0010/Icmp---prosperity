from datamodel import OrderDepth, Order, TradingState
from typing import List, Dict
import math

class Trader:
    def __init__(self):
        # Use dynamic cold-start instead of hardcoding to prevent cross-day structural breaks
        self.pepper_ema = None
        self.EMA_ALPHA = 2.0 / (30 + 1) # ~30 period EMA equivalent
        self.POSITION_LIMIT = 20

    def run(self, state: TradingState):
        orders_by_product = {}
        conversions = 0
        trader_data = "507" # Market Access Fee (Game Theory optimized non-round number)

        for item, depth in state.order_depths.items():
            pending_orders: List[Order] = []
            position = state.position.get(item, 0)
            
            best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
            best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
            
            if not best_bid or not best_ask:
                continue
                
            # STRATEGY 1: ASH_COATED_OSMIUM (Anchor Reversion)
            if item == "ASH_COATED_OSMIUM":
                fair_price = 10000
                acceptable_edge = 1
                
                # 1. Market Taking 
                # CRITICAL FIX: Sort sell orders ascending (lowest ask first)
                for ask, vol in sorted(depth.sell_orders.items()):
                    if ask <= fair_price - acceptable_edge:
                        trade_vol = min(abs(vol), self.POSITION_LIMIT - position)
                        if trade_vol > 0:
                            pending_orders.append(Order(item, ask, trade_vol))
                            position += trade_vol
                
                # CRITICAL FIX: Sort buy orders descending (highest bid first)
                for bid, vol in sorted(depth.buy_orders.items(), reverse=True):
                    if bid >= fair_price + acceptable_edge:
                        trade_vol = min(abs(vol), position - (-self.POSITION_LIMIT))
                        if trade_vol > 0:
                            pending_orders.append(Order(item, bid, -trade_vol))
                            position -= trade_vol
                            
                # 2. Market Making (Inventory Skewing & Pennying)
                bid_skew = 0 if position == 0 else (position / self.POSITION_LIMIT) * 2
                ask_skew = 0 if position == 0 else (position / self.POSITION_LIMIT) * 2
                
                my_bid = min(best_bid + 1, math.floor(fair_price - 2 - bid_skew))
                my_ask = max(best_ask - 1, math.ceil(fair_price + 2 - ask_skew))
                
                # CRITICAL FIX: Prevent spread inversion or collision
                if my_bid >= my_ask:
                    my_bid = my_ask - 1

                if position < self.POSITION_LIMIT:
                    pending_orders.append(Order(item, my_bid, self.POSITION_LIMIT - position))
                if position > -self.POSITION_LIMIT:
                    pending_orders.append(Order(item, my_ask, -self.POSITION_LIMIT - position))

            # STRATEGY 2: INTARIAN_PEPPER_ROOT (Trend Adjusted)
            elif item == "INTARIAN_PEPPER_ROOT":
                # CRITICAL FIX: Micro-Pricing (Volume Weighted Mid-Price)
                bid_vol = abs(depth.buy_orders[best_bid])
                ask_vol = abs(depth.sell_orders[best_ask])
                micro_price = (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)
                
                time_trend = state.timestamp / 1000.0
                adjusted_base = micro_price - time_trend
                
                # CRITICAL FIX: Exponential Moving Average (EMA)
                if self.pepper_ema is None:
                    self.pepper_ema = adjusted_base
                else:
                    self.pepper_ema = (self.EMA_ALPHA * adjusted_base) + ((1 - self.EMA_ALPHA) * self.pepper_ema)
                
                fair_price = self.pepper_ema + time_trend
                acceptable_edge = 1
                
                # 1. Market Taking
                for ask, vol in sorted(depth.sell_orders.items()):
                    if ask <= math.floor(fair_price) - acceptable_edge:
                        trade_vol = min(abs(vol), self.POSITION_LIMIT - position)
                        if trade_vol > 0:
                            pending_orders.append(Order(item, ask, trade_vol))
                            position += trade_vol
                
                for bid, vol in sorted(depth.buy_orders.items(), reverse=True):
                    if bid >= math.ceil(fair_price) + acceptable_edge:
                        trade_vol = min(abs(vol), position - (-self.POSITION_LIMIT))
                        if trade_vol > 0:
                            pending_orders.append(Order(item, bid, -trade_vol))
                            position -= trade_vol
                
                # 2. Market Making
                bid_skew = 0 if position == 0 else (position / self.POSITION_LIMIT) * 2
                ask_skew = 0 if position == 0 else (position / self.POSITION_LIMIT) * 2
                
                my_bid = min(best_bid + 1, math.floor(fair_price - 2 - bid_skew))
                my_ask = max(best_ask - 1, math.ceil(fair_price + 2 - ask_skew))

                # CRITICAL FIX: Prevent spread inversion or collision
                if my_bid >= my_ask:
                    my_bid = my_ask - 1

                if position < self.POSITION_LIMIT:
                    pending_orders.append(Order(item, my_bid, self.POSITION_LIMIT - position))
                if position > -self.POSITION_LIMIT:
                    pending_orders.append(Order(item, my_ask, -self.POSITION_LIMIT - position))

            orders_by_product[item] = pending_orders

        return orders_by_product, conversions, trader_data