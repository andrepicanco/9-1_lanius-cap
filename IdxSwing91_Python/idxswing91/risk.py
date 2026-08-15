"""Instrument-agnostic lot size calculation - equivalent to Core/RiskManager.mqh."""

import math

from .logger import StrategyLogger
from .symbol_spec import SymbolSpec


def normalize_volume(volume: float, spec: SymbolSpec) -> float:
    if spec.volume_step > 0.0:
        volume = math.floor(volume / spec.volume_step) * spec.volume_step
    volume = max(volume, spec.volume_min)
    volume = min(volume, spec.volume_max)
    return volume


def calculate_lot_size(
    sl_distance: float,
    spec: SymbolSpec,
    account_balance: float,
    use_fixed_lot: bool,
    fixed_lot: float,
    risk_percent: float,
    logger: StrategyLogger | None = None,
) -> float:
    """sl_distance is the SL distance in price units (points * point), not pips."""
    if use_fixed_lot:
        return normalize_volume(fixed_lot, spec)

    if sl_distance <= 0.0:
        if logger:
            logger.error("calculate_lot_size: invalid SL distance <= 0, falling back to volume min")
        return spec.volume_min

    if spec.tick_value <= 0.0 or spec.tick_size <= 0.0:
        if logger:
            logger.error("calculate_lot_size: invalid tick value/size, falling back to volume min")
        return spec.volume_min

    risk_money = account_balance * (risk_percent / 100.0)
    value_per_unit = (sl_distance / spec.tick_size) * spec.tick_value  # loss per 1.0 lot if SL hit
    if value_per_unit <= 0.0:
        return spec.volume_min

    raw_lots = risk_money / value_per_unit
    return normalize_volume(raw_lots, spec)
