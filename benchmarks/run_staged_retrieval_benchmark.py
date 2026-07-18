#!/usr/bin/env python3
"""Measure broad graph survey and selective hydration without an LLM judge."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins/navios-memory-reflex"
sys.path.insert(0, str(PLUGIN_ROOT))

from navios_memory_reflex.core import DEFAULT_DB, index_project  # noqa: E402
from navios_memory_reflex.staged import (  # noqa: E402
    format_hydration_markdown,
    format_survey_markdown,
    hydrate_index,
    survey_index,
)


REQUIRED_PATHS = (
    "docs/00-memory-objective.md",
    "docs/01-fork-contract.md",
    "docs/02-human-will.md",
    "docs/03-latent-constraint.md",
)
QUERIES = (
    "opal ambient memory objective and compaction continuity",
    "fork digestion capsule and bounded context isolation",
    "stable human direction preference and will coherence",
)


def _write_corpus(root: Path, *, distractors: int) -> None:
    docs = root / "docs"
    docs.mkdir(parents=True)
    filler = " ".join(f"fillerterm{index}" for index in range(90))
    long_tail = (filler + " ") * 4
    (docs / "00-memory-objective.md").write_text(
        "---\n"
        "tags: [memory, reflex]\n"
        "links: [03-latent-constraint.md]\n"
        "---\n"
        "# Opal Ambient Memory Objective\n\n"
        "The accepted objective is to surface relevant ambient memory before "
        "context compaction breaks continuity, while retaining exact provenance. "
        + long_tail
        + "\n",
        encoding="utf-8",
    )
    (docs / "01-fork-contract.md").write_text(
        "---\ntags: [memory, fork]\n---\n"
        "# Fork Digestion Contract\n\n"
        "A read-only fork inspects a bounded candidate manifest and returns either "
        "no_relevant_memory or a compact source-linked capsule; its raw context is "
        "discarded. "
        + long_tail
        + "\n",
        encoding="utf-8",
    )
    (docs / "02-human-will.md").write_text(
        "---\ntags: [memory, will]\n---\n"
        "# Stable Human Will\n\n"
        "A stable human-authored direction or preference does not expire merely "
        "because it is old; completion, explicit expiry, revocation, or clear "
        "supersession changes its lifecycle. "
        + long_tail
        + "\n",
        encoding="utf-8",
    )
    (docs / "03-latent-constraint.md").write_text(
        "# Copperline Mandate\n\n"
        "The copperline mandate requires an exact source-revision check before a "
        "selected body may enter consequential reasoning. "
        + long_tail
        + "\n",
        encoding="utf-8",
    )
    for number in range(distractors):
        (docs / f"distractor-{number:03d}.md").write_text(
            f"# Background Note {number}\n\n"
            "Ambient memory retrieval discusses objectives, compaction, forks, "
            "bounded context, human direction, preferences, and coherence in a "
            f"generic example {number}. "
            + long_tail
            + "\n",
            encoding="utf-8",
        )


def _required_cells(root: Path) -> dict[str, str]:
    connection = sqlite3.connect(root / DEFAULT_DB)
    rows = connection.execute(
        "SELECT path, cell_id FROM cells WHERE path IN (?, ?, ?, ?) "
        "ORDER BY path, ordinal",
        REQUIRED_PATHS,
    ).fetchall()
    connection.close()
    required: dict[str, str] = {}
    for path, cell_id in rows:
        required.setdefault(path, cell_id)
    if set(required) != set(REQUIRED_PATHS):
        raise RuntimeError("benchmark corpus did not produce every required cell")
    return required


def run_benchmark(*, distractors: int = 236) -> dict[str, Any]:
    if distractors < 20:
        raise ValueError("distractors must be at least 20")
    with tempfile.TemporaryDirectory(prefix="navios-staged-benchmark-") as temporary:
        root = Path(temporary) / "project"
        root.mkdir()
        _write_corpus(root, distractors=distractors)
        index = index_project(root)
        required = _required_cells(root)
        survey = survey_index(
            root,
            QUERIES,
            candidates_per_query=200,
            graph_hops=3,
            minimum_score=0.0,
        )
        candidates = {item["cell_id"]: item for item in survey["candidates"]}
        required_ids = list(required.values())
        candidate_hits = [cell_id for cell_id in required_ids if cell_id in candidates]
        multi_hop_hits = [
            cell_id
            for cell_id in candidate_hits
            if candidates[cell_id]["best_graph"]["hops"] > 0
        ]

        eager = hydrate_index(
            root,
            [item["cell_id"] for item in survey["candidates"]],
            max_context_chars=5_000_000,
        )
        selective = hydrate_index(
            root,
            candidate_hits,
            max_context_chars=250_000,
        )
        survey_chars = len(
            format_survey_markdown(survey, show=max(survey["candidate_count"], 1))
        )
        eager_chars = len(format_hydration_markdown(eager))
        selective_chars = len(format_hydration_markdown(selective))
        staged_chars = survey_chars + selective_chars
        negative = survey_index(
            root,
            ["volcanic upholstery submarine"],
            candidates_per_query=200,
            graph_hops=3,
        )
        recall = len(candidate_hits) / len(required_ids)
        savings = 1 - staged_chars / eager_chars if eager_chars else 0.0
        return {
            "schema": "navios-staged-retrieval-benchmark-v1",
            "selection_mode": (
                "oracle-assisted selective hydration; this measures substrate "
                "capacity, not autonomous relevance judgment"
            ),
            "corpus": {
                "documents": index["documents"],
                "cells": index["cells"],
                "edges": index["edges"],
                "distractors": distractors,
                "required_cells": len(required_ids),
            },
            "survey": {
                "queries": len(QUERIES),
                "candidates_per_query": 200,
                "union_candidates": survey["candidate_count"],
                "required_hits": len(candidate_hits),
                "required_recall": round(recall, 6),
                "multi_hop_required_hits": len(multi_hop_hits),
                "metadata_chars": survey_chars,
            },
            "context": {
                "eager_candidate_bodies": len(eager["results"]),
                "eager_candidate_body_chars": eager_chars,
                "selective_body_chars": selective_chars,
                "staged_total_chars": staged_chars,
                "staged_savings_fraction": round(savings, 6),
                "estimated_eager_tokens": round(eager_chars / 4),
                "estimated_staged_tokens": round(staged_chars / 4),
            },
            "negative_control_abstained": negative["abstained"],
            "required": [
                {
                    "path": path,
                    "cell_id": cell_id,
                    "surfaced": cell_id in candidates,
                    "best_hops": (
                        candidates[cell_id]["best_graph"]["hops"]
                        if cell_id in candidates
                        else None
                    ),
                }
                for path, cell_id in required.items()
            ],
        }


def _format_text(report: dict[str, Any]) -> str:
    corpus = report["corpus"]
    survey = report["survey"]
    context = report["context"]
    lines = [
        "NaviOS staged-retrieval substrate benchmark",
        "=" * 45,
        f"Corpus: {corpus['documents']} documents, {corpus['cells']} cells, "
        f"{corpus['edges']} edges",
        f"Required candidate recall: {survey['required_hits']}/"
        f"{corpus['required_cells']} ({survey['required_recall']:.1%})",
        f"Required memories reached through graph hops: "
        f"{survey['multi_hop_required_hits']}",
        f"Negative-control abstention: {report['negative_control_abstained']}",
        f"Eager {context['eager_candidate_bodies']} candidate bodies: "
        f"{context['eager_candidate_body_chars']:,} chars",
        f"Body-free survey + selected bodies: "
        f"{context['staged_total_chars']:,} chars",
        f"Context reduction: {context['staged_savings_fraction']:.1%}",
        "",
        "Caveat: " + report["selection_mode"],
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--distractors", type=int, default=236)
    args = parser.parse_args()
    report = run_benchmark(distractors=args.distractors)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_format_text(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
