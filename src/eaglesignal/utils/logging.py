"""Structured-ish JSON logging. Never log secrets."""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def get_logger(name: str = "eaglesignal") -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        root = logging.getLogger("eaglesignal")
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        root.propagate = False
        _CONFIGURED = True
    return logging.getLogger(name if name.startswith("eaglesignal") else f"eaglesignal.{name}")
