"""Integrity tests for the fixed discovered-component program builder.

The tests deliberately use tiny interface-only GraphSpec templates and a
temporary ic_observation_contracts module.  They test builder independence
and structural rejection; they do not assert semantic success of any actual
discovered gate.  Full discovered-library evidence is owned by the root
suite.
"""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import types
import unittest


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import ic_discovered_programs as builder
from ic_coherent_feedback import spec_digest
from ic_primitive_port_verifier import Net  # noqa: E402
from ic_research_artifacts import GraphSpec  # noqa: E402


ROLE_INTERFACES = {
    "copy_a": ("IN", "OUT1", "OUT2"),
    "and_left": ("LEFT", "RIGHT", "OUT"),
    "and_right": ("LEFT", "RIGHT", "OUT"),
    "and_join": ("LEFT", "RIGHT", "OUT"),
    "box_ab": ("IN", "OUT"),
    "copy_b": ("IN", "OUT1", "OUT2"),
    "erase_b": ("IN",),
    "unbox_ba": ("IN", "OUT"),
}


class MockTask:
    def __init__(self, family: str, input_reprs: tuple[str, ...],
                 output_reprs: tuple[str, ...], mask: int | None):
        self.family = family
        self.input_reprs = input_reprs
        self.output_reprs = output_reprs
        self.mask = mask

    @property
    def interface(self):
        return ROLE_INTERFACES[
            next(role for role in builder.ROLE_ORDER
                 if builder.ROLE_CONTRACTS[role]
                 == (self.family, self.input_reprs, self.output_reprs, self.mask))
        ]


def value_spec(rep: str, bit: bool) -> GraphSpec:
    if rep != "A":
        raise ValueError("mock program inputs are A-valued")
    if bit:
        return GraphSpec(
            ("g",),
            ("ROOT",),
            ((("F", "ROOT"), (0, 0)), ((0, 1), (0, 2))),
            0,
        )
    return GraphSpec(("e",), ("ROOT",), ((("F", "ROOT"), (0, 0)),), 0)


def install_mock_contracts() -> None:
    module = types.ModuleType("ic_observation_contracts")
    module.value_spec = value_spec
    sys.modules["ic_observation_contracts"] = module


def interface_spec(interface: tuple[str, ...]) -> GraphSpec:
    """Build a complete interface-only template."""
    if len(interface) == 3:
        return GraphSpec(
            ("g",), interface, (
                (("F", interface[0]), (0, 0)),
                (("F", interface[1]), (0, 1)),
                (("F", interface[2]), (0, 2)),
            ), 0)
    if len(interface) == 2:
        return GraphSpec(
            ("e", "e"), interface, (
                (("F", interface[0]), (0, 0)),
                (("F", interface[1]), (1, 0)),
            ), 0)
    if len(interface) == 1:
        return GraphSpec(
            ("e",), interface, ((("F", interface[0]), (0, 0)),), 0)
    raise ValueError("test template supports one, two, or three boundaries")


def empty_spec(interface: tuple[str, ...]) -> GraphSpec:
    return GraphSpec((), interface, (), 0)


def library() -> dict[str, dict[str, object]]:
    result = {}
    for library_role in set(builder.LIBRARY_ROLES.values()):
        role = next(r for r, lr in builder.LIBRARY_ROLES.items() if lr == library_role)
        interface = ROLE_INTERFACES[role]
        contract = builder.ROLE_CONTRACTS[role]
        spec = interface_spec(interface)
        result[library_role] = {
            "task": MockTask(*contract),
            "spec": spec,
            "candidate_id": spec_digest(spec.to_dict()),
        }
    return result


