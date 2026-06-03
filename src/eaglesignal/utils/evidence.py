"""SKILL-003 Evidence Store Writer.

Stores every claim used by the system. No final reasoning is allowed without
evidence. In the MVP this is an in-memory + JSONL-on-disk store.
"""
from __future__ import annotations

import hashlib
import json
from threading import RLock
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..schemas import Evidence, utcnow
from .freshness import freshness_score, reliability_score


class EvidenceStore:
    def __init__(self) -> None:
        self._items: dict[str, Evidence] = {}
        self._lock = RLock()

    def add(
        self,
        *,
        entity: str,
        source_name: str,
        source_type: str,
        claim: str,
        url: Optional[str] = None,
        published_at: Optional[datetime] = None,
        raw_excerpt: str = "",
        polarity: float = 0.0,
        data_type: str = "news",
    ) -> Evidence:
        fresh, _age = freshness_score(published_at, data_type)
        h = hashlib.sha1(
            f"{entity}|{source_name}|{claim}|{url}".encode("utf-8")
        ).hexdigest()[:16]
        ev = Evidence(
            evidence_id=h,
            entity=entity,
            source_name=source_name,
            source_type=source_type,
            url=url,
            retrieved_at=utcnow(),
            published_at=published_at,
            claim=claim,
            raw_excerpt=raw_excerpt[:2000],
            polarity=max(-1.0, min(1.0, polarity)),
            reliability_score=reliability_score(source_type),
            freshness_score=fresh,
        )
        with self._lock:
            self._items[ev.evidence_id] = ev  # dedupe by content hash
        return ev

    def all(self) -> list[Evidence]:
        with self._lock:
            return list(self._items.values())

    def for_entity(self, ticker: str) -> list[Evidence]:
        with self._lock:
            return [e for e in self._items.values() if e.entity == ticker]

    def get(self, evidence_id: str) -> Optional[Evidence]:
        with self._lock:
            return self._items.get(evidence_id)

    def dump_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            with self._lock:
                items = list(self._items.values())
            for ev in items:
                fh.write(ev.model_dump_json() + "\n")
