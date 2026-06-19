# Changelog

All notable changes to `colony-memory-hermes` are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-06-19

Initial release.

### Added
- Hermes plugin entry point (`hermes_agent.plugins` → `colony_memory:register`)
  exposing six typed tools under the `colony_memory_` prefix:
  `restore`, `backup`, `list_snapshots`, `latest`, `status`, `prune`.
- `colony-memory-hermes` CLI with `status`, `backup`, `restore`, and `list`
  subcommands — drives cron-based backup and restore-on-boot without Python.
- Env-driven client construction: `COLONY_MEMORY_API_KEY` (falls back to
  `COLONY_API_KEY`), `COLONY_MEMORY_API_BASE` (falls back to `COLONY_API_BASE`),
  `COLONY_MEMORY_LABEL`, and optional `COLONY_MEMORY_SIGNING_SEED` for
  ed25519-signed snapshots.
- Git-clone shim: pip-installs `colony-memory` on first import when the plugin is
  dropped into `~/.hermes/plugins/` rather than installed via pip.
- `plugin.yaml` manifest shipped as Hermes plugin shared-data.
- 100% test coverage (29 tests) over an in-process fake vault.
