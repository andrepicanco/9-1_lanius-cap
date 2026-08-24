# Risk Mgmt

Parametric VaR + cross-asset correlation risk report for the IdxSwing91 strategy, sent to
Telegram. Independent Python project - reads log/CSV formats produced by
`IdxSwing91_MQL`/`IdxSwing91_Python` but has no import dependency on either, so it should
generalize to other trading-risk use cases too.

## Setup

```bash
pip install -r requirements.txt
pytest tests/          # runs with no MT5 connection and no real credentials needed
```

`--mode live` additionally needs the `MetaTrader5` package (Windows-only, talks to an
already-open, logged-in desktop terminal - see requirements.txt) and either
`config/account.yaml` (copy from `config/account.example.yaml`) or `MT5_LOGIN`/
`MT5_PASSWORD`/`MT5_SERVER` environment variables, or just a terminal already logged in
manually. `--mode local` needs none of that.

## What this does

1. **VaR.** "Returns" = realized daily P/L in $ from closed trades (not price
   mark-to-market) - the natural definition for a stop/target swing strategy. Two
   parametric VaR curves are plotted: a short window (`var_window_days`, default 10) as
   the "current" risk read, and a longer baseline window (`var_baseline_days`, default
   60) for comparison. See `risk_mgmt/var.py` for the exact formula and its limitations
   (normality assumption, flat days with no trades, unrealized risk not captured until a
   trade closes).
2. **Correlation.** Daily close-to-close price returns (not trade P/L - too sparse
   per-symbol across a multi-instrument basket to correlate meaningfully) across the
   symbols in `config/symbols.yaml`. Reports a rolling-window correlation matrix
   (`corr_window_days`, default 20) plus the top-N pairs correlating most strongly right
   now, each compared against its full-history baseline so a real regime shift is
   distinguishable from "these two always move together."
3. **Report.** A VaR chart, a correlation heatmap, and a short text summary - sent to
   Telegram, or printed to stdout with `--dry-run`.

## Modes and sources

| | `--mode local` | `--mode live` |
|---|---|---|
| Trade history for VaR | `--log-dir`, parsed via `--source` | MT5 deal history (`risk_mgmt/live_state.py`) |
| Needs MT5 | No | Yes (desktop terminal, open + logged in) |
| Intended runner | your own machine, on demand | self-hosted GitHub Actions runner (cron) - see below |

`--source` (local mode only):
- `mql5_journal` (default) - parses the raw MQL5 Strategy Tester Journal text. Fragile by
  nature: it depends on the terminal's own trade-log line wording, which changes with the
  terminal's UI language (everything here assumes English - see the caveat at the top of
  `risk_mgmt/logsource/mql5_journal.py`). Needs accurate `tick_value`/`tick_size` per
  symbol in `config/symbols.yaml` to compute $ P/L, since the raw log doesn't carry them.
- `idxswing91_csv` - reads `IdxSwing91_Python`'s own
  `backtest_results/summary.csv`/`<symbol>_trades.csv` directly. Already priced, no
  spec/parsing fragility. Prefer this once you're generating backtests through
  `IdxSwing91_Python` rather than the MetaEditor Strategy Tester UI directly.

Correlation's price history has the same local/live split, via `--price-source
{mt5,csv}` (`--price-dir` for the csv option: a directory of `<symbol>.csv` files with
`date,close` columns) - so correlation can run fully offline/CI-safe even when VaR is
being computed from a live MT5 account, or vice versa.

## GitHub Actions (live mode)

`.github/workflows/risk-report-live.yml` runs on a schedule and calls
`scripts/run_risk_report.py --mode live`. It targets `runs-on: self-hosted` because the
`MetaTrader5` package needs a real desktop terminal - a normal GitHub-hosted runner can't
reach one. **This requires registering your own Windows machine (MT5 open, logged in) as
a self-hosted GitHub Actions runner** - not done by this repo, just what the workflow
expects to exist. A cloud MT5 gateway (e.g. MetaApi.cloud) would remove that requirement,
but isn't wired up here; if you adopt one later, only `risk_mgmt/live_state.py` and
`risk_mgmt/pricesource/mt5_price_history.py` would need to change.

Secrets the workflow expects (`Settings -> Secrets and variables -> Actions`):
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and optionally `MT5_LOGIN`/`MT5_PASSWORD`/
`MT5_SERVER` (only needed if the self-hosted runner's terminal isn't already logged in).

## CLI reference

```bash
# Backtest-log analysis, no Telegram send, print to stdout
python scripts/run_risk_report.py --mode local --log-dir path/to/logs --dry-run

# Same, but reading IdxSwing91_Python's own CSV output instead of a raw Journal
python scripts/run_risk_report.py --mode local --log-dir ../IdxSwing91_Python/backtest_results \
    --source idxswing91_csv --dry-run

# Live account, sends to Telegram (needs TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID set)
python scripts/run_risk_report.py --mode live
```

Full flag list: `python scripts/run_risk_report.py --help`.

## Known limitations (not solved here, worth knowing before trusting the numbers)

- Parametric VaR assumes a roughly normal daily P/L distribution. A strategy with capped
  R-multiples (fixed SL, TP at a fixed R) doesn't really produce normal outcomes -
  historical/empirical VaR would be a more faithful (if noisier) alternative.
- The `mql5_journal` source has never actually seen a stop-loss-triggered exit line in
  the wild (only take-profit, in the sample captured for its tests) - the SL-exit pattern
  is inferred by symmetry with the TP pattern and needs confirming against a real log.
- Live-mode trades (`risk_mgmt/live_state.py`) don't carry an `r_multiple` - MT5's deal
  history has no record of the original stop distance a position was opened against.
