"""Append-only, provenance-bound proposal-cell cultivation."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Sequence

from .core import (
    DEFAULT_DB,
    DEFAULT_PROPOSALS,
    MemoryError,
    _project_relative_path,
    has_symlink_component,
    index_project,
    initialize_project,
    is_protected_path,
    load_config,
    project_output_path,
    sha256_file,
    sha256_text,
    utc_now,
)


CULTIVATION_SCHEMA = "navios-memory-cultivation-v1"
PROPOSAL_SCHEMA = "navios-memory-proposal-v1"
MAX_TITLE_CHARS = 160
MAX_BODY_CHARS = 32_000
MAX_CREATED_BY_CHARS = 160
SOURCE_HASH_RE = re.compile(r"[0-9a-f]{64}", re.IGNORECASE)
TAG_RE = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,63}", re.IGNORECASE)
ALLOWED_KINDS = {
    "contradiction",
    "correction",
    "decision",
    "relationship",
    "retrieval-lesson",
    "synthesis",
    "will-claim",
}


def _clean_single_line(value: str, *, field: str, maximum: int) -> str:
    cleaned = value.strip()
    if not cleaned or "\n" in cleaned or "\r" in cleaned:
        raise MemoryError(f"{field} must be one non-empty line")
    if len(cleaned) > maximum:
        raise MemoryError(f"{field} exceeds {maximum} characters")
    return cleaned


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return (normalized[:64].rstrip("-") or "memory-proposal")


def _parse_source_spec(raw: str) -> tuple[str, str | None]:
    value = raw.strip()
    if "::" not in value:
        return value, None
    path, expected = value.rsplit("::", 1)
    if not SOURCE_HASH_RE.fullmatch(expected.strip()):
        raise MemoryError(
            "source revisions must use PATH::SHA256 with a 64-character hash"
        )
    return path.strip(), expected.strip().casefold()


def verify_provenance_sources(
    root: Path,
    source_specs: Sequence[str],
    *,
    allow_hardlinks: bool,
) -> list[dict[str, str]]:
    if not source_specs:
        raise MemoryError("at least one provenance source is required")
    verified: dict[str, dict[str, str]] = {}
    for raw in source_specs:
        raw_path, expected_hash = _parse_source_spec(raw)
        relative = _project_relative_path(root, raw_path, field="proposal source")
        if is_protected_path(relative):
            raise MemoryError(f"protected source cannot be cultivated: {relative}")
        source = root / relative
        if not source.is_file() or has_symlink_component(root, source):
            raise MemoryError(f"proposal source is unavailable or unsafe: {relative}")
        if source.stat().st_nlink > 1 and not allow_hardlinks:
            raise MemoryError(
                f"hardlinked proposal source requires explicit opt-in: {relative}"
            )
        observed_hash = sha256_file(source)
        if expected_hash is not None and observed_hash != expected_hash:
            raise MemoryError(
                f"proposal source revision changed: {relative}; expected "
                f"{expected_hash}, observed {observed_hash}"
            )
        verified[relative] = {"path": relative, "sha256": observed_hash}
    return [verified[path] for path in sorted(verified)]


def _render_proposal(
    *,
    proposal_id: str,
    title: str,
    body: str,
    kind: str,
    created_at: str,
    created_by: str,
    confidence: float,
    tags: Sequence[str],
    sources: Sequence[dict[str, str]],
) -> str:
    links = [source["path"] for source in sources]
    lines = [
        "---",
        f"schema: {PROPOSAL_SCHEMA}",
        f"proposal_id: {proposal_id}",
        "status: proposed",
        "origin: agent-derived",
        f"kind: {kind}",
        f"created_at: {created_at}",
        f"created_by: {json.dumps(created_by)}",
        "authority: evidence-only",
        "currentness: verify-before-use",
        f"confidence: {confidence:.3f}",
        f"tags: {json.dumps(list(tags), separators=(',', ':'))}",
        f"links: {json.dumps(links, separators=(',', ':'))}",
        "source_revisions:",
    ]
    for source in sources:
        lines.extend(
            [
                f"  - path: {json.dumps(source['path'])}",
                f"    sha256: {source['sha256']}",
            ]
        )
    lines.extend(["---", "", f"# {title}", "", body, "", "## Provenance", ""])
    for source in sources:
        lines.append(f"- `{source['path']}` at `{source['sha256']}`")
    return "\n".join(lines).rstrip() + "\n"


def cultivate_proposal(
    root: Path,
    *,
    title: str,
    body: str,
    sources: Sequence[str],
    kind: str = "synthesis",
    created_by: str = "navios-memory-agent",
    confidence: float = 0.75,
    tags: Sequence[str] = (),
    created_at: str | None = None,
    rebuild_index: bool = True,
) -> dict[str, Any]:
    """Create or reuse an atomic proposal cell without modifying its sources."""
    root = root.resolve()
    initialize_project(root)
    config = load_config(root)
    title = _clean_single_line(title, field="title", maximum=MAX_TITLE_CHARS)
    created_by = _clean_single_line(
        created_by, field="created_by", maximum=MAX_CREATED_BY_CHARS
    )
    body = body.strip()
    if not body:
        raise MemoryError("proposal body must not be empty")
    if len(body) > MAX_BODY_CHARS:
        raise MemoryError(f"proposal body exceeds {MAX_BODY_CHARS} characters")
    kind = kind.strip().casefold()
    if kind not in ALLOWED_KINDS:
        raise MemoryError(
            "proposal kind must be one of: " + ", ".join(sorted(ALLOWED_KINDS))
        )
    confidence = float(confidence)
    if not 0 <= confidence <= 1:
        raise MemoryError("confidence must be between 0 and 1")
    cleaned_tags = sorted({tag.strip().casefold() for tag in tags if tag.strip()})
    invalid_tags = [tag for tag in cleaned_tags if not TAG_RE.fullmatch(tag)]
    if invalid_tags:
        raise MemoryError(f"invalid proposal tag: {invalid_tags[0]}")
    verified_sources = verify_provenance_sources(
        root,
        sources,
        allow_hardlinks=bool(config.get("allow_hardlinked_sources", False)),
    )

    identity = {
        "schema": PROPOSAL_SCHEMA,
        "title": title,
        "body": body,
        "kind": kind,
        "created_by": created_by,
        "confidence": round(confidence, 6),
        "tags": cleaned_tags,
        "sources": verified_sources,
    }
    proposal_id = sha256_text(
        json.dumps(identity, separators=(",", ":"), sort_keys=True)
    )
    proposal_directory = project_output_path(
        root, DEFAULT_PROPOSALS, field="proposal directory"
    )
    proposal_directory.mkdir(parents=True, exist_ok=True)
    if has_symlink_component(root, proposal_directory):
        raise MemoryError(
            f"proposal directory contains a symlink component: {proposal_directory}"
        )
    os.chmod(proposal_directory, 0o700)
    proposal_path = project_output_path(
        root,
        DEFAULT_PROPOSALS / f"{_slug(title)}-{proposal_id[:16]}.md",
        field="proposal cell",
    )
    timestamp = _clean_single_line(
        created_at or utc_now(), field="created_at", maximum=80
    )
    rendered = _render_proposal(
        proposal_id=proposal_id,
        title=title,
        body=body,
        kind=kind,
        created_at=timestamp,
        created_by=created_by,
        confidence=confidence,
        tags=cleaned_tags,
        sources=verified_sources,
    )
    reused = proposal_path.exists()
    if reused:
        existing = proposal_path.read_text(encoding="utf-8")
        timestamp_match = re.search(r"^created_at: ([^\r\n]+)$", existing, re.MULTILINE)
        if not timestamp_match:
            raise MemoryError(f"existing proposal is malformed: {proposal_path}")
        expected_existing = _render_proposal(
            proposal_id=proposal_id,
            title=title,
            body=body,
            kind=kind,
            created_at=timestamp_match.group(1),
            created_by=created_by,
            confidence=confidence,
            tags=cleaned_tags,
            sources=verified_sources,
        )
        if existing != expected_existing:
            raise MemoryError(f"existing proposal failed identity check: {proposal_path}")
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(proposal_path, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)

    index_report = index_project(root) if rebuild_index else None
    indexed: bool | None = None
    warning: str | None = None
    if rebuild_index:
        connection = sqlite3.connect(root / DEFAULT_DB)
        try:
            indexed = bool(
                connection.execute(
                    "SELECT 1 FROM documents WHERE path = ? LIMIT 1",
                    (proposal_path.relative_to(root).as_posix(),),
                ).fetchone()
            )
        finally:
            connection.close()
        if not indexed:
            warning = (
                "proposal was created but the current include/exclude rules do not "
                "index .navios/cells/proposals; update config and assimilate again"
            )
    return {
        "schema": CULTIVATION_SCHEMA,
        "proposal_id": proposal_id,
        "proposal_path": proposal_path.relative_to(root).as_posix(),
        "status": "proposed",
        "authority": "evidence-only",
        "reused": reused,
        "source_documents_mutated": 0,
        "indexed": indexed,
        "warning": warning,
        "sources": verified_sources,
        "index": index_report,
    }
