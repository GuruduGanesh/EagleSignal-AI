from datetime import date

from eaglesignal.ingestion.earnings import (
    EarningsInfo,
    _coerce_date,
    _next_future_date,
    fetch_earnings,
)


def test_next_future_date_prefers_soonest_future():
    today = date(2026, 6, 2)
    res = _next_future_date([date(2026, 5, 1), date(2026, 6, 10), date(2026, 7, 1)], today)
    assert res == (date(2026, 6, 10), False)


def test_next_future_date_falls_back_to_recent_past_as_estimate():
    today = date(2026, 6, 2)
    res = _next_future_date([date(2026, 5, 1), date(2026, 4, 1)], today)
    assert res == (date(2026, 5, 1), True)


def test_coerce_date_parses_iso_string():
    assert _coerce_date("2026-06-12 00:00:00") == date(2026, 6, 12)
    assert _coerce_date(date(2026, 1, 9)) == date(2026, 1, 9)
    assert _coerce_date(None) is None


def test_fetch_earnings_empty_ticker_is_unavailable():
    info = fetch_earnings("")
    assert isinstance(info, EarningsInfo)
    assert info.available is False
    assert info.days_to_earnings is None
