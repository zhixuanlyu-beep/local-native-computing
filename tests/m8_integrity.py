"""M8 coverage and rejection of incomplete or altered evidence."""
from copy import deepcopy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ic_coherent_feedback import read_json, write_json
import ic_m8


REPORT = ic_m8.ROOT / "results/m8_concept_library.json.gz"


class M8Integrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.expected = ic_m8._reconstruct(ic_m8.M7_REPORT)
        cls.claimed = read_json(REPORT)
        cls.library = cls.claimed["library"]
        cls.semantics = cls.expected["counting"]["semantic_evidence"]

    def test_full_count_matrix_and_idempotence_counterexample(self):
        counting = self.expected["counting"]
        self.assertEqual(self.expected["implementation_status"], "accepted")
        self.assertEqual(counting["candidate_input_checks"], 101_504)
        self.assertEqual(counting["transform_checks"], 116)
        self.assertEqual({n: len(items) for n, items in self.semantics.items()}, {"2": 18, "3": 98})
        self.assertEqual(counting["boolean_counterexample"]["status"], "rejected")
        self.assertEqual(counting["boolean_counterexample"]["integer_or"], 2)
        self.assertEqual(self.expected["unfinished"], [])

    def test_verify_does_not_use_induction_producer(self):
        with (patch.object(ic_m8, "induce_concepts", side_effect=AssertionError("induction producer called")),
              patch.object(ic_m8, "_reconstruct", return_value=(self.rows, self.expected))):
            self.assertEqual(ic_m8.verify(REPORT), self.claimed)

    def test_concept_evidence_deletion_and_mutation_rejected(self):
        for collection in ("pairs", "rules", "manual_axioms"):
            with self.subTest(deletion=collection):
                changed = {**self.library, collection: self.library[collection][:-1]}
                with self.assertRaises(ValueError):
                    ic_m8.verify_concept_library(self.rows, changed, semantic_evidence=self.semantics)
        first_pair = self.library["pairs"][0]
        changed_pair = {**first_pair, "outcome": "forged"}
        altered = {**self.library, "pairs": [changed_pair, *self.library["pairs"][1:]]}
        with self.assertRaises(ValueError):
            ic_m8.verify_concept_library(self.rows, altered, semantic_evidence=self.semantics)

    def test_distinct_compiled_ir_pair_support(self):
        for rule in self.library["rules"]:
            digests = {pair["ir_pair_sha256"] for pair in rule["support_pairs"]}
            with self.subTest(rule=rule["id"]):
                self.assertEqual(len(digests), len(rule["support_pairs"]))
                self.assertEqual(rule["support"], len(digests))
                self.assertGreaterEqual(rule["support"], 2)

    def test_count_evidence_mutation_rejected(self):
        altered = deepcopy(self.claimed)
        altered["counting"]["candidate_input_checks"] -= 1
        with TemporaryDirectory() as folder:
            path = Path(folder) / "changed.json.gz"
            write_json(path, altered)
            with (patch.object(ic_m8, "_reconstruct", return_value=(self.rows, self.expected)),
                  self.assertRaisesRegex(ValueError, "count or baseline evidence")):
                ic_m8.verify(path)

    def test_altered_m7_archive_rejected(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "m7.json.gz"
            path.write_bytes(ic_m8.M7_REPORT.read_bytes() + b"tampering")
            with self.assertRaisesRegex(ValueError, "M7 FIFO report digest"):
                ic_m8.load_frozen_m7_rows(path, read_json(ic_m8.FREEZE))

    def test_count_positivity_checks_the_complete_terminal(self):
        baseline = self.rows[2][0]
        record = {**baseline["records"][0], "final_graph_sha256": "0" * 64}
        changed = {**baseline, "records": [record, *baseline["records"][1:]]}
        rows = {**self.rows, 2: [changed, *self.rows[2][1:]]}
        result = ic_m8.verify_m8_counts(rows)
        self.assertEqual(result["status"], "not-accepted")
        self.assertEqual(result["count_mismatches"], [])
        self.assertEqual(len(result["terminal_mismatches"]), 1)


if __name__ == "__main__":
    unittest.main()
