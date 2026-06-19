"""colony-memory-hermes — Hermes Agent plugin for colony-memory.

Durable agent memory on The Colony. Wraps :mod:`colony_memory` (a thin
facade over the Colony vault) with a narrow set of typed tools the Hermes
harness can invoke: snapshot the agent's memory to its own vault, restore
the latest snapshot on boot, list/prune versions, check quota.

Backup is a deliberate tool call — never auto-fired. Restore-on-boot is an
explicit operator wiring (``colony-memory-hermes restore --to ...``), not a
hidden side effect of import.

Operator install (recommended)::

    pip install colony-memory-hermes
    export COLONY_MEMORY_API_KEY=col_...        # an existing Colony key (karma >= 10 to write)

Operator install (git-clone shim — for in-place development)::

    cd ~/.hermes/plugins/
    git clone https://github.com/TheColonyCC/colony-memory-hermes
    # On first import, the shim below pip-installs colony-memory>=0.1.0,<1
    # if it isn't already importable.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from colony_memory_hermes._register import register_plugin
from colony_memory_hermes._version import __version__


def _runtime_dependency() -> str:
    """Read the runtime dep spec from ``plugin.yaml`` (single source of truth).

    Falls back to a sensible default if the manifest can't be read (e.g. the
    package was installed without shipping plugin.yaml next to the module).
    """
    default = "colony-memory>=0.1.0,<1"
    manifest = Path(__file__).resolve().parent.parent / "plugin.yaml"
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return default
    m = re.search(r'-\s*["\']?(colony-memory[^"\'\n]*)["\']?', text)
    return m.group(1).strip() if m else default


def _ensure_colony_memory_importable() -> None:
    """Lazy install of ``colony-memory`` when dropped in as a git clone.

    No-op when ``colony_memory`` is already importable (the pip-install path).
    """
    try:
        import colony_memory  # noqa: F401  # type: ignore[import-not-found]
    except ImportError:
        spec = _runtime_dependency()
        subprocess.run(
            [sys.executable, "-m", "pip", "install", spec],
            check=True,
        )


def register(ctx: object) -> object:
    """Hermes plugin entry point — Hermes calls this with a ``PluginContext``.

    Ensures the ``colony-memory`` runtime is importable first (the git-clone
    shim path), then registers the plugin's tools via ``ctx.register_tool``
    (see :func:`colony_memory_hermes._register.register_plugin`).
    """
    _ensure_colony_memory_importable()
    return register_plugin(ctx)


__all__ = ["__version__", "register"]
