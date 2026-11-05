"""Reduced M5 fixtures; the archived CLI replay is the complete experiment."""
import copy
import gzip
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ic_structure_reuse as reuse
from ic_reuse_benchmarks import producer, build_benchmark
from ic_research_artifacts import GraphSpec


class StructureReuseIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = reuse.inputs()
        cls.workload = cls.context["workloads"][0]

    def context_fixture(self):
        context = dict(self.context)
        context["workloads"] = [self.workload]
        context["missing"] = []
        return context

    def run_fixture(self, strategy="retained_chain", disposition="retain1", **budget):
        workload = self.workload
        built = build_benchmark(workload, workload["packet"], 1, strategy, disposition,
                                reuse.task_inputs(workload, 1), self.context["gate"])
        class Sink:
            count = 0
            def record(self, pair):
                self.count += 1
        return reuse.run_case(built, reuse.expected(workload, 1, disposition), reuse.Schedule(), Sink(),
                              reuse.predicted_census(workload, workload["packet"], 1, strategy, disposition),
                              strategy=strategy, disposition=disposition, **budget)

    def test_common_cost_basis_and_original_consumption(self):
        for strategy in reuse.STRATEGIES:
            for disposition in reuse.DISPOSITIONS:
                with self.subTest(strategy=strategy, disposition=disposition):
                    record = self.run_fixture(strategy, disposition)
                    self.assertEqual(record["status"], "passed")
                    self.assertTrue(record["source_cells_consumed"])
                    self.assertTrue(record["whole_graph_matches_reference"])
                    resources = record["resources"]
                    self.assertEqual(sum(resources["initial_categories"].values()), resources["initial_cells"])
                    self.assertEqual(sum(resources["rhs_allocations_by_kind"].values()), resources["runtime_cells_allocated"])
                    self.assertLessEqual(resources["explicit_eraser_interactions"], resources["primitive_interactions"])
                    self.assertEqual(resources["retained_cells"] > 0, disposition == "retain1")
                    self.assertEqual(record["protocol_violations"], [])

    def test_budget_exhaustion_is_not_pass_or_impossibility(self):
        self.assertEqual(self.run_fixture(max_steps=0)["status"], "incomplete")
        self.assertEqual(self.run_fixture(max_cells=0)["status"], "resource-violation")
        with self.assertRaises(ValueError):
            self.run_fixture(max_steps=True)

    def test_native_census_addition_is_not_a_peak_prediction(self):
        workload = self.workload
        a = reuse.predicted_census(workload, workload["packet"], 4, "literal", "retain1")
        b = reuse.predicted_census(workload, workload["packet"], 4, "retained_chain", "retain1")
        overhead = reuse.copy_census(workload["capsule"].code)
        overhead.update(reuse.decoder_census(workload["capsule"]))
        self.assertEqual({k: b[k]-a[k] for k in a}, {k: 4*overhead[k] for k in a})
        self.assertEqual(b, reuse.predicted_census(workload, workload["packet"], 4, "native_fanout", "retain1"))

    def test_source_production_replays_and_preserves_value_not_cell_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.gz"
            trace = reuse.ScheduleTrace(path, {"fixture": "producer"})
            original, artifact = reuse.run_producer(producer(self.workload["packet"]), self.workload["packet"], trace, **reuse.BUDGET)
            summary = trace.close()
            self.assertEqual(original["status"], "passed")
            self.assertTrue(original["source_cells_consumed"])
            replay = reuse.ScheduleTrace(path, {"fixture": "producer"}, replay=True)
            rebuilt, other = reuse.run_producer(producer(self.workload["packet"]), self.workload["packet"], replay, **reuse.BUDGET)
            self.assertEqual(summary, replay.close())
            self.assertEqual(original, rebuilt)
            self.assertEqual(artifact.spec, other.spec)

    def test_reduced_report_reconstruction_and_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.gz"
            context = self.context_fixture()
            with patch.object(reuse, "COUNTS", (1,)), patch.object(reuse, "POLICIES", (reuse.Schedule(),)):
                report, manifest = reuse._suite(path, context=context)
                self.assertEqual(report["status"], "passed")
                with patch.object(reuse, "inputs", side_effect=self.context_fixture):
                    self.assertEqual(reuse.verify_report(report, manifest, path), 6)
                    bad = copy.deepcopy(manifest)
                    bad["native_artifacts"][0]["production_evidence"] = "all-schedules-finite"
                    with self.assertRaises(ValueError):
                        reuse.verify_report(report, bad, path)
                    bad = copy.deepcopy(report)
                    bad["comparisons"][0]["vectors"]["literal"][0] += 1
                    with self.assertRaises(ValueError):
                        reuse.verify_report(bad, manifest, path)
                    with gzip.open(path, "rb") as stream:
                        raw = bytearray(stream.read())
                    raw[-1] ^= 1
                    with gzip.open(path, "wb") as stream:
                        stream.write(raw)
                    with self.assertRaises(ValueError):
                        reuse.verify_report(report, manifest, path)
            query = dict(storage_representation=reuse.STORAGE_REPRESENTATION, storage_interface=("ROOT",),
                         activation_interface=self.workload["component"].boundaries,
                         input_reprs=self.workload["input_reprs"], output_reprs=self.workload["output_reprs"],
                         source_id=self.workload["source_id"])
            matches = reuse.query_artifacts(manifest, **query)
            self.assertEqual(len(matches), 1)
            self.assertEqual(reuse.query_artifacts(manifest, **query, minimum_evidence="all-schedules-finite"), ())
            self.assertEqual(reuse.query_artifacts(manifest, **{**query, "storage_interface": ("OUT",)}), ())
            matches[0]["artifact"]["spec"]["kinds"][0] = "e"
            self.assertNotEqual(matches, reuse.query_artifacts(manifest, **query))

    def test_negative_control_and_wiring_have_durable_counterexamples(self):
        class Sink:
            count = 0
            def record(self, pair):
                self.count += 1
        negatives = reuse.negative_cases(self.context_fixture(), Sink())
        self.assertEqual([r["conclusion"] for r in negatives], ["refuted", "refuted"])
        for record in negatives:
            self.assertIn("counterexample", record)
            self.assertFalse(record["whole_graph_matches_reference"])
            self.assertFalse(reuse.full_match(GraphSpec.from_dict(record["final_graph"]).instantiate(),
                                             reuse.expected(self.workload, 1, "retain1")))

    def test_pareto_does_not_invent_a_scalar_price(self):
        records = []
        for strategy, vector in zip(reuse.STRATEGIES, ((10, 20, 30, 10), (8, 30, 40, 8), (11, 21, 31, 11))):
            resources = dict(zip(("initial_cells", "primitive_interactions", "total_symbolic_cells_allocated", "peak_live_cells"), vector))
            records.append({"workload": "fixture", "task_count": 1, "disposition": "retain1",
                            "schedule": reuse.Schedule().to_dict(), "strategy": strategy,
                            "status": "passed", "resources": resources})
        comparison = reuse.compare_costs(records)[0]
        self.assertEqual(comparison["pareto_front"], ["literal", "native_fanout"])
        self.assertFalse(comparison["relative_to_literal"]["native_fanout"]["dominates_literal"])
        self.assertTrue(comparison["relative_to_literal"]["retained_chain"]["dominated_by_literal"])


if __name__ == "__main__":
    unittest.main()
