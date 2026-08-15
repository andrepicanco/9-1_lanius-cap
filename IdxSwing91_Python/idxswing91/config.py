"""Strategy parameters - equivalent to the Inp* inputs of IdxSwing91.mq5."""

from dataclasses import dataclass

from .defines import LogLevel


@dataclass
class StrategyConfig:
    symbol: str
    timeframe: str = "M15"          # MT5 timeframe name, e.g. "M15", "H1", "H4", "D1"

    # Strategy
    ema_period: int = 9
    trigger_valid_bars: int = 3

    # Stop Loss / Take Profit
    sl_buffer_points: int = 30
    tp_r_multiple: float = 2.0

    # Trailing (ATR)
    use_trailing: bool = False
    atr_period: int = 14
    atr_multiplier: float = 2.0

    # Position sizing
    use_fixed_lot: bool = False
    fixed_lot: float = 0.10
    risk_percent: float = 1.0

    # Trade management
    magic_number: int = 910091
    trade_comment: str = "IdxSwing91"
    slippage_points: int = 10

    # Optional filters (off by default)
    max_spread_points: int = 0        # 0 = disabled
    use_trading_hours_filter: bool = False
    start_hour: int = 0               # server/broker time
    end_hour: int = 23

    # Diagnostics
    log_level: LogLevel = LogLevel.INFO

    def validate(self) -> None:
        if self.ema_period <= 0:
            raise ValueError("ema_period must be > 0")
        if self.trigger_valid_bars <= 0:
            raise ValueError("trigger_valid_bars must be > 0")
        if self.tp_r_multiple <= 0.0:
            raise ValueError("tp_r_multiple must be > 0")
        if not self.use_fixed_lot and not (0.0 < self.risk_percent <= 20.0):
            raise ValueError("risk_percent must be in (0, 20]")
        if self.use_fixed_lot and self.fixed_lot <= 0.0:
            raise ValueError("fixed_lot must be > 0")
        if self.use_trailing and (self.atr_period <= 0 or self.atr_multiplier <= 0.0):
            raise ValueError("atr_period/atr_multiplier must be > 0 when trailing is enabled")
