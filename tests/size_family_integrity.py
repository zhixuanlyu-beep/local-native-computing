"""Resource/round invariants, whole-output checks and report tampering probes."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ic_size_family_audit as audit


class SizeFamilyIntegrity(unittest.TestCase):
    def test_non_power_sizes_and_shape_depth(self):
        for n in (1, 3, 5, 7, 9, 17):
            balanced = audit.run_case(n, "balanced", "snapshot-rounds")
            comb = audit.run_case(n, "comb", "snapshot-rounds")
            for field in ("primitive_interactions", "runtime_cells_allocated",
                          "total_symbolic_cells_allocated", "peak_live_cells", "final_cells"):
                self.assertEqual(balanced["execution"][field], comb["execution"][field])
            self.assertEqual(balanced["execution"]["synchronous_rounds"], (n - 1).bit_length() + 1)
            self.assertEqual(comb["execution"]["synchronous_rounds"], n)
            self.assertEqual(balanced["construction"]["graph_api_calls"],
                             {"cell": 2 * n, "boundary": 2, "link": 2 * n + 1})

    def test_serial_is_work_not_parallel_depth(self):
        case = audit.run_case(9, "balanced", "first-active")
        self.assertEqual(case["execution"]["primitive_interactions"], 17)
        self.assertIsNone(case["execution"]["synchronous_rounds"])
        self.assertIsNone(case["execution"]["round_widths"])

    def test_preconditions(self):
        for n in (0, -1, 65, True, 2.0, "2"):
            with self.assertRaises(ValueError):
                audit.family_shape(n, "balanced")
        with self.assertRaises(ValueError):
            audit.family_shape(2, "other")
        with self.assertRaises(ValueError):
            audit.run_case(2, "balanced", "other")

    def test_wrong_output_is_rejected(self):
        with patch.object(audit, "decode_tree", return_value=("e",)):
            with self.assertRaises(AssertionError):
                audit.run_case(3, "comb", "snapshot-rounds")

    def test_report_tampering(self):
        # Small real reconstruction matrix keeps adversarial tests inexpensive.
        with patch.object(audit, "LEAF_COUNTS", (1, 3)):
            report = audit.build_report()
            audit.verify_report(report)
            mutants = []
            for metric in ("primitive_interactions", "peak_live_cells", "synchronous_rounds"):
                bad = copy.deepcopy(report)
                bad["cases"][1]["execution"][metric] += 1
                mutants.append(bad)
            bad = copy.deepcopy(report)
            bad["cases"][0]["primitive_pairs"][0][0] = "c999"
            mutants.append(bad)
            bad = copy.deepcopy(report)
            bad["source_sha256"]["ic_primitive_port_verifier.py"] = "0" * 64
            mutants.append(bad)
            bad = copy.deepcopy(report)
            bad["cases"][0]["leaves"] = True  # JSON true must not pass as integer 1.
            mutants.append(bad)
            bad = copy.deepcopy(report)
            bad["cases"].pop()
            mutants.append(bad)
            bad = copy.deepcopy(report)
            bad["undeclared"] = 0
            mutants.append(bad)
            bad = copy.deepcopy(report)
            bad["cases"][0]["primitive_pairs"].append(["c0", "c1"])
            mutants.append(bad)
            for bad in mutants:
                with self.assertRaises(ValueError):
                    audit.verify_report(bad)


if __name__ == "__main__":
    unittest.main()
