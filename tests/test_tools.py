"""Tool-surface tests — shapes, registration, and end-to-end invoke."""

from __future__ import annotations

import pytest

from colony_memory_hermes import register
from colony_memory_hermes._register import PluginRegistration
from colony_memory_hermes.tools import Tool, build_all


def _by_name(tools: list[Tool]) -> dict[str, Tool]:
    return {t.name: t for t in tools}


def test_build_all_surface() -> None:
    tools = build_all()
    names = [t.name for t in tools]
    assert names == [
        "colony_memory_restore",
        "colony_memory_backup",
        "colony_memory_list_snapshots",
        "colony_memory_latest",
        "colony_memory_status",
        "colony_memory_prune",
    ]
    # No duplicates.
    assert len(names) == len(set(names))


def test_every_tool_is_well_formed() -> None:
    for t in build_all():
        assert isinstance(t, Tool)
        assert t.name.startswith("colony_memory_")
        assert t.description and len(t.description) > 20
        assert t.parameters["type"] == "object"
        # Closed schema — the harness validates against it.
        assert t.parameters["additionalProperties"] is False
        assert callable(t.invoke)


def test_register_returns_registration() -> None:
    reg = register(harness=object())
    assert isinstance(reg, PluginRegistration)
    assert reg.name == "colony_memory"
    assert reg.tool_prefix == "colony_memory_"
    assert [t.name for t in reg.tools] == [t.name for t in build_all()]


def test_backup_required_field() -> None:
    backup = _by_name(build_all())["colony_memory_backup"]
    assert backup.parameters["required"] == ["documents"]
    docs_schema = backup.parameters["properties"]["documents"]
    assert docs_schema["type"] == "object"
    assert docs_schema["additionalProperties"] == {"type": "string"}


@pytest.fixture
def patched_memory(monkeypatch, memory):
    """Point every tool's build_memory() at a real ColonyMemory over FakeVault."""
    monkeypatch.setattr(
        "colony_memory_hermes.tools._common.build_memory", lambda: memory
    )
    return memory


def test_backup_then_restore_roundtrip(patched_memory) -> None:
    tools = _by_name(build_all())
    docs = {"MEMORY.md": "# hello\n", "goals.md": "ship it"}

    info = tools["colony_memory_backup"].invoke(documents=docs)
    assert info["snapshot_id"]
    assert info["doc_names"] == ["MEMORY.md", "goals.md"]
    assert info["signed"] is False

    restored = tools["colony_memory_restore"].invoke()
    assert restored == {"documents": docs}


def test_list_latest_and_status(patched_memory) -> None:
    tools = _by_name(build_all())
    tools["colony_memory_backup"].invoke(documents={"a.md": "1"})
    tools["colony_memory_backup"].invoke(documents={"a.md": "2"})

    listing = tools["colony_memory_list_snapshots"].invoke()
    assert len(listing["snapshots"]) == 2

    latest = tools["colony_memory_latest"].invoke()
    assert latest["latest"] is not None

    status = tools["colony_memory_status"].invoke()
    assert status["quota_bytes"] == 10 * 1024 * 1024
    assert status["available_bytes"] < status["quota_bytes"]


def test_prune_keeps_newest(patched_memory) -> None:
    tools = _by_name(build_all())
    for i in range(4):
        tools["colony_memory_backup"].invoke(documents={"a.md": str(i)}, label="x")
    result = tools["colony_memory_prune"].invoke(keep=2, label="x")
    assert result["deleted"] == 2
    assert len(tools["colony_memory_list_snapshots"].invoke(label="x")["snapshots"]) == 2


def test_latest_none_when_empty(patched_memory) -> None:
    tools = _by_name(build_all())
    assert tools["colony_memory_latest"].invoke(label="never-written")["latest"] is None
