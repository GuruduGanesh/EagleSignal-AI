"""SKILL-140 Backtesting engine (walk-forward, no lookahead).

Validates the technical signal: at each historical bar it computes the signal
using ONLY data up to that bar, then measures the realized forward return over
`horizon_days`. Reports directional accuracy, average forward return when
bullish vs bearish, and a naive Sharpe of the signal-following strategy.

This is a research validation tool, not a trade simulator — costs/slippage are
modeled as a flat per-trade haircut.
"""
from __future__ import annotations

import numpy as np

from .analysis.technical import technical_signal
from .ingestion.market_data import fetch_history


def run_backtest(ticker: str, horizon_days: int = 5, cost_pct: float = 0.05, min_history: int = 200) -> dict:
    market = fetch_history(ticker, period="2y")
    df = market.bars
    if len(df) < min_history + horizon_days + 10:
        return {"error": "insufficient history", "bars": len(df)}

    closes = df["close"].values
    preds: list[int] = []      # +1 bullish, -1 bearish, 0 neutral
    fwd_returns: list[float] = []

    for i in range(min_history, len(df) - horizon_days):
        window = df.iloc[:i]  # only past data -> no lookahead
        score = technical_signal(window).score
        signal = 1 if score >= 58 else (-1 if score <= 42 else 0)
        fwd = closes[i + horizon_days] / closes[i] - 1
        preds.append(signal)
        fwd_returns.append(float(fwd))

    preds_arr = np.array(preds)
    fwd_arr = np.array(fwd_returns)
    directional = preds_arr != 0
    n_trades = int(directional.sum())
    if n_trades == 0:
        return {"ticker": ticker, "trades": 0, "note": "no directional signals"}

    correct = ((preds_arr > 0) & (fwd_arr > 0)) | ((preds_arr < 0) & (fwd_arr < 0))
    accuracy = float(correct[directional].mean())

    strat_ret = preds_arr * fwd_arr - np.abs(preds_arr) * (cost_pct / 100)
    traded = strat_ret[directional]
    sharpe = float(traded.mean() / traded.std() * np.sqrt(252 / horizon_days)) if traded.std() else 0.0
    cum = float(np.prod(1 + traded) - 1)

    return {
        "ticker": ticker,
        "data_source": market.source,
        "trades": n_trades,
        "directional_accuracy": round(accuracy, 3),
        "avg_forward_return_pct": round(float(fwd_arr[directional].mean()) * 100, 3),
        "strategy_cum_return_pct": round(cum * 100, 2),
        "approx_sharpe": round(sharpe, 2),
        "horizon_days": horizon_days,
        "note": "Research validation only; not a live trade simulation.",
    }
