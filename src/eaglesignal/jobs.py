"""Scheduled research jobs with retry/status persistence.

The same function is used by the CLI, the FastAPI manual trigger, and Windows
Task Scheduler. That keeps scheduled collection and browser-triggered collection
from drifting into two different products.
"""
from __future__ import annotations

import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .alerts.dispatcher import dispatch_alerts
from .config import Settings, get_settings
from .pipeline import run_pipeline
from .refresh import run_refresh_jobs
from .reports.generator import write_reports


STATUS_FILE = "job_runs.json"
LOCK_FILE = "job_runs.lock"


def _status_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / STATUS_FILE


def load_job_status(settings: Settings | None = None) -> dict[str, Any]:
    path = _status_path(settings)
    if not path.exists():
        return {"runs": [], "latest": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"runs": [], "latest": {"status": "corrupt_status_file", "path": str(path)}}


def _save_job_status(entry: dict[str, Any], settings: Settings | None = None) -> None:
    path = _status_path(settings)
    data = load_job_status(settings)
    runs = data.get("runs", [])
    runs.append(entry)
    data = {"latest": entry, "runs": runs[-50:]}
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _lock_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / LOCK_FILE


def _acquire_lock(settings: Settings) -> Path | None:
    path = _lock_path(settings)
    try:
        path.mkdir()
        return path
    except FileExistsError:
        try:
            age_seconds = time.time() - path.stat().st_mtime
        except OSError:
            age_seconds = 0
        if age_seconds > 3 * 60 * 60:
            if path.is_dir():
                path.rmdir()
            else:
                path.unlink(missing_ok=True)
            path.mkdir()
            return path
        return None


def _release_lock(path: Path | None, settings: Settings) -> None:
    if path is None:
        return
    try:
        path.rmdir()
    except OSError:
        lock_path = _lock_path(settings)
        if lock_path.is_file():
            lock_path.unlink(missing_ok=True)


def run_research_job(
    *,
    strategy: str = "swing",
    horizon: str = "5D",
    tickers: list[str] | None = None,
    retries: int = 2,
    retry_delay_seconds: int = 60,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    started = datetime.now(timezone.utc)
    last_error = ""
    lock_fd = _acquire_lock(settings)
    if lock_fd is None:
        entry = {
            "status": "skipped_already_running",
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "strategy": strategy,
            "horizon": horizon,
            "tickers": tickers,
            "message": "Another EagleSignal collection job is already running.",
        }
        _save_job_status(entry, settings)
        return entry
    try:
        for attempt in range(1, retries + 2):
            try:
                # Run the prediction pipeline FIRST so the analysis gets a fresh
                # social/news rate-limit budget and captures live Bluesky/StockTwits
                # sentiment. The pipeline's per-ticker fetches populate the shared
                # 15-min cache; the refresh status pass that follows reuses that
                # cache instead of re-hitting (and exhausting) the same APIs.
                result = run_pipeline(strategy=strategy, horizon=horizon, tickers=tickers, settings=settings)
                refresh_result = run_refresh_jobs(settings=settings)
                written = write_reports(result, settings.reports_dir)
                alerts = dispatch_alerts(result.predictions, settings, settings.data_dir)
                entry = {
                    "status": "success",
                    "started_at": started.isoformat(),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "attempt": attempt,
                    "strategy": strategy,
                    "horizon": horizon,
                    "tickers": tickers,
                    "parallel_refresh": {
                        "status": "success",
                        "categories": refresh_result.get("ran", []),
                        "elapsed_sec": refresh_result.get("elapsed_sec"),
                        "as_of": refresh_result.get("as_of"),
                    },
                    "historical_snapshots": result.snapshots,
                    "prediction_count": len(result.predictions),
                    "reports": {name: str(path) for name, path in written.items()},
                    "alerts_fired": len(alerts),
                }
                _save_job_status(entry, settings)
                return entry
            except Exception as exc:  # retry the whole collection cycle
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt <= retries:
                    time.sleep(retry_delay_seconds)
                    continue
                entry = {
                    "status": "failed",
                    "started_at": started.isoformat(),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "attempt": attempt,
                    "strategy": strategy,
                    "horizon": horizon,
                    "tickers": tickers,
                    "error": last_error,
                    "traceback": traceback.format_exc(limit=8),
                }
                _save_job_status(entry, settings)
                return entry
    finally:
        _release_lock(lock_fd, settings)


def run_tuning_job(
    *,
    profiles: list[str] | None = None,
    horizon_days: int = 5,
    period: str = "2y",
    step: int = 5,
    max_tickers: int = 25,
    dry_run: bool = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Scheduled ADR-002 weight tuning job.

    This is intentionally separate from the scan lock: a retune can be scheduled
    weekly while regular refreshes keep running. The tuner itself only replays
    price-derived engines, avoiding lookahead until full source snapshots mature.
    """
    settings = settings or get_settings()
    started = datetime.now(timezone.utc)
    try:
        from .config import load_watchlist
        from .tuning import tune_multi_horizon, write_fitted

        assets, _ = load_watchlist()
        tickers = [a.ticker for a in assets]
        if max_tickers and max_tickers > 0:
            tickers = tickers[:max_tickers]
        profiles = profiles or ["swing", "intraday", "options_buying"]
        # Each profile is tuned at its natural horizon (§2.3): intraday=1D,
        # swing-family=5D, long_term/index=20D. ``horizon_days`` is the fallback
        # horizon for any profile without an explicit mapping.
        result = tune_multi_horizon(
            profiles, tickers, period=period, step=step,
            default_horizon_days=horizon_days,
        )
        output_path = None if dry_run else write_fitted(result)
        entry = {
            "status": "success",
            "job_type": "weekly_auto_retune",
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "profiles": profiles,
            "horizon_days": horizon_days,
            "horizons": result.get("horizons"),
            "period": period,
            "step": step,
            "max_tickers": max_tickers,
            "universe_size": result.get("universe_size"),
            "components": result.get("components_by_horizon") or result.get("components"),
            "output_path": output_path,
            "dry_run": dry_run,
            "note": result.get("note"),
        }
    except Exception as exc:
        entry = {
            "status": "failed",
            "job_type": "weekly_auto_retune",
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(limit=8),
        }
    _save_job_status(entry, settings)
    return entry
