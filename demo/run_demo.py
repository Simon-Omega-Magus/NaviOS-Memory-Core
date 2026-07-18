#!/usr/bin/env python3
"""Run a deterministic NaviOS Memory Reflex demonstration in a temporary copy."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins/navios-memory-reflex"
sys.path.insert(0, str(PLUGIN_ROOT))

from navios_memory_reflex.core import (  # noqa: E402
    format_packet_markdown,
    index_project,
    query_index,
)


def run_hook(
    hook: Path,
    state_dir: Path,
    root: Path,
    event_name: str,
    **values: object,
) -> dict:
    event = {
        "session_id": "navios-build-week-demo",
        "cwd": str(root),
        "hook_event_name": event_name,
        "model": "gpt-5.6",
    }
    event.update(values)
    environment = dict(os.environ)
    environment["NAVIOS_MEMORY_STATE_DIR"] = str(state_dir)
    result = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="emit one machine-readable report"
    )
    args = parser.parse_args()
    source = REPO_ROOT / "examples/demo-project"
    hook = PLUGIN_ROOT / "scripts/navios-memory-hook"
    with tempfile.TemporaryDirectory(prefix="navios-memory-reflex-demo-") as temporary:
        root = Path(temporary) / "project"
        shutil.copytree(source, root)
        state_dir = Path(temporary) / "state"
        index_report = index_project(root)
        packet = query_index(
            root,
            [
                "what must happen after context compaction",
                "which safety constraint applies before the next tool call",
                "how is retrieved memory verified",
            ],
            top_k=7,
            graph_hops=2,
        )
        events = []
        events.append(
            ("SessionStart(startup)", run_hook(hook, state_dir, root, "SessionStart", source="startup"))
        )
        events.append(
            (
                "UserPromptSubmit",
                run_hook(
                    hook,
                    state_dir,
                    root,
                    "UserPromptSubmit",
                    prompt="Continue after compaction without violating local-memory constraints",
                ),
            )
        )
        events.append(
            ("PreCompact", run_hook(hook, state_dir, root, "PreCompact", trigger="auto"))
        )
        events.append(
            ("PostCompact", run_hook(hook, state_dir, root, "PostCompact", trigger="auto"))
        )
        tool_response = run_hook(
            hook,
            state_dir,
            root,
            "PreToolUse",
            tool_name="Bash",
            tool_input={"command": "deploy --without-review"},
        )
        events.append(("PreToolUse", tool_response))
        report = {
            "index": index_report,
            "retrieval": packet,
            "hook_events": [
                {"event": name, "response": response} for name, response in events
            ],
        }
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0

        print("NaviOS Memory Reflex - deterministic judge demo")
        print("=" * 52)
        print(
            f"Indexed {index_report['documents']} documents into "
            f"{index_report['cells']} cells and {index_report['edges']} typed edges."
        )
        print(f"Index digest: {index_report['index_digest']}")
        print("\nTRIANGULATED RETRIEVAL\n")
        print(format_packet_markdown(packet))
        print("COMPACTION RECOVERY\n")
        for name, response in events[:-1]:
            message = response.get("systemMessage", "ok")
            print(f"{name:28} {message}")
        decision = tool_response["hookSpecificOutput"]
        print(
            f"{'PreToolUse':28} {decision['permissionDecision'].upper()}: "
            f"{decision['permissionDecisionReason']}"
        )
        recovered = decision["additionalContext"]
        print("\nRECOVERED CHECKPOINT EXCERPT\n")
        excerpt_start = recovered.find("# NaviOS Frozen Recovery Bundle")
        print(recovered[excerpt_start : excerpt_start + 1000].rstrip())
        print("\nDemo complete: the unsafe tool was cancelled after recovery context delivery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
