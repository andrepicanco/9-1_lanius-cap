"""Simulated broker for backtesting - fills pending stop orders and closes positions
against historical OHLC bars instead of talking to a live MT5 terminal for execution.

Fill/close rule (confirmed with the user): bar-by-bar, using only OHLC (no ticks). If a
bar's range touches both the SL and the fill level / TP, the worst case is assumed - the
SL is treated as hit first. No slippage is modeled on entries or exits; treat backtest PnL
as an optimistic upper bound, not an exact simulation.

Causality: an order placed when bar k-1 closes (event k-1) is only tested for fill/close
against bar k's range onward - never against the bar that produced the trigger itself.
The engine (backtest/engine.py) is responsible for calling process_bar() and
set_current_bar() in the correct order to preserve this.
"""

from dataclasses import dataclass

import pandas as pd

from ..defines import TriggerDir
from ..symbol_spec import SymbolSpec
from .base import Broker


@dataclass
class _PendingOrder:
    ticket: int
    direction: TriggerDir
    entry: float
    sl: float
    tp: float
    lots: float
    placed_time: pd.Timestamp


@dataclass
class _OpenPosition:
    ticket: int
    direction: TriggerDir
    entry: float
    sl: float
    tp: float
    lots: float
    open_time: pd.Timestamp
    risk_distance: float


@dataclass
class Trade:
    symbol: str
    direction: str
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    exit_reason: str  # "sl" | "tp"
    lots: float
    pnl_money: float
    r_multiple: float


class MT5BacktestBroker(Broker):
    def __init__(self, spec_by_symbol: dict[str, SymbolSpec], starting_balance: float = 10_000.0):
        self._spec = spec_by_symbol
        self.balance = starting_balance
        self.trades: list[Trade] = []

        self._pending: dict[str, _PendingOrder] = {}
        self._position: dict[str, _OpenPosition] = {}
        self._current_bar: dict[str, pd.Series] = {}
        self._next_ticket = 1

    # --- engine-facing API (not part of the Broker interface) ----------------------
    def set_current_bar(self, symbol: str, bar: pd.Series) -> None:
        """The bar whose `open` represents the 'current tick' at decision time."""
        self._current_bar[symbol] = bar

    def process_bar(self, symbol: str, bar: pd.Series) -> None:
        """Resolve fills/closes that would have happened while `bar` was forming."""
        pending = self._pending.get(symbol)
        if pending is not None:
            filled = (
                bar["high"] >= pending.entry if pending.direction == TriggerDir.BUY else bar["low"] <= pending.entry
            )
            if filled:
                risk_distance = abs(pending.entry - pending.sl)
                position = _OpenPosition(
                    ticket=pending.ticket,
                    direction=pending.direction,
                    entry=pending.entry,
                    sl=pending.sl,
                    tp=pending.tp,
                    lots=pending.lots,
                    open_time=bar["time"],
                    risk_distance=risk_distance,
                )
                del self._pending[symbol]
                self._position[symbol] = position
                # same-bar SL/TP collision on the fill bar itself - resolve immediately
                self._resolve_bar_outcome(symbol, bar)
            return

        position = self._position.get(symbol)
        if position is not None:
            self._resolve_bar_outcome(symbol, bar)

    def _resolve_bar_outcome(self, symbol: str, bar: pd.Series) -> None:
        position = self._position.get(symbol)
        if position is None:
            return

        if position.direction == TriggerDir.BUY:
            touched_sl = bar["low"] <= position.sl
            touched_tp = bar["high"] >= position.tp
        else:
            touched_sl = bar["high"] >= position.sl
            touched_tp = bar["low"] <= position.tp

        if not touched_sl and not touched_tp:
            return

        # worst case when both are touched in the same bar: SL first
        reason = "sl" if touched_sl else "tp"
        exit_price = position.sl if touched_sl else position.tp

        self._close_position(symbol, exit_price, bar["time"], reason)

    def _close_position(self, symbol: str, exit_price: float, exit_time: pd.Timestamp, reason: str) -> None:
        position = self._position.pop(symbol)
        spec = self._spec[symbol]

        profit_points = (
            exit_price - position.entry if position.direction == TriggerDir.BUY else position.entry - exit_price
        )
        pnl_money = (profit_points / spec.tick_size) * spec.tick_value * position.lots
        r_multiple = profit_points / position.risk_distance if position.risk_distance > 0 else 0.0

        self.balance += pnl_money
        self.trades.append(
            Trade(
                symbol=symbol,
                direction=position.direction.value,
                entry_time=position.open_time,
                entry_price=position.entry,
                exit_time=exit_time,
                exit_price=exit_price,
                exit_reason=reason,
                lots=position.lots,
                pnl_money=pnl_money,
                r_multiple=r_multiple,
            )
        )

    # --- Broker interface ----------------------------------------------------------
    def has_open_position(self, symbol: str) -> bool:
        return symbol in self._position

    def find_pending_order(self, symbol: str) -> int | None:
        pending = self._pending.get(symbol)
        return pending.ticket if pending else None

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
        ticket = self._next_ticket
        self._next_ticket += 1
        placed_time = self._current_bar[symbol]["time"]
        self._pending[symbol] = _PendingOrder(ticket, direction, entry, sl, tp, lots, placed_time)
        return ticket

    def cancel_order(self, symbol: str, ticket: int) -> bool:
        pending = self._pending.get(symbol)
        if pending is not None and pending.ticket == ticket:
            del self._pending[symbol]
        return True

    def apply_trailing(self, symbol: str, atr_value: float, atr_multiplier: float) -> bool:
        position = self._position.get(symbol)
        if position is None or atr_value <= 0.0 or atr_multiplier <= 0.0:
            return False

        price = self._current_bar[symbol]["open"]
        distance = atr_value * atr_multiplier

        if position.direction == TriggerDir.BUY:
            new_sl = price - distance
            if new_sl <= position.sl:
                return False
        else:
            new_sl = price + distance
            if position.sl > 0.0 and new_sl >= position.sl:
                return False

        position.sl = new_sl
        return True

    def get_prices(self, symbol: str) -> tuple[float, float]:
        price = self._current_bar[symbol]["open"]
        return price, price  # zero-spread approximation for the "current tick"

    def get_spread_points(self, symbol: str) -> int:
        bar = self._current_bar.get(symbol)
        if bar is None or "spread" not in bar.index:
            return 0
        return int(bar["spread"])

    def get_account_balance(self) -> float:
        return self.balance

    def get_symbol_spec(self, symbol: str) -> SymbolSpec:
        return self._spec[symbol]

    # --- reporting helper ------------------------------------------------------------
    def force_close_open_positions(self, symbol: str, last_bar: pd.Series) -> None:
        """Marks any still-open position as closed at the last available bar's close,
        so backtest reports don't silently drop an in-flight trade."""
        if symbol in self._position:
            self._close_position(symbol, last_bar["close"], last_bar["time"], "backtest_end")
