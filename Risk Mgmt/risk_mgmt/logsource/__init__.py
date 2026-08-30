"""LogSource abstraction: anything that can produce a list of closed Trade records for
risk analysis, regardless of what file format it actually reads from disk."""

import datetime as dt
from dataclasses import dataclass
from typing import Protocol


@dataclass
class Trade:
    symbol: str
    direction: str  # "buy" | "sell"
    entry_time: dt.datetime
    entry_price: float
    exit_time: dt.datetime
    exit_price: float
    exit_reason: str  # "tp" | "sl" | "unknown"
    lots: float
    pnl_money: float
    r_multiple: float
    risk_money: float | None = None  # $ risked at entry (SL distance priced in); None when unrecoverable


class LogSource(Protocol):
    def load_trades(self) -> list[Trade]:
        """Returns every closed trade found in the source, in no particular order."""
        ...
