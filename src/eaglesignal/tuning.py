"""ADR-002 Backtest-driven weight tuning (walk-forward, no lookahead).

Hand-set weights in ``config/weights.yml`` are *asserted*, not *measured*. This
module measures each signal engine's historical edge and fits evidence-based
weights, writing ``config/weights.fitted.yml`` (which the engine then prefers).

HONEST SCOPE — only the **price-history-derived** engines can be replayed at a
past date without lookahead, because they are pure functions of the OHLCV bars
up to that date:

* ``technical_structure``      (technical_signal + pattern_bias, as in engine.py)
* ``price_volume_momentum``    (price_volume_signal)
* ``ensemble_forecast``        (forecast_signal — Monte-Carlo + trend agents)
* ``cross_market_correlation`` (cross_market_signal vs SPY, sliced by date)

Fundamentals / options / macro / sentiment depend on point-in-time external
snapshots we do NOT have historically — fitting them from *today's* data would
be lookahead bias, so they KEEP their hand-set prior weight. We tune only the
replayable group and redistribute exactly that group's existing weight mass,
regularized toward the prior so a thin sample can't produce degenerate weights.

This is a research-validation tool, not a trade simulator.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .analysis.cross_market import cross_market_signal
from .analysis.forecast import forecast_signal
from .analysis.patterns import pattern_bias
from .analysis.technical import price_volume_signal, technical_signal
from .config import load_weights
from .ingestion.market_data import fetch_history
from .utils.logging import get_logger

log = get_logger("tuning")

# Components we can honestly replay (pure functions of past bars).
REPLAYABLE = ["technical_structure", "price_volume_momentum",
              "ensemble_forecast", "cross_market_correlation"]

# Multi-horizon tuning (§2.3): each strategy profile has a natural forward
# horizon. An intraday strategy must be measured against a 1-day forward move,
# swing-family against ~1 week, long-term/index against ~1 month. Tuning every
# profile at a single horizon mismeasures the fast and slow ones.
DEFAULT_HORIZON_DAYS = 5
PROFILE_HORIZON_DAYS = {
    "intraday": 1,
    "swing": 5,
    "options_buying": 5,
    "options_selling": 5,
    "earnings": 5,
    "index_trend": 20,
    "long_term": 20,
}


def horizon_for_profile(profile: str, default: int = DEFAULT_HORIZON_DAYS) -> int:
    return PROFILE_HORIZON_DAYS.get(profile, default)

_BULL, _BEAR = 58.0, 42.0          # directional thresholds (match the backtest)
_MIN_DIR_BARS = 25                 # min directional calls before a component earns data-driven weight
_LAMBDA = 0.6                      # regularization: fitted = (1-λ)·prior + λ·measured


def _score_at(window: pd.DataFrame, bench_window: pd.DataFrame | None,
              horizon_days: int) -> dict[str, float]:
    """All replayable component scores for a single historical window."""
    tech = technical_signal(window)
    pbias, _ = pattern_bias(window)
    tech_score = float(np.clip(tech.score + pbias * 6, 0, 100))   # mirrors engine.py
    pv = price_volume_signal(window)
    fc_comp, _ = forecast_signal(window, horizon_days)
    xm = cross_market_signal(window, bench_window)
    return {
        "technical_structure": tech_score,
        "price_volume_momentum": float(pv.score),
        "ensemble_forecast": float(fc_comp.score),
        "cross_market_correlation": float(xm.score),
    }


def replay_ticker(ticker: str, horizon_days: int, period: str, min_history: int,
                  step: int, benchmark: pd.DataFrame | None) -> dict[str, list[tuple[float, float]]]:
    """Walk forward over one ticker; return {component: [(score, fwd_return), ...]}."""
    market = fetch_history(ticker, period=period)
    df = market.bars
    pairs: dict[str, list[tuple[float, float]]] = {c: [] for c in REPLAYABLE}
    if df is None or df.empty or len(df) < min_history + horizon_days + 10:
        return pairs
    closes = df["close"].values
    last_date = df.index
    for i in range(min_history, len(df) - horizon_days, max(1, step)):
        window = df.iloc[:i]                                  # past only -> no lookahead
        bw = None
        if benchmark is not None:
            bw = benchmark[benchmark.index <= last_date[i - 1]]   # benchmark up to same date
        try:
            scores = _score_at(window, bw, horizon_days)
        except Exception as exc:
            log.warning("replay %s bar %d failed: %s", ticker, i, exc)
            continue
        fwd = float(closes[i + horizon_days] / closes[i] - 1)
        for c, s in scores.items():
            pairs[c].append((s, fwd))
    return pairs


def _metrics(pairs: list[tuple[float, float]]) -> dict:
    """Directional accuracy + information coefficient for one component."""
    if not pairs:
        return {"samples": 0, "directional_bars": 0, "accuracy": None, "ic": None, "skill": 0.0}
    arr = np.array(pairs, dtype=float)
    score, fwd = arr[:, 0], arr[:, 1]
    sig = np.where(score >= _BULL, 1, np.where(score <= _BEAR, -1, 0))
    directional = sig != 0
    n_dir = int(directional.sum())
    if n_dir > 0:
        correct = ((sig > 0) & (fwd > 0)) | ((sig < 0) & (fwd < 0))
        accuracy = float(correct[directional].mean())
    else:
        accuracy = None
    # Information coefficient: how well (score-50) ranks forward return.
    ic = None
    if len(score) >= 10 and np.std(score) > 1e-9 and np.std(fwd) > 1e-9:
        ic = float(np.corrcoef(score - 50.0, fwd)[0, 1])
    # Skill = measured directional edge over a coin-flip, only if enough samples.
    skill = 0.0
    if accuracy is not None and n_dir >= _MIN_DIR_BARS:
        skill = max(0.0, accuracy - 0.5)
    return {"samples": len(pairs), "directional_bars": n_dir,
            "accuracy": None if accuracy is None else round(accuracy, 4),
            "ic": None if ic is None else round(ic, 4), "skill": round(skill, 5)}


def _fit_profile(profile: str, comp_metrics: dict[str, dict]) -> dict[str, float]:
    """Blend measured skill with the hand-set prior; redistribute only the
    replayable group's existing weight mass. Non-replayable weights are kept."""
    # Always fit from the HAND-SET prior (explicit path bypasses any existing
    # fitted file) so re-running the tuner never compounds on its own output.
    base = load_weights(profile, path="config/weights.yml")   # normalized prior (sums to 1)
    group_mass = sum(base.get(c, 0.0) for c in REPLAYABLE)    # mass to redistribute
    prior_rel = {c: (base.get(c, 0.0) / group_mass if group_mass else 1.0 / len(REPLAYABLE))
                 for c in REPLAYABLE}

    skills = {c: comp_metrics.get(c, {}).get("skill", 0.0) for c in REPLAYABLE}
    skill_sum = sum(skills.values())
    # Components with too little data are pinned to their prior (skill stays 0
    # and we fall back to prior_rel for them so a thin sample can't distort).
    measured_rel = ({c: skills[c] / skill_sum for c in REPLAYABLE} if skill_sum > 0
                    else dict(prior_rel))

    fitted_rel = {}
    for c in REPLAYABLE:
        has_data = comp_metrics.get(c, {}).get("directional_bars", 0) >= _MIN_DIR_BARS
        m = measured_rel[c] if has_data else prior_rel[c]
        fitted_rel[c] = (1 - _LAMBDA) * prior_rel[c] + _LAMBDA * m
    rel_sum = sum(fitted_rel.values()) or 1.0

    out = dict(base)                                          # keep non-replayable + risk_penalty as-is
    for c in REPLAYABLE:
        out[c] = group_mass * (fitted_rel[c] / rel_sum)
    total = sum(out.values()) or 1.0
    return {k: round(100.0 * v / total, 3) for k, v in out.items()}   # percent, like weights.yml


