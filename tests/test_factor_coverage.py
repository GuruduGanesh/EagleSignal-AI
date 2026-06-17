from types import SimpleNamespace

from eaglesignal.analysis.factor_coverage import FACTOR_GROUPS, audit_factor_coverage


def _view(**over):
    base = dict(
        component_scores={
            "technical_structure": 72, "sentiment": 60, "macro_regime": 45,
            "options_intelligence": 66, "cross_market_correlation": 70, "fundamentals": 58,
        },
        missing_data=[],
        data_freshness={"news_items": 4, "government": "available"},
        confidence_trace={"event_calendar": [{"x": 1}], "market_regime": {"available": True}},
        options_trade_idea={},
        policy_impacts=["x"],
        global_correlations={"SPY": 0.8},
        confidence_score=70.0,
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_coverage_and_ceiling_scale_with_data():
    rich = audit_factor_coverage(_view())
    poor = audit_factor_coverage(_view(
        component_scores={"technical_structure": 60},
        missing_data=["fundamentals", "options", "macro", "sentiment", "cross_market"],
        data_freshness={"news_items": 0},
        confidence_trace={},
        policy_impacts=[],
        global_correlations={},
    ))
    assert rich["coverage_pct"] > poor["coverage_pct"]
    assert rich["confidence_ceiling"] > poor["confidence_ceiling"]
    assert rich["total_groups"] == len(FACTOR_GROUPS)


def test_no_connector_groups_always_missing():
    fc = audit_factor_coverage(_view())
    for key in ("institutional_flows", "earnings_calls", "alternative_data", "black_swan"):
        assert key in fc["missing_factor_groups"]


def test_ceiling_reason_lists_data_to_add_when_capped():
    poor = audit_factor_coverage(_view(
        component_scores={"technical_structure": 60},
        missing_data=["fundamentals", "options", "macro", "sentiment"],
        data_freshness={"news_items": 0},
        confidence_trace={},
        policy_impacts=[],
        global_correlations={},
        confidence_score=70.0,
    ))
    # ceiling below the (forced) confidence -> reason should say "capped" + what to add
    assert poor["confidence_ceiling"] <= 70
    assert "add" in poor["ceiling_reason"].lower()
    assert poor["next_data_to_add"]


def test_directional_groups_split_bull_bear():
    fc = audit_factor_coverage(_view(component_scores={
        "technical_structure": 80, "sentiment": 75, "macro_regime": 30,
        "options_intelligence": 66, "fundamentals": 40, "cross_market_correlation": 70,
    }))
    assert "technical" in fc["bullish_factor_groups"]
    assert "macroeconomic" in fc["bearish_factor_groups"]
