"""Real order execution via the `MetaTrader5` package - equivalent to TradeManager.mqh.

Requires an initialized MT5 terminal connection (see live/runner.py / mt5.initialize()).
"""

import MetaTrader5 as mt5

from ..defines import TriggerDir
from ..logger import StrategyLogger
from ..symbol_spec import SymbolSpec
from .base import Broker


class MT5LiveBroker(Broker):
    def __init__(self, magic_number: int, slippage_points: int, logger: StrategyLogger):
        self.magic_number = magic_number
        self.slippage_points = slippage_points
        self.logger = logger

    # --- helpers -----------------------------------------------------------------
    def _round_to_tick(self, symbol: str, price: float) -> float:
        info = mt5.symbol_info(symbol)
        tick_size = info.trade_tick_size if info else 0.0
        if tick_size and tick_size > 0.0:
            return round(price / tick_size) * tick_size
        digits = info.digits if info else 5
        return round(price, digits)

    def _stops_level_points(self, symbol: str) -> int:
        info = mt5.symbol_info(symbol)
        if info is None:
            return 0
        return max(info.trade_stops_level, info.trade_freeze_level)

    def _filling_type(self, symbol: str) -> int:
        """Approximates CTrade::SetTypeFillingBySymbol: prefer FOK, then IOC, else RETURN
        (pending orders commonly only accept RETURN anyway)."""
        info = mt5.symbol_info(symbol)
        mode = info.filling_mode if info else 0
        if mode & mt5.SYMBOL_FILLING_FOK:
            return mt5.ORDER_FILLING_FOK
        if mode & mt5.SYMBOL_FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    # --- Broker interface ----------------------------------------------------------
    def has_open_position(self, symbol: str) -> bool:
        positions = mt5.positions_get(symbol=symbol) or ()
        return any(p.magic == self.magic_number for p in positions)

    def find_pending_order(self, symbol: str) -> int | None:
        orders = mt5.orders_get(symbol=symbol) or ()
        for order in orders:
            if order.magic == self.magic_number:
                return order.ticket
        return None

    def place_stop_order(
        self,
        symbol: str,
        direction: TriggerDir,
        entry: float,
        sl: float,
        tp: float,
        lots: float,
        comment: str,
    ) -> int | None:
        point = mt5.symbol_info(symbol).point
        min_stop_pts = self._stops_level_points(symbol)

        entry = self._round_to_tick(symbol, entry)
        sl = self._round_to_tick(symbol, sl)
        tp = self._round_to_tick(symbol, tp)

        if min_stop_pts > 0:
            min_dist = (min_stop_pts + 1) * point
            if abs(entry - sl) < min_dist:
                self.logger.warn(
                    f"place_stop_order: SL distance {abs(entry - sl):.5f} below broker min {min_dist:.5f}, skipping"
                )
                return None
            if tp > 0.0 and abs(tp - entry) < min_dist:
                self.logger.warn("place_stop_order: TP distance below broker min, skipping")
                return None

        order_type = mt5.ORDER_TYPE_BUY_STOP if direction == TriggerDir.BUY else mt5.ORDER_TYPE_SELL_STOP

        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": lots,
            "type": order_type,
            "price": entry,
            "sl": sl,
            "tp": tp,
            "deviation": self.slippage_points,
            "magic": self.magic_number,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_type(symbol),
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            retcode = result.retcode if result else None
            comment_ = result.comment if result else "order_send returned None"
            self.logger.error(f"place_stop_order failed: retcode={retcode} desc={comment_}")
            return None

        return result.order

    def cancel_order(self, symbol: str, ticket: int) -> bool:
        request = {"action": mt5.TRADE_ACTION_REMOVE, "order": ticket}
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    def apply_trailing(self, symbol: str, atr_value: float, atr_multiplier: float) -> bool:
        positions = mt5.positions_get(symbol=symbol) or ()
        position = next((p for p in positions if p.magic == self.magic_number), None)
        if position is None or atr_value <= 0.0 or atr_multiplier <= 0.0:
            return False

        info = mt5.symbol_info(symbol)
        point = info.point
        min_dist = (self._stops_level_points(symbol) + 1) * point
        distance = atr_value * atr_multiplier

        is_buy = position.type == mt5.POSITION_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).bid if is_buy else mt5.symbol_info_tick(symbol).ask

        if is_buy:
            new_sl = self._round_to_tick(symbol, price - distance)
            if new_sl <= position.sl:
                return False  # only move up
            if (price - new_sl) < min_dist:
                return False
        else:
            new_sl = self._round_to_tick(symbol, price + distance)
            if position.sl > 0.0 and new_sl >= position.sl:
                return False  # only move down
            if (new_sl - price) < min_dist:
                return False

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": position.ticket,
            "sl": new_sl,
            "tp": position.tp,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            retcode = result.retcode if result else None
            self.logger.warn(f"apply_trailing: order_send failed retcode={retcode}")
            return False
        return True

    def get_prices(self, symbol: str) -> tuple[float, float]:
        tick = mt5.symbol_info_tick(symbol)
        return tick.bid, tick.ask

    def get_spread_points(self, symbol: str) -> int:
        tick = mt5.symbol_info_tick(symbol)
        point = mt5.symbol_info(symbol).point
        if point <= 0.0:
            return 0
        return round((tick.ask - tick.bid) / point)

    def get_account_balance(self) -> float:
        return mt5.account_info().balance

    def get_symbol_spec(self, symbol: str) -> SymbolSpec:
        info = mt5.symbol_info(symbol)
        return SymbolSpec(
            symbol=symbol,
            point=info.point,
            digits=info.digits,
            tick_value=info.trade_tick_value,
            tick_size=info.trade_tick_size,
            volume_min=info.volume_min,
            volume_max=info.volume_max,
            volume_step=info.volume_step,
            stops_level_points=info.trade_stops_level,
            freeze_level_points=info.trade_freeze_level,
        )
