"""Adversarial checks for the frozen M7 native S/P Boolean backend."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ic_localization.backend import (
    REPRESENTATIONS,
    copy_value,
    decode,
    foundation_cases,
    literal,
    literal_spec,
    validate_literal,
)
from ic_localization.evidence import run_network
from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec
from ic_observation_contracts import value_spec


def expected_outputs(values):
    net = Net()
    for label, bit in values:
        value_spec("A", bit).instantiate(net, {"ROOT": net.boundary(label)})
    return GraphSpec.from_net(net)


def mutate_first_selector_branch(spec):
    """Change one selector leaf from epsilon to the true A loop."""
    kinds = list(spec.kinds)
    wires = list(spec.wires)
    for index, kind in enumerate(kinds):
        if kind == "e":
            kinds[index] = "g"
            wires.append(((index, 1), (index, 2)))
            break
    return GraphSpec(tuple(kinds), spec.boundaries, tuple(wires), spec.cycles)


class LocalizationBackendIntegrity(unittest.TestCase):
    def test_raw_port_api_and_exact_literal_fingerprints(self):
        for rep in REPRESENTATIONS:
            for bit in (False, True):
                net = Net()
                port = literal(net, rep, bit)
                self.assertIn(port, net.adj)
                self.assertIsNone(net.adj[port])
                self.assertEqual(validate_literal(literal_spec(rep, bit), rep), literal_spec(rep, bit))
        with self.assertRaisesRegex(ValueError, "representation"):
            literal(Net(), "A", True)
        with self.assertRaisesRegex(TypeError, "Boolean"):
            literal(Net(), "S", 1)

    def test_foundation_matrix_is_frozen_at_32_unique_cases(self):
        cases = foundation_cases()
        names = [case["name"] for case in cases]
        self.assertEqual(len(cases), 32)
        self.assertEqual(len(set(names)), 32)
        for case in cases:
            self.assertIsInstance(case["initial"], GraphSpec)
            self.assertIsInstance(case["expected"], GraphSpec)
            case["initial"].instantiate().check()
            case["expected"].instantiate().check()

    def test_invalid_p_dual_view_is_rejected(self):
        from ic_coherent_output_decoder import port_graph_isomorphic
        from ic_native_control_packets import control_packet
        for bit in (False, True):
            self.assertTrue(port_graph_isomorphic(literal_spec("P", bit).instantiate(),
                                                  control_packet(bit).instantiate()))
        for wrong in (literal_spec("S", True), literal_spec("S", False),
                      value_spec("A", True), value_spec("A", False)):
            with self.assertRaisesRegex(ValueError, "inconsistent|malformed"):
                validate_literal(wrong, "P")
        changed = mutate_first_selector_branch(literal_spec("P", True))
        with self.assertRaisesRegex(ValueError, "inconsistent|malformed"):
            validate_literal(changed, "P")

    def test_wrong_selector_branch_is_a_counterexample_not_a_crash(self):
        net = Net()
        decode(net, "S", literal(net, "S", False), net.boundary("OUT"))
        initial = GraphSpec.from_net(net)
        record = run_network(initial, expected_outputs([("OUT", True)]))
        self.assertEqual(record["status"], "wrong-normal-form")
        self.assertFalse(record["whole_graph_matches_reference"])

    def test_copy_requires_distinct_free_ports(self):
        net = Net()
        first, second = copy_value(net, literal(net, "S", True), 2)
        self.assertNotEqual(first, second)
        self.assertIsNone(net.adj[first])
        self.assertIsNone(net.adj[second])
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            copy_value(net, second, -1)

    def test_missing_fanout_is_rejected_when_reused_port_is_consumed_twice(self):
        from ic_localization.backend import _select

        net = Net()
        control = literal(net, "S", True)
        branch = literal(net, "S", True)
        with self.assertRaises(AssertionError):
            _select(net, "S", control, branch, branch)

    def test_zero_copy_erases_and_copy_count_is_validated(self):
        net = Net()
        port = literal(net, "P", False)
        self.assertEqual(copy_value(net, port, 0), [])
        self.assertTrue(net.active())  # erase is native work, not an inert deletion
        for count in (1, 2, 3):
            fresh = Net()
            copied = copy_value(fresh, literal(fresh, "P", True), count)
            self.assertEqual(len(copied), count)

if __name__ == "__main__":
    unittest.main()
