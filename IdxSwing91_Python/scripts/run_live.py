"""CLI: run the IdxSwing91 live trader against the symbols in config/symbols.yaml.

Sends real orders through the connected MT5 terminal - validate on a demo account first.

Example:
    python scripts/run_live.py --poll-interval 5 --log-file logs/idxswing91.log
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from idxswing91.account import load_account_config
from idxswing91.config_io import load_default_config, load_symbols_file
from idxswing91.live.runner import run_live

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run IdxSwing91 live against a connected MT5 terminal")
    parser.add_argument("--config-dir", default=str(ROOT / "config"), help="Directory with default.yaml/symbols.yaml")
    parser.add_argument("--symbols", default=None, help="Comma-separated symbol list, overrides symbols.yaml")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Seconds between polling cycles")
    parser.add_argument("--log-file", default=None, help="Optional file to also write logs to")
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

    run_live(
        symbols=symbols,
        base_cfg=base_cfg,
        overrides=overrides,
        poll_interval_seconds=args.poll_interval,
        log_file=args.log_file,
        account=account,
    )


if __name__ == "__main__":
    main()
