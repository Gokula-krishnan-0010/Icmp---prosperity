from datamodel import OrderDepth, Order, TradingState
from typing import List, Dict
import math

class Trader:
    def __init__(self):
        # UPDATED: Keep adaptive state for warm starts, sparse books, and close-out control.
        self.pepper_ema = None
        self.EMA_ALPHA = 2.0 / (30 + 1) # ~30 period EMA equivalent
        self.POSITION_LIMIT = 20
        self.pepper_updates = 0
        self.last_fair = {
            "ASH_COATED_OSMIUM": 10000.0,
            "INTARIAN_PEPPER_ROOT": 13000.0,
        }
        self.last_best_bid = {
            "ASH_COATED_OSMIUM": 9998,
            "INTARIAN_PEPPER_ROOT": 12993,
        }
        self.last_best_ask = {
            "ASH_COATED_OSMIUM": 10016,
            "INTARIAN_PEPPER_ROOT": 13007,
        }
        self.last_spread = {
            "ASH_COATED_OSMIUM": 18.0,
            "INTARIAN_PEPPER_ROOT": 14.0,
        }

    # UPDATED
    def _clamp(self, value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    # UPDATED
    def _close_phase(self, timestamp: int) -> float:
        return self._clamp((timestamp - 90000) / 8500.0, 0.0, 1.0)

    # UPDATED
    def _target_abs_position(self, timestamp: int) -> int:
        if timestamp >= 98500:
            return 0
        phase = self._close_phase(timestamp)
        return max(2, math.floor(self.POSITION_LIMIT * (1.0 - 0.8 * phase)))

    # UPDATED
    def _inventory_relief(self, position: int, target_abs: int, timestamp: int) -> float:
        abs_pos = abs(position)
        relief = 0.0
        if abs_pos >= 18:
            relief = 2.0
        elif abs_pos >= 14:
            relief = 1.0
        elif abs_pos >= 8:
            relief = 0.5

        excess = max(0, abs_pos - target_abs)
        if excess > 0:
            relief = max(relief, 1.0 + min(1.5, 0.35 * excess))

        return relief + 0.4 * self._close_phase(timestamp)

    # UPDATED
    def _quote_size(self, position: int, side: str, target_abs: int) -> int:
        buy_capacity = max(0, target_abs - position)
        sell_capacity = max(0, target_abs + position)

        if side == "buy":
            if buy_capacity <= 0:
                return 0
            if position > 0:
                return max(1, math.ceil(buy_capacity * 0.35))
            return buy_capacity

        if sell_capacity <= 0:
            return 0
        if position < 0:
            return max(1, math.ceil(sell_capacity * 0.35))
        return sell_capacity

    # UPDATED
    def _market_view(self, item: str, depth: OrderDepth):
        actual_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
        actual_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None

        if actual_bid is not None:
            self.last_best_bid[item] = actual_bid
        if actual_ask is not None:
            self.last_best_ask[item] = actual_ask
        if actual_bid is not None and actual_ask is not None:
            self.last_spread[item] = max(1.0, float(actual_ask - actual_bid))

        if actual_bid is None and actual_ask is None:
            return None, None, None, None

        spread = max(1.0, self.last_spread[item])
        half_spread = max(1, math.ceil(spread / 2.0))
        bid = actual_bid
        ask = actual_ask

        if bid is None:
            anchor = max(self.last_best_bid[item], math.floor(self.last_fair[item] - half_spread))
            bid = min(actual_ask - 1, anchor)
        if ask is None:
            anchor = min(self.last_best_ask[item], math.ceil(self.last_fair[item] + half_spread))
            ask = max(actual_bid + 1, anchor)

        if ask <= bid:
            anchor = self.last_fair[item]
            bid = math.floor(anchor - 1)
            ask = math.ceil(anchor + 1)

        return bid, ask, actual_bid, actual_ask
                
    def run(self, state: TradingState):
        orders_by_product = {}
        conversions = 0
        trader_data = "507" # Market Access Fee (Game Theory optimized non-round number)

        for item, depth in state.order_depths.items():
            pending_orders: List[Order] = []
            position = state.position.get(item, 0)

            # UPDATED: Use synthetic fallbacks on one-sided books instead of freezing.
            best_bid, best_ask, actual_bid, actual_ask = self._market_view(item, depth)
            if best_bid is None or best_ask is None:
                continue

            close_phase = self._close_phase(state.timestamp)
            target_abs = self._target_abs_position(state.timestamp)
                
            # STRATEGY 1: ASH_COATED_OSMIUM (Anchor Reversion)
            if item == "ASH_COATED_OSMIUM":
                # UPDATED: add close-out inventory penalty and tiered relief.
                fair_price = 10000 - (close_phase * position * 0.30)
                acceptable_edge = 1

                relief = self._inventory_relief(position, target_abs, state.timestamp)
                buy_edge = max(-1.5, acceptable_edge - relief) if position <= 0 else acceptable_edge
                sell_edge = max(-1.5, acceptable_edge - relief) if position >= 0 else acceptable_edge

                # UPDATED: hard flatten excess inventory late in the session.
                excess = max(0, abs(position) - target_abs)
                if state.timestamp >= 97000 and excess > 0:
                    if position < -target_abs and actual_ask is not None:
                        take_qty = min(abs(depth.sell_orders[actual_ask]), excess)
                        if take_qty > 0:
                            pending_orders.append(Order(item, actual_ask, take_qty))
                            position += take_qty
                    elif position > target_abs and actual_bid is not None:
                        take_qty = min(abs(depth.buy_orders[actual_bid]), excess)
                        if take_qty > 0:
                            pending_orders.append(Order(item, actual_bid, -take_qty))
                            position -= take_qty

                # 1. Market Taking
                for ask, vol in sorted(depth.sell_orders.items()):
                    if ask <= fair_price - buy_edge:
                        trade_vol = min(abs(vol), target_abs - position)
                        if trade_vol > 0:
                            pending_orders.append(Order(item, ask, trade_vol))
                            position += trade_vol

                for bid, vol in sorted(depth.buy_orders.items(), reverse=True):
                    if bid >= fair_price + sell_edge:
                        trade_vol = min(abs(vol), position + target_abs)
                        if trade_vol > 0:
                            pending_orders.append(Order(item, bid, -trade_vol))
                            position -= trade_vol
                            
                # 2. Market Making (Inventory Skewing & Pennying)
                scale_limit = max(1, target_abs if target_abs > 0 else self.POSITION_LIMIT)
                bid_skew = 0 if position == 0 else (position / scale_limit) * 3.0
                ask_skew = 0 if position == 0 else (position / scale_limit) * 3.0
                
                my_bid = min(best_bid + 1, math.floor(fair_price - 2 - bid_skew - close_phase))
                my_ask = max(best_ask - 1, math.ceil(fair_price + 2 - ask_skew + close_phase))
                
                if my_bid >= my_ask:
                    my_bid = my_ask - 1

                bid_size = self._quote_size(position, "buy", target_abs)
                ask_size = self._quote_size(position, "sell", target_abs)

                if bid_size > 0 and state.timestamp < 98500:
                    pending_orders.append(Order(item, my_bid, bid_size))
                if ask_size > 0 and state.timestamp < 98500:
                    pending_orders.append(Order(item, my_ask, -ask_size))

                self.last_fair[item] = fair_price

            # STRATEGY 2: INTARIAN_PEPPER_ROOT (Trend Adjusted)
            elif item == "INTARIAN_PEPPER_ROOT":
                # UPDATED: keep state moving on sparse books with synthetic micro-price.
                if actual_bid is not None and actual_ask is not None:
                    bid_vol = abs(depth.buy_orders[actual_bid])
                    ask_vol = abs(depth.sell_orders[actual_ask])
                    micro_price = (actual_bid * ask_vol + actual_ask * bid_vol) / (bid_vol + ask_vol)
                elif actual_bid is not None:
                    micro_price = (0.7 * actual_bid) + (0.3 * best_ask)
                elif actual_ask is not None:
                    micro_price = (0.7 * actual_ask) + (0.3 * best_bid)
                else:
                    micro_price = self.last_fair[item]
                
                time_trend = state.timestamp / 1000.0
                adjusted_base = micro_price - time_trend

                # UPDATED: blended warmup for faster stabilization without a hardcoded prior.
                warmup_alpha = self.EMA_ALPHA
                if self.pepper_updates < 10:
                    warmup_alpha = max(self.EMA_ALPHA, 0.35 - (0.025 * self.pepper_updates))

                if self.pepper_ema is None:
                    self.pepper_ema = adjusted_base
                else:
                    self.pepper_ema = (warmup_alpha * adjusted_base) + ((1 - warmup_alpha) * self.pepper_ema)
                self.pepper_updates += 1

                fair_price = self.pepper_ema + time_trend
                if self.pepper_updates < 12:
                    live_weight = ((12 - self.pepper_updates) / 12.0) * 0.35
                    fair_price = ((1 - live_weight) * fair_price) + (live_weight * micro_price)
                fair_price -= close_phase * position * 0.45
                acceptable_edge = 1

                relief = self._inventory_relief(position, target_abs, state.timestamp)
                buy_edge = max(-1.5, acceptable_edge - relief) if position <= 0 else acceptable_edge
                sell_edge = max(-1.5, acceptable_edge - relief) if position >= 0 else acceptable_edge

                # UPDATED: hard flatten excess inventory late in the session.
                excess = max(0, abs(position) - target_abs)
                if state.timestamp >= 97000 and excess > 0:
                    if position < -target_abs and actual_ask is not None:
                        take_qty = min(abs(depth.sell_orders[actual_ask]), excess)
                        if take_qty > 0:
                            pending_orders.append(Order(item, actual_ask, take_qty))
                            position += take_qty
                    elif position > target_abs and actual_bid is not None:
                        take_qty = min(abs(depth.buy_orders[actual_bid]), excess)
                        if take_qty > 0:
                            pending_orders.append(Order(item, actual_bid, -take_qty))
                            position -= take_qty

                # 1. Market Taking
                for ask, vol in sorted(depth.sell_orders.items()):
                    if ask <= math.floor(fair_price) - buy_edge:
                        trade_vol = min(abs(vol), target_abs - position)
                        if trade_vol > 0:
                            pending_orders.append(Order(item, ask, trade_vol))
                            position += trade_vol
                
                for bid, vol in sorted(depth.buy_orders.items(), reverse=True):
                    if bid >= math.ceil(fair_price) + sell_edge:
                        trade_vol = min(abs(vol), position + target_abs)
                        if trade_vol > 0:
                            pending_orders.append(Order(item, bid, -trade_vol))
                            position -= trade_vol
                
                # 2. Market Making
                scale_limit = max(1, target_abs if target_abs > 0 else self.POSITION_LIMIT)
                bid_skew = 0 if position == 0 else (position / scale_limit) * 3.0
                ask_skew = 0 if position == 0 else (position / scale_limit) * 3.0
                
                my_bid = min(best_bid + 1, math.floor(fair_price - 2 - bid_skew - close_phase))
                my_ask = max(best_ask - 1, math.ceil(fair_price + 2 - ask_skew + close_phase))

                if my_bid >= my_ask:
                    my_bid = my_ask - 1

                bid_size = self._quote_size(position, "buy", target_abs)
                ask_size = self._quote_size(position, "sell", target_abs)

                if bid_size > 0 and state.timestamp < 98500:
                    pending_orders.append(Order(item, my_bid, bid_size))
                if ask_size > 0 and state.timestamp < 98500:
                    pending_orders.append(Order(item, my_ask, -ask_size))

                self.last_fair[item] = fair_price

            orders_by_product[item] = pending_orders

        return orders_by_product, conversions, trader_data
