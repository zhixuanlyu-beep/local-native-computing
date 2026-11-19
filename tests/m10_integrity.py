"""Coverage, deterministic replay, and hostile edits to M10 evidence."""

from copy import deepcopy
from hashlib import sha256
from itertools import product
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ic_m10
import ic_m10_core as core
import ic_m10_search as search
import ic_m10_verify as verifier
from ic_m9_core import enumerate_candidates


class FrozenInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bindings = ic_m10.frozen_bindings()

    def test_candidates_reuse_m9_raw_order(self):
        candidates = self.bindings["candidates"]
        self.assertEqual(len(candidates), 770)
        self.assertEqual(len({candidate["id"] for candidate in candidates}), 770)
        self.assertEqual([candidate["transform"] for candidate in candidates],
                         [candidate.to_dict() for candidate in enumerate_candidates()])

    def test_search_and_holdout_vectors(self):
        expected_edges = {"star4": [[0, 1], [0, 2], [0, 3]],
                          "cycle4": [[0, 1], [0, 3], [1, 2], [2, 3]]}
        expected_free = {"star4": [0, 1, 2, 5, 7, 12],
                         "cycle4": [0, 1, 2, 9, 11, 16]}
        for topology, domain, holdout in zip(self.bindings["topologies"], self.bindings["domains"],
                                              self.bindings["holdouts"], strict=True):
            name = topology["id"]
            with self.subTest(topology=name):
                self.assertEqual(topology["edges"], expected_edges[name])
                self.assertEqual(domain["free_slots"], expected_free[name])
                self.assertEqual([tuple(bits[i] for i in domain["free_slots"]) for bits in domain["inputs"]],
                                 list(product((False, True), repeat=6)))
                fixed = [False, False] + [True, False, False, True] * len(topology["edges"])
                self.assertTrue(all(bits[i] == fixed[i] for bits in domain["inputs"]
                                    for i in domain["fixed_slots"]))
                search_vectors = {tuple(bits) for bits in domain["inputs"]}
                self.assertTrue(search_vectors.isdisjoint(map(tuple, holdout["inputs"])))

                def key(bits):
                    bit_string = "".join("1" if bit else "0" for bit in bits)
                    return sha256(f"M10-v1:{name}:{bit_string}".encode()).digest(), bit_string

                outside = (bits for bits in product((False, True), repeat=len(fixed)) if bits not in search_vectors)
                self.assertEqual(holdout["inputs"], [list(bits) for bits in sorted(outside, key=key)[:256]])

    def test_reference_uses_each_edge_endpoint(self):
        # One permitted assignment, 0101, with a single enabled tuple per edge.
        assignment = (0, 1, 0, 1)
        for topology in self.bindings["topologies"]:
            edges = topology["edges"]
            bits = [True, False] + [False] * (4 * len(edges))
            for i, (left, right) in enumerate(edges):
                bits[2 + 4 * i + 2 * assignment[left] + assignment[right]] = True
            self.assertTrue(core.reference(tuple(bits), topology["id"]))
            for candidate in self.bindings["candidates"][:3]:
                prepared = core.prepare_candidate(candidate["transform"], topology["id"])
                record = search.evaluate_input(candidate, prepared, bits, 0, self.bindings["budget"], engine="python")
                self.assertEqual(record["status"], "passed")
            for i in range(len(edges)):
                broken = bits[:2 + 4 * i] + [False] * 4 + bits[6 + 4 * i:]
                self.assertFalse(core.reference(tuple(broken), topology["id"]))


class ExecutionEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bindings = ic_m10.frozen_bindings()

    def test_python_and_optional_native_executor_agree(self):
        from ic_m9_accel import DEFAULT_LIBRARY

        library = Path(os.environ.get("IC_M9_NATIVE_LIBRARY") or DEFAULT_LIBRARY)
        if not library.is_file():
            self.skipTest("optional M9 native library is unavailable")
        with patch.dict("os.environ", {"IC_M9_NATIVE_LIBRARY": str(library.resolve())}):
            for topology, domain in zip(self.bindings["topologies"], self.bindings["domains"], strict=True):
                for index, cap in ((0, None), (20, 31), (401, None), (769, 1)):
                    candidate = self.bindings["candidates"][index]
                    prepared = core.prepare_candidate(candidate["transform"], topology["id"])
                    bits = domain["inputs"][index % len(domain["inputs"])]
                    python = search.evaluate_input(candidate, prepared, bits, 0, self.bindings["budget"],
                                                   step_limit=cap, engine="python")
                    native = search.evaluate_input(candidate, prepared, bits, 0, self.bindings["budget"],
                                                   step_limit=cap, engine="native-c")
                    with self.subTest(topology=topology["id"], candidate=candidate["id"], cap=cap):
                        self.assertEqual(native, python)

    def test_negative_cutoff_is_not_a_complete_success(self):
        topology = self.bindings["topologies"][0]
        domain = self.bindings["domains"][0]
        candidate = self.bindings["candidates"][0]
        prepared = core.prepare_candidate(candidate["transform"], topology["id"])
        record = search.evaluate_input(
            candidate, prepared, domain["inputs"][0], 0, self.bindings["budget"],
            step_limit=1, engine="python")
        self.assertEqual(record["status"], "incomplete")
        self.assertEqual(record["steps"], 1)
        self.assertEqual(record["step_limit"], 1)
        self.assertFalse(record["whole_graph_matches_reference"])


