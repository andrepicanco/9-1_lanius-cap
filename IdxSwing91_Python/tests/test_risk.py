import pytest

from idxswing91.risk import calculate_lot_size, normalize_volume
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


def test_fixed_lot_ignores_risk_calc():
    lots = calculate_lot_size(
        sl_distance=10.0, spec=SPEC, account_balance=10_000, use_fixed_lot=True, fixed_lot=0.5, risk_percent=1.0
    )
    assert lots == 0.5


def test_risk_percent_sizing():
    # balance=10000, risk 1% = 100 money. sl_distance=1.0 price units, tick_size=0.01,
    # tick_value=1.0 -> value_per_unit = (1.0/0.01)*1.0 = 100 -> raw_lots = 100/100 = 1.0
    lots = calculate_lot_size(
        sl_distance=1.0, spec=SPEC, account_balance=10_000, use_fixed_lot=False, fixed_lot=0.1, risk_percent=1.0
    )
    assert lots == 1.0


def test_invalid_sl_distance_falls_back_to_min():
    lots = calculate_lot_size(
        sl_distance=0.0, spec=SPEC, account_balance=10_000, use_fixed_lot=False, fixed_lot=0.1, risk_percent=1.0
    )
    assert lots == SPEC.volume_min


def test_normalize_volume_clamps_and_steps():
    assert normalize_volume(0.127, SPEC) == pytest.approx(0.12)
    assert normalize_volume(0.001, SPEC) == SPEC.volume_min
    assert normalize_volume(1000.0, SPEC) == SPEC.volume_max
