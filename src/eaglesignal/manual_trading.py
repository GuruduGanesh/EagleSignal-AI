"""User-entered paper trade journal.

Unlike ``paper_trading.py`` which auto-opens tiny dummy positions from model
signals, this module tracks trades the user manually enters with their own
entry price. It never sends broker orders.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import PredictionResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _contract_multiplier(trade: dict[str, Any]) -> float:
    try:
        return float(trade.get("contract_multiplier") or 1)
    except Exception:
        return 1.0


def _apply_pl(trade: dict[str, Any], current: float) -> None:
    """Mark one open trade against a current price and compute unrealized P/L."""
    entry = float(trade["entry_price"])
    qty = float(trade["quantity"])
    mult = _contract_multiplier(trade)
    raw_pct = (float(current) / entry - 1) * 100 if entry else 0.0
    pnl_pct = raw_pct if trade.get("side") == "long" else -raw_pct
    trade.update({
        "current_price": round(float(current), 4),
        "last_marked_at": _now(),
        "unrealized_pnl_pct": round(pnl_pct, 2),
        "unrealized_pnl_dollars": round(entry * qty * mult * pnl_pct / 100, 2),
    })


def _option_mark(row: Any) -> float | None:
    try:
        bid = float(row.get("bid", 0) or 0)
        ask = float(row.get("ask", 0) or 0)
        last = float(row.get("lastPrice", 0) or 0)
        if bid > 0 and ask > 0:
            return round((bid + ask) / 2, 4)
        if last > 0:
            return round(last, 4)
    except Exception:
        return None
    return None


def parse_option_contract_meta(contract: str) -> dict[str, Any]:
    """Best-effort OCC-style contract parser.

    Supports symbols like NVDA260619C00220000 where the last 15 characters are
    YYMMDD + C/P + strike*1000.
    """
    c = (contract or "").strip().upper()
    if len(c) < 15:
        return {}
    tail = c[-15:]
    yy, mm, dd, right, strike_raw = tail[:2], tail[2:4], tail[4:6], tail[6], tail[7:]
    try:
        strike = int(strike_raw) / 1000.0
        return {
            "option_expiration": f"20{yy}-{mm}-{dd}",
            "option_type": "call" if right == "C" else "put" if right == "P" else "",
            "option_strike": strike,
        }
    except Exception:
        return {}


def _option_quote(row: Any, *, contract: str, expiry: str, option_type: str) -> dict[str, Any]:
    bid = ask = last = None
    try:
        bid = float(row.get("bid", 0) or 0)
        ask = float(row.get("ask", 0) or 0)
        last = float(row.get("lastPrice", 0) or 0)
    except Exception:
        pass
    mark = _option_mark(row)
    meta = parse_option_contract_meta(contract)
    try:
        strike = float(row.get("strike", meta.get("option_strike") or 0) or 0)
    except Exception:
        strike = meta.get("option_strike")
    return {
        "contract": contract.upper(),
        "option_contract": contract.upper(),
        "option_expiration": expiry or meta.get("option_expiration"),
        "option_type": option_type or meta.get("option_type"),
        "option_strike": strike,
        "current_price": mark,
        "mark": mark,
        "last": round(last, 4) if last is not None else None,
        "bid": round(bid, 4) if bid is not None else None,
        "ask": round(ask, 4) if ask is not None else None,
        "volume": int(row.get("volume", 0) or 0),
        "open_interest": int(row.get("openInterest", 0) or 0),
        "contract_multiplier": 100,
        "source": "options_chain",
    }


def fetch_option_contract_quote(underlying: str, contract: str) -> dict[str, Any] | None:
    from .ingestion.options_chain import fetch_options

    chain = fetch_options(underlying, max_expiries=20, min_days=0)
    if not chain.available:
        return None
    target = contract.upper()
    for expiry in chain.chains:
        for option_type, frame in (("call", expiry.calls), ("put", expiry.puts)):
            if frame is None or frame.empty or "contractSymbol" not in frame:
                continue
            matches = frame[frame["contractSymbol"].astype(str).str.upper() == target]
            if not matches.empty:
                return _option_quote(
                    matches.iloc[0],
                    contract=target,
                    expiry=expiry.expiration,
                    option_type=option_type,
                )
    return None


def _fetch_option_contract_mark(underlying: str, contract: str) -> float | None:
    quote = fetch_option_contract_quote(underlying, contract)
    return float(quote["mark"]) if quote and quote.get("mark") else None


def refresh_live_prices(data_dir: Path, ledger: dict[str, Any] | None = None, save: bool = True) -> dict[str, Any]:
    """Fetch the LATEST real market price for every open manual trade and mark P/L.

    Used by the API so the Manual Trades tab always shows a current price without
    waiting for a full pipeline scan. Uses the same real-data provider chain; if a
    price can't be fetched the trade keeps its last mark.
    """
    from .ingestion.market_data import fetch_history

    ledger = ledger if ledger is not None else load_manual_trades(data_dir)
    tickers = {
        str(t.get("ticker", "")).upper()
        for t in ledger.get("open", [])
        if t.get("ticker") and t.get("instrument_type") != "option"
    }
    prices: dict[str, float] = {}
    marked_any = False
    for tk in tickers:
        try:
            md = fetch_history(tk)
            if md.ok:
                prices[tk] = float(md.current_price or md.last_close)
        except Exception:
            continue
    for trade in ledger.get("open", []):
        if trade.get("instrument_type") == "option":
            contract = str(trade.get("option_contract") or trade.get("ticker") or "").upper()
            underlying = str(trade.get("underlying") or "").upper()
            if contract and underlying:
                try:
                    mark = _fetch_option_contract_mark(underlying, contract)
                    if mark:
                        _apply_pl(trade, mark)
                        marked_any = True
                except Exception:
                    pass
            continue
        cur = prices.get(str(trade.get("ticker", "")).upper())
        if cur:
            _apply_pl(trade, cur)
            marked_any = True
    if save and marked_any:
        save_manual_trades(data_dir, ledger)
    return ledger


def _path(data_dir: Path) -> Path:
    return data_dir / "manual_trades.json"


def load_manual_trades(data_dir: Path) -> dict[str, Any]:
    path = _path(data_dir)
    if not path.exists():
        return {"open": [], "closed": [], "updated_at": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("open", [])
        data.setdefault("closed", [])
        return data
    except Exception:
        return {"open": [], "closed": [], "updated_at": None}


def save_manual_trades(data_dir: Path, ledger: dict[str, Any]) -> None:
    path = _path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger["updated_at"] = _now()
    path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def add_manual_trade(
    data_dir: Path,
    *,
    ticker: str,
    side: str,
    entry_price: float,
    quantity: float,
    note: str = "",
    instrument_type: str = "equity",
    underlying: str | None = None,
    option_contract: str | None = None,
    option_expiration: str | None = None,
    option_type: str | None = None,
    option_strike: float | None = None,
    contract_multiplier: float | None = None,
) -> dict[str, Any]:
    side_norm = side.strip().lower()
    if side_norm not in {"long", "short"}:
        raise ValueError("side must be long or short")
    if entry_price <= 0:
        raise ValueError("entry_price must be greater than zero")
    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")

    instrument = (instrument_type or "equity").strip().lower()
    if instrument not in {"equity", "option"}:
        raise ValueError("instrument_type must be equity or option")
    multiplier = float(contract_multiplier or (100 if instrument == "option" else 1))
    parsed = parse_option_contract_meta(option_contract or ticker) if instrument == "option" else {}
    ledger = load_manual_trades(data_dir)
    trade = {
        "id": str(uuid.uuid4()),
        "ticker": ticker.strip().upper(),
        "instrument_type": instrument,
        "underlying": (underlying or ticker).strip().upper(),
        "option_contract": (option_contract or ticker).strip().upper() if instrument == "option" else "",
        "option_expiration": option_expiration or parsed.get("option_expiration") or "",
        "option_type": option_type or parsed.get("option_type") or "",
        "option_strike": float(option_strike if option_strike is not None else (parsed.get("option_strike") or 0)) if instrument == "option" else 0,
        "contract_multiplier": multiplier,
        "side": side_norm,
        "entry_price": float(entry_price),
        "quantity": float(quantity),
        "notional": round(float(entry_price) * float(quantity) * multiplier, 2),
        "opened_at": _now(),
        "note": note.strip(),
        "source": "manual_user_entry",
    }
    # Mark the latest market price immediately so the user sees it without a scan.
    try:
        if instrument == "option":
            mark = _fetch_option_contract_mark(trade["underlying"], trade["option_contract"])
            if mark:
                _apply_pl(trade, mark)
        else:
            from .ingestion.market_data import fetch_history

            md = fetch_history(trade["ticker"])
            if md.ok:
                _apply_pl(trade, float(md.current_price or md.last_close))
    except Exception:
        pass

    ledger["open"].append(trade)
    save_manual_trades(data_dir, ledger)
    return trade


def update_manual_trade(
    data_dir: Path,
    trade_id: str,
    *,
    ticker: str | None = None,
    side: str | None = None,
    entry_price: float | None = None,
    quantity: float | None = None,
    note: str | None = None,
    instrument_type: str | None = None,
    underlying: str | None = None,
    option_contract: str | None = None,
    option_expiration: str | None = None,
    option_type: str | None = None,
    option_strike: float | None = None,
    contract_multiplier: float | None = None,
) -> dict[str, Any]:
    """Edit an existing open trade. Only provided fields change; price/P-L are
    re-marked against the latest market price afterward."""
    ledger = load_manual_trades(data_dir)
    trade = next((t for t in ledger.get("open", []) if t.get("id") == trade_id), None)
    if trade is None:
        raise ValueError(f"trade id {trade_id} not found")

    if ticker is not None and ticker.strip():
        trade["ticker"] = ticker.strip().upper()
    if instrument_type is not None:
        instrument = instrument_type.strip().lower()
        if instrument not in {"equity", "option"}:
            raise ValueError("instrument_type must be equity or option")
        trade["instrument_type"] = instrument
    if underlying is not None and underlying.strip():
        trade["underlying"] = underlying.strip().upper()
    if option_contract is not None and option_contract.strip():
        trade["option_contract"] = option_contract.strip().upper()
        parsed = parse_option_contract_meta(option_contract)
        trade["option_expiration"] = trade.get("option_expiration") or parsed.get("option_expiration", "")
        trade["option_type"] = trade.get("option_type") or parsed.get("option_type", "")
        trade["option_strike"] = trade.get("option_strike") or parsed.get("option_strike", 0)
    if option_expiration is not None:
        trade["option_expiration"] = option_expiration.strip()
    if option_type is not None:
        trade["option_type"] = option_type.strip().lower()
    if option_strike is not None:
        trade["option_strike"] = float(option_strike)
    if side is not None:
        side_norm = side.strip().lower()
        if side_norm not in {"long", "short"}:
            raise ValueError("side must be long or short")
        trade["side"] = side_norm
    if entry_price is not None:
        if entry_price <= 0:
            raise ValueError("entry_price must be greater than zero")
        trade["entry_price"] = float(entry_price)
    if quantity is not None:
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        trade["quantity"] = float(quantity)
    if note is not None:
        trade["note"] = note.strip()
    if contract_multiplier is not None:
        if contract_multiplier <= 0:
            raise ValueError("contract_multiplier must be greater than zero")
        trade["contract_multiplier"] = float(contract_multiplier)

    if trade.get("instrument_type") == "option":
        trade["contract_multiplier"] = float(trade.get("contract_multiplier") or 100)
        trade["underlying"] = str(trade.get("underlying") or trade.get("ticker")).upper()
        trade["option_contract"] = str(trade.get("option_contract") or trade.get("ticker")).upper()
        parsed = parse_option_contract_meta(trade["option_contract"])
        trade["option_expiration"] = trade.get("option_expiration") or parsed.get("option_expiration", "")
        trade["option_type"] = trade.get("option_type") or parsed.get("option_type", "")
        trade["option_strike"] = trade.get("option_strike") or parsed.get("option_strike", 0)
    else:
        trade["contract_multiplier"] = float(trade.get("contract_multiplier") or 1)
    trade["notional"] = round(float(trade["entry_price"]) * float(trade["quantity"]) * _contract_multiplier(trade), 2)
    trade["updated_at"] = _now()
    # Re-mark against the latest real price.
    try:
        if trade.get("instrument_type") == "option":
            mark = _fetch_option_contract_mark(str(trade.get("underlying")), str(trade.get("option_contract")))
            if mark:
                _apply_pl(trade, mark)
        else:
            from .ingestion.market_data import fetch_history

            md = fetch_history(trade["ticker"])
            if md.ok:
                _apply_pl(trade, float(md.current_price or md.last_close))
    except Exception:
        pass

    save_manual_trades(data_dir, ledger)
    return trade


def delete_manual_trade(data_dir: Path, trade_id: str) -> dict[str, Any]:
    """Remove an open trade by id. Returns the deleted trade."""
    ledger = load_manual_trades(data_dir)
    open_trades = ledger.get("open", [])
    victim = next((t for t in open_trades if t.get("id") == trade_id), None)
    if victim is None:
        raise ValueError(f"trade id {trade_id} not found")
    ledger["open"] = [t for t in open_trades if t.get("id") != trade_id]
    save_manual_trades(data_dir, ledger)
    return victim


def mark_manual_trades(
    predictions: list[PredictionResult],
    data_dir: Path,
) -> dict[str, Any]:
    ledger = load_manual_trades(data_dir)
    price_by_ticker = {
        p.ticker.upper(): p.market_snapshot.get("current_price")
        for p in predictions
        if p.market_snapshot.get("current_price")
    }

    for trade in ledger.get("open", []):
        if trade.get("instrument_type") == "option":
            continue
        ticker = str(trade.get("ticker", "")).upper()
        current = price_by_ticker.get(ticker)
        if current:
            _apply_pl(trade, float(current))

    # For any open trade whose ticker wasn't in this run, still refresh its price.
    leftover = [t for t in ledger.get("open", []) if str(t.get("ticker", "")).upper() not in price_by_ticker]
    if leftover:
        refresh_live_prices(data_dir, ledger, save=False)

    save_manual_trades(data_dir, ledger)

    for pred in predictions:
        matches = [
            t for t in ledger.get("open", [])
            if str(t.get("ticker", "")).upper() == pred.ticker.upper()
        ]
        if matches:
            pred.manual_trade = {"open_trades": matches}
    return ledger
