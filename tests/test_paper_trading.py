from eaglesignal.paper_trading import update_paper_trades
from eaglesignal.schemas import AssetType, Direction, PredictionResult


def test_update_paper_trades_opens_dummy_long(tmp_path):
    pred = PredictionResult(
        prediction_id="p1",
        ticker="AAPL",
        asset_type=AssetType.equity,
        direction=Direction.neutral_to_bullish,
        opportunity_score=62,
        confidence_score=80,
        risk_score=30,
        market_snapshot={"current_price": 100.0},
    )

    ledger = update_paper_trades([pred], tmp_path, notional=1000)

    assert ledger["positions"]["AAPL"]["side"] == "long"
    assert pred.paper_trade["actor"] == "EagleSignal simulated paper ledger"
    assert pred.paper_trade["trade_type"] == "system_generated_dummy_stock_position"
    assert pred.paper_trade["simulated_action"] == "SIMULATED BUY (test long)"
    assert "long = simulated buy" in pred.paper_trade["side_meaning"]
    assert "NOT a real order" in pred.paper_trade["side_meaning"]
    assert pred.paper_trade["notional"] == 1000.0
    assert pred.paper_trade["unrealized_pnl_pct"] == 0.0


def test_update_paper_trades_skips_neutral_signal(tmp_path):
    pred = PredictionResult(
        prediction_id="p1",
        ticker="SPY",
        asset_type=AssetType.etf,
        direction=Direction.neutral,
        market_snapshot={"current_price": 500.0},
    )

    ledger = update_paper_trades([pred], tmp_path, notional=1000)

    assert ledger["positions"] == {}
    assert pred.paper_trade == {}
