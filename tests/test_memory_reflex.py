from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins/navios-memory-reflex"
sys.path.insert(0, str(PLUGIN_ROOT))

from navios_memory_reflex.core import (  # noqa: E402
    DEFAULT_DB,
    MemoryError,
    _graph_expand,
    format_packet_markdown,
    index_project,
    initialize_project,
    query_index,
)


class MemoryIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        initialize_project(self.root)
        (self.root / "architecture.md").write_text(
            "---\n"
            "tags: [memory, safety]\n"
            "links: [constraints.md]\n"
            "---\n"
            "# Memory Architecture\n\n"
            "The Knowledge Guardian freezes an authoritative checkpoint before "
            "compaction.\n\n"
            "After compaction, the first unsafe tool call must wait until recovery "
            "context is restored.\n\n"
            "# Retrieval\n\n"
            "Sentence cells retain exact source paths, line ranges, and content "
            "hashes.\n",
            encoding="utf-8",
        )
        (self.root / "constraints.md").write_text(
            "---\n"
            "tags: [safety]\n"
            "---\n"
            "# Constraints\n\n"
            "Never delete user data without explicit authorization.\n\n"
            "Retrieved evidence is not authority and must retain exact provenance.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_index_and_triangulated_graph_retrieval(self) -> None:
        report = index_project(self.root)
        self.assertEqual(report["documents"], 3)
        self.assertGreaterEqual(report["cells"], 8)
        self.assertGreater(report["edges"], 0)
        packet = query_index(
            self.root,
            [
                "what must happen after context compaction",
                "how are unsafe tool calls handled",
            ],
            top_k=6,
            graph_hops=2,
        )
        self.assertFalse(packet["abstained"])
        self.assertIn("first unsafe tool call", packet["results"][0]["text"])
        self.assertEqual(len(packet["results"][0]["matched_queries"]), 2)
        self.assertTrue(
            any(
                result["source"]["path"] == "constraints.md"
                and result["graph"]["hops"] > 0
                for result in packet["results"]
            )
        )
        for result in packet["results"]:
            self.assertGreater(result["source"]["start_line"], 0)
            self.assertEqual(len(result["source"]["content_sha256"]), 64)

    def test_ambiguous_basename_link_does_not_create_false_edges(self) -> None:
        (self.root / "source.md").write_text(
            "---\nlinks: [duplicate.md]\n---\n# Source\n\nUnique source phrase.\n",
            encoding="utf-8",
        )
        for directory, phrase in (("one", "Cobalt alpha"), ("two", "Cobalt beta")):
            target_dir = self.root / directory
            target_dir.mkdir()
            (target_dir / "duplicate.md").write_text(
                f"# Duplicate\n\n{phrase}.\n", encoding="utf-8"
            )
        index_project(self.root)
        connection = sqlite3.connect(self.root / DEFAULT_DB)
        explicit_edges = connection.execute(
            "SELECT count(*) FROM edges WHERE relation = 'explicit-link'"
        ).fetchone()[0]
        connection.close()
        self.assertEqual(explicit_edges, 1)

    def test_negative_control_abstains(self) -> None:
        index_project(self.root)
        packet = query_index(self.root, ["volcanic upholstery submarine"])
        self.assertTrue(packet["abstained"])
        self.assertEqual(packet["results"], [])

    def test_sensitive_names_are_excluded(self) -> None:
        (self.root / "api-token.md").write_text(
            "# Credentials\n\nDo not index this value.\n", encoding="utf-8"
        )
        index_project(self.root)
        packet = query_index(self.root, ["credentials index value"])
        self.assertTrue(packet["abstained"])

    def test_symlinked_files_and_directories_are_not_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as external_name:
            external = Path(external_name)
            (external / "outside.md").write_text(
                "# Outside\n\nUltraviolet marmalade must remain outside.\n",
                encoding="utf-8",
            )
            (self.root / "linked-file.md").symlink_to(external / "outside.md")
            (self.root / "linked-directory").symlink_to(
                external, target_is_directory=True
            )

            index_project(self.root)
            packet = query_index(self.root, ["ultraviolet marmalade outside"])
            self.assertTrue(packet["abstained"])

    def test_rebuild_is_content_deterministic(self) -> None:
        first = index_project(self.root)
        second = index_project(self.root)
        self.assertEqual(first["index_digest"], second["index_digest"])
        self.assertTrue((self.root / DEFAULT_DB).is_file())

    def test_stronger_same_depth_graph_path_repropagates(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute(
            "CREATE TABLE edges (source_cell_id TEXT, target_cell_id TEXT, "
            "relation TEXT, weight REAL)"
        )
        connection.executemany(
            "INSERT INTO edges VALUES (?, ?, ?, ?)",
            [
                ("weak-seed", "middle", "weak-path", 0.3),
                ("strong-seed", "middle", "strong-path", 1.0),
                ("middle", "descendant", "child", 1.0),
            ],
        )
        scores, traces = _graph_expand(
            connection, {"weak-seed": 1.0, "strong-seed": 0.9}, 2
        )
        connection.close()

        self.assertAlmostEqual(scores["middle"], 0.495)
        self.assertAlmostEqual(scores["descendant"], 0.27225)
        self.assertEqual(traces["middle"]["relation"], "strong-path")
        self.assertEqual(traces["descendant"]["from"], "middle")

    def test_rendered_packet_respects_complete_context_budget(self) -> None:
        index_project(self.root)
        packet = query_index(
            self.root,
            ["authoritative checkpoint compaction", "unsafe tool recovery"],
            top_k=8,
            graph_hops=2,
            max_context_chars=1000,
        )
        rendered = format_packet_markdown(packet)
        self.assertFalse(packet["abstained"])
        self.assertLessEqual(len(rendered), packet["max_context_chars"])
        self.assertEqual(packet["estimated_context_chars"], len(rendered))

    def test_too_small_context_budget_abstains_without_partial_cell(self) -> None:
        index_project(self.root)
        packet = query_index(
            self.root,
            ["authoritative checkpoint compaction"],
            max_context_chars=120,
        )
        self.assertTrue(packet["abstained"])
        self.assertEqual(packet["results"], [])
        self.assertIn("context budget", packet["abstention_reason"])

    def test_formatter_rejects_an_over_budget_packet(self) -> None:
        packet = {
            "queries": ["query"],
            "index": {"digest": "d" * 64},
            "abstained": False,
            "max_context_chars": 200,
            "results": [
                {
                    "rank": 1,
                    "cell_id": "c" * 64,
                    "score": 1.0,
                    "source": {
                        "path": "large.md",
                        "start_line": 1,
                        "end_line": 1,
                        "content_sha256": "e" * 64,
                    },
                    "heading": "Large",
                    "text": "x" * 1000,
                    "graph": {"hops": 0, "relation": "lexical-seed"},
                }
            ],
        }
        with self.assertRaises(MemoryError):
            format_packet_markdown(packet)


class HookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        initialize_project(self.root)
        (self.root / ".navios/checkpoint.md").write_text(
            "# Authoritative Checkpoint\n\n"
            "## Objective\n\nFinish the retrieval demo.\n\n"
            "## Constraint\n\nNever delete user data.\n",
            encoding="utf-8",
        )
        (self.root / "memory.md").write_text(
            "# Retrieval Design\n\n"
            "Graph expansion surfaces neighboring safety constraints with exact "
            "provenance.\n",
            encoding="utf-8",
        )
        index_project(self.root)
        self.state_dir = Path(self.temporary.name) / "state"
        self.hook = PLUGIN_ROOT / "scripts/navios-memory-hook"
        self.base = {
            "session_id": "build-week-test-session",
            "cwd": str(self.root),
            "model": "gpt-5.6",
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_hook(self, event_name: str, **values: object) -> dict:
        event = dict(self.base)
        event["hook_event_name"] = event_name
        event.update(values)
        environment = dict(os.environ)
        environment["NAVIOS_MEMORY_STATE_DIR"] = str(self.state_dir)
        result = subprocess.run(
            [sys.executable, str(self.hook)],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def state(self) -> dict:
        path = next(self.state_dir.glob("sessions/*/state.json"))
        return json.loads(path.read_text(encoding="utf-8"))

    def test_prompt_reflex_injects_evidence_without_storing_raw_prompt(self) -> None:
        self.assertEqual(self.run_hook("SessionStart", source="startup"), {})
        prompt = "Where are graph safety constraints retrieved?"
        response = self.run_hook("UserPromptSubmit", prompt=prompt)
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("memory.md", context)
        self.assertIn("Evidence SHA-256", context)
        serialized = json.dumps(self.state())
        self.assertNotIn(prompt, serialized)
        self.assertIn("last_prompt_sha256", serialized)
        self.assertLessEqual(len(context), 6500)

    def test_long_prompt_is_scored_but_only_its_digest_label_is_budgeted(self) -> None:
        self.run_hook("SessionStart", source="startup")
        prompt = "graph safety constraints " + ("x" * 9000)
        response = self.run_hook("UserPromptSubmit", prompt=prompt)
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("memory.md", context)
        self.assertIn("prompt-sha256:", context)
        self.assertNotIn("x" * 100, context)
        self.assertLessEqual(len(context), 6500)

    def test_postcompact_is_dormant_without_project_session_state(self) -> None:
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        self.base["cwd"] = str(outside)
        self.assertEqual(self.run_hook("PostCompact", trigger="auto"), {})

    def test_postcompact_pretool_fallback_cancels_one_tool(self) -> None:
        self.run_hook("SessionStart", source="startup")
        self.run_hook("UserPromptSubmit", prompt="graph recovery provenance")
        self.run_hook("PreCompact", trigger="auto")
        self.run_hook("PostCompact", trigger="auto")
        response = self.run_hook(
            "PreToolUse", tool_name="Bash", tool_input={"command": "echo unsafe"}
        )
        decision = response["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Authoritative Checkpoint", decision["additionalContext"])
        self.assertFalse(self.state()["recovery_required"])
        self.assertEqual(
            self.run_hook(
                "PreToolUse", tool_name="Bash", tool_input={"command": "echo safe"}
            ),
            {},
        )

    def test_precompact_tool_pause_does_not_count_as_recovery_delivery(self) -> None:
        self.run_hook("SessionStart", source="startup")
        self.run_hook("PreCompact", trigger="auto")
        first = self.run_hook(
            "PreToolUse", tool_name="Bash", tool_input={"command": "echo early"}
        )
        self.assertEqual(
            first["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        precompact_state = self.state()
        self.assertTrue(precompact_state["recovery_required"])
        self.assertEqual(precompact_state["delivered_epoch"], 0)
        self.assertEqual(
            precompact_state["recovery_status"], "precompact-tool-paused"
        )

        self.run_hook("PostCompact", trigger="auto")
        self.assertTrue(self.state()["recovery_required"])
        second = self.run_hook(
            "PreToolUse", tool_name="Bash", tool_input={"command": "echo after"}
        )
        self.assertEqual(
            second["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertFalse(self.state()["recovery_required"])

    def test_late_postcompact_does_not_rearm_delivered_epoch(self) -> None:
        self.run_hook("SessionStart", source="startup")
        self.run_hook("PreCompact", trigger="manual")
        response = self.run_hook("SessionStart", source="compact")
        self.assertIn(
            "Frozen Recovery Bundle",
            response["hookSpecificOutput"]["additionalContext"],
        )
        self.run_hook("PostCompact", trigger="manual")
        state = self.state()
        self.assertFalse(state["recovery_required"])
        self.assertEqual(state["recovery_status"], "ready-after-late-postcompact")

    def test_user_prompt_is_a_recovery_fallback(self) -> None:
        self.run_hook("SessionStart", source="startup")
        self.run_hook("PreCompact", trigger="auto")
        self.run_hook("PostCompact", trigger="auto")
        response = self.run_hook("UserPromptSubmit", prompt="continue")
        self.assertIn(
            "Frozen Recovery Bundle",
            response["hookSpecificOutput"]["additionalContext"],
        )
        self.assertFalse(self.state()["recovery_required"])

    def test_pending_recovery_survives_working_directory_change(self) -> None:
        self.run_hook("SessionStart", source="startup")
        self.run_hook("PreCompact", trigger="auto")
        self.run_hook("PostCompact", trigger="auto")
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        self.base["cwd"] = str(outside)

        response = self.run_hook(
            "PreToolUse", tool_name="Bash", tool_input={"command": "echo paused"}
        )
        decision = response["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Frozen Recovery Bundle", decision["additionalContext"])
        self.assertFalse(self.state()["recovery_required"])


if __name__ == "__main__":
    unittest.main()
