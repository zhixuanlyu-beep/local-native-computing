"""M4 integration integrity using recorded local witnesses and a small DAG.

The fixture imports the actual discovered graph specimens and selected raw
local trace intervals. It independently constructs and replays a reduced
staged program fixture. Complete candidate accounting and the full compiler
consumer matrix are replayed separately by the CLI in run_all.sh.
"""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import ic_multitask_discovery as m
import ic_observation_contracts as observations
from ic_discovered_programs import build_program, build_code_program


class PairCounter:
    def __init__(self):
        self.count = 0
    def record(self, pair):
        self.count += 1


class MultitaskIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = m.inputs()
        cls.saved = m.read_json(REPO / "results/multitask_discovery.json.gz")
        if cls.saved["status"] != "passed" or m.spec_digest(cls.saved["bindings"]) != m.spec_digest(cls.context["bindings"]):
            raise AssertionError("integration fixture does not bind the current fixed search")
        tasks = {task.name: task for task in cls.context["tasks"]}
        cls.library, cls.witnesses = {}, {}
        for role, entry in cls.saved["selected_library"].items():
            task = tasks[entry["task"]]
            cls.library[role] = {"task": task, "spec": m.GraphSpec.from_dict(entry["graph"]),
                                 "candidate_id": entry["candidate_id"],
                                 "cases": {tuple(case["bits"]): case["observation"] for case in entry["witness_cases"]}}
        with gzip.open(REPO / "results/multitask_discovery.ictrace.gz", "rb") as stream:
            header = json.loads(stream.readline())
            if header != {"format": "IC-PAIR-U32LE-1", **cls.saved["metadata"]}:
                raise AssertionError("local witness archive header mismatch")
            start = stream.tell()
            for entry in cls.library.values():
                for bits, oid in entry["cases"].items():
                    if oid in cls.witnesses:
                        continue
                    record = cls.saved["discovery"]["observations"][oid]
                    built = observations.build_observation(entry["task"].family, entry["spec"],
                                                           entry["task"].input_reprs, bits)
                    syntax = m.GraphSpec.from_net(built.net)
                    if m.spec_digest(syntax.to_dict()) != record["initial_graph_sha256"]:
                        raise AssertionError("local witness input reconstruction mismatch")
                    stream.seek(start + 8 * record["trace_offset_records"])
                    raw = stream.read(8 * record["primitive_interactions"])
                    if len(raw) != 8 * record["primitive_interactions"]:
                        raise AssertionError("truncated archived local witness")
                    pairs = [tuple("c" + str(i) for i in pair) for pair in struct.iter_unpack("<II", raw)]
                    cls.witnesses[oid] = {"initial": syntax, "pairs": pairs, "record": record,
                                           "component_ids": built.component_ids, "input_ids": built.input_ids}

    def test_real_discovered_staged_fixture_replay_and_field_tampering(self):
        metadata = {"scope": "reduced actual discovered DAG fixture",
                    "bindings_sha256": m.spec_digest(self.context["bindings"])}
        bit_cases = ((False, False, False), (True, False, True), (True, True, True))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.ictrace.gz"
            writer = m.ScheduleTrace(path, metadata)
            produced = [m.staged_program(build_program(self.library, bits), self.library, bits,
                                         self.witnesses, writer)[0] for bits in bit_cases]
            summary = writer.close()
            reader = m.ScheduleTrace(path, metadata, True)
            replayed = [m.staged_program(build_program(self.library, bits), self.library, bits,
                                         self.witnesses, reader)[0] for bits in bit_cases]
            self.assertEqual(summary, reader.close())
        self.assertEqual(produced, replayed)
        self.assertTrue(all(record["status"] == "passed" for record in replayed))
        rebuilt = {"status": "passed", "discovery": {"observations": []},
                   "staged_programs": replayed, "trace": summary}
        m.compare_report(deepcopy(rebuilt), rebuilt)
        mutations = []
        for key in ("primitive_interactions", "trace_offset_records", "constructive_staged_peak"):
            bad = deepcopy(rebuilt)
            bad["staged_programs"][0][key] += 1
            mutations.append(bad)
        for key in ("candidate_id", "task"):
            bad = deepcopy(rebuilt)
            bad["staged_programs"][0]["stages"][0][key] = "tampered"
            mutations.append(bad)
        bad = deepcopy(rebuilt)
        bad["staged_programs"][0]["resources"]["rule_census"]["gd"] += 1
        mutations.append(bad)
        bad = deepcopy(rebuilt)
        bad["staged_programs"][0]["final_graph"]["cycles"] += 1
        mutations.append(bad)
        bad = deepcopy(rebuilt)
        bad["staged_programs"][0]["stages"][0]["outside_unchanged"] = False
        mutations.append(bad)
        for bad in mutations:
            with self.assertRaises(ValueError):
                m.compare_report(bad, rebuilt)
        not_accepted = {**rebuilt, "status": "not-accepted"}
        with self.assertRaises(ValueError):
            m.compare_report(not_accepted, not_accepted)

    def test_corrupt_local_pair_is_rejected_before_it_is_executed(self):
        witnesses = deepcopy(self.witnesses)
        oid = self.library["copy_A"]["cases"][(False,)]
        witnesses[oid]["pairs"][0] = ("absent-cell", "other-absent-cell")
        counter = PairCounter()
        result, _ = m.staged_program(build_program(self.library, (False, False, False)), self.library,
                                     (False, False, False), witnesses, counter)
        self.assertEqual(result["status"], "proof-rejected")
        self.assertEqual(counter.count, 0)
        self.assertIn("counterexample", result)

    def test_builders_and_joint_runtime_do_not_evaluate_the_answer(self):
        bits = (True, False, True)
        target = m.small_expected(bits)
        opened = []
        code_spec = self.context["compiler"].code_spec
        original = m.GraphSpec.open_root
        def observe_open(spec, net):
            if spec is code_spec:
                opened.append(spec)
            return original(spec, net)
        with patch.object(observations.TaskContract, "evaluate", side_effect=AssertionError("host truth oracle")), \
                patch.object(m, "small_expected", side_effect=AssertionError("host answer")), \
                patch.object(m.GraphSpec, "open_root", observe_open):
            built = build_program(self.library, bits)
            code_built = build_code_program(self.library, bits, self.context["pairs"][0][0], code_spec)
            result = m.run_joint(built, target, m.Schedule("lifo"), PairCounter(), **m.PROGRAM_BUDGET)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(opened), 1)
        self.assertEqual(len(code_built.program_ids), len(code_spec.kinds))

    def test_wrong_representation_and_stale_graph_fingerprint_are_rejected(self):
        lib = {key: dict(entry) for key, entry in self.library.items()}
        lib["erase_B"]["task"] = next(t for t in self.context["tasks"] if t.family == "erase" and t.input_reprs == ("A",))
        with self.assertRaises(ValueError):
            build_program(lib, (True, True, True))
        lib = {key: dict(entry) for key, entry in self.library.items()}
        lib["box_AB"]["candidate_id"] = "stale-fingerprint"
        with self.assertRaises(ValueError):
            build_program(lib, (True, True, True))

    def test_native_cutoffs_cannot_become_verified_observations(self):
        entry = self.library["and_A"]
        built = observations.build_observation("binary", entry["spec"], ("A", "A"), (False, False))
        target = observations.expected(entry["task"], (False, False))
        for kwargs, status in (({"max_steps": 0}, "incomplete"), ({"max_cells": 0}, "resource-violation")):
            record, _ = m.observe(built, PairCounter(), **kwargs)
            self.assertEqual(m._case_status(record, target), status)
        with self.assertRaises(ValueError):
            m.observe(built, PairCounter(), max_steps=True)
        result = m.run_joint(build_program(self.library, (True, True, True)),
                             m.small_expected((True, True, True)), m.Schedule(), PairCounter(), max_steps=0)
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("counterexample", result)

    def test_changed_search_contract_or_policy_is_rejected_before_replay(self):
        for field in ("tasks", "grammars", "candidate_inventories", "representations", "frozen_reports"):
            report = dict(self.saved)
            report["bindings"] = deepcopy(self.saved["bindings"])
            report["bindings"][field] = "tampered"
            with patch.object(m, "inputs", return_value=self.context), self.assertRaises(ValueError):
                m.verify_report(report, Path("unused.ictrace.gz"))
        with patch.object(m, "POLICIES", (m.Schedule("seeded", 18),)), self.assertRaises(ValueError):
            m.inputs()


if __name__ == "__main__":
    unittest.main()