class CertificateTampering(unittest.TestCase):
    """Exercise the production verifier with a tiny complete search job."""

    @classmethod
    def setUpClass(cls):
        bindings = ic_m10.frozen_bindings()
        topology = bindings["topologies"][0]
        domain = bindings["domains"][0]
        cls.candidates = [bindings["candidates"][i] for i in (0, 1, 2, 16, 61, 384, 386, 390, 500, 690, 769)]
        cls.inputs = domain["inputs"][:8]
        cls.holdout = bindings["holdouts"][0]["inputs"][:2]
        cls.job = (topology["id"], cls.candidates, cls.inputs, cls.holdout,
                   {"max_steps": 100_000, "max_cells": 20_000})
        cls.claim = search.run_topology(cls.job)
        verifier.verify_topology((cls.job, cls.claim, False))

    def rejects(self, claim, message, *, replay=False, job=None):
        with self.assertRaisesRegex(ValueError, message):
            verifier.verify_topology((self.job if job is None else job, claim, replay))

    def test_candidate_omission_is_rejected(self):
        changed = deepcopy(self.claim)
        changed["full_enumeration"]["candidates"].pop()
        self.rejects(changed, "candidate coverage")

    def test_graph_and_step_tampering_are_rejected(self):
        changed = deepcopy(self.claim)
        record = changed["full_enumeration"]["candidates"][0]["records"][0]
        record["initial_graph_sha256"] = "0" * 64
        self.rejects(changed, "exhaustive evidence differs", replay=True)
        changed = deepcopy(self.claim)
        record = changed["certificate"]["candidates"][0]["records"][0]
        record["steps"] += 1
        self.rejects(changed, "certificate input differs")
        changed = deepcopy(self.claim)
        row = next(row for row in changed["certificate"]["candidates"]
                   if row["decision"] and row["decision"]["reason"] == "prefix-above-upper")
        row["records"][-1]["steps"] = row["decision"]["upper_bound"]
        self.rejects(changed, "FIFO prefix disagrees with Python replay")

    def test_cutoff_cannot_be_marked_passed(self):
        job = (self.job[0], self.candidates[:1], self.inputs[:1], self.holdout, {**self.job[4], "max_steps": 1})
        changed = search.run_topology(job)
        verifier.verify_topology((job, changed, True))
        baseline = changed["full_enumeration"]
        row = baseline["candidates"][0]
        self.assertEqual(row["records"][0]["status"], "incomplete")
        row["records"][0].update(status="passed", whole_graph_matches_reference=True)
        row.update(status="complete", cost=1)
        baseline["summary"] = search.summary(baseline["candidates"])
        baseline["metrics"] = search.group_metrics(baseline["candidates"])
        self.rejects(changed, "exhaustive evidence differs", replay=True, job=job)

    def test_holdout_input_cannot_enter_search(self):
        changed = deepcopy(self.claim)
        changed["full_enumeration"]["candidates"][0]["records"][0]["bits"] = list(self.holdout[0])
        self.rejects(changed, "differs from frozen search")

    def test_equal_bound_is_not_an_exclusion(self):
        changed = deepcopy(self.claim)
        rows = changed["certificate"]["candidates"]
        row = next(row for row in rows if row["decision"] and row["decision"]["reason"] == "static-live-bound")
        decision, evidence = row["decision"], row["evidence"]
        with self.assertRaisesRegex(ValueError, "strictly exceed"):
            verifier._check_static(decision["lower_bound"], evidence["initial_live_cells"],
                                   evidence["reference_live_cells"], decision["lower_bound"])
        decision["lower_bound"] = decision["upper_bound"]
        self.rejects(changed, "incorrect live-cell lower bound")

    def test_future_or_incomplete_upper_is_rejected(self):
        for later in (False, True):
            changed = deepcopy(self.claim)
            rows = changed["certificate"]["candidates"]
            excluded = [row for row in rows[:-1] if row["status"] == "excluded"]
            row = excluded[1]
            identifier = rows[-1]["candidate"] if later else excluded[0]["candidate"]
            row["upper"] = {**row["upper"], "candidate": identifier}
            with self.subTest(future=later):
                self.rejects(changed, "preceding fully verified winner")


if __name__ == "__main__":
    unittest.main()
