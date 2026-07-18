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
    assimilate_project,
    find_project_root,
    format_packet_markdown,
    index_project,
    index_status,
    initialize_project,
    query_index,
)
from .cultivation import ALLOWED_KINDS, cultivate_proposal
from .staged import (
    format_hydration_markdown,
    format_survey_markdown,
    hydrate_index,
    survey_index,
)
from .will import list_will_questions, queue_will_question


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

    assimilate_parser = subparsers.add_parser(
        "assimilate",
        help=(
            "initialize if needed and derive a read-only cell graph from ordinary files"
        ),
    )
    assimilate_parser.add_argument(
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

    survey_parser = subparsers.add_parser(
        "survey",
        help=(
            "cast multiple body-free queries before loading source paragraphs"
        ),
    )
    survey_parser.add_argument(
        "query", nargs="+", help="one or more differently angled queries"
    )
    survey_parser.add_argument(
        "--candidates",
        type=int,
        help="metadata candidates retained per query; maximum 200",
    )
    survey_parser.add_argument(
        "--hops", type=int, help="maximum typed graph expansion depth"
    )
    survey_parser.add_argument(
        "--minimum-score", type=float, help="minimum normalized per-query score"
    )
    survey_parser.add_argument(
        "--show", type=int, default=20, help="metadata candidates shown in text mode"
    )
    survey_parser.add_argument(
        "--json", action="store_true", help="emit the complete body-free survey"
    )

    hydrate_parser = subparsers.add_parser(
        "hydrate",
        help="load selected survey cells after verifying their source revisions",
    )
    hydrate_parser.add_argument(
        "cell", nargs="+", help="exact or unique 12+ character cell IDs"
    )
    hydrate_parser.add_argument(
        "--max-chars", type=int, help="maximum rendered cell-body characters"
    )
    hydrate_parser.add_argument(
        "--json", action="store_true", help="emit the exact hydration packet"
    )

    cultivate_parser = subparsers.add_parser(
        "cultivate",
        help="append a provenance-bound proposed memory cell and rebuild the index",
    )
    cultivate_parser.add_argument("--title", required=True, help="proposal title")
    body_group = cultivate_parser.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body", help="short proposal body")
    body_group.add_argument(
        "--body-file", type=Path, help="UTF-8 file containing the proposal body"
    )
    cultivate_parser.add_argument(
        "--source",
        action="append",
        required=True,
        help="source PATH or revision-locked PATH::SHA256; repeat as needed",
    )
    cultivate_parser.add_argument(
        "--kind", choices=sorted(ALLOWED_KINDS), default="synthesis"
    )
    cultivate_parser.add_argument(
        "--created-by", default="navios-memory-agent", help="producer identity"
    )
    cultivate_parser.add_argument(
        "--confidence", type=float, default=0.75, help="interpretation confidence"
    )
    cultivate_parser.add_argument(
        "--tag", action="append", default=[], help="typed retrieval tag"
    )
    cultivate_parser.add_argument(
        "--no-index", action="store_true", help="defer index rebuilding"
    )
    cultivate_parser.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
    )

    will_question_parser = subparsers.add_parser(
        "queue-will-question",
        help="queue an unresolved human-will conflict without downgrading its claims",
    )
    will_question_parser.add_argument(
        "--claim",
        action="append",
        required=True,
        help="conflicting claim or sentence-cell ID; repeat at least twice",
    )
    will_question_parser.add_argument(
        "--question", required=True, help="one bounded question for the human"
    )
    will_question_parser.add_argument(
        "--scope", required=True, help="project or decision scope affected"
    )
    will_question_parser.add_argument(
        "--source",
        action="append",
        required=True,
        help="source PATH or revision-locked PATH::SHA256; repeat as needed",
    )
    will_question_parser.add_argument(
        "--proposed-interpretation",
        help="optional agent proposal, never an automatic resolution",
    )
    will_question_parser.add_argument(
        "--blocked-action", help="optional action held pending human resolution"
    )
    will_question_parser.add_argument(
        "--created-by", default="navios-memory-agent", help="producer identity"
    )
    will_question_parser.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
    )

    will_status_parser = subparsers.add_parser(
        "will-questions", help="list validated open human-will coherence questions"
    )
    will_status_parser.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
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
        if args.command == "assimilate":
            emit(assimilate_project(root), as_json=args.json)
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
        if args.command == "survey":
            report = survey_index(
                root,
                args.query,
                candidates_per_query=args.candidates,
                graph_hops=args.hops,
                minimum_score=args.minimum_score,
            )
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(format_survey_markdown(report, show=args.show), end="")
            return 0
        if args.command == "hydrate":
            packet = hydrate_index(
                root, args.cell, max_context_chars=args.max_chars
            )
            if args.json:
                print(json.dumps(packet, indent=2, sort_keys=True))
            else:
                print(format_hydration_markdown(packet), end="")
            return 0
        if args.command == "cultivate":
            if args.body_file is not None:
                try:
                    body = args.body_file.read_text(encoding="utf-8")
                except OSError as exc:
                    raise MemoryError(
                        f"cannot read proposal body file {args.body_file}: {exc}"
                    ) from exc
            else:
                body = args.body
            report = cultivate_proposal(
                root,
                title=args.title,
                body=body,
                sources=args.source,
                kind=args.kind,
                created_by=args.created_by,
                confidence=args.confidence,
                tags=args.tag,
                rebuild_index=not args.no_index,
            )
            emit(report, as_json=args.json)
            return 0
        if args.command == "queue-will-question":
            report = queue_will_question(
                root,
                claim_ids=args.claim,
                question=args.question,
                scope=args.scope,
                sources=args.source,
                created_by=args.created_by,
                proposed_interpretation=args.proposed_interpretation,
                blocked_action=args.blocked_action,
            )
            emit(report, as_json=args.json)
            return 0
        if args.command == "will-questions":
            emit(list_will_questions(root), as_json=args.json)
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
