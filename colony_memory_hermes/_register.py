"""Hermes plugin registration hook.

Hermes loads a directory plugin by importing its ``__init__.py`` and calling
``register(ctx)`` with a ``PluginContext``. Tools are added to the global tool
registry by calling ``ctx.register_tool(name, toolset, schema, handler, ...)``
for each one — the harness does **not** read a return value. We also return a
``PluginRegistration`` record for introspection/tests (Hermes ignores it).

v0.1 ships six tools (restore / backup / list_snapshots / latest / status /
prune). There is no inbound runtime — memory backup is a deliberate tool call,
not an event stream — so this plugin has no daemon or hooks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from colony_memory_hermes import tools
from colony_memory_hermes._version import __version__
from colony_memory_hermes.lifecycle import register_lifecycle

PLUGIN_NAME = "colony_memory"
TOOL_PREFIX = "colony_memory_"
#: Hermes toolset key the tools are grouped under (toggled via `hermes tools`).
TOOLSET = "colony_memory"


@dataclass
class PluginRegistration:
    """Introspection record returned from :func:`register_plugin`.

    Hermes ignores this — tools are registered via ``ctx.register_tool`` — but
    tests and ``colony-memory-hermes`` callers read it.
    """

    name: str = PLUGIN_NAME
    version: str = __version__
    tool_prefix: str = TOOL_PREFIX
    tools: list[tools.Tool] = field(default_factory=list)


def _make_handler(tool: tools.Tool):
    """Adapt a colony_memory ``Tool`` to the Hermes registry handler contract.

    Hermes dispatches tools as ``handler(args: dict, **kwargs) -> str`` (see
    ``tools.registry.dispatch``). We unpack the model's args into the tool's
    keyword-only ``invoke`` and JSON-encode the result so the model receives a
    string, ignoring any framework kwargs (parent_agent, session_id, …).
    """

    def handler(args: dict | None = None, **_kwargs) -> str:
        result = tool.invoke(**(args or {}))
        return json.dumps(result, default=str)

    handler.__name__ = tool.name
    return handler


def register_plugin(ctx: object) -> PluginRegistration:
    """Register the plugin's tools with the Hermes harness.

    Hermes calls ``register(ctx)`` with a ``PluginContext`` exposing
    ``register_tool(...)``; we call it once per tool so they appear alongside
    the built-in tools. ``ctx`` may be a non-Hermes object in tests (no
    ``register_tool``) — then we just return the record.
    """
    reg = PluginRegistration(tools=tools.build_all())
    # Opt-in automatic backup/restore via Hermes session-lifecycle hooks.
    register_lifecycle(ctx)
    register_tool = getattr(ctx, "register_tool", None)
    if callable(register_tool):
        for t in reg.tools:
            # Hermes' registry expects ``schema`` to be the full OpenAI function
            # object — ``get_definitions`` emits ``{"type":"function","function":
            # {**schema, "name": ...}}``. So the args JSON-schema must live under
            # a ``parameters`` key; passing the bare parameters object makes the
            # model see a zero-argument tool.
            register_tool(
                name=t.name,
                toolset=TOOLSET,
                schema={
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
                handler=_make_handler(t),
                description=t.description,
                is_async=False,
                emoji="💾",
            )
    return reg
