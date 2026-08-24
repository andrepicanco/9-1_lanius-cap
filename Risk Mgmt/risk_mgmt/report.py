"""Builds the VaR chart, the correlation heatmap, and the Telegram message text from
already-computed VarResult/CorrelationResult objects."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless - this runs in a cron job / CI, never with a display
import matplotlib.pyplot as plt

from .correlation import CorrelationResult
from .var import VarResult


def plot_var_chart(result: VarResult, window_days: int, baseline_days: int, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 5))
    result.var_short.plot(ax=ax, label=f"VaR ({window_days}d)", linewidth=2)
    result.var_baseline.plot(ax=ax, label=f"VaR baseline ({baseline_days}d)", linewidth=2, linestyle="--")
    ax.set_ylabel("VaR ($)")
    ax.set_title("Parametric VaR")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


def plot_correlation_heatmap(result: CorrelationResult, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(result.rolling.values, vmin=-1, vmax=1, cmap="RdBu_r")
    symbols = list(result.rolling.columns)
    ax.set_xticks(range(len(symbols)))
    ax.set_xticklabels(symbols, rotation=45, ha="right")
    ax.set_yticks(range(len(symbols)))
    ax.set_yticklabels(symbols)
    fig.colorbar(im, ax=ax, label="rolling correlation")
    ax.set_title("Rolling price-return correlation")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


def build_message_text(
    var_result: VarResult,
    corr_result: CorrelationResult | None,
    confidence: float,
    window_days: int,
    baseline_days: int,
) -> str:
    lines = ["*IdxSwing91 Risk Report*", ""]

    short = var_result.latest_short
    baseline = var_result.latest_baseline
    lines.append(f"VaR ({confidence:.0%}, {window_days}d): " + (f"${short:,.2f}" if short is not None else "n/a - not enough history"))
    lines.append(f"VaR baseline ({confidence:.0%}, {baseline_days}d): " + (f"${baseline:,.2f}" if baseline is not None else "n/a - not enough history"))

    if corr_result is not None and corr_result.top_pairs:
        lines.append("")
        lines.append("Top correlated pairs (rolling window):")
        for pair in corr_result.top_pairs:
            delta_str = f"{pair.delta:+.2f}" if pair.delta == pair.delta else "n/a"  # NaN check
            lines.append(f"  {pair.symbol_a}/{pair.symbol_b}: {pair.rolling_corr:+.2f} (Δ vs baseline: {delta_str})")

    return "\n".join(lines)
