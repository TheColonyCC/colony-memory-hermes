"""Typed tool surface for the Hermes harness.

Six tools as of v0.1:

Write side:

- ``colony_memory_backup`` — snapshot {filename: text} to the vault
- ``colony_memory_prune`` — drop all but the newest N snapshots

Read side:

- ``colony_memory_restore`` — load the latest (or a specific) snapshot
- ``colony_memory_list_snapshots`` — versions, newest first (metadata only)
- ``colony_memory_latest`` — metadata for the most recent snapshot
- ``colony_memory_status`` — vault quota

Every tool is a dataclass with ``name``, ``description``, a JSON-schema
``parameters`` block, and an ``invoke`` that builds the underlying
``colony_memory.ColonyMemory`` call. All call paths go through
``ColonyMemory`` — no reach-through to the raw SDK, no leaking the api_key.
"""

from __future__ import annotations

from colony_memory_hermes.tools._common import Tool
from colony_memory_hermes.tools.backup import build_backup, build_prune
from colony_memory_hermes.tools.restore import (
    build_latest,
    build_list_snapshots,
    build_restore,
    build_status,
)


def build_all() -> list[Tool]:
    """Return the v0.1 tool surface in stable order.

    Restore leads (boot-time recovery is the highest-value read), then
    backup (the core write), then the listing/quota helpers.
    """
    return [
        build_restore(),
        build_backup(),
        build_list_snapshots(),
        build_latest(),
        build_status(),
        build_prune(),
    ]


__all__ = ["Tool", "build_all"]
