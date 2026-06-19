"""Opt-in automatic backup/restore wired into Hermes session lifecycle hooks.

What this Hermes actually fires (verified against the runtime, not just
``VALID_HOOKS``): ``on_session_end`` and ``on_session_finalize`` (session
ending / process shutdown) and ``on_session_reset`` (a new session begins).
Notably it does **not** fire ``on_session_start``, so there is no clean
"first boot" hook — restore is therefore best-effort on ``on_session_reset``
(once, only if local memory is empty) and the deterministic path is the
``colony-memory-hermes restore --to <dir>`` CLI in your boot script.

All callbacks are defensive: a backup/restore failure must never break the
agent's session, so everything is wrapped and logged, never raised.

Enable with env: ``COLONY_MEMORY_DIR`` (the memory dir) plus
``COLONY_MEMORY_AUTO_BACKUP=1`` and/or ``COLONY_MEMORY_AUTO_RESTORE=1``.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from colony_memory_hermes.tools import _common

logger = logging.getLogger("colony_memory_hermes.lifecycle")

#: Process-lifetime guards (a dict so callbacks mutate state without `global`).
_state = {"restored": False, "last_backup_monotonic": 0.0}
#: Collapse the on_session_end + on_session_finalize double-fire at shutdown.
_BACKUP_DEDUP_WINDOW_SEC = 10.0


def _collect_dir_documents(directory: Path) -> dict[str, str]:
    """{relative-path: text} for the text files under *directory* (no raise)."""
    docs: dict[str, str] = {}
    if not directory.is_dir():
        return docs
    for child in sorted(directory.rglob("*")):
        if child.is_file() and child.suffix.lower() in _common.TEXT_SUFFIXES:
            try:
                docs[str(child.relative_to(directory))] = child.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
    return docs


def _dir_has_text(directory: Path) -> bool:
    return bool(_collect_dir_documents(directory))


def backup_on_end(**_kwargs: object) -> None:
    """Snapshot COLONY_MEMORY_DIR to the vault when a session ends.

    Registered on both ``on_session_end`` and ``on_session_finalize``; a short
    dedup window prevents a double-write when both fire on the same shutdown.
    """
    if not _common.auto_backup_enabled():
        return
    directory = _common.memory_dir()
    if not directory:
        logger.warning("auto-backup enabled but %s is unset — skipping", _common.DIR_ENV_VAR)
        return
    now = time.monotonic()
    if now - _state["last_backup_monotonic"] < _BACKUP_DEDUP_WINDOW_SEC:
        return
    try:
        docs = _collect_dir_documents(Path(directory).expanduser())
        if not docs:
            return  # nothing to back up
        info = _common.build_memory().backup(
            docs, label=_common.default_label(), prune_keep=_common.auto_prune_keep(),
        )
        _state["last_backup_monotonic"] = now
        logger.info("auto-backup: snapshot %s (%d docs)", info.snapshot_id, len(docs))
    except Exception as exc:  # never break the session on a backup error
        logger.warning("auto-backup failed: %s", exc)


def restore_on_reset(**_kwargs: object) -> None:
    """Restore the latest snapshot into COLONY_MEMORY_DIR — once, if dir empty.

    Best-effort "restore on (re)start": only acts the first time per process and
    only when the local dir has no text files, so it can never clobber memory
    the running agent already holds. For a guaranteed restore-on-boot, run
    ``colony-memory-hermes restore --to <dir>`` before launching the agent.
    """
    if _state["restored"] or not _common.auto_restore_enabled():
        return
    directory = _common.memory_dir()
    if not directory:
        logger.warning("auto-restore enabled but %s is unset — skipping", _common.DIR_ENV_VAR)
        _state["restored"] = True
        return
    _state["restored"] = True
    try:
        out = Path(directory).expanduser()
        if _dir_has_text(out):
            logger.info("auto-restore: %s already has memory — leaving it untouched", directory)
            return
        mem = _common.build_memory()
        docs = mem.restore(label=_common.default_label())
        out.mkdir(parents=True, exist_ok=True)
        for name, text in docs.items():
            dest = out / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
        logger.info("auto-restore: wrote %d doc(s) into %s", len(docs), directory)
    except Exception as exc:  # a missing snapshot / network error is non-fatal
        logger.info("auto-restore: nothing restored (%s)", exc)


def register_lifecycle(ctx: object) -> list[str]:
    """Register the lifecycle hooks if the harness supports ``register_hook``.

    Returns the hook names registered (empty for a non-Hermes ctx / in tests).
    """
    register_hook = getattr(ctx, "register_hook", None)
    if not callable(register_hook):
        return []
    registered: list[str] = []
    # Backup when the session ends (and on full shutdown); dedup-guarded.
    for hook in ("on_session_end", "on_session_finalize"):
        register_hook(hook, backup_on_end)
        registered.append(hook)
    # Best-effort restore when a session (re)starts — no on_session_start fires.
    register_hook("on_session_reset", restore_on_reset)
    registered.append("on_session_reset")
    return registered
