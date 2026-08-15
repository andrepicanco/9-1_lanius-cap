"""Leveled logger - equivalent to Logger.mqh, backed by the stdlib logging module."""

import logging
import sys

from .defines import LogLevel

_LEVEL_MAP = {
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARN: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
}


class StrategyLogger:
    """Prefixes every message with [IdxSwing91][<symbol>][<LEVEL>], mirroring the MQL5 CLogger format."""

    def __init__(self, symbol: str, min_level: LogLevel = LogLevel.INFO, log_file: str | None = None):
        self.symbol = symbol
        self._logger = logging.getLogger(f"idxswing91.{symbol}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        if not self._logger.handlers:
            fmt = logging.Formatter(f"[IdxSwing91][{symbol}][%(levelname)s] %(message)s")

            console = logging.StreamHandler(sys.stdout)
            console.setFormatter(fmt)
            self._logger.addHandler(console)

            if log_file:
                file_handler = logging.FileHandler(log_file, encoding="utf-8")
                file_handler.setFormatter(fmt)
                self._logger.addHandler(file_handler)

        self.set_level(min_level)

    def set_level(self, min_level: LogLevel) -> None:
        for handler in self._logger.handlers:
            handler.setLevel(_LEVEL_MAP[min_level])

    def log(self, level: LogLevel, msg: str) -> None:
        self._logger.log(_LEVEL_MAP[level], msg)

    def debug(self, msg: str) -> None:
        self.log(LogLevel.DEBUG, msg)

    def info(self, msg: str) -> None:
        self.log(LogLevel.INFO, msg)

    def warn(self, msg: str) -> None:
        self.log(LogLevel.WARN, msg)

    def error(self, msg: str) -> None:
        self.log(LogLevel.ERROR, msg)