def stage_map(lib: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    return {
        role: {
            "task": lib[builder.LIBRARY_ROLES[role]]["task"],
            "inputs": dict(builder.INPUT_REFS[role]),
            "outputs": builder.STAGE_OUTPUTS[role],
        }
        for role in builder.ROLE_ORDER
    }


class DiscoveredProgramsTests(unittest.TestCase):
    def test_role_mapping_is_complete(self):
        self.assertEqual(set(builder.ROLE_CONTRACTS), set(builder.ROLE_ORDER))
        self.assertEqual(set(builder.INPUT_NAMES), {"a", "b", "c"})

    def test_validate_wiring_accepts_fixed_dag(self):
        lib = library()
        stages = {
            role: {
                "task": lib[builder.LIBRARY_ROLES[role]]["task"],
                "inputs": dict(builder.INPUT_REFS[role]),
                "outputs": builder.STAGE_OUTPUTS[role],
            }
            for role in builder.ROLE_ORDER
        }
        builder.validate_wiring(stages, builder.INPUT_TYPES, builder.FINAL_OUTPUTS)

    def test_validate_wiring_rejects_missing_stage(self):
        stages = stage_map(library())
        del stages["erase_b"]
        with self.assertRaises(ValueError):
            builder.validate_wiring(stages, builder.INPUT_TYPES, builder.FINAL_OUTPUTS)

    def test_validate_wiring_rejects_forward_reference(self):
        stages = stage_map(library())
        stages["copy_a"]["inputs"] = {
            "IN": ("stage", "unbox_ba", "OUT"),
        }
        with self.assertRaises(ValueError):
            builder.validate_wiring(stages, builder.INPUT_TYPES, builder.FINAL_OUTPUTS)

    def test_validate_wiring_rejects_duplicate_consumer(self):
        stages = stage_map(library())
        stages["and_left"]["inputs"] = {
            "LEFT": ("stage", "copy_a", "OUT1"),
            "RIGHT": ("stage", "copy_a", "OUT1"),
        }
        with self.assertRaises(ValueError):
            builder.validate_wiring(
                stages, builder.INPUT_TYPES, builder.FINAL_OUTPUTS
            )

    def test_external_outputs_cannot_reuse_internally_consumed_values(self):
        with self.assertRaises(ValueError):
            builder.validate_wiring(stage_map(library()), builder.INPUT_TYPES,
                                    {"unbox_ba": "OUT", "and_left": "OUT"})

    def test_wiring_checks_the_actual_task_representation(self):
        stages = stage_map(library())
        stages["box_ab"]["task"] = MockTask("unary", ("A",), ("A",), 2)
        with self.assertRaises(ValueError):
            builder.validate_wiring(stages, builder.INPUT_TYPES, builder.FINAL_OUTPUTS)

    @classmethod
    def setUpClass(cls):
        cls.previous_contracts = sys.modules.get("ic_observation_contracts")
        install_mock_contracts()

    @classmethod
    def tearDownClass(cls):
        if cls.previous_contracts is None:
            sys.modules.pop("ic_observation_contracts", None)
        else:
            sys.modules["ic_observation_contracts"] = cls.previous_contracts

    def test_changed_graph_cannot_keep_a_candidate_fingerprint(self):
        lib = library()
        lib["copy_A"]["candidate_id"] = "tampered"
        with self.assertRaises(ValueError):
            builder.build_program(lib, (False, False, False))

    def test_build_program_rejects_invalid_bits(self):
        with self.assertRaises(ValueError):
            builder.build_program(library(), (True, False))

    def test_build_program_instantiates_all_components(self):
        lib = library()
        built = builder.build_program(lib, (True, False, True))
        self.assertEqual(len(built.stages), len(builder.ROLE_ORDER))
        self.assertEqual(
            [stage["name"] for stage in built.stages], list(builder.ROLE_ORDER)
        )
        for stage in built.stages:
            self.assertEqual(
                stage["spec"], lib[builder.LIBRARY_ROLES[stage["name"]]]["spec"]
            )
            self.assertEqual(
                stage["candidate_id"],
                lib[builder.LIBRARY_ROLES[stage["name"]]]["candidate_id"],
            )
            self.assertIsInstance(stage["cells"], tuple)
            self.assertTrue(stage["cells"])
        self.assertEqual(len(built.input_ids), len(builder.INPUT_NAMES))
        built.net.check()

    def test_build_program_appends_inputs_after_components(self):
        lib = library()
        built = builder.build_program(lib, (True, True, True))
        component_cells = {
            cell for stage in built.stages for cell in stage["cells"]
        }
        input_cells = {cell for cells in built.input_ids for cell in cells}
        self.assertTrue(component_cells)
        self.assertTrue(input_cells)
        self.assertFalse(component_cells & input_cells)
        self.assertLess(max(int(c[1:]) for c in component_cells),
                        min(int(c[1:]) for c in input_cells))


if __name__ == "__main__":
    unittest.main()
