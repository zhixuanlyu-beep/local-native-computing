"""Integrity tests for the finite typed M3 source-program grammar."""
import copy
import unittest
from pathlib import Path
from unittest import mock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ic_typed_programs as typed


class TypedProgramIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = typed.root_dataset()

    def test_root_dataset_is_fixed_and_finite(self):
        self.assertEqual(len(self.cases), 14)
        self.assertEqual([case["name"] for case in self.cases], [
            "check-0", "check-1", "check-2", "copy-0", "copy-2", "erase-2",
            "compare-0-0", "compare-0-1", "compare-1-0", "compare-1-2", "compare-1-1",
            "fanout-1-check-erase", "fanout-0-check-check", "parallel-check0-copy1",
        ])

    def test_all_programs_normalize_to_independent_expected_diagrams(self):
        for case in self.cases:
            with self.subTest(case=case["name"]):
                program = typed.build_program(case["ast"])
                reference = typed.source_reference(case["ast"])
                expected = typed.expected_diagram(case["ast"])
                self.assertEqual(reference.outputs, typed.expected_outputs(case["ast"]))
                self.assertTrue(typed.compare_source_graph(reference, expected))
                self.assertEqual(reference.final_active_pairs, 0)
                self.assertEqual(len(reference.rule_trace), reference.source_steps)
                self.assertEqual(typed.graph_from_dict(program.to_dict()), program)

    def test_rule_trace_records_canonical_rule_and_before_census(self):
        reference = typed.source_reference(typed.Compare(1, 2))
        self.assertGreater(reference.source_steps, 0)
        for record in reference.rule_trace:
            self.assertEqual(set(record), {"rule", "before_symbols"})
            first, second = record["rule"].split("-")
            self.assertIn(frozenset((first, second)), typed.RULES)
            self.assertEqual(record["before_symbols"], dict(sorted(record["before_symbols"].items())))

    def test_builders_do_not_use_source_runtime(self):
        ast = typed.Fanout(1, "check", "erase")
        with mock.patch.object(typed, "source_apply", side_effect=AssertionError("source apply in builder")), \
             mock.patch.object(typed, "source_active_pairs", side_effect=AssertionError("active pairs in builder")), \
             mock.patch.object(typed, "source_decode", side_effect=AssertionError("source decode in builder")):
            program = typed.build_program(ast)
            expected = typed.expected_diagram(ast)
        self.assertEqual(set(program.boundary_types), {"left.O"})
        self.assertTrue(program.types)

    def test_immutable_objects_and_copy_isolation(self):
        program = typed.build_program(typed.Parallel([typed.Check(0), typed.Copy(1)]))
        with self.assertRaises(TypeError):
            program.types["x"] = "Z"
        with self.assertRaises(TypeError):
            program.adjacency[("F", "0.O")] = None
        duplicate = typed.graph_from_dict(program.to_dict())
        self.assertEqual(duplicate, program)

    def test_parallel_ownership_has_no_cross_owner_wire(self):
        ast = typed.Parallel([typed.Check(0), typed.Copy(1)])
        program = typed.build_program(ast)
        owners = typed.cell_owners(ast)
        self.assertEqual(set(owners), set(program.types))
        self.assertEqual(set(owners.values()), {"part-0", "part-1"})
        for endpoint, other in program.adjacency.items():
            if endpoint[0] in program.types and other[0] in program.types:
                self.assertEqual(owners[endpoint[0]], owners[other[0]], (endpoint, other))

    def test_ast_round_trip_and_strict_schema(self):
        for case in self.cases:
            with self.subTest(case=case["name"]):
                self.assertEqual(typed.from_dict(case["ast_dict"]), case["ast"])
        bad = typed.to_dict(typed.Check(1))
        variants = [
            {**bad, "extra": 1},
            {"kind": "Check", "n": True},
            {"kind": "Check", "n": {"kind": "Nat", "constructor": "three"}},
            {"kind": "Nope"},
            {"kind": "Parallel", "tasks": []},
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                with self.assertRaises((TypeError, ValueError)):
                    typed.from_dict(variant)

    def test_ast_bounds_reject_unbounded_single_child_nesting(self):
        # Nested singleton Parallels exhaust the global node bound without relying on Python recursion depth.
        payload = typed.Check(0)
        for _ in range(typed.MAX_AST_NODES):
            payload = typed.Parallel([payload])
        with self.assertRaises(ValueError):
            typed.validate_ast(payload)

    def test_internal_wire_polarity_and_semantic_type_are_validated(self):
        program = typed.build_program(typed.Check(0))
        raw = program.to_dict()
        # Swap the two wires so INIT.1 (out,O) meets INIT.0 (in,N): same-direction mismatch.
        raw["adjacency"] = [
            [["check.INIT", 1], ["check.INIT", 0]],
            [["check.n.Z", 0], ["F", "O"]],
        ]
        with self.assertRaises(ValueError):
            typed.graph_from_dict(raw)

    def test_public_from_dict_validates_admitted_ast_bounds(self):
        payload = typed.to_dict(typed.Check(0))
        for _ in range(typed.MAX_AST_NODES):
            payload = {"kind": "Parallel", "tasks": [payload]}
        with self.assertRaises(ValueError):
            typed.from_dict(payload)

    def test_source_validator_rejects_malformed_endpoints_and_reserved_names(self):
        with self.assertRaises(ValueError):
            typed.validate_source_graph({"F": "Z"}, {}, {})
        types = {"x": "Z"}
        with self.assertRaises(ValueError):
            typed.validate_source_graph(types, {("x", 0): ("x", 0)}, {})
        with self.assertRaises(ValueError):
            typed.validate_source_graph(types, {("x", 0): ("x", "bad")}, {})
        with self.assertRaises(ValueError):
            typed.validate_source_graph(types, {("x", 0): None}, {})
        with self.assertRaises(ValueError):
            typed.validate_source_graph(types, {("x", 0): ("x",)}, {})

    def test_nat_bounds_and_bool_rejection(self):
        with self.assertRaises(ValueError):
            typed.Check(3)
        with self.assertRaises(TypeError):
            typed.Check(True)
        self.assertEqual(typed.nat_value(typed.Succ(typed.Zero())), 1)

    def test_graph_serialization_rejects_malformed_and_aliased_wires(self):
        program = typed.build_program(typed.Compare(1, 2))
        data = program.to_dict()
        endpoint = data["adjacency"][0][0]
        self.assertEqual(typed.graph_from_dict(data), program)
        variants = []
        raw = copy.deepcopy(data)
        raw["adjacency"][0][1] = endpoint
        variants.append(raw)
        raw = copy.deepcopy(data)
        raw["adjacency"][0][0][1] = 99
        variants.append(raw)
        raw = copy.deepcopy(data)
        raw["adjacency"][0][0][1] = True
        variants.append(raw)
        raw = copy.deepcopy(data)
        raw["extra"] = 1
        variants.append(raw)
        for variant in variants:
            with self.subTest(variant=variant):
                with self.assertRaises(ValueError):
                    typed.graph_from_dict(variant)

    def test_empty_erase_program_is_valid(self):
        program = typed.build_program(typed.Erase(2))
        reference = typed.source_reference(typed.Erase(2))
        self.assertEqual(program.boundary_types, {})
        self.assertEqual(reference.outputs, ())
        self.assertEqual(reference.types, {})
        self.assertEqual(reference.adjacency, {})
        self.assertEqual(reference.rule_trace[-1]["before_symbols"], {"ERA": 1, "Z": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
