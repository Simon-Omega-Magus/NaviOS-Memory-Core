"""Command-line interface for NaviOS Memory Reflex."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .core import (
    MemoryError,
    find_project_root,
    format_packet_markdown,
    index_project,
    index_status,
    initialize_project,
    query_index,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="navios-memory",
        description=(
            "Index provenance-addressed memory cells, retrieve through typed graph "
            "edges, and support compaction-safe Codex recovery."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="project path; defaults to the current project",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init", help="create a private local memory configuration and checkpoint"
    )
    init_parser.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
    )

    index_parser = subparsers.add_parser(
        "index", help="atomically rebuild the local memory index"
    )
    index_parser.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
    )

    query_parser = subparsers.add_parser(
        "query", help="retrieve memory with lexical seeds and graph expansion"
    )
    query_parser.add_argument("query", nargs="+", help="one or more triangulation queries")
    query_parser.add_argument("--top", type=int, help="maximum returned cells")
    query_parser.add_argument("--hops", type=int, help="maximum graph expansion depth")
    query_parser.add_argument(
        "--max-chars", type=int, help="maximum rendered context packet characters"
    )
    query_parser.add_argument(
        "--json", action="store_true", help="emit the exact JSON context packet"
    )

    status_parser = subparsers.add_parser("status", help="show index identity and size")
    status_parser.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
    )
    return parser


def emit(value: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, indent=2, sort_keys=True))
        return
    for key, item in value.items():
        print(f"{key}: {item}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = find_project_root(args.root)
    try:
        if args.command == "init":
            created = initialize_project(root)
            emit(
                {
                    "project_root": str(root),
                    "created": [str(path.relative_to(root)) for path in created],
                },
                as_json=args.json,
            )
            return 0
        if args.command == "index":
            emit(index_project(root), as_json=args.json)
            return 0
        if args.command == "query":
            packet = query_index(
                root,
                args.query,
                top_k=args.top,
                graph_hops=args.hops,
                max_context_chars=args.max_chars,
            )
            if args.json:
                print(json.dumps(packet, indent=2, sort_keys=True))
            else:
                print(format_packet_markdown(packet), end="")
            return 0
        if args.command == "status":
            emit(index_status(root), as_json=args.json)
            return 0
        parser.error(f"unsupported command: {args.command}")
    except MemoryError as exc:
        print(f"navios-memory: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
