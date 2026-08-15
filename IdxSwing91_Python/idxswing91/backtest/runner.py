"""Runs the backtest successively across a list of symbols, applying per-symbol config
overrides, and aggregates a summary. This is the piece that replaces "attach one EA
instance per chart" - here it's just one more entry in a list.
"""

import dataclasses
import datetime as dt
from pathlib import Path

import pandas as pd

from ..account import AccountConfig
from ..config import StrategyConfig
from ..data.mt5_history import ensure_connection, fetch_rates, fetch_symbol_spec
from ..logger import StrategyLogger
from .engine import run_backtest
from .metrics import Metrics, compute_metrics, trades_to_frame


def apply_overrides(base_cfg: StrategyConfig, symbol: str, overrides: dict) -> StrategyConfig:
    cfg = dataclasses.replace(base_cfg, symbol=symbol)
    symbol_override = overrides.get(symbol, {})
    for key, value in symbol_override.items():
        if not hasattr(cfg, key):
            raise ValueError(f"Unknown config field '{key}' in override for symbol '{symbol}'")
        setattr(cfg, key, value)
    return cfg


def run_backtest_batch(
    symbols: list[str],
    base_cfg: StrategyConfig,
    date_from: dt.datetime,
    date_to: dt.datetime,
    overrides: dict | None = None,
    starting_balance: float = 10_000.0,
    output_dir: str | Path | None = None,
    account: AccountConfig | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Returns (summary_df, {symbol: trades_df}). If output_dir is given, writes
    summary.csv and one <symbol>_trades.csv per symbol there.
    """
    ensure_connection(account)
    overrides = overrides or {}
    summaries: list[Metrics] = []
    trades_by_symbol: dict[str, pd.DataFrame] = {}

    for symbol in symbols:
        cfg = apply_overrides(base_cfg, symbol, overrides)
        logger = StrategyLogger(symbol, cfg.log_level)

        try:
            bars = fetch_rates(symbol, cfg.timeframe, date_from, date_to)
            spec = fetch_symbol_spec(symbol)
        except RuntimeError as exc:
            logger.error(f"skipping {symbol}: {exc}")
            continue

        result = run_backtest(bars, cfg, spec, starting_balance=starting_balance, logger=logger)
        metrics = compute_metrics(symbol, result.trades, starting_balance, result.ending_balance)
        summaries.append(metrics)
        trades_by_symbol[symbol] = trades_to_frame(result.trades)

        logger.info(
            f"backtest done: {metrics.num_trades} trades, win_rate={metrics.win_rate:.1%}, "
            f"total_R={metrics.total_r:.2f}, pnl={metrics.total_pnl_money:.2f}"
        )

    summary_df = pd.DataFrame([dataclasses.asdict(m) for m in summaries])

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_df.to_csv(output_dir / "summary.csv", index=False)
        for symbol, trades_df in trades_by_symbol.items():
            trades_df.to_csv(output_dir / f"{symbol}_trades.csv", index=False)

    return summary_df, trades_by_symbol
