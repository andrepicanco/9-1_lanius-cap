"""Per-symbol state machine (IDLE -> PENDING -> IN_POSITION) - equivalent to the
HandleIdleState / HandlePendingState / HandleInPositionState flow in IdxSwing91.mq5.

This is the one place the actual strategy decisions live. Both the live runner and the
backtest engine drive the *same* SymbolStrategy instance type, only swapping which Broker
implementation is injected (real MT5 orders vs. simulated fills) and how "now"/bars are
supplied. That keeps the two modes from silently diverging.
"""

import datetime as dt

import pandas as pd

from .broker.base import Broker
from .config import StrategyConfig
from .defines import EAState, TriggerDir
from .logger import StrategyLogger
from .risk import calculate_lot_size
from .signal import check_for_trigger


def within_trading_hours(now: dt.datetime, start_hour: int, end_hour: int) -> bool:
    hour = now.hour
    if start_hour <= end_hour:
        return start_hour <= hour <= end_hour
    # wraps past midnight (e.g. start=22, end=6)
    return hour >= start_hour or hour <= end_hour


class SymbolStrategy:
    def __init__(self, cfg: StrategyConfig, broker: Broker, logger: StrategyLogger):
        cfg.validate()
        self.cfg = cfg
        self.symbol = cfg.symbol
        self.broker = broker
        self.logger = logger

        self.state = EAState.IDLE
        self.pending_ticket: int | None = None
        self.bars_since_placed = 0

    def reset(self) -> None:
        self.state = EAState.IDLE
        self.pending_ticket = None
        self.bars_since_placed = 0

    # --- mirrors RefreshState() -------------------------------------------------
    def refresh_state(self) -> None:
        if self.broker.has_open_position(self.symbol):
            self.state = EAState.IN_POSITION
            return

        pending = self.broker.find_pending_order(self.symbol)
        if pending is not None:
            if self.state != EAState.PENDING or self.pending_ticket != pending:
                # pending order exists but we didn't place it this run (e.g. restart) -
                # adopt it rather than leaving it untracked and un-expirable.
                self.pending_ticket = pending
                self.bars_since_placed = 1
            self.state = EAState.PENDING
            return

        if self.state == EAState.PENDING and self.pending_ticket is not None:
            self.logger.info("refresh_state: previously tracked pending order is gone (filled or removed)")

        self.state = EAState.IDLE
        self.pending_ticket = None
        self.bars_since_placed = 0

    # --- mirrors HandleIdleState() ----------------------------------------------
    def handle_idle(self, bars: pd.DataFrame, i: int, now: dt.datetime) -> None:
        if self.cfg.use_trading_hours_filter and not within_trading_hours(now, self.cfg.start_hour, self.cfg.end_hour):
            return

        trigger = check_for_trigger(bars, i)
        if trigger is None:
            return

        spec = self.broker.get_symbol_spec(self.symbol)
        buffer = self.cfg.sl_buffer_points * spec.point

        entry_price = trigger.level_price
        if trigger.direction == TriggerDir.BUY:
            sl_price = trigger.opposite_extreme - buffer
        else:
            sl_price = trigger.opposite_extreme + buffer

        # gap-through guard: void the trigger if price already traded past the level
        bid, ask = self.broker.get_prices(self.symbol)
        if trigger.direction == TriggerDir.BUY and ask >= entry_price:
            self.logger.warn("handle_idle: BUY trigger voided, price already gapped through level")
            return
        if trigger.direction == TriggerDir.SELL and bid <= entry_price:
            self.logger.warn("handle_idle: SELL trigger voided, price already gapped through level")
            return

        if self.cfg.max_spread_points > 0 and self.broker.get_spread_points(self.symbol) > self.cfg.max_spread_points:
            self.logger.info("handle_idle: trigger skipped, spread filter")
            return

        risk_distance = abs(entry_price - sl_price)
        tp_price = (
            entry_price + self.cfg.tp_r_multiple * risk_distance
            if trigger.direction == TriggerDir.BUY
            else entry_price - self.cfg.tp_r_multiple * risk_distance
        )

        lots = calculate_lot_size(
            sl_distance=risk_distance,
            spec=spec,
            account_balance=self.broker.get_account_balance(),
            use_fixed_lot=self.cfg.use_fixed_lot,
            fixed_lot=self.cfg.fixed_lot,
            risk_percent=self.cfg.risk_percent,
            logger=self.logger,
        )

        ticket = self.broker.place_stop_order(
            self.symbol, trigger.direction, entry_price, sl_price, tp_price, lots, self.cfg.trade_comment
        )
        if ticket is not None:
            self.state = EAState.PENDING
            self.pending_ticket = ticket
            self.bars_since_placed = 1
            self.logger.info(
                f"handle_idle: placed {trigger.direction.value.upper()} stop @ {entry_price:.5f} "
                f"SL={sl_price:.5f} TP={tp_price:.5f} lots={lots:.2f} ticket={ticket}"
            )
        else:
            self.logger.error("handle_idle: order placement failed")

    # --- mirrors HandlePendingState() --------------------------------------------
    def handle_pending(self) -> None:
        self.bars_since_placed += 1
        if self.bars_since_placed > self.cfg.trigger_valid_bars:
            if self.pending_ticket is not None:
                self.broker.cancel_order(self.symbol, self.pending_ticket)
            self.logger.info("handle_pending: trigger expired, cancelling pending order")
            self.state = EAState.IDLE
            self.pending_ticket = None
            self.bars_since_placed = 0

    # --- mirrors HandleInPositionState() -----------------------------------------
    def handle_in_position(self, atr_value: float | None) -> None:
        if not self.cfg.use_trailing or atr_value is None:
            return
        self.broker.apply_trailing(self.symbol, atr_value, self.cfg.atr_multiplier)

    # --- mirrors HandleNewBar() ----------------------------------------------------
    def on_new_bar(self, bars: pd.DataFrame, i: int, now: dt.datetime, atr_value: float | None = None) -> None:
        self.refresh_state()

        if self.state == EAState.IN_POSITION:
            self.handle_in_position(atr_value)
        elif self.state == EAState.PENDING:
            self.handle_pending()
        elif self.state == EAState.IDLE:
            self.handle_idle(bars, i, now)
