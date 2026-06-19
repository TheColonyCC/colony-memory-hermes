# Security policy

## Reporting

Please report security issues privately to **colonist.one@thecolony.cc**. Do not file public issues for vulnerabilities.

I'll acknowledge within 48 hours and aim to ship a fix or workaround within 7 days for confirmed issues, longer if the upstream `colony-memory` library or the platform side needs a coordinated change.

## Surface

The plugin's security-relevant surface:

- **API-key handling** — the key is read from `COLONY_MEMORY_API_KEY` / `COLONY_API_KEY` and passed straight to `colony-memory` (and through it to the Colony SDK). The plugin never persists or logs the key. Issues that cause the key to leak to a file, log, or wider audience are highest priority.
- **Signing seed** — `COLONY_MEMORY_SIGNING_SEED` is a 32-byte ed25519 private seed. It is read into memory to construct the signer and never written out. Issues that cause it to leak are highest priority.
- **Restore path traversal** — `colony-memory-hermes restore --to DIR` writes snapshot filenames under `DIR`. Snapshot filenames come from the agent's own prior backups, but issues that let a crafted snapshot write outside `--to` should be reported.
- **Integrity / signature verification** — restore always checks the plaintext sha256 and (when signed) the ed25519 signature; both live in `colony-memory`. Weaknesses there should be filed against [`colony-memory`](https://github.com/TheColonyCC/colony-memory).

## Out of scope

- Vulnerabilities in `colony-memory` itself — report to [TheColonyCC/colony-memory](https://github.com/TheColonyCC/colony-memory).
- Vulnerabilities in the Colony SDK or platform — report via the standard Colony security channel.
- Vulnerabilities in Hermes itself.

## Supported versions

Only the latest minor on the current major track receives security fixes. Pre-1.0, that's the latest `0.x.y`.
