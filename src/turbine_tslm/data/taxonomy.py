"""Alarm message -> subsystem class, from ``taxonomy.yaml`` (case-insensitive substring, first pattern wins)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

TAXONOMY_PATH = Path(__file__).with_name("taxonomy.yaml")
UNMAPPED = "unmapped"


@lru_cache(maxsize=1)
def load_taxonomy() -> list[tuple[str, str, tuple[str, ...]]]:
    """Ordered ``(class, kind, patterns)`` triples; kind is ``fault`` | ``benign`` | ``context``."""
    spec = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))["classes"]
    return [(cls, v["kind"], tuple(p.lower() for p in v["patterns"])) for cls, v in spec.items()]


def fault_classes() -> tuple[str, ...]:
    return tuple(cls for cls, kind, _ in load_taxonomy() if kind == "fault")


@lru_cache(maxsize=4096)
def classify(message: str) -> tuple[str, str]:
    """Return ``(class, kind)`` for a status-log message; ``("unmapped", "unknown")`` when nothing matches."""
    m = (message or "").lower()
    for cls, kind, patterns in load_taxonomy():
        if any(p in m for p in patterns):
            return cls, kind
    return UNMAPPED, "unknown"
