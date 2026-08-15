"""Trade-log metrics for a single backtest run."""

from dataclasses import dataclass

import pandas as pd

from ..broker.mt5_backtest import Trade


@dataclass
class Metrics:
    symbol: str
    num_trades: int
    win_rate: float
    avg_r: float
    total_r: float
    total_pnl_money: float
    max_drawdown_money: float
    starting_balance: float
    ending_balance: float


def trades_to_frame(trades: list[Trade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(
            columns=[
                "symbol", "direction", "entry_time", "entry_price", "exit_time",
                "exit_price", "exit_reason", "lots", "pnl_money", "r_multiple",
            ]
        )
    return pd.DataFrame([t.__dict__ for t in trades])


def compute_metrics(symbol: str, trades: list[Trade], starting_balance: float, ending_balance: float) -> Metrics:
    if not trades:
        return Metrics(symbol, 0, 0.0, 0.0, 0.0, 0.0, 0.0, starting_balance, ending_balance)

    df = trades_to_frame(trades)
    wins = df["pnl_money"] > 0

    equity = starting_balance + df["pnl_money"].cumsum()
    running_peak = equity.cummax()
    drawdown = running_peak - equity
    max_dd = drawdown.max()

    return Metrics(
        symbol=symbol,
        num_trades=len(df),
        win_rate=wins.mean(),
        avg_r=df["r_multiple"].mean(),
        total_r=df["r_multiple"].sum(),
        total_pnl_money=df["pnl_money"].sum(),
        max_drawdown_money=max_dd,
        starting_balance=starting_balance,
        ending_balance=ending_balance,
    )
