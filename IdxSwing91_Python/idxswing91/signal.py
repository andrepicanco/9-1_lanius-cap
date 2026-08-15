"""EMA9 close-cross trigger detection - equivalent to Signal/SwingSignal.mqh.

Stateless: given a small window of already-closed bars plus their EMA values, decides
whether the bar that just closed produced a BUY/SELL trigger. Never looks at a still-forming
bar, so results never repaint - same guarantee the MQL5 version documents.

Note: the SMA21 regime filter described in PARAMETROS.md is dead code in the live EA
(commented out in SwingSignal.mqh) - by explicit decision this port also omits it, to stay
faithful to the strategy that is actually running, not the stale doc.
"""

from dataclasses import dataclass

import pandas as pd

from .defines import TriggerDir


@dataclass(frozen=True)
class TriggerResult:
    direction: TriggerDir
    level_price: float          # breakout level: high (BUY) / low (SELL) of the trigger bar
    opposite_extreme: float     # low (BUY) / high (SELL) of the trigger bar, used for SL
    trigger_bar_time: pd.Timestamp


def compute_ema(close: pd.Series, period: int) -> pd.Series:
    """Matches MT5's iMA(..., MODE_EMA, PRICE_CLOSE) recursion (alpha = 2/(period+1))."""
    return close.ewm(span=period, adjust=False).mean()


def compute_atr(bars: pd.DataFrame, period: int) -> pd.Series:
    """Matches MT5's iATR recursion (Wilder's smoothing, alpha = 1/period)."""
    high, low, close = bars["high"], bars["low"], bars["close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def check_for_trigger(bars: pd.DataFrame, i: int) -> TriggerResult | None:
    """Evaluate the bar at position i (the bar that just closed) against bar i-1.

    `bars` must have columns: time, high, low, close, ema, and be indexed 0..N-1 in
    chronological order. Requires i >= 1 (need a previous closed bar to compare against).
    """
    if i < 1 or i >= len(bars):
        return None

    close_prev = bars["close"].iat[i - 1]
    close_last = bars["close"].iat[i]
    ema_prev = bars["ema"].iat[i - 1]
    ema_last = bars["ema"].iat[i]

    crossed_up = close_prev <= ema_prev and close_last > ema_last
    crossed_down = close_prev >= ema_prev and close_last < ema_last

    if not crossed_up and not crossed_down:
        return None

    high_last = bars["high"].iat[i]
    low_last = bars["low"].iat[i]
    trigger_time = bars["time"].iat[i]

    if crossed_up:
        return TriggerResult(
            direction=TriggerDir.BUY,
            level_price=high_last,
            opposite_extreme=low_last,
            trigger_bar_time=trigger_time,
        )

    return TriggerResult(
        direction=TriggerDir.SELL,
        level_price=low_last,
        opposite_extreme=high_last,
        trigger_bar_time=trigger_time,
    )