def tune(profiles: list[str], tickers: list[str], horizon_days: int = 5,
         period: str = "2y", min_history: int = 200, step: int = 5,
         benchmark_ticker: str = "SPY") -> dict:
    """Replay the universe once, then fit each requested profile from the pooled
    component metrics. Returns {"universe", "horizon_days", "components", "profiles"}."""
    bench = None
    try:
        bm = fetch_history(benchmark_ticker, period=period)
        if bm.bars is not None and not bm.bars.empty:
            bench = bm.bars
    except Exception as exc:
        log.warning("benchmark %s fetch failed: %s", benchmark_ticker, exc)

    pooled: dict[str, list[tuple[float, float]]] = {c: [] for c in REPLAYABLE}
    used: list[str] = []
    for t in tickers:
        pairs = replay_ticker(t, horizon_days, period, min_history, step, bench)
        if any(pairs[c] for c in REPLAYABLE):
            used.append(t)
            for c in REPLAYABLE:
                pooled[c].extend(pairs[c])
        log.info("replayed %s (%d bars)", t, len(pairs[REPLAYABLE[0]]))

    comp_metrics = {c: _metrics(pooled[c]) for c in REPLAYABLE}
    fitted = {p: _fit_profile(p, comp_metrics) for p in profiles}
    return {
        "universe": used,
        "universe_size": len(used),
        "horizon_days": horizon_days,
        "step": step,
        "components": comp_metrics,
        "profiles": fitted,
        "note": ("Only price-derived engines are tuned (no lookahead); "
                 "fundamentals/options/macro/sentiment keep their hand-set prior."),
    }


