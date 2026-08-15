import pandas as pd

from idxswing91.defines import TriggerDir
from idxswing91.signal import check_for_trigger


def make_bars(closes, highs, lows, emas):
    return pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=len(closes), freq="15min"),
            "close": closes,
            "high": highs,
            "low": lows,
            "ema": emas,
        }
    )


def test_cross_up_triggers_buy():
    # bar i-1: close <= ema ; bar i: close > ema
    bars = make_bars(closes=[100, 105], highs=[101, 106], lows=[99, 104], emas=[100.5, 104.5])
    result = check_for_trigger(bars, 1)
    assert result is not None
    assert result.direction == TriggerDir.BUY
    assert result.level_price == 106  # high of trigger bar
    assert result.opposite_extreme == 104  # low of trigger bar


def test_cross_down_triggers_sell():
    bars = make_bars(closes=[100, 95], highs=[101, 96], lows=[99, 94], emas=[99.5, 95.5])
    result = check_for_trigger(bars, 1)
    assert result is not None
    assert result.direction == TriggerDir.SELL
    assert result.level_price == 94  # low of trigger bar
    assert result.opposite_extreme == 96  # high of trigger bar


def test_no_cross_no_trigger():
    bars = make_bars(closes=[100, 101], highs=[102, 103], lows=[99, 100], emas=[99, 99.5])
    assert check_for_trigger(bars, 1) is None


def test_requires_previous_bar():
    bars = make_bars(closes=[100], highs=[101], lows=[99], emas=[100])
    assert check_for_trigger(bars, 0) is None
