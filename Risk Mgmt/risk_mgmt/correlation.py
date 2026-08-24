"""Cross-asset correlation, computed from underlying daily price returns (not strategy
trade P/L - most symbols in a ~13-instrument basket won't have a trade on any given day,
so a trade-P/L correlation matrix would mostly be measuring co-incidence of trade timing,
not market co-movement).
"""

from dataclasses import dataclass

import pandas as pd


def daily_returns(closes: pd.DataFrame) -> pd.DataFrame:
    return closes.pct_change().dropna(how="all")


def rolling_correlation(returns: pd.DataFrame, window_days: int) -> pd.DataFrame:
    """Correlation matrix over the trailing `window_days` returns ending at the most
    recent available day."""
    recent = returns.tail(window_days)
    return recent.corr()


def baseline_correlation(returns: pd.DataFrame) -> pd.DataFrame:
    """Correlation matrix over the full available return history - the long-run
    comparison point for `rolling_correlation`."""
    return returns.corr()


@dataclass
class CorrelatedPair:
    symbol_a: str
    symbol_b: str
    rolling_corr: float
    baseline_corr: float

    @property
    def delta(self) -> float:
        return self.rolling_corr - self.baseline_corr


def top_correlated_pairs(rolling: pd.DataFrame, baseline: pd.DataFrame, top_n: int) -> list[CorrelatedPair]:
    """The `top_n` symbol pairs by rolling correlation (highest first), each pairing
    listed once, self-pairs excluded."""
    symbols = list(rolling.columns)
    pairs = []
    for i, sym_a in enumerate(symbols):
        for sym_b in symbols[i + 1:]:
            r = rolling.loc[sym_a, sym_b]
            b = baseline.loc[sym_a, sym_b] if sym_a in baseline.index and sym_b in baseline.columns else float("nan")
            if pd.isna(r):
                continue
            pairs.append(CorrelatedPair(sym_a, sym_b, float(r), float(b) if not pd.isna(b) else float("nan")))

    pairs.sort(key=lambda p: p.rolling_corr, reverse=True)
    return pairs[:top_n]


@dataclass
class CorrelationResult:
    rolling: pd.DataFrame
    baseline: pd.DataFrame
    top_pairs: list[CorrelatedPair]


def compute_correlation(closes: pd.DataFrame, window_days: int, top_n: int) -> CorrelationResult:
    returns = daily_returns(closes)
    rolling = rolling_correlation(returns, window_days)
    baseline = baseline_correlation(returns)
    return CorrelationResult(
        rolling=rolling,
        baseline=baseline,
        top_pairs=top_correlated_pairs(rolling, baseline, top_n),
    )
