import datetime as dt

import pandas as pd
import pytest

from idxswing91.broker.base import Broker
from idxswing91.config import StrategyConfig
from idxswing91.defines import EAState, TriggerDir
from idxswing91.logger import StrategyLogger
from idxswing91.state_machine import SymbolStrategy
from idxswing91.symbol_spec import SymbolSpec

SPEC = SymbolSpec(
    symbol="TEST",
    point=0.01,
    digits=2,
    tick_value=1.0,
    tick_size=0.01,
    volume_min=0.01,
    volume_max=100.0,
    volume_step=0.01,
)


class FakeBroker(Broker):
    """Minimal in-memory broker for exercising SymbolStrategy transitions."""

    def __init__(self, price: float = 105.0, spread_points: int = 0, balance: float = 10_000.0):
        self.position = None
        self.pending = None
        self._next_ticket = 1
        self.price = price
        self.spread_points = spread_points
        self.balance = balance
        self.cancelled_tickets = []
        self.trailing_calls = []

    def has_open_position(self, symbol):
        return self.position is not None

    def find_pending_order(self, symbol):
        return self.pending["ticket"] if self.pending else None

    def place_stop_order(self, symbol, direction, entry, sl, tp, lots, comment):
        ticket = self._next_ticket
        self._next_ticket += 1
        self.pending = {"ticket": ticket, "direction": direction, "entry": entry, "sl": sl, "tp": tp, "lots": lots}
        return ticket

    def cancel_order(self, symbol, ticket):
        self.cancelled_tickets.append(ticket)
        self.pending = None
        return True

    def apply_trailing(self, symbol, atr_value, atr_multiplier):
        self.trailing_calls.append((atr_value, atr_multiplier))
        return True

    def get_prices(self, symbol):
        return self.price, self.price

    def get_spread_points(self, symbol):
        return self.spread_points

    def get_account_balance(self):
        return self.balance

    def get_symbol_spec(self, symbol):
        return SPEC


def make_bars(closes, highs, lows, emas):
    return pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=len(closes), freq="15min"),
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "ema": emas,
        }
    )


def cfg(**overrides) -> StrategyConfig:
    base = StrategyConfig(symbol="TEST", trigger_valid_bars=2)
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def logger():
    return StrategyLogger("TEST")


def test_idle_places_pending_order_on_trigger():
    broker = FakeBroker(price=100.0)  # below the entry level so the gap-guard doesn't void it
    strategy = SymbolStrategy(cfg(), broker, logger())
    bars = make_bars(closes=[100, 105], highs=[101, 106], lows=[99, 104], emas=[100.5, 104.5])

    strategy.on_new_bar(bars, 1, now=dt.datetime(2024, 1, 1, 12, 0))

    assert strategy.state == EAState.PENDING
    assert broker.pending["direction"] == TriggerDir.BUY
    assert broker.pending["entry"] == 106


def test_gap_through_voids_trigger():
    broker = FakeBroker(price=110.0)  # already through the BUY entry level of 106
    strategy = SymbolStrategy(cfg(), broker, logger())
    bars = make_bars(closes=[100, 105], highs=[101, 106], lows=[99, 104], emas=[100.5, 104.5])

    strategy.on_new_bar(bars, 1, now=dt.datetime(2024, 1, 1, 12, 0))

    assert strategy.state == EAState.IDLE
    assert broker.pending is None


def test_pending_order_expires_after_valid_bars():
    broker = FakeBroker(price=100.0)
    broker.pending = {"ticket": 7, "direction": TriggerDir.BUY, "entry": 106, "sl": 103, "tp": 112, "lots": 0.1}
    strategy = SymbolStrategy(cfg(trigger_valid_bars=2), broker, logger())
    strategy.state = EAState.PENDING
    strategy.pending_ticket = 7
    strategy.bars_since_placed = 1

    bars = make_bars(closes=[100, 101, 102], highs=[101, 102, 103], lows=[99, 100, 101], emas=[99, 99.5, 100])

    strategy.on_new_bar(bars, 1, now=dt.datetime(2024, 1, 1, 12, 0))
    assert strategy.state == EAState.PENDING  # bars_since_placed=2, not yet expired

    strategy.on_new_bar(bars, 2, now=dt.datetime(2024, 1, 1, 12, 15))
    assert strategy.state == EAState.IDLE
    assert 7 in broker.cancelled_tickets


def test_in_position_applies_trailing_when_enabled():
    broker = FakeBroker()
    broker.position = {"ticket": 1}
    strategy = SymbolStrategy(cfg(use_trailing=True), broker, logger())
    bars = make_bars(closes=[100, 101], highs=[101, 102], lows=[99, 100], emas=[99, 99.5])

    strategy.on_new_bar(bars, 1, now=dt.datetime(2024, 1, 1, 12, 0), atr_value=1.5)

    assert strategy.state == EAState.IN_POSITION
    assert broker.trailing_calls == [(1.5, 2.0)]
