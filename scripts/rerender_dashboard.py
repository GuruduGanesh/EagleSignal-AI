"""Re-render dashboard.html from an existing scan's signals.json + audit_log.jsonl.

Lets us pick up report-template/JS changes (e.g. Manual Trade Journal edit/delete
buttons) without paying for a full live re-scan. Macro/government sections are
markdown-only, so the HTML dashboard is fully reconstructable from these two files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from eaglesignal.pipeline import RunResult
from eaglesignal.reports.generator import render_html
from eaglesignal.schemas import Evidence, PredictionResult
from eaglesignal.utils.evidence import EvidenceStore


def rebuild(day_dir: Path) -> Path:
    signals = json.loads((day_dir / "signals.json").read_text(encoding="utf-8"))
    predictions = [PredictionResult.model_validate(d) for d in signals]

    store = EvidenceStore()
    audit = day_dir / "audit_log.jsonl"
    if audit.exists():
        for line in audit.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            ev = Evidence.model_validate_json(line)
            store._items[ev.evidence_id] = ev

    result = RunResult(predictions=predictions, evidence=store,
                       strategy="swing", horizon="5D")
    html = render_html(result)
    out = day_dir / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    day = sys.argv[1] if len(sys.argv) > 1 else "2026-06-01"
    base = Path(__file__).resolve().parent.parent / "reports" / day
    out = rebuild(base)
    print(f"Re-rendered {out} ({out.stat().st_size} bytes) from {len(json.loads((base/'signals.json').read_text(encoding='utf-8')))} signals")