def tune_multi_horizon(profiles: list[str], tickers: list[str], period: str = "2y",
                       min_history: int = 200, step: int = 5,
                       benchmark_ticker: str = "SPY",
                       default_horizon_days: int = DEFAULT_HORIZON_DAYS) -> dict:
    """Tune each profile at its natural horizon (§2.3).

    Profiles are grouped by ``horizon_for_profile`` and each distinct horizon is
    replayed once, so ``intraday`` is fitted against 1-day forward returns while
    swing-family stays at 5D and long-term/index at 20D. Fitted profiles are
    merged into one result that ``write_fitted`` can persist unchanged.
    """
    groups: dict[int, list[str]] = {}
    for p in profiles:
        groups.setdefault(horizon_for_profile(p, default_horizon_days), []).append(p)

    merged_profiles: dict[str, dict] = {}
    components_by_horizon: dict[str, dict] = {}
    horizon_map: dict[str, int] = {}
    universe_union: set[str] = set()
    for h, profs in sorted(groups.items()):
        res = tune(profs, tickers, horizon_days=h, period=period,
                   min_history=min_history, step=step, benchmark_ticker=benchmark_ticker)
        merged_profiles.update(res["profiles"])
        components_by_horizon[f"{h}D"] = res["components"]
        for p in profs:
            horizon_map[p] = h
        universe_union.update(res.get("universe", []))

    return {
        "universe": sorted(universe_union),
        "universe_size": len(universe_union),
        "horizon_days": None,                       # multi-horizon; see "horizons"
        "horizons": horizon_map,
        "components_by_horizon": components_by_horizon,
        "profiles": merged_profiles,
        "note": ("Multi-horizon walk-forward (§2.3): intraday=1D, swing-family=5D, "
                 "long_term/index=20D. Only price-derived engines are tuned (no lookahead); "
                 "fundamentals/options/macro/sentiment keep their hand-set prior."),
    }


def write_fitted(result: dict, path: str = "config/weights.fitted.yml") -> str:
    """Persist fitted profiles in the same shape as weights.yml so load_weights
    can consume them directly (empty default + per-profile full weight sets)."""
    import yaml

    from .config import ROOT

    p = ROOT / path
    payload = {
        "_generated_by": "eaglesignal tune (ADR-002, walk-forward, no lookahead)",
        "_universe_size": result.get("universe_size"),
        "_horizon_days": result.get("horizon_days"),
        "_note": result.get("note"),
        "default": {},
        "profiles": result["profiles"],
    }
    if result.get("horizons"):
        payload["_horizons"] = result["horizons"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return str(p)
