"""Multi-symbol live runner - one Python process polling the MT5 terminal for new bars
across every configured symbol, driving the same SymbolStrategy the backtest uses, but
against MT5LiveBroker so orders are real. Equivalent to running one IdxSwing91.mq5
instance per chart, minus the "per chart" part.
"""

import datetime as dt
import time

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from ..account import AccountConfig
from ..backtest.runner import apply_overrides
from ..broker.mt5_live import MT5LiveBroker
from ..config import StrategyConfig
from ..data.mt5_history import ensure_connection, timeframe_from_name
from ..logger import StrategyLogger
from ..signal import compute_atr, compute_ema
from ..state_machine import SymbolStrategy

HISTORY_BARS = 300  # enough for EMA/ATR warmup on typical periods


class SymbolWatcher:
    def __init__(self, cfg: StrategyConfig, strategy: SymbolStrategy, logger: StrategyLogger):
        self.cfg = cfg
        self.strategy = strategy
        self.logger = logger
        self.last_bar_time: pd.Timestamp | None = None

    def poll(self) -> None:
        tf = timeframe_from_name(self.cfg.timeframe)
        rates = mt5.copy_rates_from_pos(self.cfg.symbol, tf, 0, HISTORY_BARS)
        if rates is None or len(rates) < 3:
            self.logger.warn("poll: not enough history returned, skipping this cycle")
            return

        bars = pd.DataFrame(rates)
        bars["time"] = pd.to_datetime(bars["time"], unit="s")
        current_bar_time = bars["time"].iat[-1]

        if self.last_bar_time is not None and current_bar_time == self.last_bar_time:
            return  # same forming bar as last poll, nothing new

        is_first_poll = self.last_bar_time is None
        self.last_bar_time = current_bar_time
        if is_first_poll:
            return  # need a bar-time baseline before reacting, same as BarManager on init

        bars["ema"] = compute_ema(bars["close"], self.cfg.ema_period)
        bars["atr"] = compute_atr(bars, self.cfg.atr_period) if self.cfg.use_trailing else np.nan

        last_closed_idx = len(bars) - 2  # shift 1: the bar that just closed
        atr_value = bars["atr"].iat[last_closed_idx] if self.cfg.use_trailing else None
        atr_value = None if atr_value is not None and np.isnan(atr_value) else atr_value

        self.strategy.on_new_bar(bars, last_closed_idx, now=dt.datetime.now(), atr_value=atr_value)


def run_live(
    symbols: list[str],
    base_cfg: StrategyConfig,
    overrides: dict | None = None,
    poll_interval_seconds: float = 5.0,
    log_file: str | None = None,
    account: AccountConfig | None = None,
) -> None:
    ensure_connection(account)
    overrides = overrides or {}

    watchers: list[SymbolWatcher] = []
    for symbol in symbols:
        cfg = apply_overrides(base_cfg, symbol, overrides)
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Could not select symbol '{symbol}' in MarketWatch: {mt5.last_error()}")

        logger = StrategyLogger(symbol, cfg.log_level, log_file=log_file)
        broker = MT5LiveBroker(cfg.magic_number, cfg.slippage_points, logger)
        strategy = SymbolStrategy(cfg, broker, logger)
        watchers.append(SymbolWatcher(cfg, strategy, logger))
        logger.info(f"live runner: watching {symbol} on {cfg.timeframe}")

    try:
        while True:
            for watcher in watchers:
                try:
                    watcher.poll()
                except Exception as exc:  # keep the loop alive if one symbol misbehaves
                    watcher.logger.error(f"poll: unhandled exception: {exc!r}")
            time.sleep(poll_interval_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        mt5.shutdown()
