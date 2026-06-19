"""Write-side tools — backup, prune."""

from __future__ import annotations

from typing import Any

from colony_memory_hermes.tools import _common
from colony_memory_hermes.tools._common import Tool, _info_dict, default_label


def _backup(*, documents: dict[str, str], label: str | None = None,
            prune_keep: int | None = None) -> Any:
    mem = _common.build_memory()
    info = mem.backup(documents, label=label or default_label(), prune_keep=prune_keep)
    return _info_dict(info)


def build_backup() -> Tool:
    return Tool(
        name="colony_memory_backup",
        description=(
            "Snapshot your memory to your own Colony vault. `documents` is a "
            "{filename: text} mapping — e.g. {\"MEMORY.md\": \"...\", "
            "\"goals.md\": \"...\"}. Returns the stored snapshot's metadata "
            "(snapshot_id, sha256, byte_size). The snapshot is versioned, "
            "gzip-compressed, integrity-checked and (if a signing seed is "
            "configured) ed25519-signed. This is a deliberate action — call it "
            "when your memory has meaningfully changed, not on every turn. Set "
            "`prune_keep` to also drop all but the newest N snapshots for this "
            "label afterwards (keeps you inside the 10 MB free vault tier)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "documents": {
                    "type": "object",
                    "description": (
                        "Memory to back up, as {filename: text}. Values must be "
                        "strings (UTF-8 text). At least one entry is required."
                    ),
                    "additionalProperties": {"type": "string"},
                    "minProperties": 1,
                },
                "label": {
                    "type": "string",
                    "description": (
                        "Snapshot stream name (default from COLONY_MEMORY_LABEL "
                        "or 'default'). Use separate labels for independent "
                        "memory sets, each versioned on its own timeline."
                    ),
                },
                "prune_keep": {
                    "type": "integer",
                    "description": "Keep only the newest N snapshots for this label after writing.",
                    "minimum": 1,
                },
            },
            "required": ["documents"],
            "additionalProperties": False,
        },
        invoke=_backup,
    )


def _prune(*, keep: int = 5, label: str | None = None) -> Any:
    mem = _common.build_memory()
    deleted = mem.prune(label=label or default_label(), keep=keep)
    return {"deleted": deleted, "kept": keep, "label": label or default_label()}


def build_prune() -> Tool:
    return Tool(
        name="colony_memory_prune",
        description=(
            "Delete all but the newest `keep` snapshots for a label, reclaiming "
            "vault space. Never deletes the snapshot the 'latest' pointer "
            "references. Returns how many were deleted."
        ),
        parameters={
            "type": "object",
            "properties": {
                "keep": {
                    "type": "integer",
                    "description": "Number of newest snapshots to retain (default 5).",
                    "minimum": 1,
                },
                "label": {
                    "type": "string",
                    "description": "Snapshot stream name (default from env or 'default').",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        invoke=_prune,
    )
