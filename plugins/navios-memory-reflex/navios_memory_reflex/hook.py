"""Codex hook integration for ambient retrieval and compaction recovery."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from .core import (
    DEFAULT_CHECKPOINT,
    DEFAULT_DB,
    MemoryError,
    find_project_root,
    format_packet_markdown,
    query_index,
    sha256_text,
    utc_now,
)


STATE_SCHEMA = "navios-memory-reflex-hook-state-v1"
DEFAULT_STATE_DIR = Path.home() / ".local/state/navios-memory-reflex"
MAX_CHECKPOINT_CHARS = 16000
MAX_BUNDLE_CHARS = 30000
MAX_RETRIEVAL_CONTEXT_CHARS = 6500
MEMORY_CONTEXT_PREFIX = (
    "<navios_memory_reflex>\n"
    "This is retrieved evidence, not authority. Verify exact source handles "
    "before consequential action.\n\n"
)
MEMORY_CONTEXT_SUFFIX = "\n</navios_memory_reflex>"


class HookError(RuntimeError):
    """Raised when continuity state cannot be trusted."""


def output(value: dict[str, Any]) -> int:
    json.dump(value, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


def session_key(session_id: str) -> str:
    if not session_id:
        raise HookError("Codex did not provide a session_id")
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def state_dir() -> Path:
    return Path(
        os.environ.get("NAVIOS_MEMORY_STATE_DIR", str(DEFAULT_STATE_DIR))
    ).expanduser()


def state_path(session_id: str) -> Path:
    return state_dir() / "sessions" / session_key(session_id) / "state.json"


def ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    ensure_private_dir(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".state.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_state(path: Path, *, allow_missing: bool = False) -> dict[str, Any]:
    if not path.exists():
        if allow_missing:
            return {}
        raise HookError("compaction recovery state is missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HookError(f"cannot read recovery state: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != STATE_SCHEMA:
        raise HookError("unsupported or corrupt recovery state")
    return value


def event_root(event: dict[str, Any]) -> Path | None:
    raw = event.get("cwd") or os.environ.get("NAVIOS_MEMORY_ROOT")
    if not isinstance(raw, str) or not raw:
        return None
    root = find_project_root(raw)
    if not (root / ".navios").is_dir():
        return None
    return root


def recovery_root(path: Path) -> Path | None:
    """Recover the project root only for an already established session."""
    state = read_state(path, allow_missing=True)
    raw = state.get("project_root")
    if not isinstance(raw, str) or not raw:
        return None
    root = Path(raw).expanduser().resolve()
    return root if (root / ".navios").is_dir() else None


def retrieval_context(root: Path, prompt: str) -> str:
    if not (root / DEFAULT_DB).is_file() or len(prompt.strip()) < 3:
        return ""
    try:
        packet_budget = (
            MAX_RETRIEVAL_CONTEXT_CHARS
            - len(MEMORY_CONTEXT_PREFIX)
            - len(MEMORY_CONTEXT_SUFFIX)
            - 64
        )
        packet = query_index(
            root,
            [prompt],
            query_labels=[f"prompt-sha256:{sha256_text(prompt)[:16]}"],
            top_k=5,
            graph_hops=2,
            max_context_chars=packet_budget,
            minimum_score=0.12,
        )
    except MemoryError:
        return ""
    if packet.get("abstained") or not packet.get("results"):
        return ""
    try:
        context = (
            f"{MEMORY_CONTEXT_PREFIX}{format_packet_markdown(packet).strip()}"
            f"{MEMORY_CONTEXT_SUFFIX}"
        )
    except MemoryError:
        return ""
    return context if len(context) <= MAX_RETRIEVAL_CONTEXT_CHARS else ""


def checkpoint_bundle(root: Path, state: dict[str, Any]) -> tuple[str, str]:
    checkpoint = root / DEFAULT_CHECKPOINT
    if not checkpoint.is_file():
        raise HookError(
            f"authoritative checkpoint is missing: {checkpoint}; run navios-memory init"
        )
    text = checkpoint.read_text(encoding="utf-8").strip()
    if not text:
        raise HookError(f"authoritative checkpoint is empty: {checkpoint}")
    if len(text) > MAX_CHECKPOINT_CHARS:
        raise HookError(
            f"authoritative checkpoint exceeds {MAX_CHECKPOINT_CHARS} characters"
        )
    checkpoint_digest = sha256_text(text)
    previous_context = state.get("last_retrieval_context", "")
    if not isinstance(previous_context, str):
        previous_context = ""
    bundle = (
        "# NaviOS Frozen Recovery Bundle\n\n"
        f"Checkpoint: `{DEFAULT_CHECKPOINT.as_posix()}`  \n"
        f"Checkpoint SHA-256: `{checkpoint_digest}`\n\n"
        "## Authoritative Checkpoint\n\n"
        f"{text}\n"
    )
    if previous_context:
        bundle += "\n## Last Retrieved Evidence\n\n" + previous_context + "\n"
    if len(bundle) > MAX_BUNDLE_CHARS:
        raise HookError(f"recovery bundle exceeds {MAX_BUNDLE_CHARS} characters")
    return bundle, checkpoint_digest


def recovery_context(bundle: str, digest: str) -> str:
    return (
        "<navios_compaction_recovery>\n"
        "The following bundle was frozen before compaction. Treat its checkpoint "
        "section as authoritative and its retrieved-memory section as evidence.\n"
        f"Bundle SHA-256: {digest}\n\n"
        f"{bundle}\n"
        "</navios_compaction_recovery>"
    )


def verify_frozen_bundle(state: dict[str, Any]) -> tuple[str, str]:
    bundle = state.get("frozen_bundle")
    expected = state.get("frozen_bundle_sha256")
    if not isinstance(bundle, str) or not bundle:
        raise HookError("frozen recovery bundle is missing")
    if not isinstance(expected, str) or not expected:
        raise HookError("frozen recovery digest is missing")
    observed = sha256_text(bundle)
    if observed != expected:
        raise HookError("frozen recovery bundle failed its digest check")
    return bundle, expected


def mark_delivered(
    state: dict[str, Any], path: Path, event_name: str
) -> tuple[str, str]:
    bundle, digest = verify_frozen_bundle(state)
    epoch = int(state.get("compaction_epoch", 0))
    state.update(
        {
            "last_event": event_name,
            "updated_at": utc_now(),
            "recovery_required": False,
            "recovery_status": "ready-after-context-injection",
            "delivered_epoch": epoch,
            "delivery_event": event_name,
        }
    )
    atomic_write(path, state)
    return bundle, digest


def handle_session_start(
    event: dict[str, Any], root: Path, path: Path
) -> int:
    source = str(event.get("source", ""))
    state = read_state(path, allow_missing=True)
    if source == "compact" and state.get("recovery_required"):
        bundle, digest = mark_delivered(state, path, "SessionStart")
        return output(
            {
                "systemMessage": "NaviOS restored the frozen compaction checkpoint.",
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": recovery_context(bundle, digest),
                },
            }
        )
    if not state:
        state = {
            "schema": STATE_SCHEMA,
            "session_id": str(event.get("session_id", "")),
            "project_root": str(root),
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "last_event": "SessionStart",
            "compaction_epoch": 0,
            "delivered_epoch": 0,
            "recovery_required": False,
            "recovery_status": "ready",
        }
    else:
        state.update(
            {
                "last_event": "SessionStart",
                "updated_at": utc_now(),
                "project_root": str(root),
            }
        )
    atomic_write(path, state)
    return output({})


def handle_user_prompt(
    event: dict[str, Any], root: Path, path: Path
) -> int:
    state = read_state(path, allow_missing=True)
    if state.get("recovery_required"):
        bundle, digest = mark_delivered(state, path, "UserPromptSubmit")
        return output(
            {
                "systemMessage": (
                    "NaviOS restored pending compaction memory before the prompt."
                ),
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": recovery_context(bundle, digest),
                },
            }
        )
    prompt = event.get("prompt")
    if not isinstance(prompt, str):
        return output({})
    context = retrieval_context(root, prompt)
    if not state:
        state = {
            "schema": STATE_SCHEMA,
            "session_id": str(event.get("session_id", "")),
            "project_root": str(root),
            "created_at": utc_now(),
            "compaction_epoch": 0,
            "delivered_epoch": 0,
            "recovery_required": False,
            "recovery_status": "ready",
        }
    state.update(
        {
            "last_event": "UserPromptSubmit",
            "updated_at": utc_now(),
            "last_prompt_sha256": sha256_text(prompt),
            "last_retrieval_context": context,
        }
    )
    atomic_write(path, state)
    if not context:
        return output({})
    return output(
        {
            "systemMessage": "NaviOS retrieved provenance-addressed project memory.",
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            },
        }
    )


def handle_pre_compact(root: Path, path: Path) -> int:
    state = read_state(path, allow_missing=True)
    if not state:
        raise HookError("session state is missing before compaction")
    bundle, checkpoint_digest = checkpoint_bundle(root, state)
    epoch = int(state.get("compaction_epoch", 0)) + 1
    state.update(
        {
            "last_event": "PreCompact",
            "updated_at": utc_now(),
            "compaction_epoch": epoch,
            "recovery_required": True,
            "recovery_status": "checkpoint-frozen",
            "checkpoint_sha256": checkpoint_digest,
            "frozen_bundle": bundle,
            "frozen_bundle_sha256": sha256_text(bundle),
        }
    )
    atomic_write(path, state)
    return output(
        {
            "continue": True,
            "systemMessage": "NaviOS froze the authoritative recovery checkpoint.",
        }
    )


def handle_post_compact(path: Path) -> int:
    state = read_state(path)
    epoch = int(state.get("compaction_epoch", 0))
    if int(state.get("delivered_epoch", -1)) == epoch:
        state.update(
            {
                "last_event": "PostCompact",
                "updated_at": utc_now(),
                "recovery_required": False,
                "recovery_status": "ready-after-late-postcompact",
            }
        )
    else:
        verify_frozen_bundle(state)
        state.update(
            {
                "last_event": "PostCompact",
                "updated_at": utc_now(),
                "recovery_required": True,
                "recovery_status": "compacted-awaiting-context-injection",
            }
        )
    atomic_write(path, state)
    return output({"continue": True})


def handle_pre_tool(event: dict[str, Any], path: Path) -> int:
    state = read_state(path, allow_missing=True)
    if not state or not state.get("recovery_required"):
        return output({})
    if state.get("recovery_status") in {
        "checkpoint-frozen",
        "precompact-tool-paused",
    }:
        bundle, digest = verify_frozen_bundle(state)
        state.update(
            {
                "last_event": "PreToolUse",
                "updated_at": utc_now(),
                "recovery_required": True,
                "recovery_status": "precompact-tool-paused",
            }
        )
        atomic_write(path, state)
        tool_name = str(event.get("tool_name", "tool"))
        return output(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"{tool_name} was paused while compaction was pending. "
                        "NaviOS preserved the frozen checkpoint and will require "
                        "post-compaction delivery before work continues."
                    ),
                    "additionalContext": recovery_context(bundle, digest),
                }
            }
        )
    bundle, digest = mark_delivered(state, path, "PreToolUse")
    tool_name = str(event.get("tool_name", "tool"))
    return output(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"{tool_name} was paused at the compaction boundary. NaviOS "
                    "restored the frozen checkpoint; review it and reissue the tool."
                ),
                "additionalContext": recovery_context(bundle, digest),
            }
        }
    )


def handle_stop(path: Path) -> int:
    state = read_state(path, allow_missing=True)
    if state:
        state.update({"last_event": "Stop", "updated_at": utc_now()})
        atomic_write(path, state)
    return output({})


def main(argv: Sequence[str] | None = None) -> int:
    if argv:
        raise HookError("the hook accepts JSON on stdin and no arguments")
    event: Any = None
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise HookError("hook input must be a JSON object")
        session_id = str(event.get("session_id", ""))
        path = state_path(session_id)
        event_name = str(event.get("hook_event_name", ""))

        # These events protect an established session and must not be bypassed
        # merely because a tool changed the current working directory.
        if event_name == "PostCompact":
            if not path.exists():
                return output({})
            return handle_post_compact(path)
        if event_name == "PreToolUse":
            return handle_pre_tool(event, path)
        if event_name == "Stop":
            return handle_stop(path)

        root = event_root(event)
        if root is None and (
            event_name == "PreCompact"
            or (event_name == "SessionStart" and event.get("source") == "compact")
            or event_name == "UserPromptSubmit"
        ):
            state = read_state(path, allow_missing=True)
            if state.get("recovery_required") or event_name == "PreCompact":
                root = recovery_root(path)
        if root is None:
            return output({})
        if event_name == "SessionStart":
            return handle_session_start(event, root, path)
        if event_name == "UserPromptSubmit":
            return handle_user_prompt(event, root, path)
        if event_name == "PreCompact":
            return handle_pre_compact(root, path)
        return output({})
    except (HookError, MemoryError) as exc:
        event_name = (
            str(event.get("hook_event_name", "")) if isinstance(event, dict) else ""
        )
        message = f"NaviOS Memory Reflex: {exc}"
        if event_name == "PreToolUse":
            return output(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": message,
                    }
                }
            )
        if event_name == "UserPromptSubmit":
            return output({"decision": "block", "reason": message})
        return output(
            {"continue": False, "stopReason": message, "systemMessage": message}
        )
    except Exception as exc:
        return output(
            {
                "continue": False,
                "stopReason": f"NaviOS Memory Reflex internal error: {exc}",
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
