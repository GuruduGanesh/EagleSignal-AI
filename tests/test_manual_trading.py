from eaglesignal.manual_trading import add_manual_trade, mark_manual_trades
from eaglesignal.schemas import AssetType, PredictionResult


def test_manual_trade_marks_long_pnl(tmp_path):
    add_manual_trade(
        tmp_path,
        ticker="NVDA",
        side="long",
        entry_price=100,
        quantity=2,
        note="test",
    )
    pred = PredictionResult(
        prediction_id="p1",
        ticker="NVDA",
        asset_type=AssetType.equity,
        market_snapshot={"current_price": 110},
    )

    ledger = mark_manual_trades([pred], tmp_path)

    trade = ledger["open"][0]
    assert trade["unrealized_pnl_pct"] == 10.0
    assert trade["unrealized_pnl_dollars"] == 20.0
    assert pred.manual_trade["open_trades"][0]["ticker"] == "NVDA"


def test_manual_trade_rejects_bad_side(tmp_path):
    try:
        add_manual_trade(tmp_path, ticker="AAPL", side="hold", entry_price=1, quantity=1)
    except ValueError as exc:
        assert "side" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_manual_option_trade_uses_contract_multiplier(tmp_path, monkeypatch):
    monkeypatch.setattr("eaglesignal.manual_trading._fetch_option_contract_mark", lambda *_args: None)

    trade = add_manual_trade(
        tmp_path,
        ticker="NVDA260619C00220000",
        side="long",
        entry_price=5,
        quantity=2,
        instrument_type="option",
        underlying="NVDA",
        option_contract="NVDA260619C00220000",
        contract_multiplier=100,
    )

    assert trade["instrument_type"] == "option"
    assert trade["underlying"] == "NVDA"
    assert trade["option_contract"] == "NVDA260619C00220000"
    assert trade["option_expiration"] == "2026-06-19"
    assert trade["option_type"] == "call"
    assert trade["option_strike"] == 220.0
    assert trade["notional"] == 1000.0
