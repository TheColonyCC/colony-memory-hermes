"""Tests for env-driven client construction + signer parsing."""

from __future__ import annotations

import base64

import pytest

from colony_memory_hermes.tools import _common


def test_build_memory_requires_key(monkeypatch) -> None:
    monkeypatch.delenv("COLONY_MEMORY_API_KEY", raising=False)
    monkeypatch.delenv("COLONY_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="is not set"):
        _common.build_memory()


def test_build_memory_uses_fallback_key(monkeypatch) -> None:
    captured: dict = {}

    class FakeMem:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    import colony_memory

    monkeypatch.delenv("COLONY_MEMORY_API_KEY", raising=False)
    monkeypatch.setenv("COLONY_API_KEY", "col_fallback")
    monkeypatch.setattr(colony_memory, "ColonyMemory", FakeMem)
    _common.build_memory()
    assert captured["api_key"] == "col_fallback"
    assert "signer" not in captured


def test_default_label(monkeypatch) -> None:
    monkeypatch.delenv("COLONY_MEMORY_LABEL", raising=False)
    assert _common.default_label() == "default"
    monkeypatch.setenv("COLONY_MEMORY_LABEL", "prod")
    assert _common.default_label() == "prod"


def test_signer_from_hex_seed(monkeypatch) -> None:
    pytest.importorskip("cryptography")
    seed_hex = "11" * 32
    monkeypatch.setenv(_common.SIGNING_SEED_ENV_VAR, seed_hex)
    signer = _common._build_signer()
    assert signer is not None
    assert signer.did_key.startswith("did:key:z")


def test_signer_from_b64_seed(monkeypatch) -> None:
    pytest.importorskip("cryptography")
    seed = bytes(range(32))
    b64 = base64.urlsafe_b64encode(seed).rstrip(b"=").decode()
    monkeypatch.setenv(_common.SIGNING_SEED_ENV_VAR, b64)
    signer = _common._build_signer()
    assert signer is not None


def test_signer_bad_length(monkeypatch) -> None:
    monkeypatch.setenv(_common.SIGNING_SEED_ENV_VAR, "abcd")
    with pytest.raises(RuntimeError, match="32 bytes"):
        _common._build_signer()


def test_no_signer_when_unset(monkeypatch) -> None:
    monkeypatch.delenv(_common.SIGNING_SEED_ENV_VAR, raising=False)
    assert _common._build_signer() is None
