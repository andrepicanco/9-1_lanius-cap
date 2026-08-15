"""Broker interface used by SymbolStrategy - equivalent to what TradeManager.mqh exposes
to IdxSwing91.mq5. Two implementations: mt5_live (real orders) and mt5_backtest (simulated
fills against historical bars).
"""

from abc import ABC, abstractmethod

from ..defines import TriggerDir
from ..symbol_spec import SymbolSpec


class Broker(ABC):
    @abstractmethod
    def has_open_position(self, symbol: str) -> bool:
        ...

    @abstractmethod
    def find_pending_order(self, symbol: str) -> int | None:
        """Returns a ticket id for an own-magic pending order on `symbol`, or None."""

    @abstractmethod
    def place_stop_order(
        self,
        symbol: str,
        direction: TriggerDir,
        entry: float,
        sl: float,
        tp: float,
        lots: float,
        comment: str,
    ) -> int | None:
        """Places a Buy Stop / Sell Stop. Returns ticket id on success, None on failure."""

    @abstractmethod
    def cancel_order(self, symbol: str, ticket: int) -> bool:
        ...

    @abstractmethod
    def apply_trailing(self, symbol: str, atr_value: float, atr_multiplier: float) -> bool:
        """Only tightens the stop, never loosens - same contract as TradeManager::ApplyTrailing."""

    @abstractmethod
    def get_prices(self, symbol: str) -> tuple[float, float]:
        """Returns (bid, ask)."""

    @abstractmethod
    def get_spread_points(self, symbol: str) -> int:
        ...

    @abstractmethod
    def get_account_balance(self) -> float:
        ...

    @abstractmethod
    def get_symbol_spec(self, symbol: str) -> SymbolSpec:
        ...
