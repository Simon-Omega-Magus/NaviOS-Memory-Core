from __future__ import annotations

import json
import hashlib
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
    assimilate_project,
    format_packet_markdown,
    index_project,
    initialize_project,
    query_index,
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

    def test_assimilate_plain_notes_without_mutating_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            source = root / "ordinary-notes.md"
            original = (
                b"# Ordinary Notes\n\n"
                b"A regular document becomes derived memory cells without edits.\n"
            )
            source.write_bytes(original)

            report = assimilate_project(root)

            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(report["source_mode"], "read-only")
            self.assertEqual(report["source_documents_mutated"], 0)
            self.assertIn(".navios/config.json", report["created"])
            self.assertIn(".navios/relationships.json", report["created"])
            packet = query_index(root, ["derived memory cells"])
            self.assertFalse(packet["abstained"])
            self.assertEqual(packet["results"][0]["source"]["path"], "ordinary-notes.md")

    def test_cultivate_creates_append_only_provenance_proposal(self) -> None:
        original = (self.root / "architecture.md").read_bytes()
        source_hash = hashlib.sha256(original).hexdigest()
        arguments = {
            "title": "Compaction retrieval lesson",
            "body": (
                "A body-free survey should precede selective hydration when "
                "candidate ambiguity is high."
            ),
            "sources": [f"architecture.md::{source_hash}"],
            "kind": "retrieval-lesson",
            "created_by": "test-agent",
            "confidence": 0.9,
            "tags": ["memory", "retrieval"],
        }

        first = cultivate_proposal(self.root, **arguments)
        second = cultivate_proposal(self.root, **arguments)

        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertTrue(first["indexed"])
        self.assertIsNone(first["warning"])
        self.assertEqual(first["proposal_id"], second["proposal_id"])
        self.assertEqual((self.root / "architecture.md").read_bytes(), original)
        proposals = list((self.root / ".navios/cells/proposals").glob("*.md"))
        self.assertEqual(len(proposals), 1)
        proposal = proposals[0].read_text(encoding="utf-8")
        self.assertIn("status: proposed", proposal)
        self.assertIn("authority: evidence-only", proposal)
        self.assertIn(source_hash, proposal)
        packet = query_index(self.root, ["body-free selective hydration ambiguity"])
        self.assertFalse(packet["abstained"])
        retrieved = next(
            result
            for result in packet["results"]
            if result["source"]["path"] == first["proposal_path"]
        )
        self.assertEqual(retrieved["memory"]["origin"], "agent-derived")
        self.assertEqual(retrieved["memory"]["authority"], "evidence-only")
        self.assertEqual(retrieved["memory"]["status"], "proposed")
        self.assertEqual(
            retrieved["memory"]["classification"], "proposal-path-enforced"
        )
        survey = survey_index(
            self.root, ["body-free selective hydration ambiguity"]
        )
        surveyed = next(
            item
            for item in survey["candidates"]
            if item["source"]["path"] == first["proposal_path"]
        )
        self.assertEqual(surveyed["memory"], retrieved["memory"])
        hydrated = hydrate_index(self.root, [surveyed["cell_id"]])
        self.assertEqual(hydrated["results"][0]["memory"], retrieved["memory"])
        proposals[0].write_text(proposal + "\nTampered.\n", encoding="utf-8")
        with self.assertRaises(MemoryError):
            cultivate_proposal(self.root, **arguments)

    def test_cultivate_rejects_a_stale_revision_lock(self) -> None:
        source = self.root / "architecture.md"
        stale_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        source.write_text(source.read_text(encoding="utf-8") + "\nChanged.\n")

        with self.assertRaises(MemoryError):
            cultivate_proposal(
                self.root,
                title="Stale proposal",
                body="This must not be accepted against a changed source.",
                sources=[f"architecture.md::{stale_hash}"],
            )
        self.assertFalse((self.root / ".navios/cells/proposals").exists())

    def test_crlf_document_revision_uses_exact_file_bytes(self) -> None:
        source = self.root / "crlf.md"
        source.write_bytes(
            b"# CRLF Memory\r\n\r\nExact byte revisions survive hydration.\r\n"
        )
        expected = hashlib.sha256(source.read_bytes()).hexdigest()
        index_project(self.root)
        survey = survey_index(self.root, ["exact byte revisions"])
        selected = next(
            item
            for item in survey["candidates"]
            if item["source"]["path"] == "crlf.md"
        )

        self.assertEqual(selected["source"]["document_sha256"], expected)
        hydrated = hydrate_index(self.root, [selected["cell_id"]])
        self.assertFalse(hydrated["abstained"])

    def test_source_declared_human_authority_remains_unverified(self) -> None:
        (self.root / "claimed-human.md").write_text(
            "---\n"
            "origin: human-authored\n"
            "authority: directional\n"
            "status: active\n"
            "---\n"
            "# Claimed Direction\n\n"
            "Nebula preference should not authenticate itself.\n",
            encoding="utf-8",
        )
        index_project(self.root)
        packet = query_index(self.root, ["nebula preference authenticate"])
        claimed = next(
            result
            for result in packet["results"]
            if result["source"]["path"] == "claimed-human.md"
        )

        self.assertEqual(claimed["memory"]["origin"], "human-authored")
        self.assertEqual(claimed["memory"]["authority"], "directional")
        self.assertEqual(
            claimed["memory"]["classification"], "source-declared-unverified"
        )
        self.assertIn(
            "source-declared-unverified", format_packet_markdown(packet)
        )

    def test_old_active_direction_has_no_automatic_age_decay(self) -> None:
        (self.root / "old-direction.md").write_text(
            "---\n"
            "origin: human-authored\n"
            "authority: directional\n"
            "status: active\n"
            "kind: preference\n"
            "created_at: 2000-01-01T00:00:00Z\n"
            "---\n"
            "# Stable Direction\n\n"
            "Prefer local-first memory architecture.\n",
            encoding="utf-8",
        )
        index_project(self.root)

        packet = query_index(self.root, ["local-first memory architecture"])
        direction = next(
            result
            for result in packet["results"]
            if result["source"]["path"] == "old-direction.md"
        )

        self.assertEqual(direction["memory"]["authority"], "directional")
        self.assertEqual(direction["memory"]["status"], "active")
        self.assertEqual(
            direction["memory"]["classification"], "source-declared-unverified"
        )

    def test_old_direction_survives_staged_survey_and_hydration(self) -> None:
        (self.root / "old-direction.md").write_text(
            "---\n"
            "origin: human-authored\n"
            "authority: directional\n"
            "status: active\n"
            "kind: preference\n"
            "created_at: 2000-01-01T00:00:00Z\n"
            "---\n"
            "# Stable Direction\n\n"
            "Prefer local-first memory architecture.\n",
            encoding="utf-8",
        )
        index_project(self.root)

        survey = survey_index(self.root, ["local-first memory architecture"])
        candidate = next(
            item
            for item in survey["candidates"]
            if item["source"]["path"] == "old-direction.md"
        )
        self.assertEqual(candidate["memory"]["authority"], "directional")
        self.assertEqual(candidate["memory"]["status"], "active")

        hydrated = hydrate_index(self.root, [candidate["cell_id"]])
        direction = hydrated["results"][0]
        self.assertEqual(direction["memory"]["authority"], "directional")
        self.assertEqual(direction["memory"]["status"], "active")
        self.assertEqual(
            direction["memory"]["classification"], "source-declared-unverified"
        )

    def test_will_conflict_queue_preserves_claims_without_execution_effect(self) -> None:
        original = (self.root / "architecture.md").read_bytes()
        source_hash = hashlib.sha256(original).hexdigest()
        constraint_hash = hashlib.sha256(
            (self.root / "constraints.md").read_bytes()
        ).hexdigest()
        arguments = {
            "claim_ids": ["claim:older", "claim:newer"],
            "question": "Should the newer interface preference replace the older one?",
            "scope": "demo.interface",
            "sources": [
                f"architecture.md::{source_hash}",
                f"constraints.md::{constraint_hash}",
            ],
            "created_by": "test-agent",
            "proposed_interpretation": "Retain both until Simon resolves the scope.",
            "blocked_action": "Selecting the final interface default.",
        }

        first = queue_will_question(
            self.root, created_at="2026-07-18T12:00:00Z", **arguments
        )
        second = queue_will_question(
            self.root, created_at="2026-07-19T12:00:00Z", **arguments
        )
        queue = list_will_questions(self.root)

        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["question_id"], second["question_id"])
        self.assertEqual(queue["open_count"], 1)
        question = queue["questions"][0]
        self.assertEqual(
            question["directional_effect"],
            "preserve-all-cited-claims-pending-resolution",
        )
        self.assertEqual(question["execution_effect"], "none")
        self.assertFalse(question["age_decay"])
        self.assertEqual((self.root / "architecture.md").read_bytes(), original)

    def test_will_conflict_queue_rejects_single_claim_and_tampering(self) -> None:
        with self.assertRaises(MemoryError):
            queue_will_question(
                self.root,
                claim_ids=["claim:only"],
                question="Is this enough?",
                scope="demo",
                sources=["architecture.md"],
            )

        report = queue_will_question(
            self.root,
            claim_ids=["claim:a", "claim:b"],
            question="Which claim governs this scope?",
            scope="demo",
            sources=["architecture.md", "constraints.md"],
        )
        path = self.root / report["question_path"]
        value = json.loads(path.read_text(encoding="utf-8"))
        value["age_decay"] = True
        path.write_text(json.dumps(value), encoding="utf-8")

        with self.assertRaises(MemoryError):
            list_will_questions(self.root)

    def test_will_queue_revalidates_sources_and_rejects_hardlink_aliases(self) -> None:
        report = queue_will_question(
            self.root,
            claim_ids=["claim:a", "claim:b"],
            question="Which claim governs this scope?",
            scope="demo",
            sources=["architecture.md", "constraints.md"],
        )
        path = self.root / report["question_path"]
        alias = self.root / "will-question-alias.json"
        os.link(path, alias)
        with self.assertRaises(MemoryError):
            list_will_questions(self.root)
        alias.unlink()

        (self.root / "constraints.md").write_text(
            "# Changed\n\nThe cited source revision no longer exists.\n",
            encoding="utf-8",
        )
        with self.assertRaises(MemoryError):
            list_will_questions(self.root)

    def test_hardlinked_control_file_is_rejected(self) -> None:
        config = self.root / ".navios/config.json"
        os.link(config, self.root / "config-alias.json")
        with self.assertRaises(MemoryError):
            index_project(self.root)

    def test_index_rejects_a_symlinked_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as external_name:
            external = Path(external_name) / "outside.sqlite3"
            sentinel = b"do not replace"
            external.write_bytes(sentinel)
            (self.root / DEFAULT_DB).symlink_to(external)

            with self.assertRaises(MemoryError):
                index_project(self.root)
            self.assertEqual(external.read_bytes(), sentinel)

    def test_initialize_rejects_a_symlinked_memory_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            base = Path(temporary_name)
            root = base / "project"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (root / ".navios").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(MemoryError):
                initialize_project(root)
            self.assertEqual(list(outside.iterdir()), [])

    def test_cultivate_rejects_a_symlinked_proposal_directory(self) -> None:
        with tempfile.TemporaryDirectory() as external_name:
            external = Path(external_name)
            cells = self.root / ".navios/cells"
            cells.mkdir()
            (cells / "proposals").symlink_to(external, target_is_directory=True)

            with self.assertRaises(MemoryError):
                cultivate_proposal(
                    self.root,
                    title="Unsafe output",
                    body="This proposal must remain inside the project.",
                    sources=["architecture.md"],
                )
            self.assertEqual(list(external.iterdir()), [])

    def test_hardlinked_sources_require_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as external_name:
            external = Path(external_name) / "outside.md"
            external.write_text(
                "# Hardlink\n\nQuasar hardlink evidence.\n", encoding="utf-8"
            )
            linked = self.root / "linked.md"
            try:
                os.link(external, linked)
            except OSError as exc:
                self.skipTest(f"hardlinks unavailable: {exc}")

            index_project(self.root)
            self.assertTrue(query_index(self.root, ["quasar hardlink"])["abstained"])

            config_path = self.root / ".navios/config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["allow_hardlinked_sources"] = True
            config_path.write_text(
                json.dumps(config, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            index_project(self.root)
            packet = query_index(self.root, ["quasar hardlink"])
            self.assertFalse(packet["abstained"])
            selected = next(
                result
                for result in packet["results"]
                if result["source"]["path"] == "linked.md"
            )
            hydrated = hydrate_index(self.root, [selected["cell_id"]])
            self.assertFalse(hydrated["abstained"])

    def test_non_destructive_relationship_overlay_adds_typed_edge(self) -> None:
        overlay = self.root / ".navios/relationships.json"
        overlay.write_text(
            json.dumps(
                {
                    "schema": "navios-memory-relationships-v1",
                    "relations": [
                        {
                            "source": "architecture.md",
                            "target": "constraints.md",
                            "relation": "guards",
                            "weight": 0.95,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        report = index_project(self.root)
        connection = sqlite3.connect(self.root / DEFAULT_DB)
        count = connection.execute(
            "SELECT count(*) FROM edges WHERE relation = 'overlay:guards' "
            "AND weight = 0.95"
        ).fetchone()[0]
        connection.close()

        self.assertEqual(report["overlay_relations"], 1)
        self.assertEqual(count, 1)

    def test_relationship_overlay_rejects_unindexed_paths(self) -> None:
        (self.root / ".navios/relationships.json").write_text(
            json.dumps(
                {
                    "schema": "navios-memory-relationships-v1",
                    "relations": [
                        {
                            "source": "architecture.md",
                            "target": "../outside.md",
                            "relation": "unsafe",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(MemoryError):
            index_project(self.root)

    def test_body_free_survey_triangulates_without_paragraph_text(self) -> None:
        index_project(self.root)
        report = survey_index(
            self.root,
            [
                "authoritative checkpoint compaction recovery",
                "unsafe tool evidence provenance",
            ],
            candidates_per_query=200,
            graph_hops=2,
        )

        self.assertFalse(report["abstained"])
        self.assertGreater(report["multi_query_candidate_count"], 0)
        self.assertTrue(all("text" not in item for item in report["candidates"]))
        self.assertTrue(
            any(
                item["best_graph"]["hops"] > 0
                and len(item["best_graph"]["path"])
                == item["best_graph"]["hops"]
                for item in report["candidates"]
            )
        )
        rendered = format_survey_markdown(report, show=20)
        self.assertNotIn("Never delete user data", rendered)
        self.assertIn("Paths, headings, line ranges", rendered)
        self.assertIn("Memory Architecture", rendered)

    def test_survey_enforces_two_hundred_candidates_per_query(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            initialize_project(root)
            for number in range(225):
                (root / f"note-{number:03d}.md").write_text(
                    f"# Note {number}\n\nSharedneedle evidence number {number}.\n",
                    encoding="utf-8",
                )
            index_project(root)
            report = survey_index(
                root,
                ["sharedneedle"],
                candidates_per_query=200,
                graph_hops=0,
            )

            self.assertEqual(report["per_query_candidate_counts"], [200])
            self.assertEqual(report["candidate_count"], 200)

    def test_selective_hydration_accepts_prefix_and_checks_source_revision(self) -> None:
        index_project(self.root)
        survey = survey_index(
            self.root,
            ["authoritative checkpoint compaction"],
            candidates_per_query=20,
        )
        selected = survey["candidates"][0]
        packet = hydrate_index(self.root, [selected["cell_id"][:16]])

        self.assertFalse(packet["abstained"])
        self.assertEqual(packet["results"][0]["cell_id"], selected["cell_id"])
        self.assertIn(packet["results"][0]["text"], format_hydration_markdown(packet))

        source = self.root / selected["source"]["path"]
        source.write_text(source.read_text(encoding="utf-8") + "\nChanged.\n")
        with self.assertRaises(MemoryError):
            hydrate_index(self.root, [selected["cell_id"]])

    def test_selective_hydration_never_emits_partial_cell(self) -> None:
        index_project(self.root)
        survey = survey_index(
            self.root,
            ["authoritative checkpoint compaction"],
            candidates_per_query=20,
        )
        packet = hydrate_index(
            self.root,
            [survey["candidates"][0]["cell_id"]],
            max_context_chars=120,
        )
        self.assertTrue(packet["abstained"])
        self.assertEqual(packet["results"], [])

    def test_direct_query_rejects_a_stale_source_revision(self) -> None:
        index_project(self.root)
        source = self.root / "architecture.md"
        source.write_text(source.read_text(encoding="utf-8") + "\nChanged.\n")

        with self.assertRaises(MemoryError):
            query_index(self.root, ["authoritative checkpoint compaction"])

    def test_direct_query_rechecks_hardlink_policy(self) -> None:
        with tempfile.TemporaryDirectory() as external_name:
            source = self.root / "architecture.md"
            external = Path(external_name) / "same-bytes.md"
            external.write_bytes(source.read_bytes())
            index_project(self.root)
            source.unlink()
            os.link(external, source)

            with self.assertRaises(MemoryError):
                query_index(self.root, ["authoritative checkpoint compaction"])

    def test_selective_hydration_rejects_tampered_escape_paths(self) -> None:
        for tampered_path in ("../outside.md", "/etc/hosts"):
            with self.subTest(tampered_path=tampered_path):
                with tempfile.TemporaryDirectory() as temporary_name:
                    base = Path(temporary_name)
                    root = base / "project"
                    root.mkdir()
                    initialize_project(root)
                    (root / "note.md").write_text(
                        "# Note\n\nIndexed body.\n", encoding="utf-8"
                    )
                    outside = base / "outside.md"
                    outside.write_text(
                        "# Outside\n\nExternal body.\n", encoding="utf-8"
                    )
                    index_project(root)
                    connection = sqlite3.connect(root / DEFAULT_DB)
                    cell_id = connection.execute(
                        "SELECT cell_id FROM cells WHERE path = 'note.md'"
                    ).fetchone()[0]
                    document_hash = hashlib.sha256(outside.read_bytes()).hexdigest()
                    connection.execute(
                        "UPDATE documents SET path = ?, content_sha256 = ? "
                        "WHERE path = 'note.md'",
                        (tampered_path, document_hash),
                    )
                    connection.execute(
                        "UPDATE cells SET path = ? WHERE path = 'note.md'",
                        (tampered_path,),
                    )
                    connection.commit()
                    connection.close()

                    with self.assertRaises(MemoryError):
                        hydrate_index(root, [cell_id])

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


class CLITests(unittest.TestCase):
    def test_assimilate_survey_and_hydrate_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            (root / "notes.md").write_text(
                "# Memory Growth\n\n"
                "Ordinary notes become provenance-linked derived cells.\n",
                encoding="utf-8",
            )
            (root / "direction.md").write_text(
                "# Direction\n\nKeep old and new preferences visible until resolved.\n",
                encoding="utf-8",
            )
            command = PLUGIN_ROOT / "scripts/navios-memory"

            assimilate = subprocess.run(
                [sys.executable, str(command), "--root", str(root), "assimilate", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(assimilate.returncode, 0, assimilate.stderr)
            self.assertEqual(json.loads(assimilate.stdout)["source_mode"], "read-only")

            survey = subprocess.run(
                [
                    sys.executable,
                    str(command),
                    "--root",
                    str(root),
                    "survey",
                    "provenance derived cells",
                    "memory growth ordinary notes",
                    "--candidates",
                    "200",
                    "--hops",
                    "2",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(survey.returncode, 0, survey.stderr)
            report = json.loads(survey.stdout)
            self.assertGreater(report["candidate_count"], 0)
            self.assertTrue(all("text" not in item for item in report["candidates"]))

            hydrate = subprocess.run(
                [
                    sys.executable,
                    str(command),
                    "--root",
                    str(root),
                    "hydrate",
                    report["candidates"][0]["cell_id"][:16],
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(hydrate.returncode, 0, hydrate.stderr)
            self.assertIn("text", json.loads(hydrate.stdout)["results"][0])

            cultivate = subprocess.run(
                [
                    sys.executable,
                    str(command),
                    "--root",
                    str(root),
                    "cultivate",
                    "--title",
                    "Derived memory lesson",
                    "--body",
                    "Selective hydration keeps irrelevant cell bodies out.",
                    "--source",
                    "notes.md",
                    "--kind",
                    "retrieval-lesson",
                    "--tag",
                    "retrieval",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(cultivate.returncode, 0, cultivate.stderr)
            cultivation = json.loads(cultivate.stdout)
            self.assertEqual(cultivation["status"], "proposed")
            self.assertTrue((root / cultivation["proposal_path"]).is_file())

            queued = subprocess.run(
                [
                    sys.executable,
                    str(command),
                    "--root",
                    str(root),
                    "queue-will-question",
                    "--claim",
                    "claim:old",
                    "--claim",
                    "claim:new",
                    "--question",
                    "Which claim governs this test?",
                    "--scope",
                    "test.scope",
                    "--source",
                    "notes.md",
                    "--source",
                    "direction.md",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(queued.returncode, 0, queued.stderr)
            self.assertEqual(json.loads(queued.stdout)["execution_effect"], "none")

            listed = subprocess.run(
                [
                    sys.executable,
                    str(command),
                    "--root",
                    str(root),
                    "will-questions",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertEqual(json.loads(listed.stdout)["open_count"], 1)


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

    def test_prompt_reflex_does_not_inject_a_stale_indexed_body(self) -> None:
        self.run_hook("SessionStart", source="startup")
        source = self.root / "memory.md"
        source.write_text(source.read_text(encoding="utf-8") + "\nChanged.\n")

        response = self.run_hook(
            "UserPromptSubmit", prompt="Where are graph safety constraints retrieved?"
        )

        self.assertEqual(response, {})
        self.assertEqual(self.state()["last_retrieval_context"], "")

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
