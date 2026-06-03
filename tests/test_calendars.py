from datetime import date

from eaglesignal.ingestion.calendars import (
    _first_friday,
    events_within_horizon,
    market_events,
)


def test_first_friday_rule():
    assert _first_friday(2026, 1) == date(2026, 1, 2)   # Jan 1 2026 is a Thursday
    assert _first_friday(2026, 2) == date(2026, 2, 6)   # Feb 1 2026 is a Sunday


def test_market_events_include_curated_fomc_and_rule_based():
    evs = market_events(today=date(2026, 1, 26), days_ahead=21)
    kinds = {e.kind for e in evs}
    assert "fomc" in kinds          # curated 2026-01-28
    assert "jobless_claims" in kinds  # weekly Thursday rule
    fomc = next(e for e in evs if e.kind == "fomc")
    assert fomc.impact == "high"
    assert fomc.days_away == 2


def test_events_within_horizon_includes_earnings_and_macro():
    evs = events_within_horizon(
        horizon_days=5, today=date(2026, 1, 26), days_to_earnings=3, ticker="NVDA"
    )
    kinds = {e.kind for e in evs}
    assert "earnings" in kinds
    assert "fomc" in kinds                      # FOMC 01-28 is 2 days out
    assert all(e.days_away <= 5 for e in evs)


def test_events_within_horizon_excludes_distant_events():
    # 1-day horizon, earnings 30 days out -> nothing inside the window.
    evs = events_within_horizon(
        horizon_days=1, today=date(2026, 6, 1), days_to_earnings=30, ticker="NVDA"
    )
    assert all(e.days_away <= 1 for e in evs)
    assert not any(e.kind == "earnings" for e in evs)
