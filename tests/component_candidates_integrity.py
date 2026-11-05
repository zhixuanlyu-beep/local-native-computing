"""Integrity checks for the M4 finite component-candidate grammar."""
from itertools import product
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ic_coherent_feedback import spec_digest
from ic_component_candidates import (
    MAX_ENUMERABLE_CELLS,
    Candidate,
    candidate_specs,
    grammar_descriptor,
    grammar_digest,
)
from ic_primitive_port_verifier import AR, pairings
from ic_research_artifacts import GraphSpec


def matching_count(endpoint_count):
    if endpoint_count == 0:
        return 1
    if endpoint_count % 2:
        return 0
    factorial = 1
    double_factorial = 1
    for value in range(2, endpoint_count + 1, 2):
        double_factorial *= value
    for value in range(2, endpoint_count + 1):
        factorial *= value
    return factorial // double_factorial


def expected_count(interface, minimum, maximum, kinds):
    total = 0
    for cell_count in range(minimum, maximum + 1):
        for kind_tuple in product(kinds, repeat=cell_count):
            endpoint_count = len(interface) + sum(AR[kind] + 1 for kind in kind_tuple)
            total += matching_count(endpoint_count)
    return total


class ComponentCandidateGrammar(unittest.TestCase):
    def test_exact_counts_for_small_arity_cases(self):
        cases = [
            ((), 0, 3, ("e", "g", "d"),
             expected_count((), 0, 3, ("e", "g", "d"))),
            (("IN",), 0, 1, ("e",), 1),
            (("A", "B"), 0, 1, ("e",), 1),
            (("A", "B"), 0, 1, ("g",), 1),
            (("A", "B", "C", "D"), 0, 1, ("g",), 3),
            (("IN",), 0, 2, ("e",), 1),
        ]
        for interface, minimum, maximum, kinds, expected in cases:
            with self.subTest(interface=interface, bounds=(minimum, maximum), kinds=kinds):
                candidates = list(candidate_specs(interface, maximum, minimum, kinds))
                self.assertEqual(len(candidates), expected)
                self.assertEqual([candidate.index for candidate in candidates],
                                 list(range(expected)))
                for candidate in candidates:
                    self.assertIsInstance(candidate, Candidate)
                    self.assertIsInstance(candidate.spec, GraphSpec)
                    self.assertEqual(candidate.cells, len(candidate.spec.kinds))
                    self.assertEqual(candidate.fingerprint,
                                     spec_digest(candidate.spec.to_dict()))

    def test_count_bounds_select_each_cell_count_exactly_once(self):
        interface = ("A", "B")
        candidates = list(candidate_specs(interface, 3, 1, ("e", "g", "d")))
        counts = {candidate.cells for candidate in candidates}
        self.assertEqual(counts, {2})
        expected_tuples = list(product(("e", "g", "d"), repeat=2))
        observed_tuples = [candidate.spec.kinds for candidate in candidates
                          if candidate.cells == 2]
        self.assertEqual(sorted(set(observed_tuples)),
                         sorted(expected_tuples))
        expected_two = sum(
            matching_count(len(interface) + sum(AR[kind] + 1 for kind in kinds))
            for kinds in expected_tuples
        )
        self.assertEqual(len(observed_tuples), expected_two)

    def test_exact_serialization_set_is_complete_and_stable(self):
        first = list(candidate_specs(("A", "B"), 2, 1, ("g",)))
        second = list(candidate_specs(("A", "B"), 2, 1, ("g",)))
        self.assertEqual(first, second)
        serializations = [candidate.spec.to_dict() for candidate in first]
        self.assertEqual(len(serializations), len(set(map(repr, serializations))))
        expected = []
        for kind in product(("g",), repeat=2):
            endpoints = [
                (cell, port)
                for cell, kind_name in enumerate(kind)
                for port in range(AR[kind_name] + 1)
            ] + [("F", label) for label in ("A", "B")]
            for wires in pairings(endpoints):
                expected.append(GraphSpec(kind, ("A", "B"), tuple(wires), 0))
        def matching_key(spec):
            return frozenset(frozenset(wire) for wire in spec.wires)

        self.assertEqual({matching_key(candidate.spec) for candidate in first},
                         {matching_key(spec) for spec in expected})
        for candidate in first:
            self.assertEqual(candidate.spec.cycles, 0)

    def test_ledger_keeps_disconnected_active_and_cyclic_principal_syntax(self):
        all_candidates = list(candidate_specs(("A", "B"), 2, 2, ("g", "d", "e")))
        by_serialization = {
            frozenset(frozenset(wire) for wire in candidate.spec.wires): candidate
            for candidate in all_candidates
        }

        disconnected = GraphSpec(("g", "e"), ("A", "B"), (
            (("F", "A"), (0, 0)),
            (("F", "B"), (1, 0)),
            ((0, 1), (0, 2)),
        ), 0)
        self.assertIn(
            frozenset(frozenset(wire) for wire in disconnected.wires), by_serialization
        )

        active = GraphSpec(("e", "e"), ("A", "B"), (
            ((0, 0), (1, 0)),
            (("F", "A"), ("F", "B")),
        ), 0)
        self.assertIn(
            frozenset(frozenset(wire) for wire in active.wires), by_serialization
        )
        active_net = active.instantiate()
        self.assertEqual(active_net.active(), [("c0", "c1")])

        cyclic = GraphSpec(("e", "g"), ("A", "B"), (
            ((0, 0), (1, 0)),
            ((1, 1), (1, 2)),
            (("F", "A"), ("F", "B")),
        ), 0)
        self.assertIn(
            frozenset(frozenset(wire) for wire in cyclic.wires), by_serialization
        )
        cyclic_net = cyclic.instantiate()
        gamma_name = "c1"
        self.assertEqual(cyclic_net.adj[(gamma_name, 1)], (gamma_name, 2))

        boundary_pair = next(
            candidate for candidate in candidate_specs(("A", "B"), 0, 0, ("e",))
        )
        self.assertEqual(boundary_pair.spec.wires,
                         ((("F", "A"), ("F", "B")),))

    def test_every_candidate_is_instantiable_and_roundtrips(self):
        for candidate in candidate_specs(("A", "B"), 2, 0, ("e", "g", "d")):
            with self.subTest(candidate=candidate):
                net = candidate.spec.instantiate()
                net.check()
                self.assertEqual(GraphSpec.from_net(net), candidate.spec)
                self.assertEqual(net.cycles, 0)

    def test_interface_order_is_literal_and_not_isomorphism_deduplicated(self):
        left = list(candidate_specs(("X", "Y"), 1, 0, ("g",)))
        right = list(candidate_specs(("Y", "X"), 1, 0, ("g",)))
        self.assertEqual(len(left), len(right))
        self.assertEqual(len(left), len({candidate.fingerprint for candidate in left}))
        self.assertNotEqual(left[0].fingerprint, right[0].fingerprint)
        self.assertNotEqual([candidate.spec for candidate in left],
                            [candidate.spec for candidate in right])

    def test_invalid_parameters_are_rejected(self):
        invalid = [
            (["A"], 1, 0, ("g",), TypeError),
            (("A", 1), 1, 0, ("g",), TypeError),
            (("", "B"), 1, 0, ("g",), ValueError),
            (("A", "A"), 1, 0, ("g",), ValueError),
            (("A",), "1", 0, ("g",), TypeError),
            (("A",), True, 0, ("g",), TypeError),
            (("A",), -1, 0, ("g",), ValueError),
            (("A",), 4, 0, ("g",), ValueError),
            (("A",), 1, "0", ("g",), TypeError),
            (("A",), 1, False, ("g",), TypeError),
            (("A",), 1, -1, ("g",), ValueError),
            (("A",), 1, 2, ("g",), ValueError),
            (("A",), 1, 0, ["g"], TypeError),
            (("A",), 1, 0, (), ValueError),
            (("A",), 1, 0, ("g", 1), TypeError),
            (("A",), 1, 0, ("x",), ValueError),
            (("A",), 1, 0, ("g", "g"), ValueError),
        ]
        for interface, maximum, minimum, kinds, error in invalid:
            with self.subTest(interface=interface, bounds=(minimum, maximum), kinds=kinds):
                with self.assertRaises(error):
                    candidate_specs(interface, maximum, minimum, kinds)

    def test_descriptor_and_digest_bind_the_exact_grammar(self):
        descriptor = grammar_descriptor(("A", "B"), 2, 1, ("g", "d"))
        self.assertEqual(descriptor["format"], "IC-COMPONENT-CANDIDATES-1")
        self.assertEqual(descriptor["interface"], ["A", "B"])
        self.assertEqual(descriptor["min_cells"], 1)
        self.assertEqual(descriptor["max_cells"], 2)
        self.assertEqual(descriptor["kinds"], ["g", "d"])
        self.assertEqual(descriptor["wire_cycles"], 0)
        self.assertEqual(descriptor["deduplication"], "none")
        self.assertEqual(descriptor["max_enumerable_cells"], MAX_ENUMERABLE_CELLS)
        self.assertEqual(grammar_digest(("A", "B"), 2, 1, ("g", "d")),
                         spec_digest(descriptor))
        self.assertNotEqual(grammar_digest(("A", "B"), 2, 1, ("g", "d")),
                            grammar_digest(("B", "A"), 2, 1, ("g", "d")))

        invalid_descriptors = [
            (("A", "A"), 1, 0, ("g",), ValueError),
            (("A",), 4, 0, ("g",), ValueError),
            (("A",), 1, 0, ("q",), ValueError),
        ]
        for interface, maximum, minimum, kinds, error in invalid_descriptors:
            with self.subTest(interface=interface, bounds=(minimum, maximum), kinds=kinds):
                with self.assertRaises(error):
                    grammar_descriptor(interface, maximum, minimum, kinds)

    def test_grammar_has_no_runtime_or_oracle_entry_points(self):
        import ic_component_candidates as grammar
        for forbidden in ("FastNet", "reduce", "execute", "oracle", "evaluator"):
            self.assertFalse(hasattr(grammar, forbidden))
        self.assertEqual(grammar.candidate_specs, candidate_specs)


if __name__ == "__main__":
    unittest.main()
