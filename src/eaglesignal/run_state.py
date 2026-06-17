"""Resumable run-state checkpointing (SKILL-163).

Persists ``run_state.json`` so a scan that is interrupted by a rate limit,
timeout, network failure, or crash can be diagnosed and resumed without
restarting from scratch. Progress is written after EVERY ticker so the last
good state survives an abrupt kill.

The pipeline degrades gracefully per ticker already (one failure never aborts the
run); this adds durable visibility + a retry list for the failed names.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Exponential backoff schedule for rate limits / transient provider errors.
BACKOFF_SCHEDULE_SECONDS = [30, 60, 120, 300]


def backoff_seconds(attempt: int) -> float:
    """Seconds to wait before retry ``attempt`` (1-based): 30, 60, 120, 300, …"""
    idx = max(0, min(attempt - 1, len(BACKOFF_SCHEDULE_SECONDS) - 1))
    return float(BACKOFF_SCHEDULE_SECONDS[idx])


@dataclass
class RunState:
    path: Path
    run_id: str
    start_time: str
    strategy: str = "swing"
    horizon: str = "5D"
    current_stage: str = "init"
    last_updated: str = ""
    pending_tickers: list[str] = field(default_factory=list)
    completed_tickers: list[str] = field(default_factory=list)
    failed_tickers: list[str] = field(default_factory=list)
    skipped_tickers: list[str] = field(default_factory=list)
    last_successful_ticker: Optional[str] = None
    retry_count: dict = field(default_factory=dict)
    error_message: Optional[str] = None
    resume_from_here: bool = True
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "start_time": self.start_time,
            "last_updated": self.last_updated,
            "strategy": self.strategy,
            "horizon": self.horizon,
            "current_stage": self.current_stage,
            "pending_tickers": self.pending_tickers,
            "completed_tickers": self.completed_tickers,
            "failed_tickers": self.failed_tickers,
            "skipped_tickers": self.skipped_tickers,
            "last_successful_ticker": self.last_successful_ticker,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "resume_from_here": self.resume_from_here,
            "counts": {
                "pending": len(self.pending_tickers),
                "completed": len(self.completed_tickers),
                "failed": len(self.failed_tickers),
                "skipped": len(self.skipped_tickers),
            },
        }

    def _save(self) -> None:
        """Atomic write (temp file + replace) so a crash never truncates state."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.to_dict(), fh, indent=2, default=str)
            os.replace(tmp, self.path)
        except Exception:
            pass  # checkpointing must never break the run

    def stage(self, name: str, now: str) -> None:
        with self._lock:
            self.current_stage = name
            self.last_updated = now
            self._save()

    def mark_completed(self, ticker: str, now: str) -> None:
        with self._lock:
            if ticker in self.pending_tickers:
                self.pending_tickers.remove(ticker)
            if ticker not in self.completed_tickers:
                self.completed_tickers.append(ticker)
            self.last_successful_ticker = ticker
            self.last_updated = now
            self._save()

    def mark_failed(self, ticker: str, now: str, error: str = "") -> None:
        with self._lock:
            if ticker in self.pending_tickers:
                self.pending_tickers.remove(ticker)
            if ticker not in self.failed_tickers:
                self.failed_tickers.append(ticker)
            self.error_message = (error or "")[:300]
            self.last_updated = now
            self._save()

    def bump_retry(self, ticker: str) -> int:
        with self._lock:
            n = int(self.retry_count.get(ticker, 0)) + 1
            self.retry_count[ticker] = n
            return n

    def finish(self, now: str) -> None:
        with self._lock:
            self.current_stage = "complete"
            self.resume_from_here = False
            self.last_updated = now
            self._save()


def state_path(data_dir) -> Path:
    return Path(data_dir) / "run_state.json"


def load_state(data_dir) -> Optional[dict]:
    """Read a prior run_state.json (for resume / inspection). None if absent."""
    p = state_path(data_dir)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def new_run_state(data_dir, run_id: str, start_time: str, tickers: list[str],
                  strategy: str, horizon: str) -> RunState:
    rs = RunState(
        path=state_path(data_dir), run_id=run_id, start_time=start_time,
        strategy=strategy, horizon=horizon, last_updated=start_time,
        pending_tickers=list(tickers),
    )
    rs._save()
    return rs
