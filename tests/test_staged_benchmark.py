from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.run_staged_retrieval_benchmark import run_benchmark  # noqa: E402


class StagedRetrievalBenchmarkTests(unittest.TestCase):
    def test_staged_substrate_retains_recall_and_reduces_body_context(self) -> None:
        report = run_benchmark(distractors=40)

        self.assertEqual(report["survey"]["required_recall"], 1.0)
        self.assertGreaterEqual(report["survey"]["multi_hop_required_hits"], 1)
        self.assertTrue(report["negative_control_abstained"])
        self.assertGreater(report["context"]["staged_savings_fraction"], 0.35)
        self.assertIn("oracle-assisted", report["selection_mode"])


if __name__ == "__main__":
    unittest.main()
