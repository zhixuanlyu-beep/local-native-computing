"""M7 grammar, oracle isolation, minimax, budget and archive adversaries."""
from copy import deepcopy
from itertools import permutations, product
from pathlib import Path
import gzip
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ic_coherent_feedback import read_json, write_json
from ic_schedule_audit import ScheduleTrace
from ic_localization import model
from ic_localization.evidence import expected_value, run_network, BUDGET, SMALL_BUDGET, frozen_bindings
from ic_localization import report


class LocalizationIntegrity(unittest.TestCase):
    def test_complete_raw_grammar_and_input_domain(self):
        for n, count in ((2, 18), (3, 98)):
            problem = model.ChainProblem(n)
            candidates = list(model.enumerate_transforms(problem))
            inputs = list(problem.inputs())
            self.assertEqual(len(candidates), count)
            self.assertEqual(len(set(candidates)), count)
            self.assertEqual(inputs, list(product((False, True), repeat=2+4*(n-1))))
            direct = [t for t in candidates if t.kind == "direct"]
            self.assertEqual({t.representation for t in direct}, {"S", "P"})
            for representation in ("S", "P"):
                rest = [t for t in candidates if t.kind != "direct" and t.representation == representation]
                self.assertEqual({t.order for t in rest}, set(permutations(range(n))))
                for order in permutations(range(n)):
                    self.assertEqual({t.materialize for t in rest if t.order == order},
                                     set(product((False, True), repeat=n)))
            self.assertEqual(candidates, list(model.enumerate_transforms(problem)))
            for transform in candidates:
                self.assertEqual(model.Transform.from_dict(transform.to_dict()), transform)

    def test_constructor_cannot_consult_reference(self):
        problem = model.ChainProblem(2)
        with patch.object(model, "reference", side_effect=AssertionError("reference oracle")):
            for transform in model.enumerate_transforms(problem):
                compiled = model.compile_transform(problem, transform)
                for bits in ((False,)*6, (True,)*6):
                    a = model.build_network(problem, transform, bits, compiled=compiled)
                    b = model.build_network(problem, transform, bits, compiled=compiled)
                    self.assertEqual(a, b)
                    a.validate()

    def test_frozen_manifest_and_explicit_materialization(self):
        self.assertTrue(report.same_evidence(read_json(report.FREEZE), frozen_bindings()))
        problem = model.ChainProblem(3)
        plans = [model.compile_transform(problem, model.Transform("ve", (0, 1, 2), (flag, False, False), "S"))
                 for flag in (False, True)]
        self.assertEqual([plan.materialized_entries for plan in plans], [0, 2])
        self.assertGreater(plans[0].operation_counts["AND"], plans[1].operation_counts["AND"])
        self.assertGreater(plans[0].operation_counts["OR"], plans[1].operation_counts["OR"])
        from collections import Counter
        consumers = Counter(arg for op in plans[1].ir[problem.input_bits:] for arg in op.arguments)
        self.assertEqual(sum(i >= problem.input_bits and count > 1 for i, count in consumers.items()), 2)

    def test_full_n2_matrix_against_independent_reference(self):
        for transform in model.enumerate_transforms(model.ChainProblem(2)):
            candidate = report._candidate((2, transform.to_dict()))
            self.assertEqual(candidate["status"], "complete")
            self.assertEqual(len(candidate["records"]), 64)
            self.assertEqual(len({r["resources"]["initial_cells"] for r in candidate["records"]}), 1)
            for record in candidate["records"]:
                resource = record["resources"]
                self.assertEqual(sum(resource["rule_census"].values()), resource["primitive_interactions"])
                self.assertEqual(resource["initial_cells"]+resource["runtime_cells_allocated"],
                                 resource["final_cells"]+2*resource["primitive_interactions"])
                self.assertEqual(resource["cyclic_wires"], 0)

    def test_minimax_requires_all_candidates_and_preserves_ties(self):
        transforms = list(model.enumerate_transforms(model.ChainProblem(2)))[:3]
        candidates = [{"transform": t.to_dict(), "status": "complete", "worst_fifo_interactions": w}
                      for t, w in zip(transforms, (10, 10, 20))]
        result = report.summarize(candidates)
        self.assertEqual(result["status"], "class-optimal")
        self.assertEqual(len(result["optimal_transforms"]), 2)
        self.assertEqual(result["minimum_worst_fifo_interactions"], 10)
        candidates[-1]["status"] = "incomplete"
        result = report.summarize(candidates)
        self.assertEqual(result["status"], "best-known")
        self.assertEqual(result["unfinished"], [transforms[-1].to_dict()])

    def test_budget_and_complete_graph_rules(self):
        problem = model.ChainProblem(2)
        transform = next(iter(model.enumerate_transforms(problem)))
        initial = model.build_network(problem, transform, (True,)*6)
        target = expected_value(True)
        self.assertEqual(run_network(initial, target, budget={"max_steps": 0})["status"], "incomplete")
        self.assertEqual(run_network(initial, target, budget={"max_cells": 0})["status"], "resource-exhausted")
        from ic_research_artifacts import GraphSpec
        cyclic = GraphSpec(initial.kinds, initial.boundaries, initial.wires, 1)
        self.assertEqual(run_network(cyclic, target)["status"], "wrong-normal-form")
        for budget in ({"max_steps": True}, {"max_cells": -1}, {"unknown": 3}):
            with self.assertRaises(ValueError):
                run_network(initial, target, budget=budget)
        self.assertEqual(BUDGET, {"max_steps": 2000000, "max_cells": 250000})
        self.assertEqual(SMALL_BUDGET, {"max_states": 4096, "max_transitions": 32768, "max_cells": 128})

    def test_visible_result_does_not_stop_cleanup_and_runtime_peak_is_bounded(self):
        from ic_primitive_port_verifier import Net
        from ic_research_artifacts import GraphSpec
        target = expected_value(True)
        net = target.instantiate()
        net.link((net.cell("e"), 0), (net.cell("e"), 0))
        initial = GraphSpec.from_net(net)
        self.assertEqual(run_network(initial, target, budget={"max_steps": 0})["status"], "incomplete")
        completed = run_network(initial, target, budget={"max_steps": 1})
        self.assertEqual(completed["status"], "passed")
        self.assertEqual(completed["resources"]["primitive_interactions"], 1)

        growing = Net()
        g, d = growing.cell("g"), growing.cell("d")
        growing.link((g, 0), (d, 0))
        for cell in (g, d):
            for port in (1, 2):
                growing.link((cell, port), growing.boundary(f"{cell}-{port}"))
        cutoff = run_network(GraphSpec.from_net(growing), target, budget={"max_cells": 2})
        self.assertEqual(cutoff["status"], "resource-exhausted")
        self.assertEqual(cutoff["resources"]["primitive_interactions"], 1)
        self.assertEqual(cutoff["resources"]["peak_live_cells"], 4)

    def test_pair_trace_replay_truncation_and_append(self):
        problem = model.ChainProblem(2)
        initial = model.build_network(problem, next(iter(model.enumerate_transforms(problem))), (True,)*6)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"trace.gz"
            trace = ScheduleTrace(path, {"fixture": "M7"})
            first = run_network(initial, expected_value(True), trace=trace)
            summary = trace.close()
            trace = ScheduleTrace(path, {"fixture": "M7"}, replay=True)
            self.assertEqual(report.semantic(first), report.semantic(run_network(initial, expected_value(True), trace=trace)))
            self.assertEqual(summary, trace.close())
            original = gzip.decompress(path.read_bytes())
            for data in (original[:-8], original+b"\0"*8):
                path.write_bytes(gzip.compress(data))
                with self.assertRaises(ValueError):
                    trace = ScheduleTrace(path, {"fixture": "M7"}, replay=True)
                    try:
                        run_network(initial, expected_value(True), trace=trace)
                        trace.close()
                    except BaseException:
                        if not trace.stream.closed:
                            trace.abort()
                        raise

    def test_report_cost_omission_and_status_mutations(self):
        # Exercise the actual archive comparator without repeating the full
        # 101,504-run search for each deliberate field mutation.
        rebuilt = {"contract": "M7", "candidates": [{"cost": 12}, {"cost": 14}],
                   "status": "class-optimal", "host_seconds": {"search": 2.0}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"report.json.gz"
            for mutation in ("cost", "cost-type", "omission", "status", "extra", "timing"):
                claimed = deepcopy(rebuilt)
                if mutation == "cost":
                    claimed["candidates"][0]["cost"] += 1
                elif mutation == "cost-type":
                    claimed["candidates"][0]["cost"] = 12.0
                elif mutation == "omission":
                    claimed["candidates"].pop()
                elif mutation == "status":
                    claimed["status"] = "best-known"
                elif mutation == "timing":
                    claimed["host_seconds"]["search"] = -1.0
                else:
                    claimed["unexpected"] = 1
                write_json(path, claimed)
                with patch.object(report, "_suite", return_value=rebuilt), self.assertRaises(ValueError):
                    report.verify(path, "unused-trace")
            claimed = deepcopy(rebuilt)
            claimed["host_seconds"]["search"] = 100.0
            write_json(path, claimed)
            with patch.object(report, "_suite", return_value=rebuilt):
                self.assertEqual(report.verify(path, "unused-trace"), rebuilt)


if __name__ == "__main__":
    unittest.main()
