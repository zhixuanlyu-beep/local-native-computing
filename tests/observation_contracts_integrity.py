"""Integrity tests for fixed M4 observation contracts."""

from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import ic_observation_contracts as oc
from ic_package_codec import validate_package
from ic_primitive_port_verifier import isomorphic
from ic_research_artifacts import GraphSpec


def candidate(interface):
    if interface == ("LEFT", "RIGHT", "OUT"):
        return GraphSpec(("g",), interface,
                         ((("F", "LEFT"), (0, 0)),
                          (("F", "RIGHT"), (0, 1)),
                          (("F", "OUT"), (0, 2))))
    if interface == ("IN", "OUT"):
        return GraphSpec(("e", "e"), interface,
                         ((("F", "IN"), (0, 0)),
                          (("F", "OUT"), (1, 0))))
    if interface == ("IN", "OUT1", "OUT2"):
        return GraphSpec(("g",), interface,
                         ((("F", "IN"), (0, 0)),
                          (("F", "OUT1"), (0, 1)),
                          (("F", "OUT2"), (0, 2))))
    if interface == ("IN",):
        return GraphSpec(("e",), interface, ((("F", "IN"), (0, 0)),))
    raise AssertionError(interface)


class ObservationContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contracts = oc.contracts()

    def test_ledger_is_complete_and_fixed(self):
        self.assertEqual(len(self.contracts), 36)
        self.assertEqual([c.name for c in self.contracts[:16]],
                         [f"binary-A-A-{mask:02d}" for mask in range(16)])
        self.assertEqual([c.name for c in self.contracts[16:32]],
                         [f"unary-{source}-{target}-{mask}"
                          for source in ("A", "B") for target in ("A", "B")
                          for mask in range(4)])
        self.assertEqual([c.name for c in self.contracts[32:]],
                         ["copy-A", "copy-B", "erase-A", "erase-B"])

    def test_truth_masks_interfaces_and_inputs(self):
        for task in self.contracts:
            with self.subTest(task=task.name):
                self.assertEqual(task.interface, oc.FAMILY_INTERFACES[task.family])
                inputs = task.inputs()
                if task.family == "binary":
                    self.assertEqual(inputs, ((False, False), (False, True),
                                               (True, False), (True, True)))
                    outputs = [task.evaluate(bits)[0] for bits in inputs]
                    self.assertEqual(outputs,
                                     [bool((task.mask >> i) & 1) for i in range(4)])
                elif task.family == "unary":
                    self.assertEqual(inputs, ((False,), (True,)))
                    outputs = [task.evaluate(bits)[0] for bits in inputs]
                    self.assertEqual(outputs,
                                     [bool((task.mask >> i) & 1) for i in range(2)])
                elif task.family == "copy":
                    self.assertEqual([task.evaluate(bits) for bits in inputs],
                                     [(False, False), (True, True)])
                else:
                    self.assertEqual([task.evaluate(bits) for bits in inputs], [(), ()])

    def test_specific_and_and_identity(self):
        logical_and = next(c for c in self.contracts if c.name == "binary-A-A-08")
        identity = next(c for c in self.contracts if c.name == "unary-A-A-2")
        self.assertEqual([logical_and.evaluate(bits)[0] for bits in logical_and.inputs()],
                         [False, False, False, True])
        self.assertEqual([identity.evaluate(bits)[0] for bits in identity.inputs()],
                         [False, True])

    def test_value_specs_and_b_packages(self):
        self.assertEqual(oc.value_spec("A", False).kinds, ("e",))
        self.assertEqual(oc.value_spec("A", True).kinds, ("g",))
        self.assertEqual(oc.value_spec("A", True).wires,
                         ((("F", "ROOT"), (0, 0)), ((0, 1), (0, 2))))
        for bit in (False, True):
            spec = oc.value_spec("B", bit)
            self.assertEqual(spec.boundaries, ("ROOT",))
            package = spec.instantiate()
            self.assertEqual(package.check(), None)
            self.assertFalse(package.active())
            self.assertEqual(validate_package(package), ("F", "ROOT"))
            self.assertTrue(all(kind in ("g", "e") for kind in package.nodes.values()))
        self.assertEqual(oc.value_spec("B", False).kinds, ("g", "e", "e"))
        self.assertEqual(oc.value_spec("B", True).kinds, ("g", "e", "g"))

    def test_task_contract_rejects_strict_schema_errors(self):
        def make(name, family, input_reprs, output_reprs, mask):
            return lambda: oc.TaskContract(
                name, family, input_reprs, output_reprs, mask
            )

        bad = [
            make("", "binary", ("A", "A"), ("A",), 0),
            make("x", "unknown", ("A", "A"), ("A",), 0),
            make("x", "binary", ("A",), ("A",), 0),
            make("x", "binary", ("A", "A"), ("B",), 0),
            make("x", "binary", ("A", "A"), ("A",), 16),
            make("x", "unary", ("A", "A"), ("A",), 0),
            make("x", "unary", ("A",), ("A", "A"), 0),
            make("x", "unary", ("A",), ("A",), 4),
            make("x", "copy", ("A",), ("A", "B"), None),
            make("x", "copy", ("A",), ("A", "A"), 0),
            make("x", "erase", ("A",), ("A",), None),
            make("x", "erase", ("A",), (), 0),
        ]
        for task in bad:
            with self.subTest(task=task):
                self.assertRaises((TypeError, ValueError), task)

    def test_builder_does_not_evaluate_task(self):
        spec = candidate(("LEFT", "RIGHT", "OUT"))
        with mock.patch.object(oc.TaskContract, "evaluate",
                               side_effect=AssertionError("builder evaluated task")):
            built = oc.build_observation("binary", spec, ("A", "A"), (True, False))
        self.assertIsInstance(built, oc.BuiltObservation)
        self.assertEqual(built.net.check(), None)
        self.assertEqual(len(built.input_ids), 2)
        self.assertTrue(all(ids for ids in built.input_ids))

    def test_build_observation_for_every_contract_input(self):
        for task in self.contracts:
            spec = candidate(task.interface)
            for bits in task.inputs():
                with self.subTest(task=task.name, bits=bits):
                    built = oc.build_observation(
                        task.family, spec, task.input_reprs, bits
                    )
                    self.assertEqual(built.net.check(), None)
                    component_numbers = [int(name[1:]) for name in built.component_ids]
                    input_numbers = [int(name[1:])
                                     for ids in built.input_ids for name in ids]
                    self.assertTrue(component_numbers)
                    self.assertTrue(input_numbers)
                    self.assertLess(max(component_numbers), min(input_numbers))

    def test_expected_complete_graph_for_every_contract_input(self):
        output_labels = {
            "binary": {"OUT"},
            "unary": {"OUT"},
            "copy": {"OUT1", "OUT2"},
            "erase": set(),
        }
        for task in self.contracts:
            for bits in task.inputs():
                with self.subTest(task=task.name, bits=bits):
                    target = oc.expected(task, bits)
                    self.assertEqual(target.check(), None)
                    self.assertFalse(target.active())
                    self.assertEqual({label for _, label in target.free},
                                     output_labels[task.family])
                    rebuilt = GraphSpec.from_net(target).instantiate()
                    self.assertTrue(isomorphic(target, rebuilt))

    def test_build_observation_strict_parameters(self):
        good = candidate(("LEFT", "RIGHT", "OUT"))
        bad = [
            ("unknown", good, ("A", "A"), (False, False)),
            ("binary", good, ("A",), (False, False)),
            ("binary", good, ("A", "B"), (False, False)),
            ("binary", good, ("A", "A"), (False,)),
            ("binary", good, ("A", "A"), (False, 1)),
        ]
        for family, spec, reps, bits in bad:
            with self.subTest(args=(family, reps, bits)):
                self.assertRaises((TypeError, ValueError), oc.build_observation,
                                  family, spec, reps, bits)
        wrong = candidate(("IN", "OUT"))
        self.assertRaises(ValueError, oc.build_observation, "binary", wrong,
                          ("A", "A"), (False, False))
        self.assertRaises(TypeError, oc.build_observation, "binary", object(),
                          ("A", "A"), (False, False))

    def test_value_spec_strict_parameters(self):
        self.assertRaises(ValueError, oc.value_spec, "C", True)
        self.assertRaises(TypeError, oc.value_spec, "A", 1)

    def test_cli_runs_from_parent_directory(self):
        result = subprocess.run(
            [sys.executable, str(REPO / "ic_observation_contracts.py")],
            cwd=REPO.parent, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: fixed observation contracts 36", result.stdout)


if __name__ == "__main__":
    unittest.main()
