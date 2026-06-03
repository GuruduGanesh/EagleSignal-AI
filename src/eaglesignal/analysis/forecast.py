"""SKILL-125 Ensemble forecast engine (uncertainty-aware, research only).

Conceptually borrows from the two deep-learning reference repos without copying
their code or fabricating data:

* JordiCorbilla/stock-prediction-deep-neural-learning — separate *direction* and
  *magnitude*, and emit stochastic bands instead of one overconfident number.
* huseinzol05/Stock-Prediction-Models — Monte-Carlo simulation for expected
  ranges, and trading-agent rules (turtle breakout, MA-crossover, momentum) kept
  as research-only ensemble votes.

Everything is computed from REAL downloaded OHLCV history (log-returns drift and
volatility). The Monte-Carlo paths are a forward *simulation of uncertainty*, not
observed market prices, and are labelled as such in the output. No TensorFlow
dependency — this is deterministic NumPy so it runs anywhere the Docker image
runs and is unit-testable.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from ..schemas import Forecast, SignalComponent


def _agent_votes(df: pd.DataFrame) -> dict[str, str]:
    """Rule-based trend agents -> long / short / flat votes."""
    close = df["close"]
    votes: dict[str, str] = {}

    # Turtle / Donchian breakout (20-bar high/low channel).
    if len(close) > 20:
        hi = close.iloc[-21:-1].max()
        lo = close.iloc[-21:-1].min()
        last = close.iloc[-1]
        votes["turtle"] = "long" if last >= hi else "short" if last <= lo else "flat"

    # Moving-average crossover (fast 20 vs slow 50).
    if len(close) > 50:
        fast = close.rolling(20).mean().iloc[-1]
        slow = close.rolling(50).mean().iloc[-1]
        votes["ma_crossover"] = "long" if fast > slow else "short" if fast < slow else "flat"

    # 3-month momentum.
    if len(close) > 63:
        mom = close.iloc[-1] / close.iloc[-63] - 1
        votes["momentum"] = "long" if mom > 0.02 else "short" if mom < -0.02 else "flat"

    return votes


def _votes_to_score(votes: dict[str, str]) -> float:
    if not votes:
        return 50.0
    net = sum(1 if v == "long" else -1 if v == "short" else 0 for v in votes.values())
    return float(np.clip(50 + (net / len(votes)) * 30, 0, 100))


def _gpu_enabled() -> bool:
    return os.environ.get("ENABLE_GPU_MONTE_CARLO", "0").strip().lower() in {"1", "true", "yes", "on"}


def monte_carlo(
    df: pd.DataFrame,
    horizon_days: int,
    n_paths: int | None = None,
    seed: int = 7,
    use_gpu: bool | None = None,
) -> dict:
    """Geometric-Brownian-motion Monte Carlo seeded from REAL daily log-returns."""
    if n_paths is None:
        try:
            n_paths = int(os.environ.get("MONTE_CARLO_PATHS", "4000"))
        except ValueError:
            n_paths = 4000
    close = df["close"].astype(float)
    rets = np.log(close / close.shift(1)).dropna().to_numpy()
    if len(rets) < 30:
        return {}
    # Use a trailing window so drift reflects the recent regime, not ancient data.
    window = rets[-252:] if len(rets) > 252 else rets
    mu = float(np.mean(window))
    sigma = float(np.std(window))
    backend = "numpy_cpu"
    if use_gpu is None:
        use_gpu = _gpu_enabled()
    if use_gpu:
        try:
            import cupy as cp  # type: ignore

            cp.random.seed(seed)
            shocks_gpu = cp.random.normal(mu, sigma, size=(n_paths, horizon_days))
            cum_gpu = shocks_gpu.sum(axis=1)
            simple_gpu = cp.exp(cum_gpu) - 1.0
            simple = cp.asnumpy(simple_gpu)
            backend = "cupy_gpu"
        except Exception:
            simple = None
            backend = "numpy_cpu_fallback"
    else:
        simple = None
    if simple is None:
        rng = np.random.default_rng(seed)
        shocks = rng.normal(mu, sigma, size=(n_paths, horizon_days))
        cum = shocks.sum(axis=1)  # log return over the horizon
        simple = np.exp(cum) - 1.0
    return {
        "prob_up": float(np.mean(simple > 0)),
        "expected_return_pct": float(np.median(simple) * 100),
        "p05_return_pct": float(np.percentile(simple, 5) * 100),
        "p95_return_pct": float(np.percentile(simple, 95) * 100),
        "daily_vol": sigma,
        "n_paths": n_paths,
        "backend": backend,
    }


def forecast_signal(
    df: pd.DataFrame,
    horizon_days: int = 5,
    *,
    n_paths: int | None = None,
    use_gpu: bool | None = None,
) -> tuple[SignalComponent, Forecast]:
    """Returns an ensemble SignalComponent plus the richer Forecast object."""
    if df is None or df.empty or len(df) < 30:
        comp = SignalComponent(name="ensemble_forecast", score=50.0, weight=0.0, available=False,
                               rationale=["Not enough history for an ensemble forecast."])
        return comp, Forecast(horizon_days=horizon_days, available=False)

    votes = _agent_votes(df)
    mc = monte_carlo(df, horizon_days, n_paths=n_paths, use_gpu=use_gpu)

    notes: list[str] = []
    if votes:
        agree = ", ".join(f"{k}:{v}" for k, v in votes.items())
        notes.append(f"Trend agents — {agree}.")
    score = _votes_to_score(votes)

    fc = Forecast(
        horizon_days=horizon_days,
        agent_votes=votes,
        method="trend_agents",
        available=True,
        rationale=notes.copy(),
    )

    if mc:
        fc.prob_up = round(mc["prob_up"], 3)
        fc.expected_return_pct = round(mc["expected_return_pct"], 2)
        fc.p05_return_pct = round(mc["p05_return_pct"], 2)
        fc.p95_return_pct = round(mc["p95_return_pct"], 2)
        fc.n_paths = mc["n_paths"]
        fc.method = f"monte_carlo_gbm(real_returns,{mc.get('backend', 'numpy_cpu')})+trend_agents"
        notes.append(
            f"Monte-Carlo {horizon_days}D ({mc['n_paths']} paths from real returns): "
            f"P(up)={mc['prob_up']:.0%}, median {fc.expected_return_pct:+.1f}%, "
            f"band [{fc.p05_return_pct:+.1f}%, {fc.p95_return_pct:+.1f}%]."
        )
        fc.rationale = notes.copy()
        # Blend the simulated up-probability into the ensemble score (magnitude
        # comes from the bands; direction here is the probability tilt).
        prob_score = 50 + (mc["prob_up"] - 0.5) * 60  # P(up)=0.5 -> 50
        score = float(np.clip(0.5 * score + 0.5 * prob_score, 0, 100))

    comp = SignalComponent(name="ensemble_forecast", score=round(score, 1), weight=0.0, rationale=notes)
    return comp, fc
