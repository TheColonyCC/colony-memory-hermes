"""Lifecycle-hook tests + the full Hermes-contract smoke test."""

from __future__ import annotations

from pathlib import Path

import pytest

from colony_memory_hermes import lifecycle, register
from colony_memory_hermes.tools import _common


class FakeHarness:
    """Implements the slice of Hermes' PluginContext we use: register_tool + register_hook."""

    def __init__(self) -> None:
        self.tools: list[dict] = []
        self.hooks: list[tuple[str, object]] = []

    def register_tool(self, **kwargs) -> None:
        self.tools.append(kwargs)

    def register_hook(self, hook_name: str, callback) -> None:
        self.hooks.append((hook_name, callback))


# --- CI smoke: load exactly as Hermes does -----------------------------------

def test_register_wires_tools_and_lifecycle_hooks() -> None:
    """The smoke test that would have caught a broken plugin contract: loading
    via register(ctx) must register all six tools AND the lifecycle hooks."""
    ctx = FakeHarness()
    register(ctx)

    assert [t["name"] for t in ctx.tools] == [
        "colony_memory_restore", "colony_memory_backup", "colony_memory_list_snapshots",
        "colony_memory_latest", "colony_memory_status", "colony_memory_prune",
    ]
    hook_names = [h for h, _ in ctx.hooks]
    assert hook_names == ["on_session_end", "on_session_finalize", "on_session_reset"]
    # end + finalize share the backup callback; reset gets restore.
    by = {h: cb for h, cb in ctx.hooks}
    assert by["on_session_end"] is by["on_session_finalize"] is lifecycle.backup_on_end
    assert by["on_session_reset"] is lifecycle.restore_on_reset


def test_register_lifecycle_noop_without_register_hook() -> None:
    assert lifecycle.register_lifecycle(object()) == []


# --- backup_on_end -----------------------------------------------------------

@pytest.fixture
def reset_guards(monkeypatch):
    monkeypatch.setattr(lifecycle, "_state", {"restored": False, "last_backup_monotonic": 0.0})


