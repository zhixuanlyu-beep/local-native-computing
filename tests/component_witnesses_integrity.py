"""Focused integrity checks for exact component witness lifting."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ic_component_witnesses import (
    boundary_cell_map,
    match_bound_graph,
    match_value,
    lift_trace,
)
from ic_coherent_feedback import spec_digest
from ic_primitive_port_verifier import AR, Net, pair
from ic_research_artifacts import GraphSpec
from ic_program_suspension import append_spec
from ic_schedule_audit import Schedule, ScheduleTrace, ScheduledNet


class Recorder:
    def __init__(self, offset=0):
        self.count = offset
        self.records = []

    def record(self, pair):
        self.records.append(pair)
        self.count += 1


def contextual(rule, *, context_after=False):
    reference, _, _, boundaries = pair(*rule)
    actual = GraphSpec.from_net(reference).instantiate(ScheduledNet(Schedule("witness")))
    outside = actual.cell("e")
    outside_boundary = actual.boundary("CTX")
    actual.link((outside, 0), outside_boundary)
    return reference, actual, outside, boundaries


def cell_context(rule):
    reference, _, _, boundaries = pair(*rule)
    actual = GraphSpec.from_net(reference).instantiate(ScheduledNet(Schedule("witness")))
    # Pair the full arity of an outside cell so the enclosing net stays
    # complete even when the imported rule has no local free boundaries.
    outside = actual.cell("e" if not boundaries else "g")
    principal_boundary = actual.boundary("CTX_ROOT")
    actual.link((outside, 0), principal_boundary)
    # Detach each exact local boundary endpoint and remove its physical
    # boundary key, retaining the neighboring cell port as the target for
    # attachment to the outside context.
    ordered_local_ports = []
    for label in sorted(boundaries):
        local_port = actual.adj[("F", label)]
        actual.adj.pop(("F", label))
        actual.free.remove(("F", label))
        actual.adj[local_port] = None
        ordered_local_ports.append(local_port)
    if ordered_local_ports:
        # Attach at most two local interface ports per outside cell.  This
        # keeps the focused fixture complete without manufacturing extra
        # disconnected context components merely to fill one gamma cell.
        for index in range(0, len(ordered_local_ports), 2):
            context = outside if index == 0 else actual.cell("g")
            if context is not outside:
                actual.link(
                    (context, 0),
                    actual.boundary("CTX_ROOT" + str(index)),
                )
            actual.link((context, 1), ordered_local_ports[index])
            if index + 1 < len(ordered_local_ports):
                actual.link((context, 2), ordered_local_ports[index + 1])
            else:
                actual.link(
                    (context, 2),
                    actual.boundary("CTX_AUX" + str(index)),
                )
    # Bind each reference boundary to the outside consumer port; the matcher
    # follows that endpoint to the corresponding local cell port.
    cell_bindings = {
        label: actual.adj[local_port]
        for label, local_port in zip(sorted(boundaries), ordered_local_ports)
    }
    actual.check()
    return reference, actual, outside, cell_bindings


class ExactWitnessMatching(unittest.TestCase):
    def test_all_six_primitive_local_embeddings_and_boundary_wrapper(self):
        for left, right in (("g", "g"), ("g", "d"), ("g", "e"),
                            ("d", "d"), ("d", "e"), ("e", "e")):
            with self.subTest(rule=(left, right)):
                reference, actual, _, boundaries = contextual((left, right))
                expected = dict(zip(reference.nodes, actual.nodes))
                if reference.free:
                    self.assertEqual(
                        match_bound_graph(reference, actual, boundaries), expected
                    )
                boundary_actual = GraphSpec.from_net(reference).instantiate()
                if boundary_actual.free:
                    self.assertEqual(
                        boundary_cell_map(reference, boundary_actual), expected
                    )

    def test_embedding_allows_outside_cells_and_exact_boundary_wires(self):
        reference, actual, outside, boundaries = contextual(("g", "d"))
        self.assertNotIn(outside, match_bound_graph(reference, actual, boundaries).values())

        cell_reference, cell_actual, cell_outside, cell_bindings = cell_context(("g", "d"))
        cell_map = match_bound_graph(cell_reference, cell_actual, cell_bindings)
        self.assertNotIn(cell_outside, cell_map.values())

        wire = Net()
        left_boundary = wire.boundary("L")
        right_boundary = wire.boundary("R")
        wire.link(left_boundary, right_boundary)
        actual_wire = Net()
        actual_wire.link(actual_wire.boundary("L"), actual_wire.boundary("R"))
        self.assertEqual(
            match_bound_graph(wire, actual_wire, {"L": ("F", "L"), "R": ("F", "R")}),
            {},
        )

    def test_bad_maps_and_noninjective_or_missing_cells_rejected(self):
        reference, actual, _, boundaries = contextual(("g", "d"))
        with self.assertRaises(ValueError):
            match_bound_graph(reference, actual, {"A1": boundaries["A1"]})
        bad = dict(zip(reference.nodes, actual.nodes))
        bad["c0"] = "c1"
        with self.assertRaises(ValueError):
            match_bound_graph(reference, actual, boundaries, bad)

    def test_value_matching_requires_principal_package(self):
        value = GraphSpec(("e",), ("ROOT",), ((("F", "ROOT"), (0, 0)),), 0)
        actual = value.instantiate(ScheduledNet(Schedule("witness")))
        host = actual.cell("e")
        actual.link((host, 0), actual.boundary("HOST"))
        with self.assertRaises(ValueError):
            match_value(GraphSpec(("d",), ("ROOT",), ((("F", "ROOT"), (0, 0)),), 0), actual, ("F", "HOST"))

    def test_four_boundary_wire_labels_must_match_exactly(self):
        def four_wire_net(first, second):
            net = Net()
            for label in first + second:
                net.boundary(label)
            for left, right in zip(first, second):
                net.link(("F", left), ("F", right))
            return net

        reference = four_wire_net(("A", "C"), ("B", "D"))
        matching = four_wire_net(("A", "C"), ("B", "D"))
        crossed = four_wire_net(("A", "B"), ("C", "D"))

        bindings = {label: ("F", label) for label in ("A", "B", "C", "D")}
        self.assertEqual(match_bound_graph(reference, matching, bindings), {})
        with self.assertRaises(ValueError):
            match_bound_graph(reference, crossed, bindings)


class ExactTraceLifting(unittest.TestCase):
    def test_primitive_lift_records_translated_pairs(self):
        reference, actual, outside, boundaries = contextual(("g", "d"))
        initial_map = {"c0": "c0", "c1": "c1"}
        recorder = Recorder(offset=7)
        result = lift_trace(
            GraphSpec.from_net(reference), actual, initial_map, boundaries,
            (("c0", "c1"),), recorder,
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["trace_offset_records"], 7)
        self.assertEqual(result["primitive_interactions"], 1)
        self.assertEqual(result["context_cells"], 1)
        self.assertEqual(result["outside_unchanged"], True)
        self.assertIn("reference_final_graph", result)
        self.assertIn("reference_resources", result)

    def test_fresh_identifier_shift_when_context_is_appended_first(self):
        reference, _, _, _ = contextual(("g", "e"))
        actual = ScheduledNet(Schedule("witness"))
        local_spec = GraphSpec.from_net(reference)
        binding_map = {}
        # Each interface label gets its own physical consumer-cell port.
        # The remaining ports of the context cells are made complete before
        # the literal graph is appended, so instantiate cannot leave holes.
        for index, label in enumerate(local_spec.boundaries):
            context = actual.cell("g")
            actual.link((context, 0), actual.boundary("CTX::" + label))
            actual.link((context, 2), actual.boundary("CTX_AUX::" + label))
            binding_map[label] = (context, 1)
        local_cells = append_spec(local_spec, actual, binding_map)
        initial_map = dict(zip(reference.nodes, local_cells))
        recorder = Recorder()
        result = lift_trace(
            GraphSpec.from_net(reference), actual, initial_map, binding_map,
            (("c0", "c1"),), recorder,
        )
        self.assertEqual(result["status"], "passed")
        self.assertNotEqual(recorder.records, [("c0", "c1")])
        # Context cells were allocated before the local component, while the
        # RHS cells are allocated by the reduction itself.  The final live
        # reference cells therefore use fresh actual identifiers.
        self.assertEqual(
            result["renaming"],
            {"c2": "c4", "c3": "c5"},
        )
    def test_closed_erase_component_with_fixed_seed(self):
        reference = Net()
        a = reference.cell("e")
        b = reference.cell("e")
        reference.link((a, 0), (b, 0))
        actual = GraphSpec.from_net(reference).instantiate(ScheduledNet(Schedule("witness")))
        result = lift_trace(
            GraphSpec.from_net(reference), actual, {"c0": "c0", "c1": "c1"}, {},
            (("c0", "c1"),), Recorder(),
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["context_cells"], 0)
        self.assertEqual(result["renaming"], {})

    def test_cutoff_and_resource_violation_preserve_evidence(self):
        reference, actual, _, boundaries = contextual(("g", "d"))
        cutoff = lift_trace(
            GraphSpec.from_net(reference), actual,
            {"c0": "c0", "c1": "c1"}, boundaries,
            (("c0", "c1"),), Recorder(), max_steps=0,
        )
        self.assertEqual(cutoff["status"], "incomplete")
        self.assertEqual(cutoff["primitive_interactions"], 0)
        self.assertIn("final_graph", cutoff)

        resource = lift_trace(
            GraphSpec.from_net(reference), actual,
            {"c0": "c0", "c1": "c1"}, boundaries,
            (("c0", "c1"),), Recorder(), max_cells=2,
        )
        self.assertEqual(resource["status"], "resource-violation")

    def test_bad_pair_and_non_witness_schedule_rejected(self):
        reference, actual, _, boundaries = contextual(("g", "d"))
        with self.assertRaises(ValueError):
            lift_trace(
                GraphSpec.from_net(reference), actual,
                {"c0": "c0", "c1": "c1"}, boundaries,
                (("c0", "c1"), ("c0", "c1")), Recorder(),
            )
        fifo = ScheduledNet()
        with self.assertRaises(ValueError):
            lift_trace(
                GraphSpec.from_net(reference), fifo,
                {"c0": "c0", "c1": "c1"}, {}, (), Recorder(),
            )


if __name__ == "__main__":
    unittest.main()
