"""Shared fixtures — a fake ColonyMemory + a fake vault-backed real one.

Most plugin tests don't need real network: they monkey-patch
``colony_memory_hermes.tools._common.build_memory`` (and the CLI's lazy
import of it) to return a ``FakeMemory``. A couple of round-trip tests use
the *real* ``ColonyMemory`` against an in-process ``FakeVault`` so the
plugin's wiring is exercised end-to-end.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeVault:
    """In-memory stand-in for the Colony vault surface ColonyMemory uses."""

    def __init__(self, quota: int = 10 * 1024 * 1024) -> None:
        self.files: dict[str, str] = {}
        self.quota = quota

    def _used(self) -> int:
        return sum(len(c.encode("utf-8")) for c in self.files.values())

    def vault_status(self) -> dict:
        used = self._used()
        return {
            "quota_bytes": self.quota,
            "used_bytes": used,
            "available_bytes": self.quota - used,
            "file_count": len(self.files),
        }

    def vault_list_files(self) -> dict:
        return {"files": [{"filename": fn} for fn in sorted(self.files)]}

    def vault_get_file(self, filename: str) -> dict:
        if filename not in self.files:
            raise KeyError(filename)
        return {"filename": filename, "content": self.files[filename]}

    def vault_upload_file(self, filename: str, content: str) -> dict:
        self.files[filename] = content
        return {"filename": filename, "ok": True}

    def vault_delete_file(self, filename: str) -> dict:
        self.files.pop(filename, None)
        return {"ok": True}


@pytest.fixture
def vault() -> FakeVault:
    return FakeVault()


@pytest.fixture
def memory(vault: FakeVault):
    from colony_memory import ColonyMemory

    return ColonyMemory(backend=vault)