def test_backup_on_end_disabled_is_noop(monkeypatch, memory, tmp_path, reset_guards):
    monkeypatch.delenv(_common.AUTO_BACKUP_ENV_VAR, raising=False)
    monkeypatch.setenv(_common.DIR_ENV_VAR, str(tmp_path))
    (tmp_path / "MEMORY.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(_common, "build_memory", lambda: memory)
    lifecycle.backup_on_end()
    assert memory.list_snapshots() == []  # nothing written


def test_backup_on_end_snapshots_dir(monkeypatch, memory, tmp_path, reset_guards):
    monkeypatch.setenv(_common.AUTO_BACKUP_ENV_VAR, "1")
    monkeypatch.setenv(_common.DIR_ENV_VAR, str(tmp_path))
    (tmp_path / "MEMORY.md").write_text("# state\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "n.txt").write_text("note", encoding="utf-8")
    monkeypatch.setattr(_common, "build_memory", lambda: memory)

    lifecycle.backup_on_end()
    snaps = memory.list_snapshots()
    assert len(snaps) == 1
    assert sorted(snaps[0].doc_names) == ["MEMORY.md", "sub/n.txt"]

    # Dedup window: an immediate second fire (end + finalize) does not double-write.
    lifecycle.backup_on_end()
    assert len(memory.list_snapshots()) == 1


def test_backup_on_end_empty_dir_noop(monkeypatch, memory, tmp_path, reset_guards):
    monkeypatch.setenv(_common.AUTO_BACKUP_ENV_VAR, "1")
    monkeypatch.setenv(_common.DIR_ENV_VAR, str(tmp_path))  # no text files
    monkeypatch.setattr(_common, "build_memory", lambda: memory)
    lifecycle.backup_on_end()
    assert memory.list_snapshots() == []


def test_backup_on_end_survives_errors(monkeypatch, tmp_path, reset_guards):
    # A backup failure must never propagate out of the hook.
    monkeypatch.setenv(_common.AUTO_BACKUP_ENV_VAR, "1")
    monkeypatch.setenv(_common.DIR_ENV_VAR, str(tmp_path))
    (tmp_path / "a.md").write_text("x", encoding="utf-8")

    def boom():
        raise RuntimeError("no key")

    monkeypatch.setattr(_common, "build_memory", boom)
    lifecycle.backup_on_end()  # must not raise


# --- restore_on_reset --------------------------------------------------------

def test_restore_on_reset_into_empty_dir(monkeypatch, memory, tmp_path, reset_guards):
    # Seed the vault with a snapshot, then restore into a fresh dir.
    memory.backup({"MEMORY.md": "restored!", "g.md": "goals"}, label="default")
    out = tmp_path / "mem"
    monkeypatch.setenv(_common.AUTO_RESTORE_ENV_VAR, "1")
    monkeypatch.setenv(_common.DIR_ENV_VAR, str(out))
    monkeypatch.setattr(_common, "build_memory", lambda: memory)

    lifecycle.restore_on_reset()
    assert (out / "MEMORY.md").read_text(encoding="utf-8") == "restored!"
    assert (out / "g.md").read_text(encoding="utf-8") == "goals"


def test_restore_on_reset_skips_populated_dir(monkeypatch, memory, tmp_path, reset_guards):
    memory.backup({"MEMORY.md": "from-vault"}, label="default")
    out = tmp_path / "mem"
    out.mkdir()
    (out / "MEMORY.md").write_text("local-live", encoding="utf-8")  # live memory present
    monkeypatch.setenv(_common.AUTO_RESTORE_ENV_VAR, "1")
    monkeypatch.setenv(_common.DIR_ENV_VAR, str(out))
    monkeypatch.setattr(_common, "build_memory", lambda: memory)

    lifecycle.restore_on_reset()
    # Local memory is never clobbered.
    assert (out / "MEMORY.md").read_text(encoding="utf-8") == "local-live"


def test_restore_on_reset_once_per_process(monkeypatch, memory, tmp_path, reset_guards):
    memory.backup({"MEMORY.md": "v"}, label="default")
    out = tmp_path / "mem"
    monkeypatch.setenv(_common.AUTO_RESTORE_ENV_VAR, "1")
    monkeypatch.setenv(_common.DIR_ENV_VAR, str(out))
    monkeypatch.setattr(_common, "build_memory", lambda: memory)

    lifecycle.restore_on_reset()
    assert (out / "MEMORY.md").exists()
    # Wipe and fire again — guard means no second restore this process.
    (out / "MEMORY.md").unlink()
    lifecycle.restore_on_reset()
    assert not (out / "MEMORY.md").exists()


def test_restore_on_reset_disabled_is_noop(monkeypatch, memory, tmp_path, reset_guards):
    memory.backup({"MEMORY.md": "v"}, label="default")
    out = tmp_path / "mem"
    monkeypatch.delenv(_common.AUTO_RESTORE_ENV_VAR, raising=False)
    monkeypatch.setenv(_common.DIR_ENV_VAR, str(out))
    monkeypatch.setattr(_common, "build_memory", lambda: memory)
    lifecycle.restore_on_reset()
    assert not out.exists()


def test_backup_on_end_enabled_without_dir_is_noop(monkeypatch, reset_guards):
    monkeypatch.setenv(_common.AUTO_BACKUP_ENV_VAR, "1")
    monkeypatch.delenv(_common.DIR_ENV_VAR, raising=False)
    lifecycle.backup_on_end()  # warns + returns, no exception


def test_restore_on_reset_enabled_without_dir_is_noop(monkeypatch, reset_guards):
    monkeypatch.setenv(_common.AUTO_RESTORE_ENV_VAR, "1")
    monkeypatch.delenv(_common.DIR_ENV_VAR, raising=False)
    lifecycle.restore_on_reset()  # warns, sets guard, returns


def test_restore_on_reset_no_snapshot_is_quiet(monkeypatch, memory, tmp_path, reset_guards):
    # Empty vault → restore finds nothing → non-fatal, nothing written.
    out = tmp_path / "mem"
    monkeypatch.setenv(_common.AUTO_RESTORE_ENV_VAR, "1")
    monkeypatch.setenv(_common.DIR_ENV_VAR, str(out))
    monkeypatch.setattr(_common, "build_memory", lambda: memory)
    lifecycle.restore_on_reset()
    assert not any(out.glob("*")) if out.exists() else True


def test_collect_dir_documents_skips_unreadable(monkeypatch, tmp_path):
    (tmp_path / "ok.md").write_text("fine", encoding="utf-8")
    (tmp_path / "bad.md").write_text("x", encoding="utf-8")
    real = Path.read_text

    def flaky(self, *a, **k):
        if self.name == "bad.md":
            raise OSError("boom")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", flaky)
    docs = lifecycle._collect_dir_documents(tmp_path)
    assert docs == {"ok.md": "fine"}
