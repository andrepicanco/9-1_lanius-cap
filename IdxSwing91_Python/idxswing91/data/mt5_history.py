"""Historical OHLC + symbol spec retrieval via the MT5 terminal's own API - the
backtest data source, since the MQL5 Strategy Tester isn't reachable from Python.
"""

import datetime as dt

import MetaTrader5 as mt5
import pandas as pd

from ..account import AccountConfig
from ..symbol_spec import SymbolSpec

_TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def timeframe_from_name(name: str) -> int:
    try:
        return _TIMEFRAME_MAP[name.upper()]
    except KeyError:
        raise ValueError(f"Unsupported timeframe '{name}'. Use one of: {', '.join(_TIMEFRAME_MAP)}") from None


def ensure_connection(account: AccountConfig | None = None) -> None:
    """Connects to the MT5 terminal. If `account` is given, logs in with those
    credentials (launching the terminal if needed); otherwise attaches to whatever
    terminal is already open and logged in. A no-op if already connected, so it's safe
    to call repeatedly with no args from fetch_rates/fetch_symbol_spec."""
    if mt5.terminal_info():
        return

    kwargs = account.to_mt5_kwargs() if account else {}
    if not mt5.initialize(**kwargs):
        raise RuntimeError(f"mt5.initialize() failed: {mt5.last_error()}")


def fetch_rates(symbol: str, timeframe: str, date_from: dt.datetime, date_to: dt.datetime) -> pd.DataFrame:
    ensure_connection()

    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Could not select symbol '{symbol}' in MarketWatch: {mt5.last_error()}")

    tf = timeframe_from_name(timeframe)
    rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No historical data returned for {symbol} {timeframe} ({date_from} - {date_to})")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df[["time", "open", "high", "low", "close", "tick_volume", "spread"]].reset_index(drop=True)


def fetch_symbol_spec(symbol: str) -> SymbolSpec:
    ensure_connection()

    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Could not select symbol '{symbol}' in MarketWatch: {mt5.last_error()}")

    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"symbol_info('{symbol}') returned None: {mt5.last_error()}")

    return SymbolSpec(
        symbol=symbol,
        point=info.point,
        digits=info.digits,
        tick_value=info.trade_tick_value,
        tick_size=info.trade_tick_size,
        volume_min=info.volume_min,
        volume_max=info.volume_max,
        volume_step=info.volume_step,
        stops_level_points=info.trade_stops_level,
        freeze_level_points=info.trade_freeze_level,
    )
