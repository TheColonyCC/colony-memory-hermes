"""Common types + helpers shared across tool modules."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

#: Primary key env var; falls back to the generic COLONY_API_KEY so an agent
#: that already exports its Colony key doesn't need a second copy.
API_KEY_ENV_VAR = "COLONY_MEMORY_API_KEY"
API_KEY_FALLBACK_ENV_VAR = "COLONY_API_KEY"
API_BASE_ENV_VAR = "COLONY_MEMORY_API_BASE"
API_BASE_FALLBACK_ENV_VAR = "COLONY_API_BASE"
LABEL_ENV_VAR = "COLONY_MEMORY_LABEL"
#: Optional 32-byte ed25519 seed (hex or base64url) — when set, every backup's
#: manifest is signed and bound to the derived did:key.
SIGNING_SEED_ENV_VAR = "COLONY_MEMORY_SIGNING_SEED"

DEFAULT_LABEL = "default"

JsonSchema = dict[str, Any]


@dataclass
class Tool:
    """Hermes-shaped tool descriptor.

    The harness reads ``name`` + ``description`` + ``parameters`` to build
    the model's tool-call surface, and invokes ``invoke`` with the kwargs the
    model emitted. ``parameters`` is a JSON Schema object describing the
    tool's arguments; the harness validates against it before calling
    ``invoke``, so the tool body can trust the shapes it receives.
    """

    name: str
    description: str
    parameters: JsonSchema
    invoke: Callable[..., Any]


def default_label() -> str:
    return os.environ.get(LABEL_ENV_VAR) or DEFAULT_LABEL


def _build_signer() -> Any | None:
    """Build an ``Ed25519Signer`` from ``COLONY_MEMORY_SIGNING_SEED`` if set.

    Accepts a 64-char hex seed or a base64url-encoded 32-byte seed. Returns
    ``None`` when the env var is unset (unsigned snapshots).
    """
    raw = os.environ.get(SIGNING_SEED_ENV_VAR)
    if not raw:
        return None
    raw = raw.strip()
    seed: bytes
    try:
        seed = bytes.fromhex(raw)
    except ValueError:
        import base64

        padded = raw + "=" * ((4 - len(raw) % 4) % 4)
        seed = base64.urlsafe_b64decode(padded)
    if len(seed) != 32:
        raise RuntimeError(
            f"{SIGNING_SEED_ENV_VAR} must decode to 32 bytes (got {len(seed)}); "
            "use a 64-char hex or base64url-encoded ed25519 seed"
        )
    from colony_memory import Ed25519Signer

    return Ed25519Signer(seed)


def build_memory() -> Any:
    """Build a fresh ``ColonyMemory`` from environment.

    Reads ``COLONY_MEMORY_API_KEY`` (or ``COLONY_API_KEY``), an optional base
    URL override, and an optional signing seed. Re-imports ``colony_memory``
    on every call so the import is lazy (helps tests monkey-patch it) but
    cheap (Python caches the module).

    Raises ``RuntimeError`` if no api_key is configured.
    """
    api_key = os.environ.get(API_KEY_ENV_VAR) or os.environ.get(API_KEY_FALLBACK_ENV_VAR)
    if not api_key:
        raise RuntimeError(
            f"{API_KEY_ENV_VAR} (or {API_KEY_FALLBACK_ENV_VAR}) is not set. Export your "
            "Colony API key (col_…) — writing to the vault needs an account with karma >= 10."
        )

    from colony_memory import ColonyMemory

    kwargs: dict[str, Any] = {"api_key": api_key}
    base = os.environ.get(API_BASE_ENV_VAR) or os.environ.get(API_BASE_FALLBACK_ENV_VAR)
    if base:
        kwargs["base_url"] = base
    signer = _build_signer()
    if signer is not None:
        kwargs["signer"] = signer

    return ColonyMemory(**kwargs)


def _info_dict(info: Any) -> dict[str, Any]:
    """Flatten a ``SnapshotInfo`` dataclass into a JSON-safe dict."""
    return {
        "snapshot_id": info.snapshot_id,
        "label": info.label,
        "created_at": info.created_at,
        "doc_names": list(info.doc_names),
        "part_count": info.part_count,
        "byte_size": info.byte_size,
        "plaintext_sha256": info.plaintext_sha256,
        "signed": info.signed,
        "issuer": info.issuer,
    }
