from eaglesignal.analysis.economic_events import analyze_economic_event_impact
from eaglesignal.ingestion.calendars import CalendarEvent


def test_economic_event_impact_quiet_calendar():
    impact = analyze_economic_event_impact(
        [],
        direction="bullish",
        horizon_days=5,
        market_regime={"label": "risk_on", "score": 68},
        macro_values={"vix": 13.5},
    )

    assert impact["available"] is True
    assert impact["event_count"] == 0
    assert impact["risk_level"] == "quiet"
    assert "No scheduled" in impact["summary"]


def test_economic_event_impact_flags_high_impact_binary_risk():
    events = [
        CalendarEvent(
            date="2026-06-05",
            kind="nfp",
            title="Non-farm payrolls / jobs report",
            impact="high",
            scope="market",
            source="BLS schedule",
            days_away=0,
        ),
        CalendarEvent(
            date="2026-06-08",
            kind="earnings",
            title="NVDA earnings report",
            impact="high",
            scope="ticker",
            ticker="NVDA",
            source="earnings connector",
            days_away=3,
        ),
    ]

    impact = analyze_economic_event_impact(
        events,
        direction="neutral_to_bullish",
        horizon_days=5,
        market_regime={"label": "risk_off", "score": 42},
        macro_values={"vix": 24.2, "yield_curve_10y_2y": -0.25},
    )

    assert impact["event_count"] == 2
    assert impact["high_impact_count"] == 2
    assert impact["risk_level"] in {"high", "extreme"}
    assert impact["action"] == "prefer_defined_risk_options_or_wait"
    assert impact["events"][0]["channel"]
    assert "Bullish thesis is event-sensitive" in impact["summary"]
