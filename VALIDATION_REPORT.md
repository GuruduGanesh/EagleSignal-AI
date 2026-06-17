# VALIDATION_REPORT.md

Strict expected-move / reward-risk validation for EagleSignal research candidates.
Research only — not financial advice.

## Formulas (single source of truth: `analysis/candidate_gate.py`)

```
expected_points (bullish)  = target_price - current_price
expected_points (bearish)  = current_price - target_price
expected_percent           = expected_points / current_price * 100

min_required_points        = 5  if current_price < 100 else 10
min_required_percent       = 5
final_required_points      = max(current_price * 0.05, min_required_points)

risk_points (bullish)      = current_price - stop_price
risk_points (bearish)      = stop_price - current_price
reward_risk_ratio          = expected_points / risk_points
```

A ticker is a **VALID_RESEARCH_CANDIDATE** only if ALL hold:

```
expected_points     >= final_required_points
expected_percent    >= 5
reward_risk_ratio   >= 2.0
risk_score          <= 55
confidence_score    >= 55   (tier: bullish/bearish)
opportunity_score   >= 60   (tier: bullish/bearish)
```

Strong tier additionally requires `opportunity >= 70`, `confidence >= 65`,
`risk <= 45`, and a real catalyst.

## Target rule — percentage dominates for expensive stocks

| Price | 5% of price | Point floor | **Final required points** | Bullish target must reach |
|------:|------------:|------------:|--------------------------:|--------------------------:|
| 54    | 2.70        | 5           | **5.00**                  | ≥ 59.00 |
| 80    | 4.00        | 5           | **5.00**                  | ≥ 85.00 |
| 120   | 6.00        | 10          | **10.00**                 | ≥ 130.00 |
| 340   | 17.00       | 10          | **17.00**                 | ≥ 357.00 |
| 1032  | 51.60       | 10          | **51.60**                 | ≥ 1083.60 |

The system never accepts a flat 10-point move on a high-priced stock when 5% is
larger.

## Downgrade vocabulary

`VALID_RESEARCH_CANDIDATE` → strong/plain `bullish_research_candidate` /
`bearish_research_candidate`. Otherwise:

| Validation status | Label |
|---|---|
| REJECTED | `rejected_insufficient_expected_move` · `rejected_low_reward` · `rejected_high_risk` |
| WATCHLIST | `watchlist_only` (move qualifies but conviction light) |
| NO_TRADE | `no_trade` (no directional edge / no data) |

## Targets are NEVER faked

The target is derived from the **profile-horizon Monte-Carlo forecast on real
historical returns** (5D swing / 20D long-term / 1D intraday) — the honest
expected move over the holding period. If that move does not clear the bar, the
ticker is **rejected**, not inflated. Quality over quantity.

## Sample validation (live scan, 2026-06-04, swing/5D)

| Ticker | Current | Target | Exp pts | Exp % | Req pts | R/R | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| HPE  | 53.69  | 54.34  | +0.66 | +1.22% | 5.00  | 0.24 | REJECTED · insufficient move |
| NVDA | 218.66 | 219.60 | +0.94 | +0.43% | 10.93 | 0.11 | REJECTED · insufficient move |
| MSFT | 428.05 | 427.32 | −0.73 | −0.17% | 21.40 | −0.05 | REJECTED · insufficient move |
| PLTR | 141.70 | 141.76 | +0.06 | +0.04% | 10.00 | 0.01 | NO_TRADE · no edge |

This is the **intended** behaviour: a 5%+ move in a 5-day swing window is a high
bar for large caps, so most names are correctly rejected. More VALID candidates
appear on (a) the **20-day / long-term profile** (larger honest moves), and
(b) high-volatility names. See PENDING_ITEMS.md for the horizon trade-off.

## Consistency check across tabs

The gate is computed ONCE in `predict()`; every view reads the same
`PredictionResult` fields:

- **Overview** — Live verdict / Research action = gated label.
- **Bull/Bear Verdicts** — full validation columns (status, exp pts/%, req pts, R/R, reason).
- **Trade Summary / Trade Strategy** — Bull/Bear = gated; target/stop = `p.target_price`/`p.stop_price`.
- **Options Edge** — Bull/Bear badge = gated.
- **CSV / JSON / Markdown** — include validation_status + gate fields.

Verified: Verdicts table renders 15 header columns == 15 cells/row; all four
trade tables column-consistent.

## Tests

`tests/test_candidate_gate.py` (9) + full suite **95 passed**.
