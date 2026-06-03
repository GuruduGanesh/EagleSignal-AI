"""Command-line entrypoint. CLI-first MVP (lesson from investdaytip).

Examples:
  python -m eaglesignal run
  python -m eaglesignal run --strategy options_buying --horizon 5D --tickers NVDA,AMD
  python -m eaglesignal backtest --ticker AAPL
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __product__, __version__
from .alerts.dispatcher import dispatch_alerts
from .backtest import run_backtest
from .config import get_settings
from .jobs import load_job_status, run_research_job, run_tuning_job
from .pipeline import run_pipeline
from .reports.generator import write_reports


def _cmd_run(args: argparse.Namespace) -> int:
    settings = get_settings()
    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else None
    result = run_pipeline(strategy=args.strategy, horizon=args.horizon, tickers=tickers, settings=settings)
    written = write_reports(result, settings.reports_dir)
    fired = dispatch_alerts(result.predictions, settings, settings.data_dir)

    print(f"\n{__product__} v{__version__} — {len(result.predictions)} signals "
          f"(strategy={args.strategy}, horizon={args.horizon})")
    for p in result.predictions[: args.top]:
        print(f"  {p.ticker:6s} {p.direction.value:20s} opp={p.opportunity_score:5.1f} "
              f"conf={p.confidence_score:5.1f} risk={p.risk_score:5.1f} [{p.severity.value}]")
    print("\nArtifacts:")
    for name, path in written.items():
        print(f"  {name}: {path}")
    print(f"\nAlerts fired: {len(fired)}")
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    stats = run_backtest(args.ticker, horizon_days=args.horizon_days)
    print(f"\nWalk-forward backtest — {args.ticker} (horizon {args.horizon_days}D)")
    for k, v in stats.items():
        print(f"  {k:22s}: {v}")
    return 0


def _cmd_advise(args: argparse.Namespace) -> int:
    from .advisor import advise, parse_portfolio

    res = advise(args.message, settings=get_settings(), portfolio=parse_portfolio(args.portfolio))
    print(f"\n{__product__} advisor [{res['backend']}, {res['used_signals']} signals] — research only\n")
    print(res["answer"])
    return 0


def _cmd_markets(_args: argparse.Namespace) -> int:
    from .ingestion.global_markets import fetch_global_indexes

    snap = fetch_global_indexes()
    print(f"\nGlobal markets — {snap.regime_note}\n")
    for gi in snap.indexes.values():
        chg = f"{gi.day_change_pct:+.2f}%" if gi.day_change_pct is not None else "n/a"
        print(f"  {gi.region:7s} {gi.name:16s} {gi.symbol:12s} last={gi.last} ({chg})")
    return 0


def _cmd_collect(args: argparse.Namespace) -> int:
    settings = get_settings()
    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
    result = run_research_job(
        strategy=args.strategy,
        horizon=args.horizon,
        tickers=tickers,
        retries=args.retries,
        retry_delay_seconds=args.retry_delay_seconds,
        settings=settings,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "success" else 1


def _cmd_job_status(_args: argparse.Namespace) -> int:
    print(json.dumps(load_job_status(get_settings()), indent=2, default=str))
    return 0


def _cmd_tune(args: argparse.Namespace) -> int:
    from .config import load_watchlist
    from .tuning import REPLAYABLE, tune, write_fitted

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
    else:
        assets, _ = load_watchlist()
        tickers = [a.ticker for a in assets]
    if args.max_tickers:
        tickers = tickers[: args.max_tickers]
    profiles = [p.strip() for p in args.profiles.split(",")]

    print(f"\nADR-002 weight tuning — {len(tickers)} tickers, profiles={profiles}, "
          f"horizon {args.horizon_days}D, step {args.step} (walk-forward, no lookahead)\n")
    result = tune(profiles, tickers, horizon_days=args.horizon_days,
                  period=args.period, step=args.step)

    print(f"Universe actually replayed: {result['universe_size']} tickers")
    print("\nMeasured edge per replayable component (pooled):")
    print(f"  {'component':26s} {'samples':>8s} {'dir.bars':>9s} {'accuracy':>9s} {'IC':>7s} {'skill':>7s}")
    for c in REPLAYABLE:
        m = result["components"][c]
        acc = "n/a" if m["accuracy"] is None else f"{m['accuracy']:.3f}"
        ic = "n/a" if m["ic"] is None else f"{m['ic']:+.3f}"
        print(f"  {c:26s} {m['samples']:>8d} {m['directional_bars']:>9d} {acc:>9s} {ic:>7s} {m['skill']:>7.4f}")

    print("\nFitted weights (%, prior → fitted for replayable components):")
    from .config import load_weights
    for p in profiles:
        prior = load_weights(p, path="config/weights.yml")
        print(f"\n  [{p}]")
        for c in REPLAYABLE:
            print(f"    {c:26s} {100 * prior.get(c, 0):6.2f} → {result['profiles'][p].get(c, 0):6.2f}")

    if args.dry_run:
        print("\n--dry-run: not written. Re-run without --dry-run to save config/weights.fitted.yml.")
    else:
        path = write_fitted(result)
        print(f"\nWrote {path}")
        print("The engine now prefers these weights (set EAGLESIGNAL_USE_FITTED=0 to ignore).")
    return 0


def _cmd_auto_tune(args: argparse.Namespace) -> int:
    profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
    result = run_tuning_job(
        profiles=profiles,
        horizon_days=args.horizon_days,
        period=args.period,
        step=args.step,
        max_tickers=args.max_tickers,
        dry_run=args.dry_run,
        settings=get_settings(),
    )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "success" else 1


def main(argv: list[str] | None = None) -> int:
    # Force UTF-8 stdout so reports/answers with unicode never crash on Windows consoles.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass
    parser = argparse.ArgumentParser(prog="eaglesignal", description=f"{__product__} — research only, not financial advice.")
    parser.add_argument("--version", action="version", version=f"{__product__} v{__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the full prediction pipeline and write reports.")
    run_p.add_argument("--strategy", default="swing",
                       choices=["intraday", "swing", "earnings", "long_term", "options_buying", "options_selling", "index_trend"])
    run_p.add_argument("--horizon", default="5D", choices=["intraday", "1D", "5D", "20D"])
    run_p.add_argument("--tickers", default=None, help="Comma-separated tickers (overrides watchlist).")
    run_p.add_argument("--top", type=int, default=10, help="How many signals to print.")
    run_p.set_defaults(func=_cmd_run)

    bt_p = sub.add_parser("backtest", help="Walk-forward backtest of the technical signal.")
    bt_p.add_argument("--ticker", required=True)
    bt_p.add_argument("--horizon-days", type=int, default=5, dest="horizon_days")
    bt_p.set_defaults(func=_cmd_backtest)

    ad_p = sub.add_parser("advise", help="Ask the AI advisor about the latest signals (research only).")
    ad_p.add_argument("message", help="Your question, e.g. 'what should I buy?'")
    ad_p.add_argument("--portfolio", default=None, help="Holdings, e.g. 'AAPL:10, MSFT:5'")
    ad_p.set_defaults(func=_cmd_advise)

    mk_p = sub.add_parser("markets", help="Show live US/Europe/Asia index levels and global regime.")
    mk_p.set_defaults(func=_cmd_markets)

    collect_p = sub.add_parser("collect", help="Scheduled/manual collection job with retry and report generation.")
    collect_p.add_argument("--strategy", default="swing",
                           choices=["intraday", "swing", "earnings", "long_term", "options_buying", "options_selling", "index_trend"])
    collect_p.add_argument("--horizon", default="5D", choices=["intraday", "1D", "5D", "20D"])
    collect_p.add_argument("--tickers", default=None, help="Comma-separated tickers (overrides watchlist).")
    collect_p.add_argument("--retries", type=int, default=2)
    collect_p.add_argument("--retry-delay-seconds", type=int, default=60, dest="retry_delay_seconds")
    collect_p.set_defaults(func=_cmd_collect)

    status_p = sub.add_parser("job-status", help="Show latest scheduled/manual collection job status.")
    status_p.set_defaults(func=_cmd_job_status)

    tune_p = sub.add_parser("tune", help="ADR-002: backtest-fit scoring weights (walk-forward, no lookahead).")
    tune_p.add_argument("--tickers", default=None, help="Comma-separated tickers (default: full watchlist).")
    tune_p.add_argument("--max-tickers", type=int, default=20, dest="max_tickers",
                        help="Cap universe size for runtime (0 = no cap).")
    tune_p.add_argument("--profiles", default="swing,intraday,options_buying",
                        help="Comma-separated strategy profiles to fit.")
    tune_p.add_argument("--horizon-days", type=int, default=5, dest="horizon_days")
    tune_p.add_argument("--step", type=int, default=5, help="Evaluate every Nth bar (lower = slower, more samples).")
    tune_p.add_argument("--period", default="2y", help="History window to replay (yfinance period).")
    tune_p.add_argument("--dry-run", action="store_true", help="Print results without writing weights.fitted.yml.")
    tune_p.set_defaults(func=_cmd_tune)

    auto_tune_p = sub.add_parser("auto-tune", help="Scheduled weekly retune job with status persistence.")
    auto_tune_p.add_argument("--max-tickers", type=int, default=25, dest="max_tickers")
    auto_tune_p.add_argument("--profiles", default="swing,intraday,options_buying")
    auto_tune_p.add_argument("--horizon-days", type=int, default=5, dest="horizon_days")
    auto_tune_p.add_argument("--step", type=int, default=5)
    auto_tune_p.add_argument("--period", default="2y")
    auto_tune_p.add_argument("--dry-run", action="store_true")
    auto_tune_p.set_defaults(func=_cmd_auto_tune)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
