import datetime as dt
from pathlib import Path

import pytest

from risk_mgmt.logsource.mql5_journal import MQL5JournalSource
from risk_mgmt.symbol_spec import SymbolSpec

FIXTURES = Path(__file__).parent / "fixtures"
SPEC = {"ES35": SymbolSpec(symbol="ES35", tick_value=1.0, tick_size=0.5)}
NO_LIVE_FALLBACK = lambda symbol: None  # noqa: E731 - forces the "not found" branch deterministically


def test_parses_the_one_completed_trade_in_the_sample_log():
    trades = MQL5JournalSource.from_directory(FIXTURES, SPEC, pattern="sample_journal.log").load_trades()

    assert len(trades) == 1
    trade = trades[0]
    assert trade.symbol == "ES35"
    assert trade.direction == "sell"
    assert trade.entry_time == dt.datetime(2026, 1, 12, 9, 19, 36)
    assert trade.entry_price == pytest.approx(17567.48)
    assert trade.exit_time == dt.datetime(2026, 1, 12, 10, 41, 37)
    assert trade.exit_price == pytest.approx(17408.42)
    assert trade.exit_reason == "tp"
    assert trade.lots == pytest.approx(0.2)


def test_pnl_uses_the_symbol_spec_tick_value_and_size():
    trade = MQL5JournalSource.from_directory(FIXTURES, SPEC, pattern="sample_journal.log").load_trades()[0]

    profit_points = trade.entry_price - trade.exit_price  # sell trade, profit when price falls
    expected_pnl = (profit_points / SPEC["ES35"].tick_size) * SPEC["ES35"].tick_value * trade.lots
    assert trade.pnl_money == pytest.approx(expected_pnl)


def test_r_multiple_uses_the_original_sl_from_the_placement_line_not_the_trailed_one():
    # The fixture's ticket #4 was placed with SL=17657.00 (original), then trailed to
    # 17644.74 before the TP hit ("position modified" line) - r_multiple must be based
    # on the original 17657.00 risk distance, not the trailed one.
    trade = MQL5JournalSource.from_directory(FIXTURES, SPEC, pattern="sample_journal.log").load_trades()[0]

    original_sl = 17657.00
    risk_distance = abs(trade.entry_price - original_sl)
    profit_points = trade.entry_price - trade.exit_price
    assert trade.r_multiple == pytest.approx(profit_points / risk_distance)


def test_expired_and_still_pending_orders_produce_no_trade():
    # The fixture also has tickets #2, #3, #6 (expired, never filled) and #7 (still
    # pending at end of log) - none of these should show up as trades.
    trades = MQL5JournalSource.from_directory(FIXTURES, SPEC, pattern="sample_journal.log").load_trades()
    assert len(trades) == 1  # only ticket #4 actually filled and closed


def test_raises_on_missing_symbol_spec_with_no_live_fallback_available():
    with pytest.raises(KeyError, match="fetched live from MT5"):
        MQL5JournalSource.from_directory(
            FIXTURES, {}, pattern="sample_journal.log", spec_fetcher=NO_LIVE_FALLBACK
        ).load_trades()


def test_raises_when_no_files_match():
    with pytest.raises(FileNotFoundError):
        MQL5JournalSource.from_directory(FIXTURES, SPEC, pattern="*.does_not_exist")


# --- real .log file format (UTF-16, different column layout) -----------------------

AUS200_SPEC = {"AUS200": SymbolSpec(symbol="AUS200", tick_value=1.0, tick_size=0.01)}


def test_parses_the_real_utf16_log_format_and_a_genuine_stop_loss_exit():
    trades = MQL5JournalSource.from_directory(
        FIXTURES, AUS200_SPEC, pattern="sample_journal_real_format.log"
    ).load_trades()

    assert len(trades) == 1
    trade = trades[0]
    assert trade.symbol == "AUS200"
    assert trade.direction == "buy"
    assert trade.entry_time == dt.datetime(2026, 1, 2, 3, 44, 59)
    assert trade.entry_price == pytest.approx(8730.00)
    assert trade.exit_time == dt.datetime(2026, 1, 2, 8, 13, 5)
    assert trade.exit_price == pytest.approx(8715.30)
    assert trade.exit_reason == "sl"

    original_sl = 8691.60
    risk_distance = abs(trade.entry_price - original_sl)
    profit_points = trade.exit_price - trade.entry_price  # buy trade
    assert trade.r_multiple == pytest.approx(profit_points / risk_distance)


def test_missing_spec_falls_back_to_the_injected_fetcher():
    # spec_fetcher is injected here instead of hitting a real MT5 connection - this is
    # what the CLI wires to a real live lookup by default (see MQL5JournalSource docstring).
    fetcher_calls = []

    def fake_fetcher(symbol):
        fetcher_calls.append(symbol)
        return SymbolSpec(symbol=symbol, tick_value=1.0, tick_size=0.01)

    trades = MQL5JournalSource.from_directory(
        FIXTURES, {}, pattern="sample_journal_real_format.log", spec_fetcher=fake_fetcher
    ).load_trades()

    assert fetcher_calls == ["AUS200"]
    assert len(trades) == 1


def test_missing_spec_raises_a_clear_error_when_the_fetcher_also_fails():
    with pytest.raises(KeyError, match="fetched live from MT5"):
        MQL5JournalSource.from_directory(
            FIXTURES, {}, pattern="sample_journal_real_format.log", spec_fetcher=NO_LIVE_FALLBACK
        ).load_trades()
