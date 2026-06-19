"""``colony-memory-hermes`` shell entry point.

Exposed as the ``colony-memory-hermes`` console script. Lets operators drive
backup/restore from cron or a boot script without writing Python.

Subcommands:

- ``status`` — print vault quota for the configured account.
- ``backup`` — snapshot files/dirs into the vault. ``--from`` may be repeated;
  directories are walked (text files only). ``--prune-keep N`` trims afterwards.
- ``restore`` — write the latest (or ``--snapshot-id``) snapshot's files into
  ``--to`` a directory. ``--list`` lists versions instead.
- ``list`` — list snapshots (newest first) as JSON.

All paths read the api_key from ``COLONY_MEMORY_API_KEY`` (or ``COLONY_API_KEY``).

Cron example — nightly backup of an agent's memory dir, keeping 14 versions::

    0 3 * * *  COLONY_MEMORY_API_KEY=col_… colony-memory-hermes backup \\
        --from ~/.hermes/MEMORY.md --from ~/.hermes/memory --prune-keep 14

Boot example — restore on startup before the agent loop::

    colony-memory-hermes restore --to ~/.hermes/memory || true
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from colony_memory_hermes._version import __version__

# Extensions we treat as restorable text when walking a directory.
_TEXT_SUFFIXES = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".xml", ".csv",
    ".cfg", ".ini", ".html",
}


def _collect_documents(sources: list[str]) -> dict[str, str]:
    """Turn ``--from`` paths into a {filename: text} mapping.

    A file becomes one entry keyed by its basename; a directory is walked and
    each text file becomes an entry keyed by its path relative to that dir.
    Raises ``SystemExit`` on a missing path or an out-of-budget binary file.
    """
    docs: dict[str, str] = {}
    for raw in sources:
        p = Path(raw).expanduser()
        if not p.exists():
            raise SystemExit(f"error: no such file or directory: {p}")
        if p.is_file():
            docs[p.name] = p.read_text(encoding="utf-8")
            continue
        for child in sorted(p.rglob("*")):
            if child.is_file() and child.suffix.lower() in _TEXT_SUFFIXES:
                docs[str(child.relative_to(p))] = child.read_text(encoding="utf-8")
    if not docs:
        raise SystemExit("error: nothing to back up (no text files found in --from paths)")
    return docs


def _cmd_status(_: argparse.Namespace) -> int:
    from colony_memory_hermes.tools._common import build_memory

    print(json.dumps(build_memory().status(), indent=2))
    return 0


def _cmd_backup(args: argparse.Namespace) -> int:
    from colony_memory_hermes.tools._common import build_memory, default_label

    docs = _collect_documents(args.from_)
    mem = build_memory()
    info = mem.backup(docs, label=args.label or default_label(), prune_keep=args.prune_keep)
    print(json.dumps({
        "snapshot_id": info.snapshot_id,
        "label": info.label,
        "doc_names": list(info.doc_names),
        "byte_size": info.byte_size,
        "signed": info.signed,
    }, indent=2))
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    from colony_memory_hermes.tools._common import build_memory, default_label

    mem = build_memory()
    label = args.label or default_label()
    if args.list:
        snaps = mem.list_snapshots(label=label)
        print(json.dumps([
            {"snapshot_id": s.snapshot_id, "created_at": s.created_at,
             "doc_names": list(s.doc_names), "byte_size": s.byte_size}
            for s in snaps
        ], indent=2))
        return 0
    docs = mem.restore(label=label, snapshot_id=args.snapshot_id, verify=not args.no_verify)
    out = Path(args.to).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    for name, text in docs.items():
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    print(f"restored {len(docs)} file(s) to {out}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    from colony_memory_hermes.tools._common import build_memory

    snaps = build_memory().list_snapshots(label=args.label)
    print(json.dumps([
        {"snapshot_id": s.snapshot_id, "label": s.label, "created_at": s.created_at,
         "doc_names": list(s.doc_names), "byte_size": s.byte_size, "signed": s.signed}
        for s in snaps
    ], indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="colony-memory-hermes",
        description="Back up and restore agent memory on the Colony vault.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("status", help="print vault quota")
    s.set_defaults(func=_cmd_status)

    b = sub.add_parser("backup", help="snapshot files/dirs into the vault")
    b.add_argument("--from", dest="from_", action="append", required=True,
                   metavar="PATH", help="file or directory to back up (repeatable)")
    b.add_argument("--label", help="snapshot stream name")
    b.add_argument("--prune-keep", type=int, metavar="N",
                   help="keep only the newest N snapshots afterwards")
    b.set_defaults(func=_cmd_backup)

    r = sub.add_parser("restore", help="write a snapshot's files to a directory")
    r.add_argument("--to", help="output directory (required unless --list)")
    r.add_argument("--label", help="snapshot stream name")
    r.add_argument("--snapshot-id", help="restore this snapshot instead of latest")
    r.add_argument("--no-verify", action="store_true", help="skip signature verification")
    r.add_argument("--list", action="store_true", help="list versions instead of restoring")
    r.set_defaults(func=_cmd_restore)

    ls = sub.add_parser("list", help="list snapshots (newest first)")
    ls.add_argument("--label", help="only list snapshots for this label")
    ls.set_defaults(func=_cmd_list)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "restore" and not args.list and not args.to:
        print("error: restore needs --to DIR (or --list)", file=sys.stderr)
        return 2
    try:
        result: Any = args.func(args)
        return int(result or 0)
    except RuntimeError as e:  # missing api_key, etc. — operator-actionable
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
