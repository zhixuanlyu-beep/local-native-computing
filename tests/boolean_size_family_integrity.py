"""Input-independent construction, native semantics, bounds and evidence checks."""
import copy
from itertools import product
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ic_boolean_size_family as family
from ic_research_artifacts import GraphSpec


class BooleanSizeFamilyIntegrity(unittest.TestCase):
    def test_build_and_plug_do_not_consult_reference(self):
        with patch.object(family, "reference", side_effect=AssertionError("oracle called")):
            framework = family.build_framework(4, "balanced")
            before = framework.to_dict()
            for bits in product((False, True), repeat=4):
                instance = family.plug_inputs(framework, bits)
                self.assertEqual(len(instance.nodes), 7)
                self.assertEqual(instance.free, {("F", "OUT")})
                self.assertEqual(framework.to_dict(), before)
                # Every gate and each framework wire between gates survive
                # input plugging with the original cell names and port order.
                for i, kind in enumerate(framework.kinds):
                    self.assertEqual(instance.nodes[f"c{i}"], kind)
                for a, b in framework.wires:
                    if a[0] != "F" and b[0] != "F":
                        self.assertEqual(instance.adj[(f"c{a[0]}", a[1])], (f"c{b[0]}", b[1]))

    def test_all_inputs_at_non_power_width(self):
        for shape in family.SHAPES:
            framework = family.build_framework(5, shape)
            for bits in product((False, True), repeat=5):
                resources = []
                for policy in family.POLICIES:
                    case = family.run_case(framework, bits, policy)
                    self.assertEqual(case["status"], "passed")
                    self.assertEqual(case["expected_bit"], all(bits))
                    self.assertEqual(case["resources"]["initial_cells"], 9)
                    self.assertEqual(case["resources"]["peak_live_cells"], 9)
                    resources.append(family.canonical(case["resources"]))
                self.assertEqual(len(set(resources)), 1)

    def test_fixed_size_does_not_fix_work(self):
        framework = family.build_framework(2, "balanced")
        cases = [family.run_case(framework, bits, "snapshot-rounds")
                 for bits in product((False, True), repeat=2)]
        self.assertEqual(len({c["framework_sha256"] for c in cases}), 1)
        self.assertEqual([c["resources"]["primitive_interactions"] for c in cases], [2, 3, 1, 1])
        self.assertEqual({c["resources"]["initial_cells"] for c in cases}, {3})

    def test_all_true_shape_rounds(self):
        for width in (1, 3, 5, 8, 17):
            for shape in family.SHAPES:
                c = family.run_case(family.build_framework(width, shape), (True,) * width, "snapshot-rounds")
                # A local AND gate can annihilate before its RIGHT input is
                # ready, so ordinary Boolean-circuit depth is not this metric.
                expected = width.bit_length() - 1 if shape == "balanced" else width - 1
                self.assertEqual(c["synchronous_rounds"], expected)
                self.assertEqual(c["resources"]["primitive_interactions"], width - 1)

    def test_preconditions(self):
        for width in (0, 65, True, 2.0, "2"):
            with self.assertRaises(ValueError):
                family.build_framework(width, "balanced")
        with self.assertRaises(ValueError):
            family.build_framework(2, "other")
        framework = family.build_framework(2, "balanced")
        for bits in ([True, False], (1, False), (True, "false")):
            with self.assertRaises(TypeError):
                family.plug_inputs(framework, bits)
        with self.assertRaises(ValueError):
            family.plug_inputs(framework, (True,))
        for name, value in (("max_steps", -1), ("max_cells", True)):
            with self.assertRaises(ValueError):
                family.run_case(framework, (True, True), "first-active", **{name: value})

    def test_cutoffs_are_preserved(self):
        framework = family.build_framework(4, "balanced")
        for policy in family.POLICIES:
            c = family.run_case(framework, (True,) * 4, policy, max_steps=0)
            self.assertEqual(c["status"], "interaction-cutoff")
            self.assertFalse(c["whole_terminal_matches"])
            self.assertIsNone(c["synchronous_rounds"])
        c = family.run_case(framework, (True,) * 4, "snapshot-rounds", max_steps=1)
        self.assertEqual(c["status"], "interaction-cutoff")
        self.assertEqual(c["round_widths"], [1])
        self.assertIsNone(c["synchronous_rounds"])
        c = family.run_case(framework, (True,) * 4, "first-active", max_cells=6)
        self.assertEqual(c["status"], "resource-violation")
        self.assertEqual(c["primitive_pairs"], [])
        identity = family.build_framework(1, "balanced")
        c = family.run_case(identity, (False,), "snapshot-rounds", max_steps=0)
        self.assertEqual(c["status"], "passed")
        self.assertEqual(c["synchronous_rounds"], 0)

    def test_wrong_terminal_is_not_success(self):
        # OUT at the principal port leaves the input principals on auxiliaries:
        # this is quiescent but has the wrong complete graph.
        bad = GraphSpec(("g",), ("INPUT_0", "INPUT_1", "OUT"),
                        ((("F", "OUT"), (0, 0)), (("F", "INPUT_0"), (0, 1)),
                         (("F", "INPUT_1"), (0, 2))))
        case = family.run_case(bad, (True, False), "first-active")
        self.assertEqual(case["status"], "incorrect-terminal")
        self.assertFalse(case["whole_terminal_matches"])
        self.assertEqual(case["resources"]["final_cells"], 3)

    def test_exploration_cutoff_is_not_all_schedule_evidence(self):
        framework = family.build_framework(2, "balanced")
        with patch.object(family, "EXPLORATION_BOUNDS",
                          {"max_states": 1, "max_transitions": 0, "max_cells": 16}):
            record = family.exploration_record(framework, (True, True))
        self.assertEqual(record["status"], "not-accepted")
        self.assertFalse(record["exploration"]["complete"])
        self.assertFalse(record["exploration"]["all_executions_terminate"])

    def test_report_tampering(self):
        with patch.object(family, "WIDTHS", (1, 2)):
            report = family.build_report()
            family.verify_report(report)
            mutations = [
                lambda r: r["cases"][0].update(expected_bit=True),
                lambda r: r["cases"][-1]["primitive_pairs"].append(["c0", "c999"]),
                lambda r: r["frameworks"][0].update(sha256="0" * 64),
                lambda r: r["source_sha256"].update({"ic_primitive_port_verifier.py": "0" * 64}),
                lambda r: r["cases"][0]["resources"].update(initial_cells=True),
                lambda r: r["explorations"][0]["exploration"].update(complete=False),
                lambda r: r["cases"].pop(),
                lambda r: r.update(undeclared=True),
                lambda r: r["contract"]["bounds"].update(max_steps=0),
            ]
            for mutate in mutations:
                bad = copy.deepcopy(report)
                mutate(bad)
                with self.assertRaises(ValueError):
                    family.verify_report(bad)


if __name__ == "__main__":
    unittest.main()
