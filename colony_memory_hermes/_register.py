"""Hermes plugin registration hook.

The harness loads plugins by walking the ``hermes_agent.plugins``
entry-point group and calling each entry's ``register(harness)``. We
delegate to :func:`register_plugin` so the public
``colony_memory_hermes.register`` symbol stays small.

The returned ``PluginRegistration`` carries the tools the harness should
add to its tool registry. v0.1 ships six tools (backup / restore /
list_snapshots / latest / status / prune). There is no inbound runtime —
memory backup is a deliberate tool call, not an event stream, so this
plugin has no daemon.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from colony_memory_hermes import tools
from colony_memory_hermes._version import __version__

PLUGIN_NAME = "colony_memory"
TOOL_PREFIX = "colony_memory_"


@dataclass
class PluginRegistration:
    """Returned to the harness on plugin load.

    The harness reads ``tools`` and adds each entry to its tool registry,
    keyed by ``name``. Other fields are diagnostic.
    """

    name: str = PLUGIN_NAME
    version: str = __version__
    tool_prefix: str = TOOL_PREFIX
    tools: list[tools.Tool] = field(default_factory=list)


def register_plugin(harness: object) -> PluginRegistration:
    """Build the plugin's registration record.

    ``harness`` is opaque to this plugin — we don't poke at its internals.
    Backup/restore are exposed purely as tools; there is no separate
    runtime process to wire in.
    """
    return PluginRegistration(tools=tools.build_all())
