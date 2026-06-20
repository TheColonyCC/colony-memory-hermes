# Authoring a Hermes plugin: the contract, and four traps

Notes from shipping two Hermes plugins (`colony-memory-hermes`,
`colony-chat-hermes`). Each trap below is something that fails **silently** —
the plugin installs, `hermes plugins list` shows it enabled, and yet it does
nothing — so they cost real debugging time. Verified against the Hermes runtime
at `~/.hermes/hermes-agent` (`hermes_cli/plugins.py`, `tools/registry.py`), not
just the docs.

## The contract (what Hermes actually calls)

A **directory plugin** lives at `~/.hermes/plugins/<name>/` and needs two things:

1. `plugin.yaml` — the manifest (`name`, `version`, `kind`, `tool_prefix`,
   optional `env` / `provides_tools` / `provides_hooks`).
2. `__init__.py` **at the plugin root** exposing `register(ctx)`.

At session start Hermes scans `~/.hermes/plugins/` (and pip packages exposing the
`hermes_agent.plugins` entry-point group), imports each plugin's `__init__.py`,
and calls `register(ctx)` with a `PluginContext`. You register tools/hooks by
**calling methods on `ctx`** — the return value is ignored.

---

## Trap 1 — `register(ctx)` must *call* `ctx.register_tool`, not *return* tools

The single most expensive mistake. It's tempting to write:

```python
def register(ctx):
    return PluginRegistration(tools=[...])   # WRONG — Hermes ignores the return
```

Hermes does `register_fn(ctx)` and never reads the result. Tools only exist if
you call `ctx.register_tool(...)` per tool:

```python
def register(ctx):
    for t in build_all():
        ctx.register_tool(
            name=t.name,
            toolset="my_toolset",
            schema={"name": t.name, "description": t.description, "parameters": t.parameters},
            handler=make_handler(t),
            is_async=False,
            description=t.description,
        )
```

Symptom: plugin loads, `enabled: True`, but the agent has zero of your tools.

## Trap 2 — `schema` is the **full** function object, not just the parameters

`tools.registry.get_definitions()` emits `{"type": "function", "function":
{**schema, "name": ...}}`. So the JSON-schema of the arguments must live under a
`parameters` key inside `schema`:

```python
schema = {"name": "x", "description": "...", "parameters": {"type": "object", "properties": {...}}}
```

If you pass the bare parameters object (`{"type": "object", "properties": ...}`)
as `schema`, the model sees a **zero-argument tool** — it can call it but never
with arguments. Symptom: the agent reports "this tool takes no parameters."

## Trap 3 — directory install imports the plugin dir's *own* `__init__.py`

`hermes plugins install <owner/repo>` git-clones into `~/.hermes/plugins/<name>/`
and imports **that directory's** `__init__.py`. A pip-style src layout (code under
`my_plugin/`, no root `__init__.py`) fails with *"No `__init__.py` in
…/plugins/<name>"*. Add a thin root `__init__.py` shim that puts the clone on
`sys.path` and re-exports `register` (exclude it from the wheel; the
pip/entry-point path imports your package directly and never uses it):

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from my_plugin import register  # noqa: E402
```

## Trap 4 — only some lifecycle hooks actually fire

`VALID_HOOKS` lists hooks the manager *accepts*, not hooks that *fire*. Grep the
runtime for `invoke_hook(`/`_invoke_hook(` before relying on one. In this build,
**`on_session_start` is never fired for plugins** — what fires is
`on_session_end`, `on_session_finalize`, and `on_session_reset` (plus the tool
hooks). So "restore on boot" via `on_session_start` silently never runs; do it on
`on_session_reset` (best-effort) or via a CLI in the boot script (deterministic).

## Handler signature

Registered tools are dispatched as `handler(args: dict, **kwargs) -> str`
(`tools.registry.dispatch`). Unpack the model's args and JSON-encode the result;
ignore framework kwargs (`parent_agent`, `session_id`, …):

```python
def make_handler(tool):
    def handler(args=None, **_kw):
        return json.dumps(tool.invoke(**(args or {})), default=str)
    return handler
```

## Verify it for real (the regression test that catches all of the above)

Don't trust `plugins list`. Load through the real contract and assert tools (and
hooks) register, with correct parameter schemas:

```python
from hermes_cli.plugins import get_plugin_manager
m = get_plugin_manager(); m.discover_and_load(force=True)
info = next(p for p in m.list_plugins() if p["key"] == "my_plugin")
assert info["tools"] > 0 and info["error"] is None
from tools.registry import registry
defs = registry.get_definitions({"my_tool"})
assert defs[0]["function"]["parameters"]["properties"]  # Trap 2 guard
```

A FakeCtx implementing `register_tool` + `register_hook` makes this a unit test
that lives in the plugin's own suite (see this repo's `tests/test_lifecycle.py`).
