"""Small real primitive traces for M3 evidence and failure-classification checks.

The complete archived matrix is replayed separately by the CLI in run_all.sh.
These tests execute and replay a small native net, then mutate metadata against
that captured replay; they do not stand in for complete-matrix verification.
"""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ic_coherent_feedback import spec_digest
from ic_composition_certificates import execute, compare_report, full_match
import ic_composition_certificates as composition
from ic_composition_examples import primitive_copy, bad_delta_copy
from ic_primitive_port_verifier import Net, pair
from ic_research_artifacts import GraphSpec
from ic_schedule_audit import Schedule, ScheduledNet, ScheduleTrace
from ic_rule_trace_lifting import translated_witness_pair


class Counter:
    count = 0
    def record(self, pair):
        self.count += 1


class Evidence(unittest.TestCase):
    def test_runtime_policies_must_match_the_bound_contract(self):
        with patch.object(composition, "POLICIES", (Schedule("seeded", 18),)):
            with self.assertRaises(ValueError):
                composition.inputs()

    def test_copy_precondition_and_stale_witness_ids_are_rejected(self):
        payload = Net()
        d = payload.cell("d")
        payload.link((d, 0), payload.boundary("ROOT"))
        for port in (1, 2):
            payload.link((d, port), (payload.cell("e"), 0))
        with self.assertRaises(ValueError):
            primitive_copy(payload)
        bypass = bad_delta_copy()
        negative = execute(bypass["initial"], bypass["expected"], Schedule(), Counter())
        self.assertEqual(negative["status"], "wrong-normal-form")
        contextual = GraphSpec.from_net(pair("g", "d")[0]).instantiate(ScheduledNet(Schedule("witness")))
        mapping = {"old-0": "c0", "old-1": "c1"}
        self.assertEqual(translated_witness_pair(("old-0", "old-1"), mapping, contextual), ("c0", "c1"))
        for proposed in (("old-0", "old-1"), ("c1", "c0")):
            with self.assertRaises(ValueError):
                translated_witness_pair(("old-0", "old-1"), mapping, contextual, proposed=proposed)
        with self.assertRaises(ValueError):
            translated_witness_pair(("absent", "old-1"), mapping, contextual)

    def test_real_replay_and_mutated_resource_and_graph_claims(self):
        initial = pair("g", "d")[0]
        target = GraphSpec.from_net(initial).instantiate()
        target.reduce(*target.active()[0])
        metadata = {"scope": "tiny native composition integrity fixture"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.gz"
            writer = ScheduleTrace(path, metadata)
            produced = execute(initial, target, Schedule(), writer)
            summary = writer.close()
            reader = ScheduleTrace(path, metadata, True)
            replayed = execute(initial, target, Schedule(), reader)
            self.assertEqual(summary, reader.close())
        self.assertEqual(produced, replayed)
        self.assertEqual(produced["status"], "passed")
        rebuilt = {"status": "passed", "typed_programs": [replayed], "trace": summary}
        compare_report(deepcopy(rebuilt), rebuilt)
        mutations = []
        for key, value in (("primitive_interactions", 2), ("trace_offset_records", 1),
                           ("terminal", False), ("whole_graph_matches_reference", False),
                           ("initial_graph_sha256", "bad"), ("final_graph_sha256", "bad")):
            bad = deepcopy(rebuilt)
            bad["typed_programs"][0][key] = value
            mutations.append(bad)
        for key in ("peak_live_cells", "runtime_cells_allocated", "sum_projected_peaks_bound"):
            bad = deepcopy(rebuilt)
            bad["typed_programs"][0]["resources"][key] += 1
            mutations.append(bad)
        bad = deepcopy(rebuilt)
        bad["typed_programs"][0]["final_graph"]["cycles"] += 1
        mutations.append(bad)
        bad = deepcopy(rebuilt)
        bad["trace"]["sha256_of_pair_records"] = "bad"
        mutations.append(bad)
        for bad in mutations:
            with self.assertRaises(ValueError):
                compare_report(bad, rebuilt)
        incomplete = {**rebuilt, "status": "not-accepted"}
        with self.assertRaises(ValueError):
            compare_report(incomplete, incomplete)

    def test_cutoffs_are_not_success_and_keep_counterexample(self):
        initial = pair("g", "d")[0]
        target = GraphSpec.from_net(initial).instantiate()
        target.reduce(*target.active()[0])
        for kwargs, status in (({"max_steps": 0}, "incomplete"),
                               ({"max_cells": 1}, "resource-violation"),
                               ({"max_cells": 3}, "resource-violation")):
            record = execute(initial, target, Schedule(), Counter(), **kwargs)
            self.assertEqual(record["status"], status)
            self.assertIn("counterexample", record)
        for kwargs in ({"max_steps": True}, {"max_cells": -1}):
            with self.assertRaises(ValueError):
                execute(initial, target, Schedule(), Counter(), **kwargs)

    def test_full_graph_rejects_hidden_component_cycle_and_wrong_labels(self):
        target = Net()
        root = target.cell("e")
        target.link((root, 0), target.boundary("OUT"))
        syntax = GraphSpec.from_net(target)
        extra = syntax.instantiate()
        a, b = extra.cell("g"), extra.cell("e")
        extra.link((a, 0), (a, 1))
        extra.link((a, 2), (b, 0))
        self.assertFalse(full_match(extra, target))
        cyclic = syntax.instantiate()
        cyclic.cycles += 1
        self.assertFalse(full_match(cyclic, target))
        mislabeled = GraphSpec(syntax.kinds, ("OTHER",),
                               tuple(tuple(("F", "OTHER") if p == ("F", "OUT") else p for p in w)
                                     for w in syntax.wires)).instantiate()
        self.assertFalse(full_match(mislabeled, target))
        self.assertNotEqual(spec_digest(GraphSpec.from_net(cyclic).to_dict()), spec_digest(syntax.to_dict()))


if __name__ == "__main__":
    unittest.main()
