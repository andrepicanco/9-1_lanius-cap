"""CLI: assess IdxSwing91's risk (parametric VaR + basket correlation) and report it,
either from local backtest log files or from a live MT5 account.

Examples:
    python scripts/run_risk_report.py --mode local --log-dir path/to/logs --dry-run
    python scripts/run_risk_report.py --mode local --log-dir logs --source idxswing91_csv
    python scripts/run_risk_report.py --mode live
"""

import argparse
import datetime as dt
import sys
from pathlib import Path

from .account import load_account_config
from .config_io import load_default_config, load_symbols_file
from .correlation import compute_correlation, quarterly_pc1_series
from .logsource.idxswing91_csv import IdxSwing91CsvSource
from .logsource.mql5_journal import MQL5JournalSource
from .monthly import asset_month_stats, month_summaries, overall_summary
from .pricesource.csv_price_history import CsvPriceSource
from .pricesource.mt5_price_history import Mt5PriceSource
from .report import build_message_text, plot_correlation_heatmap, plot_pc1_chart, plot_var_chart
from .telegram import send_message, send_photo
from .var import compute_var
from .xlsx_report import write_monthly_workbook

ROOT = Path(__file__).resolve().parent.parent


def _load_trades(args, specs) -> list:
    if args.mode == "live":
        from .live_state import fetch_closed_trades

        account = load_account_config(args.account_config)
        date_to = dt.datetime.now()
        date_from = date_to - dt.timedelta(days=args.baseline_lookback_days)
        return fetch_closed_trades(date_from, date_to, account)

    if args.log_dir is None:
        raise SystemExit("--log-dir is required for --mode local")

    if args.source == "mql5_journal":
        # account is used only as a fallback for symbols missing from config/symbols.yaml -
        # if no MT5 terminal is reachable, resolution just falls back to raising per-symbol.
        account = load_account_config(args.account_config)
        return MQL5JournalSource.from_directory(args.log_dir, specs, account=account).load_trades()
    return IdxSwing91CsvSource.from_directory(args.log_dir).load_trades()


def _closes_date_range(args, trades) -> tuple[dt.datetime, dt.datetime]:
    """Price history needs to cover at least the same span as the loaded trades - a
    fixed --baseline-lookback-days trailing window from *today* would silently truncate
    it for --mode local, where the log's own date range can be anything (e.g. an 8-month
    backtest log analyzed months later), unrelated to when the report happens to run.
    """
    if trades:
        earliest = min(t.entry_time for t in trades)
        latest = max(t.exit_time for t in trades)
        return earliest - dt.timedelta(days=1), latest + dt.timedelta(days=1)

    date_to = dt.datetime.now()
    date_from = date_to - dt.timedelta(days=args.baseline_lookback_days)
    return date_from, date_to


def _load_closes(args, symbols, trades):
    if args.price_source == "csv":
        if args.price_dir is None:
            raise SystemExit("--price-dir is required for --price-source csv")
        return CsvPriceSource(args.price_dir).load_daily_closes(symbols)

    account = load_account_config(args.account_config)
    date_from, date_to = _closes_date_range(args, trades)
    return Mt5PriceSource(date_from, date_to, account).load_daily_closes(symbols)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["local", "live"], required=True)
    parser.add_argument("--source", choices=["mql5_journal", "idxswing91_csv"], default="mql5_journal",
                         help="Backtest log format to parse (--mode local only)")
    parser.add_argument("--log-dir", default=None, help="Directory with backtest log files (--mode local only)")
    parser.add_argument("--price-source", choices=["mt5", "csv"], default="mt5",
                         help="Where correlation's daily close prices come from")
    parser.add_argument("--price-dir", default=None, help="Directory of <symbol>.csv price history (--price-source csv only)")
    parser.add_argument("--baseline-lookback-days", type=int, default=180,
                         help="How far back to pull live trade/price history (--mode live / --price-source mt5)")
    parser.add_argument("--config-dir", default=str(ROOT / "config"), help="Directory with default.yaml/symbols.yaml")
    parser.add_argument("--output-dir", default=str(ROOT / "outputs"), help="Where charts get written")
    parser.add_argument("--account-config", default=str(ROOT / "config" / "account.yaml"),
                         help="Optional MT5 login (see config/account.example.yaml). MT5_LOGIN/MT5_PASSWORD/"
                         "MT5_SERVER env vars take priority if set.")
    parser.add_argument("--dry-run", action="store_true", help="Print the report instead of sending it to Telegram")
    parser.add_argument("--skip-correlation", action="store_true", help="Only compute VaR, skip the correlation section")
    return parser


