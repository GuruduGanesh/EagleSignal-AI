from types import SimpleNamespace

from eaglesignal.analysis.index_strategies import (
    build_index_strategies,
    is_index_strategy_ticker,
)


def _pred(ticker, asset_type, price, target, move_pct, momentum, snapshots, move_points=None):
    return SimpleNamespace(
        ticker=ticker,
        asset_type=SimpleNamespace(value=asset_type),
        market_snapshot={"current_price": price},
        target_price=target,
        expected_percent=move_pct,
        expected_points=move_points,
        component_scores={"price_volume_momentum": momentum},
        market_regime={"label": "risk_on"},
        trend_impact={"summary": "uptrend"},
        catalysts=["FOMC in 3d"],
        options_trade_idea={"all_expiry_snapshots": snapshots, "min_index_option_move_points": 50.0},
    )


def _snap(action, direction, premium, delta, vol, conf, dte=10):
    return {
        "action": action, "direction": direction, "reference_option_price": premium,
        "delta": delta, "exact_contract_volume": vol, "confidence": conf,
        "reference_contract": f"{action}-{premium}", "expiration": "2026-07-17",
        "days_to_expiry": dte, "atm_strike": 100, "avg_iv": 22, "bid_ask_spread_pct": 4,
        "contract_multiplier": 100, "total_oi": 5000,
    }


def test_only_index_predictions_are_recognized():
    spx = _pred("SPX", "index", 6000, 6100, 1.6, 60, [])
    spy = _pred("SPY", "etf", 600, 610, 1.6, 60, [])
    aapl = _pred("AAPL", "equity", 300, 310, 3.3, 60, [])
    assert is_index_strategy_ticker(spx)
    assert not is_index_strategy_ticker(spy)
    assert not is_index_strategy_ticker(aapl)


def test_only_sub_35_premium_promoted_and_profit_computed():
    # cheap call (premium 10, delta 0.5, move 20) -> exit 20 -> +100% profit
    cheap = _snap("BUY CALL", "up", 10.0, 0.5, 4000, 72)
    pricey = _snap("BUY CALL", "up", 60.0, 0.5, 9000, 80)  # > $35, excluded
    p = _pred("NDX", "index", 20000, 20120, 0.6, 70, [cheap, pricey], move_points=120.0)
    rows = build_index_strategies([p], max_option_price=35.0, min_profit_pct=10.0)
    assert len(rows) == 1
    r = rows[0]
    assert r["entry_premium"] == 10.0
    assert r["profit_pct"] >= 10.0 and r["profit_ok"]
    assert r["both_ok"]  # 120 index points + >10% option profit
    assert r["strategy"] == "Long Call"


def test_weak_index_move_flagged_not_actionable():
    s = _snap("BUY CALL", "up", 5.0, 0.5, 3000, 65)
    p = _pred("SPX", "index", 6000, 6030, 0.5, 60, [s], move_points=30.0)
    rows = build_index_strategies([p], max_option_price=35.0, min_profit_pct=10.0)
    assert rows and not rows[0]["both_ok"]
    assert "50 index pts" in rows[0]["status"] or rows[0]["status"].startswith("👀")


def test_lower_price_higher_volume_ranks_first():
    a = _snap("BUY CALL", "up", 30.0, 0.5, 500, 70)    # pricey, low vol
    b = _snap("BUY CALL", "up", 8.0, 0.5, 9000, 70)    # cheap, high vol -> should win
    p = _pred("RUT", "index", 2100, 2175, 3.6, 75, [a, b], move_points=75.0)
    rows = build_index_strategies([p], max_option_price=35.0, min_profit_pct=10.0, per_index=2)
    assert rows[0]["entry_premium"] == 8.0


def test_watch_rows_keep_real_contract_values_when_gate_blocks_trade():
    blocked = _snap("NO TRADE", "up", 12.5, 0.35, 1800, 25)
    p = _pred("SPX", "index", 6000, 6035, 0.6, 58, [blocked], move_points=35.0)
    rows = build_index_strategies([p], max_option_price=35.0, min_profit_pct=10.0)
    assert rows
    assert rows[0]["contract"] != "—"
    assert rows[0]["entry_premium"] == 12.5
