"""Bar-by-bar backtest loop for a single symbol - drives the same SymbolStrategy used
live, against a MT5BacktestBroker. See broker/mt5_backtest.py for the fill/close rules
and the causality argument for why process_bar(bars[k-1]) runs before on_new_bar(i=k-1).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..broker.mt5_backtest import MT5BacktestBroker, Trade
from ..config import StrategyConfig
from ..logger import StrategyLogger
from ..signal import compute_atr, compute_ema
from ..state_machine import SymbolStrategy
from ..symbol_spec import SymbolSpec


@dataclass
class BacktestResult:
    symbol: str
    trades: list[Trade]
    ending_balance: float
    bars_used: int


def run_backtest(
    bars: pd.DataFrame,
    cfg: StrategyConfig,
    spec: SymbolSpec,
    starting_balance: float = 10_000.0,
    logger: StrategyLogger | None = None,
) -> BacktestResult:
    cfg.validate()
    bars = bars.reset_index(drop=True).copy()
    bars["ema"] = compute_ema(bars["close"], cfg.ema_period)
    bars["atr"] = compute_atr(bars, cfg.atr_period) if cfg.use_trailing else np.nan

    log = logger or StrategyLogger(cfg.symbol, cfg.log_level)
    broker = MT5BacktestBroker({cfg.symbol: spec}, starting_balance=starting_balance)
    strategy = SymbolStrategy(cfg, broker, log)

    n = len(bars)
    for k in range(1, n):
        broker.set_current_bar(cfg.symbol, bars.iloc[k])
        broker.process_bar(cfg.symbol, bars.iloc[k - 1])

        atr_value = bars["atr"].iat[k - 1] if cfg.use_trailing else None
        atr_value = None if atr_value is not None and np.isnan(atr_value) else atr_value

        strategy.on_new_bar(bars, k - 1, now=bars["time"].iat[k], atr_value=atr_value)

    if n > 0:
        broker.force_close_open_positions(cfg.symbol, bars.iloc[-1])

    return BacktestResult(
        symbol=cfg.symbol,
        trades=broker.trades,
        ending_balance=broker.balance,
        bars_used=n,
    )
