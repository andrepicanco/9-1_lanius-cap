import pandas as pd
import pytest

from risk_mgmt.correlation import compute_correlation, daily_returns, top_correlated_pairs


def _closes(n_days: int = 30) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    a = pd.Series(range(100, 100 + n_days), index=dates, dtype=float)
    b = a * 2  # perfectly correlated with a
    c = pd.Series([100.0 - (i % 2) for i in range(n_days)], index=dates)  # alternating, ~uncorrelated
    return pd.DataFrame({"A": a, "B": b, "C": c})


def test_perfectly_correlated_series_score_close_to_one():
    result = compute_correlation(_closes(), window_days=10, top_n=3)
    assert result.rolling.loc["A", "B"] == pytest.approx(1.0, abs=1e-6)


def test_top_pairs_lists_each_pair_once_excluding_self_pairs():
    result = compute_correlation(_closes(), window_days=10, top_n=10)
    pair_keys = {frozenset((p.symbol_a, p.symbol_b)) for p in result.top_pairs}

    assert len(pair_keys) == len(result.top_pairs)  # no duplicates
    assert all(p.symbol_a != p.symbol_b for p in result.top_pairs)
    assert frozenset(("A", "B")) in pair_keys


def test_top_n_is_respected():
    result = compute_correlation(_closes(), window_days=10, top_n=1)
    assert len(result.top_pairs) == 1
    assert result.top_pairs[0].rolling_corr == pytest.approx(1.0, abs=1e-6)  # A/B is the strongest pair


def test_daily_returns_drops_the_first_row():
    closes = _closes(n_days=5)
    returns = daily_returns(closes)
    assert len(returns) == len(closes) - 1
