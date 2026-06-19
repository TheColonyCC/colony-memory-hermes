"""CLI tests — backup/restore round-trip through the console script."""

from __future__ import annotations

import json

import pytest

from colony_memory_hermes import cli


@pytest.fixture
def patched_cli(monkeypatch, memory):
    """Make the CLI's lazy build_memory() return a real ColonyMemory/FakeVault."""
    monkeypatch.setattr(
        "colony_memory_hermes.tools._common.build_memory", lambda: memory
    )
    return memory


def test_version(capsys) -> None:
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0
    assert "colony-memory-hermes" in capsys.readouterr().out


def test_backup_restore_roundtrip(tmp_path, patched_cli, capsys) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "MEMORY.md").write_text("# state\n", encoding="utf-8")
    (src / "sub").mkdir()
    (src / "sub" / "notes.txt").write_text("remember this", encoding="utf-8")
    # A binary-ish file with a non-text suffix is skipped.
    (src / "blob.bin").write_bytes(b"\x00\x01")

    rc = cli.main(["backup", "--from", str(src)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert sorted(out["doc_names"]) == ["MEMORY.md", "sub/notes.txt"]

    dest = tmp_path / "dest"
    rc = cli.main(["restore", "--to", str(dest)])
    assert rc == 0
    assert (dest / "MEMORY.md").read_text(encoding="utf-8") == "# state\n"
    assert (dest / "sub" / "notes.txt").read_text(encoding="utf-8") == "remember this"


def test_backup_single_file(tmp_path, patched_cli, capsys) -> None:
    f = tmp_path / "MEMORY.md"
    f.write_text("hi", encoding="utf-8")
    rc = cli.main(["backup", "--from", str(f)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["doc_names"] == ["MEMORY.md"]


def test_backup_missing_path(tmp_path, patched_cli) -> None:
    with pytest.raises(SystemExit, match="no such file"):
        cli.main(["backup", "--from", str(tmp_path / "nope")])


def test_backup_empty_dir(tmp_path, patched_cli) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SystemExit, match="nothing to back up"):
        cli.main(["backup", "--from", str(empty)])


def test_restore_needs_to(patched_cli, capsys) -> None:
    rc = cli.main(["restore"])
    assert rc == 2
    assert "needs --to" in capsys.readouterr().err


def test_restore_list(tmp_path, patched_cli, capsys) -> None:
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    cli.main(["backup", "--from", str(f)])
    capsys.readouterr()
    rc = cli.main(["restore", "--list"])
    assert rc == 0
    listing = json.loads(capsys.readouterr().out)
    assert len(listing) == 1


def test_list_and_status(tmp_path, patched_cli, capsys) -> None:
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    cli.main(["backup", "--from", str(f)])
    capsys.readouterr()

    cli.main(["list"])
    assert len(json.loads(capsys.readouterr().out)) == 1

    cli.main(["status"])
    assert "quota_bytes" in json.loads(capsys.readouterr().out)


def test_missing_key_returns_1(monkeypatch, capsys) -> None:
    monkeypatch.delenv("COLONY_MEMORY_API_KEY", raising=False)
    monkeypatch.delenv("COLONY_API_KEY", raising=False)
    rc = cli.main(["status"])
    assert rc == 1
    assert "error" in capsys.readouterr().err
