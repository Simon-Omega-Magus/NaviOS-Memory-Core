"""Dependency-light, local-first cognitive memory indexing and retrieval."""

from __future__ import annotations

import fnmatch
import hashlib
import heapq
import json
import math
import os
import re
import sqlite3
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


INDEX_SCHEMA = "navios-memory-index-v2"
PACKET_SCHEMA = "navios-memory-context-packet-v1"
ASSIMILATION_SCHEMA = "navios-memory-assimilation-v1"
DEFAULT_DB = Path(".navios/memory.sqlite3")
DEFAULT_CONFIG = Path(".navios/config.json")
DEFAULT_CHECKPOINT = Path(".navios/checkpoint.md")
DEFAULT_RELATIONSHIPS = Path(".navios/relationships.json")
DEFAULT_PROPOSALS = Path(".navios/cells/proposals")
RELATIONSHIPS_SCHEMA = "navios-memory-relationships-v1"
SUPPORTED_SUFFIXES = {
    ".md",
    ".txt",
    ".rst",
    ".py",
    ".js",
    ".ts",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
}
DEFAULT_IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
}
PROTECTED_NAME_PARTS = {
    ".env",
    "credential",
    "credentials",
    "id_rsa",
    "id_ed25519",
    "private-key",
    "private_key",
    "secret",
    "secrets",
    "token",
    "tokens",
}
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "with",
}
WORD_RE = re.compile(r"[a-z0-9][a-z0-9_./:-]*", re.IGNORECASE)
FRONTMATTER_LIST_RE = re.compile(r"^\s*(tags|links)\s*:\s*\[(.*)]\s*$", re.IGNORECASE)
FRONTMATTER_SCALAR_RE = re.compile(
    r"^\s*([a-z0-9_-]+)\s*:\s*([^\r\n]*)$", re.IGNORECASE
)
MARKDOWN_LINK_RE = re.compile(r"\[[^]]*]\(([^)]+)\)")
WIKILINK_RE = re.compile(r"\[\[([^]|#]+)")
RELATION_RE = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,63}", re.IGNORECASE)
MEMORY_METADATA_KEYS = {
    "authority",
    "confidence",
    "created_at",
    "created_by",
    "currentness",
    "expires_at",
    "kind",
    "origin",
    "proposal_id",
    "schema",
    "scope",
    "status",
    "valid_from",
}


class MemoryError(RuntimeError):
    """Raised when a memory operation cannot be completed safely."""


@dataclass(frozen=True)
class Cell:
    cell_id: str
    document_id: str
    path: str
    ordinal: int
    start_line: int
    end_line: int
    heading: str
    kind: str
    text: str
    content_sha256: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tokenize(value: str) -> list[str]:
    return [
        token.casefold()
        for token in WORD_RE.findall(value)
        if token.casefold() not in STOPWORDS and len(token) > 1
    ]


def find_project_root(start: Path | str) -> Path:
    path = Path(start).expanduser().resolve()
    if path.is_file():
        path = path.parent
    for candidate in (path, *path.parents):
        if (candidate / ".navios").exists() or (candidate / ".git").exists():
            return candidate
    return path


def default_config() -> dict[str, Any]:
    return {
        "schema": "navios-memory-config-v1",
        "include": ["**/*.md", "**/*.txt", "**/*.rst"],
        "exclude": [
            ".git/**",
            ".navios/memory.sqlite3",
            "**/.env*",
            "**/*credential*",
            "**/*secret*",
            "**/*token*",
        ],
        "max_file_bytes": 524288,
        "allow_hardlinked_sources": False,
        "relationship_overlay": DEFAULT_RELATIONSHIPS.as_posix(),
        "retrieval": {
            "top_k": 8,
            "graph_hops": 2,
            "max_context_chars": 7000,
            "minimum_score": 0.05,
            "survey_candidates_per_query": 200,
        },
    }


