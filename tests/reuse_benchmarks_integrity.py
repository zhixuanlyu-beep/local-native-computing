"""Integrity checks for M5 reuse-benchmark constructors.

These tests are deliberately reduced: the full archived M5 suite supplies the
complete native matrices and report replay.  Here we pin the constructor API,
allocation partition, strategy-specific initial structure, oracle-free
construction, workload immutability, and preallocation of every future input.
"""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ic_structure_reuse as reuse
import ic_reuse_benchmarks as benchmarks
from ic_research_artifacts import GraphSpec


class ReuseBenchmarkIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = reuse.inputs()
        cls.workload = cls.context["workloads"][0]

    def inputs(self, count):
        return reuse.task_inputs(self.workload, count)

    def build(self, count=1, strategy="literal", disposition="retain1", workload=None):
        workload = workload or self.workload
        return benchmarks.build_benchmark(
            workload, workload["packet"], count, strategy, disposition,
            self.inputs(count), self.context["gate"])

    def test_public_strategy_constants(self):
        self.assertEqual(benchmarks.STRATEGIES,
                         ("literal", "native_fanout", "retained_chain"))
        self.assertEqual(benchmarks.DISPOSITIONS, ("retain1", "dispose_all"))
        self.assertEqual(benchmarks.MAX_TASKS, 4)
        self.assertEqual(set(benchmarks.CATEGORIES), {
            "source_value", "source_machinery", "dispatch_control", "task_literals",
            "copy_routers", "activation_machinery", "task_inputs", "task_consumers",
            "reserve_consumer"})

    def test_all_strategies_construct_and_partition_initial_resources(self):
        for strategy in benchmarks.STRATEGIES:
            with self.subTest(strategy=strategy):
                built = self.build(2, strategy=strategy)
                self.assertEqual(len(built.stages), 2)
                self.assertEqual(set(built.initial_categories), set(built.net.nodes))
                self.assertEqual(len(built.initial_categories), len(built.net.nodes))
                self.assertTrue(set(built.initial_categories.values()).issubset(
                    set(benchmarks.CATEGORIES)))
                self.assertIn("source_value", built.initial_categories.values())
                self.assertIn("activation_machinery", built.initial_categories.values())
                self.assertIn("task_inputs", built.initial_categories.values())

    def test_strategy_specific_literal_and_router_counts(self):
        cases = {
            "literal": 0,
            "native_fanout": 2,  # balanced tree over 3 leaves for n=2
            "retained_chain": 2,  # one delta router per task
        }
        for strategy, expected in cases.items():
            with self.subTest(strategy=strategy):
                built = self.build(2, strategy=strategy)
                routers = [cell for cell, label in built.initial_categories.items()
                           if label == "copy_routers"]
                self.assertEqual(len(routers), expected)
                self.assertTrue(all(built.net.nodes[cell] == "d" for cell in routers))
                if strategy == "retained_chain":
                    self.assertEqual(
                        [stage["copy_head"] for stage in built.stages], routers)
                else:
                    self.assertTrue(all(stage["copy_head"] is None
                                        for stage in built.stages))
                literal_count = sum(label == "task_literals"
                                    for label in built.initial_categories.values())
                self.assertEqual(literal_count,
                                 2 * len(self.workload["capsule"].package.kinds)
                                 if strategy == "literal" else 0)

    def test_reserve_disposition_and_common_outputs_are_prewired(self):
        for disposition in benchmarks.DISPOSITIONS:
            with self.subTest(disposition=disposition):
                built = self.build(2, strategy="native_fanout", disposition=disposition)
                self.assertEqual(built.reserve_eraser is not None,
                                 disposition == "dispose_all")
                self.assertEqual(("F", "RESERVE") in built.net.free,
                                 disposition == "retain1")
                for index in (0, 1):
                    self.assertIn(("F", f"STATUS_{index}"), built.net.free)
                    for label in self.workload["output_labels"]:
                        self.assertIn(("F", f"TASK_{index}_{label}"), built.net.free)

    def test_constructor_rejects_invalid_parameters(self):
        workload = self.workload
        packet, gate = workload["packet"], self.context["gate"]
        valid = (workload, packet, 1, "literal", "retain1", ((False, False),), gate)
        invalid = [
            (workload, packet, 0, "literal", "retain1", (), gate),
            (workload, packet, True, "literal", "retain1", ((False, False),), gate),
            (workload, packet, 5, "literal", "retain1", ((False, False),) * 5, gate),
            (workload, packet, 1, "wrong", "retain1", ((False, False),), gate),
            (workload, packet, 1, "literal", "wrong", ((False, False),), gate),
            (workload, packet, 1, "literal", "retain1", [(False, False)], gate),
            (workload, packet, 1, "literal", "retain1", ((0, 0),), gate),
            (workload, packet, 1, "literal", "retain1", ((False,),), gate),
            (workload, packet, 2, "literal", "retain1", ((False, False),), gate),
            (workload, packet, 1, "literal", "retain1", ((False, False),), "gate"),
        ]
        for args in invalid:
            with self.subTest(args=args):
                self.assertRaises((TypeError, ValueError),
                                  benchmarks.build_benchmark, *args)
        # A valid construction must remain valid after all rejection probes.
        self.assertIsNotNone(benchmarks.build_benchmark(*valid))

    def test_packet_and_producer_are_oracle_free(self):
        packet = self.workload["packet"]
        before = packet.to_dict()
        built = benchmarks.producer(packet)
        self.assertEqual(packet.to_dict(), before)
        self.assertEqual(built.net.nodes[built.producer_fan], "d")
        self.assertEqual(built.net.nodes[built.producer_eraser], "e")
        self.assertEqual(set(built.source_ids), set(built.net.nodes) -
                         {built.producer_fan, built.producer_eraser})
        # The producer is deliberately not just the packet: it adds the native
        # copy fanout and eraser while preserving the packet as source material.
        self.assertEqual(set(packet.kinds).issubset(set(built.net.nodes.values())), True)
        delta_data = next(w for w in self.context["workloads"] if w["name"] == "copy_A")["capsule"].package
        with self.assertRaises(ValueError):
            benchmarks.make_packet(delta_data)
        with self.assertRaises(ValueError):
            benchmarks.producer(delta_data)
        with patch.object(benchmarks, "load_discovery",
                          side_effect=AssertionError("default gate loaded")):
            benchmarks.build_benchmark(self.workload, packet, 1, "literal",
                                       "retain1", ((False, False),),
                                       self.context["gate"])

    def test_builder_does_not_evaluate_task_or_mutate_workload(self):
        frozen = {
            key: (value.to_dict() if isinstance(value, GraphSpec) else value)
            for key, value in self.workload.items() if key != "source_cases"
        }
        # The workload carries a serialized task contract, not a live TaskContract.
        # Building the actual TaskContract is allowed only for schema validation;
        # evaluating it would be an oracle and must not occur in the builder.
        with patch.object(benchmarks.TaskContract, "evaluate",
                          side_effect=AssertionError("task evaluated")):
            self.build(2, strategy="retained_chain")
        actual = {
            key: (value.to_dict() if isinstance(value, GraphSpec) else value)
            for key, value in self.workload.items() if key != "source_cases"
        }
        self.assertEqual(actual, frozen)
        # The constructor must not add or replace the capsule field when absent.
        stripped = {key: value for key, value in self.workload.items()
                    if key != "capsule"}
        capsule = self.workload["capsule"]
        with patch.object(benchmarks, "build_capsule", return_value=capsule):
            built = self.build(1, workload=stripped)
        self.assertEqual(built.initial_categories, self.build(1).initial_categories)
        self.assertNotIn("capsule", stripped)

    def test_all_future_task_inputs_are_preallocated(self):
        count = 4
        for strategy in benchmarks.STRATEGIES:
            with self.subTest(strategy=strategy):
                built = self.build(count, strategy=strategy)
                self.assertEqual(len(built.stages), count)
                expected_inputs = 0
                for bits in self.inputs(count):
                    for label, representation, bit in zip(
                            self.workload["input_labels"],
                            self.workload["input_reprs"], bits):
                        expected_inputs += len(
                            reuse.value_spec(representation, bit).kinds)
                actual_inputs = sum(label == "task_inputs"
                                    for label in built.initial_categories.values())
                self.assertEqual(actual_inputs, expected_inputs)
                self.assertEqual([stage["index"] for stage in built.stages],
                                 list(range(count)))
                self.assertEqual([tuple(stage["input_bits"]) for stage in built.stages],
                                 list(self.inputs(count)))


if __name__ == "__main__":
    unittest.main()
