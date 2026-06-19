"""Read-side tools — restore, list_snapshots, latest, status."""

from __future__ import annotations

from typing import Any

from colony_memory_hermes.tools import _common
from colony_memory_hermes.tools._common import Tool, _info_dict, default_label


def _restore(*, label: str | None = None, snapshot_id: str | None = None,
             verify: bool = True) -> Any:
    mem = _common.build_memory()
    docs = mem.restore(label=label or default_label(), snapshot_id=snapshot_id, verify=verify)
    return {"documents": docs}


def build_restore() -> Tool:
    return Tool(
        name="colony_memory_restore",
        description=(
            "Restore your memory from the vault — the latest snapshot by "
            "default, or a specific `snapshot_id`. Returns {documents: "
            "{filename: text}}. Call this on boot to recover state from a "
            "previous run. The plaintext sha256 is always checked; if the "
            "snapshot is signed, its ed25519 signature is verified too "
            "(unless `verify` is false). Errors if there's nothing to restore."
        ),
        parameters={
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Snapshot stream name (default from env or 'default').",
                },
                "snapshot_id": {
                    "type": "string",
                    "description": "Restore this exact snapshot instead of the latest.",
                },
                "verify": {
                    "type": "boolean",
                    "description": "Verify the ed25519 signature when present (default true).",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        invoke=_restore,
    )


def _list_snapshots(*, label: str | None = None) -> Any:
    mem = _common.build_memory()
    snaps = mem.list_snapshots(label=label)
    return {"snapshots": [_info_dict(s) for s in snaps]}


def build_list_snapshots() -> Tool:
    return Tool(
        name="colony_memory_list_snapshots",
        description=(
            "List your stored snapshots, newest first, optionally filtered to "
            "one `label`. Returns metadata only (no payload) — snapshot_id, "
            "created_at, doc_names, byte_size, signed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Only list snapshots for this label (omit for all).",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        invoke=_list_snapshots,
    )


def _latest(*, label: str | None = None) -> Any:
    mem = _common.build_memory()
    info = mem.latest(label=label or default_label())
    return {"latest": _info_dict(info) if info is not None else None}


def build_latest() -> Tool:
    return Tool(
        name="colony_memory_latest",
        description=(
            "Return metadata for the most recent snapshot of a label (what "
            "`restore` would load), or null if none exists. Cheap freshness "
            "check before deciding whether to back up again."
        ),
        parameters={
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Snapshot stream name (default from env or 'default').",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        invoke=_latest,
    )


def _status() -> Any:
    mem = _common.build_memory()
    return mem.status()


def build_status() -> Tool:
    return Tool(
        name="colony_memory_status",
        description=(
            "Report your vault quota: quota_bytes, used_bytes, available_bytes, "
            "file_count. The free tier is 10 MB total, 1 MB per file; snapshots "
            "are gzipped so this stretches a long way. Check before a large "
            "backup."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        invoke=_status,
    )
