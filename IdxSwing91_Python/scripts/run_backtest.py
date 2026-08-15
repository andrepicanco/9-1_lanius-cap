"""CLI: run the IdxSwing91 backtest across the symbols listed in config/symbols.yaml.

Example:
    python scripts/run_backtest.py --from 2023-01-01 --to 2024-01-01
    python scripts/run_backtest.py --symbols US500,PETR4 --from 2023-06-01 --to 2023-12-31
"""

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from idxswing91.account import load_account_config
from idxswing91.backtest.runner import run_backtest_batch
from idxswing91.config_io import load_default_config, load_symbols_file

ROOT = Path(__file__).resolve().parent.parent


def parse_date(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%d")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run IdxSwing91 backtest over historical MT5 data")
    parser.add_argument("--config-dir", default=str(ROOT / "config"), help="Directory with default.yaml/symbols.yaml")
    parser.add_argument("--symbols", default=None, help="Comma-separated symbol list, overrides symbols.yaml")
    parser.add_argument("--from", dest="date_from", required=True, type=parse_date, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", required=True, type=parse_date, help="YYYY-MM-DD")
    parser.add_argument("--balance", type=float, default=10_000.0, help="Starting account balance for sizing")
    parser.add_argument("--output-dir", default=str(ROOT / "backtest_results"), help="Where to write CSV reports")
    parser.add_argument(
        "--account-config",
        default=str(ROOT / "config" / "account.yaml"),
        help="Optional broker login (see config/account.example.yaml). If missing, "
        "attaches to whatever MT5 terminal is already open and logged in.",
    )
    args = parser.parse_args()

    config_dir = Path(args.config_dir)
    base_cfg = load_default_config(config_dir / "default.yaml")
    symbols_from_file, overrides = load_symbols_file(config_dir / "symbols.yaml")
    symbols = args.symbols.split(",") if args.symbols else symbols_from_file
    account = load_account_config(args.account_config)

    if not symbols:
        parser.error("No symbols to run - pass --symbols or populate config/symbols.yaml")

    summary_df, _ = run_backtest_batch(
        symbols=symbols,
        base_cfg=base_cfg,
        date_from=args.date_from,
        date_to=args.date_to,
        overrides=overrides,
        starting_balance=args.balance,
        output_dir=args.output_dir,
        account=account,
    )

    print("\n=== Summary ===")
    print(summary_df.to_string(index=False))
    print(f"\nReports written to {args.output_dir}")


if __name__ == "__main__":
    main()
