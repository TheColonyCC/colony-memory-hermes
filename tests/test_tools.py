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
    reg = register(object())
    assert isinstance(reg, PluginRegistration)
    assert reg.name == "colony_memory"
    assert reg.tool_prefix == "colony_memory_"
    assert [t.name for t in reg.tools] == [t.name for t in build_all()]


class _FakeCtx:
    """Stand-in for Hermes' PluginContext.register_tool contract."""

    def __init__(self) -> None:
        self.registered: list[dict] = []

    def register_tool(self, **kwargs) -> None:
        self.registered.append(kwargs)


def test_register_calls_ctx_register_tool() -> None:
    # When given a real PluginContext (has register_tool), every tool is
    # registered with the Hermes contract: name, toolset, schema, handler.
    ctx = _FakeCtx()
    register(ctx)
    names = [r["name"] for r in ctx.registered]
    assert names == [t.name for t in build_all()]
    for r in ctx.registered:
        assert r["toolset"] == "colony_memory"
        # schema is the full OpenAI function object: args live under "parameters"
        assert r["schema"]["parameters"]["type"] == "object"
        assert r["schema"]["description"]
        assert r["schema"]["name"] == r["name"]
        assert callable(r["handler"])
        assert r["description"]
        assert r["is_async"] is False


def test_ctx_handler_unpacks_args_and_returns_json(monkeypatch) -> None:
    # The handler Hermes invokes is handler(args: dict, **kwargs) -> str:
    # it unpacks the model's args into the tool and JSON-encodes the result.
    import json

    from colony_memory_hermes.tools import _common

    class _Mem:
        def status(self):
            return {"quota_bytes": 10, "used_bytes": 1, "available_bytes": 9, "file_count": 1}

    monkeypatch.setattr(_common, "build_memory", _Mem)
    ctx = _FakeCtx()
    register(ctx)
    status_handler = next(
        r["handler"] for r in ctx.registered if r["name"] == "colony_memory_status"
    )
    out = status_handler({})  # Hermes passes the args dict positionally
    assert isinstance(out, str)
    assert json.loads(out)["quota_bytes"] == 10
    # extra framework kwargs are ignored
    with_kwargs = status_handler({}, parent_agent=object(), session_id="x")
    assert json.loads(with_kwargs)["file_count"] == 1


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
