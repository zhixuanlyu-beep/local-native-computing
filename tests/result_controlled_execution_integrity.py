"""M6 constructors, whole-network semantics, strict report/trace evidence."""
from copy import deepcopy
import gzip
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ic_result_controlled_execution as execution
import ic_result_controlled_report as report
from ic_result_controlled_composition import PairList, build_local, local_expected, staged_case
from ic_result_controlled_evidence import run_case, POLICIES
from ic_result_controlled_library import load_control_library
from ic_schedule_audit import ScheduleTrace
from ic_research_artifacts import GraphSpec


class ResultControlledIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library_path = report.ROOT / "results/structure_library.json.gz"
        cls.library, cls.compiler, cls.bound = report.inputs(cls.library_path)

    def test_frozen_matrix_and_source_transition(self):
        self.assertEqual(len(execution.cases()), 24)
        self.assertEqual(execution.reference_states([2, 1, 0])[0], [True, False, True])
        self.assertEqual(execution.reference_states([2, 4, 2])[0], [True, False, True])
        self.assertEqual(execution.BUDGET, {"max_steps": 2000000, "max_cells": 250000})
        self.assertEqual(execution.SMALL_BUDGET,
                         {"max_states": 4096, "max_transitions": 32768, "max_cells": 128})
        with patch.object(report, "cases", return_value=[{"name": "narrowed", "numbers": [0]}]):
            with self.assertRaises(ValueError):
                report.inputs(self.library_path)

    def test_constructor_has_no_flags_or_reference_evaluation(self):
        for numbers in ([0], [1, 2, 4], [2, 1, 0]):
            with patch.object(execution, "reference_result", side_effect=AssertionError("oracle")), \
                 patch.object(execution, "reference_states", side_effect=AssertionError("oracle")), \
                 patch.object(execution, "source_result_graph", side_effect=AssertionError("oracle")):
                built = execution.build_result_sequence(numbers, library=self.library, compiler=self.compiler)
                built.net.check()
                self.assertTrue(all("enabled" not in stage for stage in built.stages))
        with self.assertRaises(TypeError):
            execution.build_result_sequence([0], flags=[True], library=self.library)

    def test_invalid_inputs_are_precondition_rejections(self):
        for numbers in ([], [0] * 4, [True], [-1], [5], [0.5]):
            with self.subTest(numbers=numbers), self.assertRaises(ValueError):
                execution.build_result_sequence(numbers, library=self.library, compiler=self.compiler)
        for depth in (-1, True, 0.5):
            with self.assertRaises(ValueError):
                execution.build_result_sequence([0], library=self.library, reader_depth=depth)

    def test_real_result_and_skip_recovery_under_all_three_policies(self):
        numbers = [2, 1, 0]
        target = execution.expected(self.compiler, numbers, self.library)
        for policy in POLICIES:
            built = execution.build_result_sequence(numbers, library=self.library, compiler=self.compiler)
            result = run_case(built, target, PairList(), policy, expected_states=[True, False, True])
            self.assertEqual(result["status"], "passed", result["protocol_violations"])
            self.assertTrue(result["whole_graph_matches_reference"])
            self.assertEqual(result["resources"]["cyclic_wires"], 0)

    def test_budget_statuses_and_complete_graph(self):
        built = execution.build_result_sequence([0], library=self.library, compiler=self.compiler)
        target = execution.expected(self.compiler, [0], self.library)
        for budget, status in (({"max_steps": 0}, "incomplete"),
                               ({"max_cells": 0}, "resource-violation")):
            result = run_case(built, target, PairList(), POLICIES[0], budget=budget, expected_states=[True])
            self.assertEqual(result["status"], status)
        with self.assertRaises(ValueError):
            run_case(built, target, PairList(), POLICIES[0], budget={"max_steps": True})

    def test_correct_final_graph_does_not_excuse_premature_handoff(self):
        negative = report.negative_probes(self.library, self.compiler, PairList())
        self.assertEqual(negative["shallow_reader"]["status"], "wrong-normal-form")
        wrong = negative["premature_handoff"]
        self.assertTrue(wrong["whole_graph_matches_reference"])
        self.assertEqual(wrong["status"], "protocol-violation")
        self.assertTrue(wrong["protocol_violations"])

    def fixture(self):
        bound = deepcopy(self.bound)
        bound["local_cases"] = [{"number": 0, "enabled": bit} for bit in (False, True)]
        bound["cases"] = [{"name": "reduced-zero", "numbers": [0]}]
        return self.library, self.compiler, bound

    def test_saved_trace_replay_and_all_evidence_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.gz"
            context = self.fixture()
            original = report._suite(path, self.library_path, context=context)
            rebuilt = report._suite(path, self.library_path, replay=True, context=context)
            self.assertEqual(original, rebuilt)
            self.assertEqual(original["status"], "passed")
            for section in ("bindings", "metadata", "local_cases", "cases", "staged", "trace"):
                changed = deepcopy(original)
                changed[section] = None
                with self.subTest(section=section), self.assertRaises(ValueError):
                    report.compare_report(changed, rebuilt)
            raw = gzip.decompress(path.read_bytes())
            split = raw.index(b"\n") + 1
            for name, invalid in (("truncated", raw[:-8]), ("appended", raw + b"\0" * 8),
                                  ("pair", raw[:split] + b"\xff" * 8 + raw[split + 8:])):
                damaged = Path(directory) / (name + ".gz")
                damaged.write_bytes(gzip.compress(invalid))
                with self.subTest(name=name), self.assertRaises(ValueError):
                    report._suite(damaged, self.library_path, replay=True, context=context)


if __name__ == "__main__":
    unittest.main()
