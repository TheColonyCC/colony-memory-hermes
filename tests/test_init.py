"""Tests for the package init — git-clone shim + dependency parsing."""

from __future__ import annotations

import sys

import colony_memory_hermes as pkg
from colony_memory_hermes.tools import _common


def test_runtime_dependency_reads_manifest() -> None:
    spec = pkg._runtime_dependency()
    assert spec.startswith("colony-memory")
    assert ">=0.1" in spec


def test_runtime_dependency_fallback(monkeypatch) -> None:
    from pathlib import Path

    def boom(*a, **k):
        raise OSError("no manifest")

    monkeypatch.setattr(Path, "read_text", boom)
    assert pkg._runtime_dependency() == "colony-memory>=0.1.0,<1"


def test_ensure_importable_noop_when_present() -> None:
    # colony_memory is installed in the test env -> shim must not shell out.
    pkg._ensure_colony_memory_importable()  # no exception, no install


def test_ensure_importable_installs_when_missing(monkeypatch) -> None:
    calls: list = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

    monkeypatch.setitem(sys.modules, "colony_memory", None)  # force ImportError
    monkeypatch.setattr(pkg.subprocess, "run", fake_run)
    pkg._ensure_colony_memory_importable()
    assert calls and calls[0][1:3] == ["-m", "pip"]
    assert any("colony-memory" in part for part in calls[0])


def test_build_memory_passes_base_url_and_signer(monkeypatch) -> None:
    pytest_seed = "22" * 32
    captured: dict = {}

    class FakeMem:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    import colony_memory

    monkeypatch.setenv("COLONY_MEMORY_API_KEY", "col_x")
    monkeypatch.setenv("COLONY_MEMORY_API_BASE", "https://example.test")
    monkeypatch.setenv(_common.SIGNING_SEED_ENV_VAR, pytest_seed)
    monkeypatch.setattr(colony_memory, "ColonyMemory", FakeMem)
    _common.build_memory()
    assert captured["base_url"] == "https://example.test"
    assert captured["signer"] is not None