def main(argv: list[str] | None = None) -> None:
    # Windows consoles default stdout to the system codepage (e.g. cp1252), which can't
    # encode characters this report legitimately uses (Δ in the correlation delta
    # lines) - force UTF-8 so --dry-run works the same in any terminal/CI runner.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)

    config_dir = Path(args.config_dir)
    cfg = load_default_config(config_dir / "default.yaml")
    cfg.validate()
    # symbols.yaml's `symbols:` basket is no longer used for correlation/PC1 - that
    # universe is always "whatever was actually traded" (see traded_symbols below).
    # `specs` (tick_value/tick_size) is still used, independent of that basket list.
    _, specs = load_symbols_file(config_dir / "symbols.yaml")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    trades = _load_trades(args, specs)
    var_result = compute_var(trades, cfg.var_window_days, cfg.var_baseline_days, cfg.var_confidence)
    var_chart_path = plot_var_chart(var_result, cfg.var_window_days, cfg.var_baseline_days, output_dir / "var.png")

    overall = overall_summary(trades)
    asset_stats = asset_month_stats(trades)
    monthly = month_summaries(trades, var_result.daily_pnl, cfg.var_confidence)

    xlsx_path = None
    if monthly:
        xlsx_path = write_monthly_workbook(asset_stats, monthly, cfg.var_confidence, output_dir / "monthly_report.xlsx")

    traded_symbols = sorted({t.symbol for t in trades})

    corr_result = None
    corr_chart_path = None
    quarterly_pc1 = None
    pc1_chart_path = None
    if not args.skip_correlation and traded_symbols:
        closes = _load_closes(args, traded_symbols, trades)
        if not closes.empty:
            corr_result = compute_correlation(closes, cfg.corr_window_days, cfg.top_n_pairs)
            corr_chart_path = plot_correlation_heatmap(corr_result, output_dir / "correlation.png")

            # same fixed `closes` columns (traded_symbols) in every quarter, so the 1/n
            # PC1 floor stays constant and quarters are actually comparable
            quarterly_pc1 = quarterly_pc1_series(closes)
            if quarterly_pc1:
                pc1_chart_path = plot_pc1_chart(quarterly_pc1, output_dir / "pc1.png")

    message = build_message_text(
        var_result, corr_result, cfg.var_confidence, cfg.var_window_days, cfg.var_baseline_days,
        overall=overall, asset_stats=asset_stats, month_summaries_list=monthly, quarterly_pc1=quarterly_pc1,
    )

    if args.dry_run:
        print(message)
        print(f"\nVaR chart: {var_chart_path}")
        if corr_chart_path:
            print(f"Correlation chart: {corr_chart_path}")
        if pc1_chart_path:
            print(f"PC1 concentration chart: {pc1_chart_path}")
        if xlsx_path:
            print(f"Monthly report: {xlsx_path}")
        return

    send_message(message)
    send_photo(var_chart_path, caption="VaR")
    if corr_chart_path:
        send_photo(corr_chart_path, caption="Correlation")
    if pc1_chart_path:
        send_photo(pc1_chart_path, caption="PC1 concentration")


if __name__ == "__main__":
    main()
