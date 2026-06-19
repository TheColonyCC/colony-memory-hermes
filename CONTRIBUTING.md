# Contributing

Thanks for the interest. The shape of this plugin is intentionally narrow — every tool the model sees is a choice point in the agent's prompt, so the bar for "add a new tool" is high.

## What's in scope

- Bug fixes in the CLI or existing tools.
- Better docstrings and JSON Schemas on the tool surface.
- New tests for paths the suite doesn't yet cover.
- Hardening: restore-path safety, signer/seed parsing edge cases, quota-guard cases.

## What's out of scope

- Adding tools that wrap `colony-memory` / Colony SDK methods we deliberately omitted. The v0.1 tool surface (backup / restore / list / latest / status / prune) is a design choice — agents that need more can drop down to `colony_memory.ColonyMemory` directly. If you have a strong case for promoting one, open an issue first.
- Anything that bypasses `colony-memory`. Every call path goes through it; no fresh HTTP clients in the plugin.
- Anything that leaks the api_key or signing seed past `colony-memory`'s boundary.

## Local development

```bash
git clone https://github.com/TheColonyCC/colony-memory-hermes
cd colony-memory-hermes
pip install -e ".[dev]"
pytest --cov=colony_memory_hermes
ruff check colony_memory_hermes tests
mypy colony_memory_hermes
```

The test suite runs against an in-process fake vault (`tests/conftest.py`), so no
network or Colony account is needed. Keep coverage at 100%.
