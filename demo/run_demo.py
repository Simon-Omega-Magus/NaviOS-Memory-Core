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
    assimilate_project,
    format_packet_markdown,
    query_index,
    sha256_file,
)
from navios_memory_reflex.cultivation import cultivate_proposal  # noqa: E402
from navios_memory_reflex.staged import (  # noqa: E402
    format_hydration_markdown,
    format_survey_markdown,
    hydrate_index,
    survey_index,
)
from navios_memory_reflex.will import (  # noqa: E402
    list_will_questions,
    queue_will_question,
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
        assimilation = assimilate_project(root)
        index_report = assimilation["index"]
        survey = survey_index(
            root,
            [
                "current objective and accepted memory decisions",
                "compaction safety constraints before a tool call",
                "provenance verification and graph retrieval architecture",
            ],
            candidates_per_query=200,
            graph_hops=3,
        )
        selected_ids = [
            item["cell_id"] for item in survey["candidates"][:3]
        ]
        hydration = hydrate_index(root, selected_ids, max_context_chars=7000)
        decision_source = root / "docs/decisions.md"
        cultivation = cultivate_proposal(
            root,
            title="Staged retrieval lesson",
            body=(
                "Use a body-free multi-query survey before selective hydration "
                "when broad candidate inspection would otherwise consume the "
                "primary context window."
            ),
            sources=[
                f"docs/decisions.md::{sha256_file(decision_source)}"
            ],
            kind="retrieval-lesson",
            created_by="navios-build-week-demo",
            confidence=0.9,
            tags=["memory", "retrieval"],
        )
        will_question = queue_will_question(
            root,
            claim_ids=["claim:checkpoint-first", "claim:graph-first"],
            question=(
                "Should graph memory replace checkpoints or remain an additive "
                "retrieval layer?"
            ),
            scope="demo.memory-continuity",
            sources=[
                "docs/architecture.md",
                f"docs/decisions.md::{sha256_file(decision_source)}",
            ],
            created_by="navios-build-week-demo",
            proposed_interpretation=(
                "Keep both claims active and use graph memory additively until the "
                "human resolves the replacement question."
            ),
            blocked_action="Removing checkpoint recovery from the demo.",
        )
        will_queue = list_will_questions(root)
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
            "assimilation": assimilation,
            "index": index_report,
            "survey": survey,
            "hydration": hydration,
            "cultivation": cultivation,
            "will_question": will_question,
            "will_queue": will_queue,
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
        print("\nBODY-FREE MULTI-QUERY SURVEY\n")
        print(format_survey_markdown(survey, show=6))
        print("SELECTIVE HYDRATION\n")
        print(format_hydration_markdown(hydration))
        print("PROPOSAL-FIRST MEMORY CULTIVATION\n")
        print(
            f"Created {cultivation['proposal_path']} with status "
            f"{cultivation['status']}; indexed={cultivation['indexed']}; "
            f"source files mutated={cultivation['source_documents_mutated']}.\n"
        )
        print("HUMAN-WILL COHERENCE QUEUE\n")
        print(
            f"Queued {will_question['question_id']} with "
            f"{will_question['directional_effect']}; execution effect="
            f"{will_question['execution_effect']}; open questions="
            f"{will_queue['open_count']}.\n"
        )
        print("BOUNDED PROMPT RETRIEVAL\n")
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