def initialize_project(root: Path) -> list[Path]:
    root = root.resolve()
    navios = project_output_path(root, Path(".navios"), field="memory directory")
    navios.mkdir(parents=True, exist_ok=True)
    if not navios.is_dir() or has_symlink_component(root, navios):
        raise MemoryError(f"memory directory must be an in-project directory: {navios}")
    os.chmod(navios, 0o700)
    created: list[Path] = []
    config_path = project_output_path(root, DEFAULT_CONFIG, field="memory config")
    if not config_path.exists():
        config_path.write_text(
            json.dumps(default_config(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        created.append(config_path)
    checkpoint_path = project_output_path(
        root, DEFAULT_CHECKPOINT, field="memory checkpoint"
    )
    if not checkpoint_path.exists():
        checkpoint_path.write_text(
            "# Authoritative Checkpoint\n\n"
            "## Objective\n\nDescribe the accepted objective.\n\n"
            "## Current State\n\nRecord verified progress.\n\n"
            "## Constraints\n\nRecord safety and behavioral constraints.\n\n"
            "## Next Action\n\nRecord the next bounded action.\n",
            encoding="utf-8",
        )
        created.append(checkpoint_path)
    relationships_path = project_output_path(
        root, DEFAULT_RELATIONSHIPS, field="relationship overlay"
    )
    if not relationships_path.exists():
        relationships_path.write_text(
            json.dumps(
                {"schema": RELATIONSHIPS_SCHEMA, "relations": []},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        created.append(relationships_path)
    ignore_path = project_output_path(
        root, Path(".naviosignore"), field="memory ignore file"
    )
    if not ignore_path.exists():
        ignore_path.write_text(
            ".git/**\n.navios/memory.sqlite3\n**/.env*\n"
            "**/*credential*\n**/*secret*\n**/*token*\n",
            encoding="utf-8",
        )
        created.append(ignore_path)
    return created


def load_config(root: Path) -> dict[str, Any]:
    path = root / DEFAULT_CONFIG
    if not path.exists():
        return default_config()
    require_unaliased_control_file(root, path, field="config")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MemoryError(f"invalid config {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MemoryError(f"config must be a JSON object: {path}")
    return value


def load_ignore_patterns(root: Path, config: dict[str, Any]) -> list[str]:
    patterns = [str(item) for item in config.get("exclude", [])]
    ignore_path = root / ".naviosignore"
    if ignore_path.is_file():
        require_unaliased_control_file(
            root, ignore_path, field="ignore configuration"
        )
        for line in ignore_path.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                patterns.append(value)
    return patterns


def is_protected_path(relative_path: str) -> bool:
    parts = [part.casefold() for part in Path(relative_path).parts]
    return any(
        protected in part
        for part in parts
        for protected in PROTECTED_NAME_PARTS
    )


def path_matches(relative_path: str, patterns: Sequence[str]) -> bool:
    normalized = relative_path.replace(os.sep, "/")
    for pattern in patterns:
        candidates = [pattern]
        if "**/" in pattern:
            candidates.append(pattern.replace("**/", ""))
        if any(
            fnmatch.fnmatch(normalized, candidate)
            or Path(normalized).match(candidate)
            for candidate in candidates
        ):
            return True
    return False


def has_symlink_component(root: Path, path: Path) -> bool:
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def require_unaliased_control_file(root: Path, path: Path, *, field: str) -> None:
    """Reject mutable control files reachable through symlinks or hardlinks."""
    if not path.is_file() or has_symlink_component(root, path):
        raise MemoryError(f"{field} must be a regular in-project file: {path}")
    try:
        links = path.stat().st_nlink
    except OSError as exc:
        raise MemoryError(f"cannot inspect {field}: {path}: {exc}") from exc
    if links != 1:
        raise MemoryError(f"{field} must not have hardlink aliases: {path}")


def project_output_path(root: Path, raw: Path, *, field: str) -> Path:
    """Return a lexically in-project output path without following symlinks."""
    root = root.resolve()
    candidate = raw.expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise MemoryError(f"{field} must stay inside the project: {raw}") from exc
    if relative == Path("."):
        raise MemoryError(f"{field} must not replace the project root")
    if has_symlink_component(root, candidate):
        raise MemoryError(f"{field} contains a symlink component: {candidate}")
    return candidate


def verify_indexed_source(
    root: Path,
    relative_path: str,
    expected_sha256: str,
    *,
    allow_hardlinks: bool,
) -> Path:
    """Fail closed unless an indexed source still matches its exact byte revision."""
    relative = _project_relative_path(root, relative_path, field="indexed source path")
    source = root / relative
    try:
        matches = (
            source.is_file()
            and not has_symlink_component(root, source)
            and (allow_hardlinks or source.stat().st_nlink == 1)
            and sha256_file(source) == expected_sha256
        )
    except (OSError, ValueError) as exc:
        raise MemoryError(
            f"cannot verify indexed source path: {relative_path}: {exc}"
        ) from exc
    if not matches:
        raise MemoryError(
            "source changed or became unavailable since indexing: "
            f"{relative_path}; run navios-memory assimilate again"
        )
    return source


def iter_source_files(root: Path, config: dict[str, Any]) -> Iterator[Path]:
    includes = [str(item) for item in config.get("include", ["**/*.md"])]
    excludes = load_ignore_patterns(root, config)
    max_bytes = int(config.get("max_file_bytes", 524288))
    allow_hardlinks = bool(config.get("allow_hardlinked_sources", False))
    for path in sorted(root.rglob("*")):
        if not path.is_file() or has_symlink_component(root, path):
            continue
        relative = path.relative_to(root).as_posix()
        if any(part in DEFAULT_IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix.casefold() not in SUPPORTED_SUFFIXES:
            continue
        if not path_matches(relative, includes):
            continue
        if path_matches(relative, excludes) or is_protected_path(relative):
            continue
        stat = path.stat()
        if stat.st_size > max_bytes:
            continue
        if stat.st_nlink > 1 and not allow_hardlinks:
            continue
        yield path


def parse_frontmatter(lines: Sequence[str]) -> tuple[list[str], list[str]]:
    if not lines or lines[0].strip() != "---":
        return [], []
    tags: list[str] = []
    links: list[str] = []
    for line in lines[1:80]:
        if line.strip() == "---":
            break
        match = FRONTMATTER_LIST_RE.match(line)
        if not match:
            continue
        values = [
            item.strip().strip("'\"")
            for item in match.group(2).split(",")
            if item.strip()
        ]
        if match.group(1).casefold() == "tags":
            tags.extend(values)
        else:
            links.extend(values)
    return sorted(set(tags)), sorted(set(links))


def parse_memory_metadata(lines: Sequence[str], relative_path: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "origin": "unclassified",
        "authority": "evidence",
        "status": "unclassified",
        "kind": "source",
        "classification": "default-unclassified",
    }
    if lines and lines[0].strip() == "---":
        declared: dict[str, Any] = {}
        for line in lines[1:80]:
            if line.strip() == "---":
                break
            match = FRONTMATTER_SCALAR_RE.match(line)
            if not match:
                continue
            key = match.group(1).casefold()
            if key not in MEMORY_METADATA_KEYS or key in {"tags", "links"}:
                continue
            raw = match.group(2).strip()
            if len(raw) > 256:
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = raw.strip("'\"")
            if isinstance(value, (str, int, float, bool)) or value is None:
                declared[key] = value
        if declared:
            metadata.update(declared)
            metadata["classification"] = "source-declared-unverified"
    proposal_prefix = DEFAULT_PROPOSALS.as_posix() + "/"
    if relative_path.startswith(proposal_prefix):
        metadata.update(
            {
                "origin": "agent-derived",
                "authority": "evidence-only",
                "status": "proposed",
                "classification": "proposal-path-enforced",
            }
        )
    return metadata


def extract_links(text: str, frontmatter_links: Sequence[str]) -> list[str]:
    links = list(frontmatter_links)
    links.extend(MARKDOWN_LINK_RE.findall(text))
    links.extend(WIKILINK_RE.findall(text))
    return sorted(
        {
            item.split("#", 1)[0].strip()
            for item in links
            if item.strip() and "://" not in item
        }
    )


def split_cells(relative_path: str, text: str, document_id: str) -> list[Cell]:
    lines = text.splitlines()
    cells: list[Cell] = []
    heading = Path(relative_path).name
    buffer: list[tuple[int, str]] = []

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        content = "\n".join(value.rstrip() for _, value in buffer).strip()
        if not content or content == "---":
            buffer = []
            return
        start_line = buffer[0][0]
        end_line = buffer[-1][0]
        content_hash = sha256_text(content)
        ordinal = len(cells)
        cell_id = sha256_text(
            f"{relative_path}\0{start_line}\0{end_line}\0{content_hash}"
        )
        sentence_count = len(re.findall(r"[.!?](?:\s|$)", content))
        kind = "sentence" if sentence_count <= 1 and "\n" not in content else "passage"
        cells.append(
            Cell(
                cell_id=cell_id,
                document_id=document_id,
                path=relative_path,
                ordinal=ordinal,
                start_line=start_line,
                end_line=end_line,
                heading=heading,
                kind=kind,
                text=content,
                content_sha256=content_hash,
            )
        )
        buffer = []

    in_frontmatter = bool(lines and lines[0].strip() == "---")
    frontmatter_closed = not in_frontmatter
    for line_number, line in enumerate(lines, start=1):
        if in_frontmatter and not frontmatter_closed:
            if line_number > 1 and line.strip() == "---":
                frontmatter_closed = True
            continue
        if line.startswith("#"):
            flush()
            heading = line.lstrip("#").strip() or heading
            continue
        if not line.strip():
            flush()
            continue
        buffer.append((line_number, line))
    flush()
    return cells


def connect(
    edges: dict[tuple[str, str, str], float],
    source: str,
    target: str,
    relation: str,
    weight: float,
) -> None:
    if source == target:
        return
    key = (source, target, relation)
    edges[key] = max(edges.get(key, 0.0), weight)


def _project_relative_path(root: Path, raw: Any, *, field: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise MemoryError(f"{field} must be a non-empty relative path")
    candidate = Path(raw.strip())
    if candidate.is_absolute() or ".." in candidate.parts:
        raise MemoryError(f"{field} must stay inside the project: {raw!r}")
    normalized = Path(os.path.normpath(candidate.as_posix()))
    if normalized == Path(".") or ".." in normalized.parts:
        raise MemoryError(f"{field} must identify a project file: {raw!r}")
    return normalized.as_posix()


def load_relationship_overlay(
    root: Path,
    config: dict[str, Any],
    document_by_path: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    raw_overlay = config.get(
        "relationship_overlay", DEFAULT_RELATIONSHIPS.as_posix()
    )
    relative_overlay = _project_relative_path(
        root, raw_overlay, field="relationship_overlay"
    )
    overlay_path = root / relative_overlay
    if not overlay_path.exists():
        return [], None
    require_unaliased_control_file(
        root, overlay_path, field="relationship overlay"
    )
    try:
        value = json.loads(overlay_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MemoryError(f"invalid relationship overlay {overlay_path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != RELATIONSHIPS_SCHEMA:
        raise MemoryError(
            f"unsupported relationship overlay schema: {overlay_path}"
        )
    raw_relations = value.get("relations")
    if not isinstance(raw_relations, list):
        raise MemoryError(f"relationship overlay relations must be a list: {overlay_path}")

    relations: list[dict[str, Any]] = []
    for index, raw_relation in enumerate(raw_relations):
        if not isinstance(raw_relation, dict):
            raise MemoryError(f"relationship {index} must be an object")
        source = _project_relative_path(
            root, raw_relation.get("source"), field=f"relationship {index} source"
        )
        target = _project_relative_path(
            root, raw_relation.get("target"), field=f"relationship {index} target"
        )
        relation = raw_relation.get("relation")
        if not isinstance(relation, str) or not RELATION_RE.fullmatch(relation):
            raise MemoryError(
                f"relationship {index} relation must match {RELATION_RE.pattern}"
            )
        weight = raw_relation.get("weight", 1.0)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise MemoryError(f"relationship {index} weight must be numeric")
        normalized_weight = float(weight)
        if not math.isfinite(normalized_weight) or not 0 < normalized_weight <= 1:
            raise MemoryError(
                f"relationship {index} weight must be greater than 0 and at most 1"
            )
        if source not in document_by_path or target not in document_by_path:
            missing = source if source not in document_by_path else target
            raise MemoryError(
                f"relationship {index} references an unindexed exact path: {missing}"
            )
        relations.append(
            {
                "source": source,
                "target": target,
                "relation": relation.casefold(),
                "weight": normalized_weight,
            }
        )
    relations.sort(
        key=lambda item: (
            item["source"],
            item["target"],
            item["relation"],
            item["weight"],
        )
    )
    canonical = json.dumps(relations, separators=(",", ":"), sort_keys=True)
    return relations, sha256_text(canonical)


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE documents (
            document_id TEXT PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            links_json TEXT NOT NULL,
            memory_metadata_json TEXT NOT NULL
        );
        CREATE TABLE cells (
            cell_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(document_id),
            path TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            heading TEXT NOT NULL,
            kind TEXT NOT NULL,
            text TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            token_count INTEGER NOT NULL
        );
        CREATE TABLE edges (
            source_cell_id TEXT NOT NULL REFERENCES cells(cell_id),
            target_cell_id TEXT NOT NULL REFERENCES cells(cell_id),
            relation TEXT NOT NULL,
            weight REAL NOT NULL,
            PRIMARY KEY (source_cell_id, target_cell_id, relation)
        );
        CREATE INDEX cells_path_idx ON cells(path);
        CREATE INDEX edges_source_idx ON edges(source_cell_id);
        CREATE INDEX edges_target_idx ON edges(target_cell_id);
        """
    )


def index_project(root: Path, db_path: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    config = load_config(root)
    destination = project_output_path(
        root, db_path or DEFAULT_DB, field="memory index"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if has_symlink_component(root, destination):
        raise MemoryError(f"memory index contains a symlink component: {destination}")
    os.chmod(destination.parent, 0o700)
    documents: list[dict[str, Any]] = []
    all_cells: list[Cell] = []
    for path in iter_source_files(root, config):
        relative = path.relative_to(root).as_posix()
        try:
            raw_content = path.read_bytes()
            text = raw_content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        content_sha = sha256_bytes(raw_content)
        document_id = sha256_text(relative)
        lines = text.splitlines()
        tags, frontmatter_links = parse_frontmatter(lines)
        title = next(
            (line.lstrip("#").strip() for line in lines if line.startswith("#")),
            path.name,
        )
        cells = split_cells(relative, text, document_id)
        if not cells:
            continue
        documents.append(
            {
                "document_id": document_id,
                "path": relative,
                "title": title,
                "content_sha256": content_sha,
                "tags": tags,
                "links": extract_links(text, frontmatter_links),
                "memory_metadata": parse_memory_metadata(lines, relative),
                "cells": cells,
            }
        )
        all_cells.extend(cells)

    edges: dict[tuple[str, str, str], float] = {}
    document_by_path = {item["path"]: item for item in documents}
    overlay_relations, overlay_digest = load_relationship_overlay(
        root, config, document_by_path
    )
    basename_paths: dict[str, list[str]] = defaultdict(list)
    tags_to_documents: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in documents:
        basename_paths[Path(document["path"]).name].append(document["path"])
        for tag in document["tags"]:
            tags_to_documents[tag.casefold()].append(document)
        cells = document["cells"]
        for left, right in zip(cells, cells[1:]):
            connect(edges, left.cell_id, right.cell_id, "sequence", 0.86)
            connect(edges, right.cell_id, left.cell_id, "sequence", 0.86)
            if left.heading == right.heading:
                connect(edges, left.cell_id, right.cell_id, "same-heading", 0.92)
                connect(edges, right.cell_id, left.cell_id, "same-heading", 0.92)

    for document in documents:
        source = document["cells"][0].cell_id
        source_parent = Path(document["path"]).parent
        for raw_link in document["links"]:
            candidate = (source_parent / raw_link).as_posix()
            targets = []
            if candidate in document_by_path:
                targets = [candidate]
            elif raw_link in document_by_path:
                targets = [raw_link]
            else:
                basename_matches = basename_paths.get(Path(raw_link).name, [])
                targets = basename_matches if len(basename_matches) == 1 else []
            for target_path in targets:
                target = document_by_path[target_path]["cells"][0].cell_id
                connect(edges, source, target, "explicit-link", 1.0)
                connect(edges, target, source, "backlink", 0.78)

    for tagged_documents in tags_to_documents.values():
        ordered = sorted(tagged_documents, key=lambda item: item["path"])
        for left, right in zip(ordered, ordered[1:]):
            left_cell = left["cells"][0].cell_id
            right_cell = right["cells"][0].cell_id
            connect(edges, left_cell, right_cell, "shared-tag", 0.72)
            connect(edges, right_cell, left_cell, "shared-tag", 0.72)

    for overlay in overlay_relations:
        source = document_by_path[overlay["source"]]["cells"][0].cell_id
        target = document_by_path[overlay["target"]]["cells"][0].cell_id
        connect(
            edges,
            source,
            target,
            f"overlay:{overlay['relation']}",
            overlay["weight"],
        )

    descriptor, temp_name = tempfile.mkstemp(
        prefix=".memory.", suffix=".sqlite3", dir=destination.parent
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(temp_path)
        create_schema(connection)
        indexed_at = utc_now()
        index_digest = sha256_text(
            "\n".join(
                f"{item['path']}:{item['content_sha256']}" for item in documents
            )
            + f"\noverlay:{overlay_digest or 'none'}"
        )
        connection.executemany(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            [
                ("schema", INDEX_SCHEMA),
                ("indexed_at", indexed_at),
                ("project_root", str(root)),
                ("index_digest", index_digest),
                ("relationship_overlay_sha256", overlay_digest or "none"),
                ("relationship_count", str(len(overlay_relations))),
            ],
        )
        for document in documents:
            connection.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    document["document_id"],
                    document["path"],
                    document["title"],
                    document["content_sha256"],
                    json.dumps(document["tags"], separators=(",", ":")),
                    json.dumps(document["links"], separators=(",", ":")),
                    json.dumps(
                        document["memory_metadata"],
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )
        connection.executemany(
            "INSERT INTO cells VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    cell.cell_id,
                    cell.document_id,
                    cell.path,
                    cell.ordinal,
                    cell.start_line,
                    cell.end_line,
                    cell.heading,
                    cell.kind,
                    cell.text,
                    cell.content_sha256,
                    len(tokenize(cell.text)),
                )
                for cell in all_cells
            ],
        )
        connection.executemany(
            "INSERT INTO edges VALUES (?, ?, ?, ?)",
            [(*key, weight) for key, weight in sorted(edges.items())],
        )
        connection.commit()
        connection.close()
        connection = None
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, destination)
    finally:
        if connection is not None:
            connection.close()
        if temp_path.exists():
            temp_path.unlink()
    return {
        "schema": INDEX_SCHEMA,
        "project_root": str(root),
        "database": str(destination),
        "documents": len(documents),
        "cells": len(all_cells),
        "edges": len(edges),
        "overlay_relations": len(overlay_relations),
        "source_mode": "read-only",
        "index_digest": index_digest,
        "indexed_at": indexed_at,
    }


def assimilate_project(root: Path) -> dict[str, Any]:
    """Derive a replaceable cell graph from ordinary files without editing them."""
    root = root.resolve()
    created = initialize_project(root)
    report = index_project(root)
    return {
        "schema": ASSIMILATION_SCHEMA,
        "project_root": str(root),
        "created": [path.relative_to(root).as_posix() for path in created],
        "source_mode": "read-only",
        "source_documents_mutated": 0,
        "index": report,
    }


def open_index(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise MemoryError(f"memory index not found: {db_path}; run index first")
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        schema_row = connection.execute(
            "SELECT value FROM meta WHERE key = 'schema'"
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        if connection is not None:
            connection.close()
        raise MemoryError(f"invalid memory index {db_path}: {exc}") from exc
    if not schema_row or schema_row[0] != INDEX_SCHEMA:
        connection.close()
        raise MemoryError(f"unsupported memory index schema: {db_path}")
    return connection


def decode_memory_metadata(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MemoryError("memory index contains invalid authority metadata") from exc
    if not isinstance(value, dict):
        raise MemoryError("memory authority metadata must be an object")
    return value


def _bm25_scores(
    rows: Sequence[sqlite3.Row], query_tokens: Sequence[str]
) -> dict[str, float]:
    tokenized = {row["cell_id"]: tokenize(row["text"]) for row in rows}
    if not query_tokens or not tokenized:
        return {}
    document_frequency: Counter[str] = Counter()
    for tokens in tokenized.values():
        document_frequency.update(set(tokens))
    average_length = sum(len(tokens) for tokens in tokenized.values()) / len(tokenized)
    scores: dict[str, float] = {}
    total = len(tokenized)
    k1 = 1.5
    b = 0.75
    for cell_id, tokens in tokenized.items():
        frequencies = Counter(tokens)
        score = 0.0
        for term in query_tokens:
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            df = document_frequency.get(term, 0)
            inverse = math.log(1 + (total - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (
                1 - b + b * len(tokens) / max(average_length, 1.0)
            )
            score += inverse * frequency * (k1 + 1) / denominator
        if score:
            scores[cell_id] = score
    return scores


def _graph_expand(
    connection: sqlite3.Connection,
    seeds: dict[str, float],
    hops: int,
) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    scores = dict(seeds)
    traces: dict[str, dict[str, Any]] = {
        cell_id: {"hops": 0, "relation": "lexical-seed", "from": None}
        for cell_id in seeds
    }
    best_state = {(cell_id, 0): score for cell_id, score in seeds.items()}
    state_paths: dict[tuple[str, int], list[dict[str, Any]]] = {
        (cell_id, 0): [] for cell_id in seeds
    }
    frontier = [(-score, 0, cell_id) for cell_id, score in seeds.items()]
    heapq.heapify(frontier)
    while frontier:
        negative_score, depth, current = heapq.heappop(frontier)
        current_score = -negative_score
        if current_score < best_state.get((current, depth), 0.0):
            continue
        current_path = state_paths.get((current, depth), [])
        if depth >= hops:
            continue
        neighbors = connection.execute(
            "SELECT target_cell_id, relation, weight FROM edges "
            "WHERE source_cell_id = ? ORDER BY weight DESC, target_cell_id",
            (current,),
        ).fetchall()
        for neighbor in neighbors:
            target = neighbor["target_cell_id"]
            next_depth = depth + 1
            propagated = current_score * float(neighbor["weight"]) * 0.55
            state = (target, next_depth)
            candidate_path = [
                *current_path,
                {
                    "from_cell_id": current,
                    "to_cell_id": target,
                    "relation": neighbor["relation"],
                    "weight": float(neighbor["weight"]),
                },
            ]
            if propagated > best_state.get(state, 0.0):
                best_state[state] = propagated
                state_paths[state] = candidate_path
                heapq.heappush(frontier, (-propagated, next_depth, target))
            if propagated > scores.get(target, 0.0):
                scores[target] = propagated
                traces[target] = {
                    "hops": next_depth,
                    "relation": neighbor["relation"],
                    "from": current,
                    "path": candidate_path,
                }
    return scores, traces


def query_index(
    root: Path,
    queries: Sequence[str],
    *,
    query_labels: Sequence[str] | None = None,
    db_path: Path | None = None,
    top_k: int | None = None,
    graph_hops: int | None = None,
    max_context_chars: int | None = None,
    minimum_score: float | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    config = load_config(root)
    retrieval = config.get("retrieval", {})
    top_k = int(top_k if top_k is not None else retrieval.get("top_k", 8))
    graph_hops = int(
        graph_hops if graph_hops is not None else retrieval.get("graph_hops", 2)
    )
    max_context_chars = int(
        max_context_chars
        if max_context_chars is not None
        else retrieval.get("max_context_chars", 7000)
    )
    minimum_score = float(
        minimum_score
        if minimum_score is not None
        else retrieval.get("minimum_score", 0.05)
    )
    if top_k < 1:
        raise MemoryError("top_k must be at least 1")
    if graph_hops < 0:
        raise MemoryError("graph_hops must be non-negative")
    if max_context_chars < 1:
        raise MemoryError("max_context_chars must be at least 1")
    cleaned_queries = [value.strip() for value in queries if value.strip()]
    if not cleaned_queries:
        raise MemoryError("at least one non-empty query is required")
    if query_labels is None:
        display_queries = cleaned_queries
    else:
        display_queries = [str(value).strip() for value in query_labels]
        if len(display_queries) != len(cleaned_queries) or any(
            not value for value in display_queries
        ):
            raise MemoryError(
                "query_labels must contain one non-empty label per cleaned query"
            )
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
    combined: dict[str, float] = defaultdict(float)
    matches: dict[str, set[int]] = defaultdict(set)
    best_trace: dict[str, dict[str, Any]] = {}
    per_query_max: list[float] = []
    for query_number, query in enumerate(cleaned_queries):
        lexical = _bm25_scores(rows, tokenize(query))
        if not lexical:
            per_query_max.append(0.0)
            continue
        seed_limit = max(top_k * 2, 12)
        seeds = dict(
            sorted(lexical.items(), key=lambda item: (-item[1], item[0]))[:seed_limit]
        )
        expanded, traces = _graph_expand(connection, seeds, graph_hops)
        maximum = max(expanded.values(), default=0.0)
        per_query_max.append(maximum)
        if not maximum:
            continue
        for cell_id, score in expanded.items():
            normalized = score / maximum
            if normalized < minimum_score:
                continue
            combined[cell_id] += normalized
            matches[cell_id].add(query_number)
            current_trace = best_trace.get(cell_id)
            candidate_trace = traces.get(cell_id, {})
            if current_trace is None or candidate_trace.get("hops", 99) < current_trace.get(
                "hops", 99
            ):
                best_trace[cell_id] = candidate_trace

    if not combined:
        connection.close()
        return {
            "schema": PACKET_SCHEMA,
            "generated_at": utc_now(),
            "queries": display_queries,
            "abstained": True,
            "abstention_reason": "no lexical seed matched the indexed memory",
            "index": {"digest": index_digest, "indexed_at": indexed_at},
            "results": [],
            "max_context_chars": max_context_chars,
            "estimated_context_chars": 0,
        }

    ranked: list[tuple[str, float]] = []
    query_count = len(cleaned_queries)
    for cell_id, score in combined.items():
        matched_count = len(matches[cell_id])
        triangulation_bonus = 0.35 * max(matched_count - 1, 0)
        coverage_bonus = 0.15 * matched_count / query_count
        ranked.append((cell_id, score + triangulation_bonus + coverage_bonus))
    ranked.sort(key=lambda item: (-item[1], rows_by_id[item[0]]["path"], item[0]))

    results: list[dict[str, Any]] = []
    used_chars = 0
    packet_base = {
        "schema": PACKET_SCHEMA,
        "generated_at": utc_now(),
        "queries": display_queries,
        "abstained": False,
        "abstention_reason": None,
        "index": {"digest": index_digest, "indexed_at": indexed_at},
        "max_context_chars": max_context_chars,
    }
    allow_hardlinks = bool(config.get("allow_hardlinked_sources", False))
    verified_documents: set[str] = set()
    for cell_id, score in ranked:
        row = rows_by_id[cell_id]
        if row["path"] not in verified_documents:
            try:
                verify_indexed_source(
                    root,
                    row["path"],
                    row["document_content_sha256"],
                    allow_hardlinks=allow_hardlinks,
                )
            except Exception:
                connection.close()
                raise
            verified_documents.add(row["path"])
        text = row["text"]
        trace = best_trace.get(cell_id, {})
        result = {
            "rank": len(results) + 1,
            "cell_id": cell_id,
            "score": round(score, 6),
            "matched_queries": [
                display_queries[index] for index in sorted(matches[cell_id])
            ],
            "source": {
                "path": row["path"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "content_sha256": row["content_sha256"],
            },
            "heading": row["heading"],
            "kind": row["kind"],
            "memory": decode_memory_metadata(row["memory_metadata_json"]),
            "text": text,
            "graph": {
                "hops": int(trace.get("hops", 0)),
                "relation": trace.get("relation", "lexical-seed"),
                "from_cell_id": trace.get("from"),
            },
        }
        candidate_results = [*results, result]
        projected = len(
            _render_packet_markdown({**packet_base, "results": candidate_results})
        )
        if projected > max_context_chars:
            continue
        results.append(result)
        used_chars = projected
        if len(results) >= top_k:
            break
    connection.close()
    if not results:
        return {
            **packet_base,
            "abstained": True,
            "abstention_reason": (
                "matching evidence exceeded the context budget; no partial cell was injected"
            ),
            "results": [],
            "estimated_context_chars": 0,
        }
    return {**packet_base, "results": results, "estimated_context_chars": used_chars}


def _render_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# NaviOS Memory Context",
        "",
        "Queries: " + " | ".join(packet["queries"]),
        f"Index: `{packet['index']['digest'][:16]}`",
        "",
    ]
    if packet.get("abstained"):
        lines.extend(
            [
                "No memory was injected.",
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
                f"Cell: `{result['cell_id'][:16]}`  ",
                f"Evidence SHA-256: `{source['content_sha256']}`  ",
                f"Score: `{result['score']}`; graph: "
                f"`{result['graph']['hops']}-hop/{result['graph']['relation']}`",
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


def format_packet_markdown(packet: dict[str, Any]) -> str:
    rendered = _render_packet_markdown(packet)
    budget = packet.get("max_context_chars")
    if budget is not None and len(rendered) > int(budget):
        raise MemoryError(
            f"formatted context packet is {len(rendered)} characters; budget is {budget}"
        )
    return rendered


def index_status(root: Path, db_path: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    database = project_output_path(root, db_path or DEFAULT_DB, field="memory index")
    connection = open_index(database)
    meta = dict(connection.execute("SELECT key, value FROM meta").fetchall())
    documents = connection.execute("SELECT count(*) FROM documents").fetchone()[0]
    cells = connection.execute("SELECT count(*) FROM cells").fetchone()[0]
    edges = connection.execute("SELECT count(*) FROM edges").fetchone()[0]
    connection.close()
    return {
        "schema": meta["schema"],
        "project_root": meta["project_root"],
        "database": str(database),
        "indexed_at": meta["indexed_at"],
        "index_digest": meta["index_digest"],
        "documents": documents,
        "cells": cells,
        "edges": edges,
    }
