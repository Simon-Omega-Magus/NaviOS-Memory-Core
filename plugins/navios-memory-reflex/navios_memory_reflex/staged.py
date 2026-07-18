"""Metadata-first graph survey and selective cell hydration."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

from .core import (
    DEFAULT_DB,
    MemoryError,
    _bm25_scores,
    _graph_expand,
    decode_memory_metadata,
    load_config,
    open_index,
    project_output_path,
    tokenize,
    utc_now,
    verify_indexed_source,
)


SURVEY_SCHEMA = "navios-memory-survey-v1"
HYDRATION_SCHEMA = "navios-memory-hydration-v1"
CELL_REFERENCE_RE = re.compile(r"[0-9a-f]{12,64}", re.IGNORECASE)
MAX_CANDIDATES_PER_QUERY = 200


def _clean_queries(
    queries: Sequence[str], query_labels: Sequence[str] | None
) -> tuple[list[str], list[str]]:
    cleaned = [value.strip() for value in queries if value.strip()]
    if not cleaned:
        raise MemoryError("at least one non-empty query is required")
    if query_labels is None:
        return cleaned, cleaned
    labels = [str(value).strip() for value in query_labels]
    if len(labels) != len(cleaned) or any(not value for value in labels):
        raise MemoryError(
            "query_labels must contain one non-empty label per cleaned query"
        )
    return cleaned, labels


def survey_index(
    root: Path,
    queries: Sequence[str],
    *,
    query_labels: Sequence[str] | None = None,
    db_path: Path | None = None,
    candidates_per_query: int | None = None,
    graph_hops: int | None = None,
    minimum_score: float | None = None,
) -> dict[str, Any]:
    """Return broad graph candidates and intersections without body paragraphs."""
    root = root.resolve()
    config = load_config(root)
    retrieval = config.get("retrieval", {})
    candidates_per_query = int(
        candidates_per_query
        if candidates_per_query is not None
        else retrieval.get("survey_candidates_per_query", MAX_CANDIDATES_PER_QUERY)
    )
    graph_hops = int(
        graph_hops if graph_hops is not None else retrieval.get("graph_hops", 2)
    )
    minimum_score = float(
        minimum_score
        if minimum_score is not None
        else retrieval.get("minimum_score", 0.05)
    )
    if not 1 <= candidates_per_query <= MAX_CANDIDATES_PER_QUERY:
        raise MemoryError(
            "candidates_per_query must be between 1 and "
            f"{MAX_CANDIDATES_PER_QUERY}"
        )
    if not 0 <= graph_hops <= 8:
        raise MemoryError("graph_hops must be between 0 and 8")
    if not 0 <= minimum_score <= 1:
        raise MemoryError("minimum_score must be between 0 and 1")
    cleaned_queries, display_queries = _clean_queries(queries, query_labels)

    database = project_output_path(root, db_path or DEFAULT_DB, field="memory index")
    connection = open_index(database)
    rows = connection.execute(
        "SELECT c.cell_id, c.document_id, c.path, c.ordinal, c.start_line, "
        "c.end_line, c.heading, c.kind, c.text, c.content_sha256, "
        "c.token_count, d.content_sha256 AS document_content_sha256, "
        "d.memory_metadata_json "
        "FROM cells c JOIN documents d ON d.document_id = c.document_id"
    ).fetchall()
    rows_by_id = {row["cell_id"]: row for row in rows}
    index_digest = connection.execute(
        "SELECT value FROM meta WHERE key = 'index_digest'"
    ).fetchone()[0]
    indexed_at = connection.execute(
        "SELECT value FROM meta WHERE key = 'indexed_at'"
    ).fetchone()[0]

    evidence_by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    per_query_counts: list[int] = []
    for query_number, query in enumerate(cleaned_queries):
        lexical = _bm25_scores(rows, tokenize(query))
        if not lexical:
            per_query_counts.append(0)
            continue
        seed_limit = min(len(rows), max(candidates_per_query, 12))
        seeds = dict(
            sorted(lexical.items(), key=lambda item: (-item[1], item[0]))[
                :seed_limit
            ]
        )
        expanded, traces = _graph_expand(connection, seeds, graph_hops)
        maximum = max(expanded.values(), default=0.0)
        if not maximum:
            per_query_counts.append(0)
            continue
        ranked_query = [
            (cell_id, score / maximum)
            for cell_id, score in expanded.items()
            if score / maximum >= minimum_score
        ]
        ranked_query.sort(
            key=lambda item: (-item[1], rows_by_id[item[0]]["path"], item[0])
        )
        ranked_query = ranked_query[:candidates_per_query]
        per_query_counts.append(len(ranked_query))
        for query_rank, (cell_id, normalized_score) in enumerate(
            ranked_query, start=1
        ):
            trace = traces.get(
                cell_id,
                {
                    "hops": 0,
                    "relation": "lexical-seed",
                    "from": None,
                    "path": [],
                },
            )
            evidence_by_cell[cell_id].append(
                {
                    "query_index": query_number,
                    "query": display_queries[query_number],
                    "rank": query_rank,
                    "normalized_score": round(normalized_score, 6),
                    "graph": {
                        "hops": int(trace.get("hops", 0)),
                        "relation": trace.get("relation", "lexical-seed"),
                        "from_cell_id": trace.get("from"),
                        "path": trace.get("path", []),
                    },
                }
            )

    candidates: list[dict[str, Any]] = []
    query_count = len(cleaned_queries)
    for cell_id, evidence in evidence_by_cell.items():
        row = rows_by_id[cell_id]
        overlap_count = len(evidence)
        combined_score = sum(item["normalized_score"] for item in evidence)
        combined_score += 0.35 * max(overlap_count - 1, 0)
        combined_score += 0.15 * overlap_count / query_count
        strongest = min(
            evidence,
            key=lambda item: (
                item["graph"]["hops"],
                -item["normalized_score"],
                item["query_index"],
            ),
        )
        candidates.append(
            {
                "cell_id": cell_id,
                "score": round(combined_score, 6),
                "overlap_count": overlap_count,
                "source": {
                    "path": row["path"],
                    "start_line": row["start_line"],
                    "end_line": row["end_line"],
                    "cell_sha256": row["content_sha256"],
                    "document_sha256": row["document_content_sha256"],
                },
                "heading": row["heading"],
                "kind": row["kind"],
                "memory": decode_memory_metadata(row["memory_metadata_json"]),
                "query_evidence": sorted(
                    evidence, key=lambda item: item["query_index"]
                ),
                "best_graph": strongest["graph"],
            }
        )
    candidates.sort(
        key=lambda item: (
            -item["score"],
            -item["overlap_count"],
            item["source"]["path"],
            item["cell_id"],
        )
    )
    for rank, candidate in enumerate(candidates, start=1):
        candidate["rank"] = rank

    connection.close()
    overlap_histogram = Counter(item["overlap_count"] for item in candidates)
    abstained = not candidates
    report = {
        "schema": SURVEY_SCHEMA,
        "generated_at": utc_now(),
        "queries": display_queries,
        "abstained": abstained,
        "abstention_reason": (
            "no lexical seed matched the indexed memory" if abstained else None
        ),
        "index": {"digest": index_digest, "indexed_at": indexed_at},
        "parameters": {
            "candidates_per_query": candidates_per_query,
            "graph_hops": graph_hops,
            "minimum_score": minimum_score,
        },
        "per_query_candidate_counts": per_query_counts,
        "candidate_count": len(candidates),
        "multi_query_candidate_count": sum(
            item["overlap_count"] >= 2 for item in candidates
        ),
        "all_query_candidate_count": sum(
            item["overlap_count"] == query_count for item in candidates
        ),
        "overlap_histogram": {
            str(key): overlap_histogram[key] for key in sorted(overlap_histogram)
        },
        "candidates": candidates,
    }
    report["estimated_metadata_chars"] = len(
        json.dumps(candidates, separators=(",", ":"), sort_keys=True)
    )
    return report


def format_survey_markdown(report: dict[str, Any], *, show: int = 20) -> str:
    if show < 1:
        raise MemoryError("show must be at least 1")
    lines = [
        "# NaviOS Body-Free Memory Survey",
        "",
        "Queries: " + " | ".join(report["queries"]),
        f"Index: `{report['index']['digest'][:16]}`",
        f"Candidates: `{report['candidate_count']}`; multi-query: "
        f"`{report['multi_query_candidate_count']}`; all-query: "
        f"`{report['all_query_candidate_count']}`",
        "",
        (
            "Source body paragraphs are omitted. Paths, headings, line ranges, "
            "hashes, and graph traces remain visible metadata."
        ),
        "",
    ]
    if report.get("abstained"):
        lines.append(
            f"Abstained: {report.get('abstention_reason', 'no supported result')}"
        )
        return "\n".join(lines).rstrip() + "\n"
    for candidate in report["candidates"][:show]:
        source = candidate["source"]
        line_range = (
            str(source["start_line"])
            if source["start_line"] == source["end_line"]
            else f"{source['start_line']}-{source['end_line']}"
        )
        query_ranks = ", ".join(
            f"q{item['query_index'] + 1}=#{item['rank']}"
            for item in candidate["query_evidence"]
        )
        graph = candidate["best_graph"]
        memory = candidate.get("memory", {})
        lines.extend(
            [
                f"## {candidate['rank']}. {candidate['heading']}",
                "",
                f"Source: `{source['path']}:{line_range}`  ",
                f"Cell: `{candidate['cell_id']}`  ",
                f"Score: `{candidate['score']}`; overlap: "
                f"`{candidate['overlap_count']}`; {query_ranks}  ",
                f"Best graph path: `{graph['hops']}-hop/{graph['relation']}`",
                "Memory: "
                f"`{memory.get('origin', 'unclassified')}` / "
                f"`{memory.get('authority', 'evidence')}` / "
                f"`{memory.get('status', 'unclassified')}`; classification: "
                f"`{memory.get('classification', 'default-unclassified')}`",
                "",
            ]
        )
    hidden = max(report["candidate_count"] - min(show, report["candidate_count"]), 0)
    if hidden:
        lines.append(f"{hidden} additional metadata candidates omitted from this view.")
    return "\n".join(lines).rstrip() + "\n"


def _resolve_cell(
    connection: sqlite3.Connection, reference: str
) -> sqlite3.Row:
    cleaned = reference.strip().casefold()
    if not CELL_REFERENCE_RE.fullmatch(cleaned):
        raise MemoryError(
            "cell references must be 12-64 hexadecimal characters from a survey"
        )
    rows = connection.execute(
        "SELECT c.cell_id, c.document_id, c.path, c.ordinal, c.start_line, "
        "c.end_line, c.heading, c.kind, c.text, c.content_sha256, "
        "d.content_sha256 AS document_content_sha256, d.memory_metadata_json "
        "FROM cells c JOIN documents d ON d.document_id = c.document_id "
        "WHERE c.cell_id LIKE ? ORDER BY c.cell_id LIMIT 2",
        (cleaned + "%",),
    ).fetchall()
    if not rows:
        raise MemoryError(f"cell reference is not present in the index: {reference}")
    if len(rows) > 1:
        raise MemoryError(f"cell reference is ambiguous: {reference}")
    return rows[0]


def _render_hydration_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# NaviOS Selective Memory Hydration",
        "",
        f"Index: `{packet['index']['digest'][:16]}`",
        "",
    ]
    if packet.get("abstained"):
        lines.extend(
            [
                "No cell bodies were hydrated.",
                "",
                f"Reason: {packet.get('abstention_reason', 'no supported result')}",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"
    for result in packet["results"]:
        source = result["source"]
        memory = result.get("memory", {})
        line_range = (
            str(source["start_line"])
            if source["start_line"] == source["end_line"]
            else f"{source['start_line']}-{source['end_line']}"
        )
        lines.extend(
            [
                f"## {result['rank']}. {result['heading']}",
                "",
                f"Source: `{source['path']}:{line_range}`  ",
                f"Cell: `{result['cell_id']}`  ",
                f"Cell SHA-256: `{source['cell_sha256']}`  ",
                f"Document SHA-256: `{source['document_sha256']}`",
                "Memory: "
                f"`{memory.get('origin', 'unclassified')}` / "
                f"`{memory.get('authority', 'evidence')}` / "
                f"`{memory.get('status', 'unclassified')}`; classification: "
                f"`{memory.get('classification', 'default-unclassified')}`",
                "",
                result["text"],
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def hydrate_index(
    root: Path,
    cell_references: Sequence[str],
    *,
    db_path: Path | None = None,
    max_context_chars: int | None = None,
) -> dict[str, Any]:
    """Load only explicitly selected cells after checking source currentness."""
    root = root.resolve()
    config = load_config(root)
    retrieval = config.get("retrieval", {})
    max_context_chars = int(
        max_context_chars
        if max_context_chars is not None
        else retrieval.get("max_context_chars", 7000)
    )
    if max_context_chars < 1:
        raise MemoryError("max_context_chars must be at least 1")
    cleaned = [value.strip() for value in cell_references if value.strip()]
    if not cleaned:
        raise MemoryError("at least one cell reference is required")

    database = project_output_path(root, db_path or DEFAULT_DB, field="memory index")
    connection = open_index(database)
    index_digest = connection.execute(
        "SELECT value FROM meta WHERE key = 'index_digest'"
    ).fetchone()[0]
    indexed_at = connection.execute(
        "SELECT value FROM meta WHERE key = 'indexed_at'"
    ).fetchone()[0]
    resolved: list[sqlite3.Row] = []
    seen: set[str] = set()
    try:
        for reference in cleaned:
            row = _resolve_cell(connection, reference)
            if row["cell_id"] not in seen:
                resolved.append(row)
                seen.add(row["cell_id"])

        verified_documents: set[str] = set()
        allow_hardlinks = bool(config.get("allow_hardlinked_sources", False))
        for row in resolved:
            if row["path"] in verified_documents:
                continue
            verify_indexed_source(
                root,
                row["path"],
                row["document_content_sha256"],
                allow_hardlinks=allow_hardlinks,
            )
            verified_documents.add(row["path"])
    except Exception:
        connection.close()
        raise
    connection.close()

    base = {
        "schema": HYDRATION_SCHEMA,
        "generated_at": utc_now(),
        "abstained": False,
        "abstention_reason": None,
        "index": {"digest": index_digest, "indexed_at": indexed_at},
        "max_context_chars": max_context_chars,
    }
    results: list[dict[str, Any]] = []
    used_chars = 0
    for row in resolved:
        result = {
            "rank": len(results) + 1,
            "cell_id": row["cell_id"],
            "source": {
                "path": row["path"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "cell_sha256": row["content_sha256"],
                "document_sha256": row["document_content_sha256"],
            },
            "heading": row["heading"],
            "kind": row["kind"],
            "memory": decode_memory_metadata(row["memory_metadata_json"]),
            "text": row["text"],
        }
        candidate_results = [*results, result]
        projected = len(
            _render_hydration_markdown({**base, "results": candidate_results})
        )
        if projected > max_context_chars:
            continue
        results.append(result)
        used_chars = projected
    if not results:
        return {
            **base,
            "abstained": True,
            "abstention_reason": (
                "selected cells exceeded the context budget; no partial cell was loaded"
            ),
            "results": [],
            "estimated_context_chars": 0,
        }
    return {**base, "results": results, "estimated_context_chars": used_chars}


def format_hydration_markdown(packet: dict[str, Any]) -> str:
    rendered = _render_hydration_markdown(packet)
    budget = packet.get("max_context_chars")
    if budget is not None and len(rendered) > int(budget):
        raise MemoryError(
            f"formatted hydration is {len(rendered)} characters; budget is {budget}"
        )
    return rendered
