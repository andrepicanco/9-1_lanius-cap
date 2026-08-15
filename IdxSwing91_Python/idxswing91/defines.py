"""Enums shared across the strategy - equivalent to Defines.mqh."""

from enum import Enum, IntEnum


class TriggerDir(Enum):
    NONE = "none"
    BUY = "buy"
    SELL = "sell"


class EAState(Enum):
    IDLE = "idle"
    PENDING = "pending"
    IN_POSITION = "in_position"


class LogLevel(IntEnum):
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3
