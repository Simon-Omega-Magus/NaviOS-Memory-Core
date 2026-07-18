"""Append-only human-will coherence questions with exact provenance."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from .core import (
    MemoryError,
    has_symlink_component,
    initialize_project,
    load_config,
    project_output_path,
    sha256_text,
    utc_now,
)
from .cultivation import verify_provenance_sources


WILL_QUESTION_SCHEMA = "navios-will-coherence-question-v1"
WILL_QUEUE_SCHEMA = "navios-will-coherence-queue-v1"
DEFAULT_WILL_QUESTIONS = Path(".navios/will/questions")
CLAIM_ID_RE = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,199}", re.IGNORECASE)
MAX_QUESTION_CHARS = 2_000
MAX_SCOPE_CHARS = 400
MAX_DETAIL_CHARS = 4_000
MAX_CREATED_BY_CHARS = 160
QUESTION_FIELDS = {
    "schema",
    "question_id",
    "status",
    "created_at",
    "created_by",
    "claims",
    "question",
    "scope",
    "proposed_interpretation",
    "blocked_action",
    "directional_effect",
    "execution_effect",
    "age_decay",
    "question_hash",
}


def _single_line(value: str, *, field: str, maximum: int) -> str:
    cleaned = value.strip()
    if not cleaned or "\n" in cleaned or "\r" in cleaned:
        raise MemoryError(f"{field} must be one non-empty line")
    if len(cleaned) > maximum:
        raise MemoryError(f"{field} exceeds {maximum} characters")
    return cleaned


def _bounded_detail(value: str | None, *, field: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_DETAIL_CHARS:
        raise MemoryError(f"{field} exceeds {MAX_DETAIL_CHARS} characters")
    return cleaned


def _canonical(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _aware_timestamp(value: str) -> bool:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except (AttributeError, ValueError):
        return False


def _validated_claim_ids(values: Sequence[str]) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise MemoryError("claim IDs must be a sequence")
    if any(not isinstance(value, str) for value in values):
        raise MemoryError("claim IDs must be strings")
    claims: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            claims.append(cleaned)
            seen.add(cleaned)
    if len(claims) < 2:
        raise MemoryError("a coherence question requires at least two distinct claim IDs")
    invalid = [value for value in claims if not CLAIM_ID_RE.fullmatch(value)]
    if invalid:
        raise MemoryError(f"invalid claim ID: {invalid[0]}")
    return claims


def _question_body(
    *,
    question_id: str,
    created_at: str,
    created_by: str,
    claims: Sequence[dict[str, Any]],
    question: str,
    scope: str,
    proposed_interpretation: str | None,
    blocked_action: str | None,
) -> dict[str, Any]:
    return {
        "schema": WILL_QUESTION_SCHEMA,
        "question_id": question_id,
        "status": "open",
        "created_at": created_at,
        "created_by": created_by,
        "claims": list(claims),
        "question": question,
        "scope": scope,
        "proposed_interpretation": proposed_interpretation,
        "blocked_action": blocked_action,
        "directional_effect": "preserve-all-cited-claims-pending-resolution",
        "execution_effect": "none",
        "age_decay": False,
    }


def _validate_question(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != WILL_QUESTION_SCHEMA:
        raise MemoryError("will-coherence question has an unsupported schema")
    if set(value) != QUESTION_FIELDS:
        raise MemoryError("will-coherence question fields do not match its schema")
    if not _aware_timestamp(value.get("created_at")):
        raise MemoryError("will-coherence question has an invalid created_at timestamp")
    claims = value.get("claims")
    if not isinstance(claims, list):
        raise MemoryError("will-coherence question claims must be a list")
    claim_ids = _validated_claim_ids(
        [claim.get("claim_id", "") for claim in claims if isinstance(claim, dict)]
    )
    if len(claim_ids) != len(claims):
        raise MemoryError("will-coherence claims must have distinct IDs")
    source_keys: set[tuple[str, str]] = set()
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {"claim_id", "source"}:
            raise MemoryError("will-coherence claim has an invalid schema")
        source = claim.get("source")
        if (
            not isinstance(source, dict)
            or set(source) != {"path", "sha256"}
            or not isinstance(source.get("path"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", "")))
        ):
            raise MemoryError("will-coherence claim lacks an exact source revision")
        source_keys.add((source["path"], source["sha256"]))
    if len(source_keys) != len(claims):
        raise MemoryError("each will-coherence claim requires a distinct source revision")
    expected = value.get("question_hash")
    if not isinstance(expected, str):
        raise MemoryError("will-coherence question is missing its content hash")
    unsigned = dict(value)
    unsigned.pop("question_hash", None)
    if expected != sha256_text(_canonical(unsigned)):
        raise MemoryError("will-coherence question failed its content-hash check")
    if value.get("status") != "open":
        raise MemoryError("will-coherence question status must remain open")
    if value.get("directional_effect") != "preserve-all-cited-claims-pending-resolution":
        raise MemoryError("will-coherence question changed cited-claim disposition")
    if value.get("execution_effect") != "none" or value.get("age_decay") is not False:
        raise MemoryError("will-coherence question changed its safety invariants")
    return value


def queue_will_question(
    root: Path,
    *,
    claim_ids: Sequence[str],
    question: str,
    scope: str,
    sources: Sequence[str],
    created_by: str = "navios-memory-agent",
    proposed_interpretation: str | None = None,
    blocked_action: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Queue one bounded conflict question without downgrading either claim."""
    root = root.resolve()
    initialize_project(root)
    config = load_config(root)
    claims = _validated_claim_ids(claim_ids)
    question = _single_line(
        question, field="question", maximum=MAX_QUESTION_CHARS
    )
    scope = _single_line(scope, field="scope", maximum=MAX_SCOPE_CHARS)
    created_by = _single_line(
        created_by, field="created_by", maximum=MAX_CREATED_BY_CHARS
    )
    proposed_interpretation = _bounded_detail(
        proposed_interpretation, field="proposed_interpretation"
    )
    blocked_action = _bounded_detail(blocked_action, field="blocked_action")
    verified_sources: list[dict[str, str]] = []
    source_keys: set[tuple[str, str]] = set()
    for source_spec in sources:
        source = verify_provenance_sources(
            root,
            [source_spec],
            allow_hardlinks=bool(config.get("allow_hardlinked_sources", False)),
        )[0]
        key = (source["path"], source["sha256"])
        if key in source_keys:
            raise MemoryError("each claim requires a distinct source revision")
        source_keys.add(key)
        verified_sources.append(source)
    if len(claims) != len(verified_sources):
        raise MemoryError(
            "each claim ID must have one distinct --source revision"
        )
    claim_records = sorted(
        [
            {"claim_id": claim_id, "source": source}
            for claim_id, source in zip(claims, verified_sources, strict=True)
        ],
        key=lambda claim: claim["claim_id"],
    )
    identity = {
        "schema": WILL_QUESTION_SCHEMA,
        "claims": claim_records,
        "question": question,
        "scope": scope,
        "proposed_interpretation": proposed_interpretation,
        "blocked_action": blocked_action,
    }
    question_id = "will-question:" + sha256_text(_canonical(identity))
    timestamp = _single_line(
        created_at or utc_now(), field="created_at", maximum=80
    )
    if not _aware_timestamp(timestamp):
        raise MemoryError("created_at must be a timezone-aware ISO-8601 timestamp")
    body = _question_body(
        question_id=question_id,
        created_at=timestamp,
        created_by=created_by,
        claims=claim_records,
        question=question,
        scope=scope,
        proposed_interpretation=proposed_interpretation,
        blocked_action=blocked_action,
    )
    body["question_hash"] = sha256_text(_canonical(body))

    directory = project_output_path(
        root, DEFAULT_WILL_QUESTIONS, field="will-coherence question directory"
    )
    directory.mkdir(parents=True, exist_ok=True)
    if has_symlink_component(root, directory):
        raise MemoryError(
            f"will-coherence question directory contains a symlink: {directory}"
        )
    os.chmod(directory, 0o700)
    path = project_output_path(
        root,
        DEFAULT_WILL_QUESTIONS / f"{question_id.removeprefix('will-question:')[:24]}.json",
        field="will-coherence question",
    )
    reused = path.exists()
    if reused:
        if path.stat().st_nlink != 1:
            raise MemoryError(f"will question must not have hardlink aliases: {path}")
        try:
            existing = _validate_question(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise MemoryError(f"cannot validate existing will question {path}: {exc}") from exc
        comparable = dict(existing)
        comparable["created_at"] = timestamp
        comparable["created_by"] = created_by
        comparable["question_hash"] = body["question_hash"]
        if comparable != body:
            raise MemoryError(f"existing will question failed identity check: {path}")
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(body, handle, indent=2, sort_keys=True)
            handle.write("\n")

    return {
        "schema": WILL_QUEUE_SCHEMA,
        "question_id": question_id,
        "question_path": path.relative_to(root).as_posix(),
        "status": "open",
        "reused": reused,
        "directional_effect": body["directional_effect"],
        "execution_effect": "none",
        "source_documents_mutated": 0,
        "sources": verified_sources,
    }


def list_will_questions(root: Path) -> dict[str, Any]:
    """Return the validated open queue without interpreting or resolving it."""
    root = root.resolve()
    directory = project_output_path(
        root, DEFAULT_WILL_QUESTIONS, field="will-coherence question directory"
    )
    if not directory.exists():
        return {"schema": WILL_QUEUE_SCHEMA, "open_count": 0, "questions": []}
    if not directory.is_dir() or has_symlink_component(root, directory):
        raise MemoryError(f"unsafe will-coherence question directory: {directory}")
    config = load_config(root)
    questions: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise MemoryError(f"unsafe will-coherence question file: {path}")
        try:
            question = _validate_question(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise MemoryError(f"cannot read will-coherence question {path}: {exc}") from exc
        source_specs = [
            f"{claim['source']['path']}::{claim['source']['sha256']}"
            for claim in question["claims"]
        ]
        verify_provenance_sources(
            root,
            source_specs,
            allow_hardlinks=bool(config.get("allow_hardlinked_sources", False)),
        )
        questions.append(question)
    return {
        "schema": WILL_QUEUE_SCHEMA,
        "open_count": len(questions),
        "questions": questions,
    }
