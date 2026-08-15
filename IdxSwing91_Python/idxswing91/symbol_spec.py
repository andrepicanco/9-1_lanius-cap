"""Instrument specification needed for sizing/pricing - the fields pulled from MT5's
SymbolInfo that RiskManager.mqh and TradeManager.mqh rely on. Kept separate from the
MT5 data layer so backtest/live/tests can all construct one without a live connection.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolSpec:
    symbol: str
    point: float
    digits: int
    tick_value: float
    tick_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    stops_level_points: int = 0
    freeze_level_points: int = 0
