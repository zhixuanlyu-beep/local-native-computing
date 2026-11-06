"""M6 exact contextual port maps and honestly recorded witness cutoffs."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ic_result_controlled_composition as composition
from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec
from ic_result_controlled_library import load_control_library, ROOT
from source_ic_coherent_compiler import CoherentICCompiler


def local_graph():
    net = Net()
    a, b, c = net.cell("g"), net.cell("d"), net.cell("g")
    net.link((a, 0), net.boundary("LEFT"))
    net.link((a, 1), (b, 2))
    net.link((a, 2), net.boundary("EXTRA_LEFT"))
    net.link((b, 0), net.boundary("MIDDLE"))
    net.link((b, 1), (c, 1))
    net.link((c, 0), net.boundary("RIGHT"))
    net.link((c, 2), net.boundary("EXTRA_RIGHT"))
    net.check()
    return net


class CorrespondenceIntegrity(unittest.TestCase):
    def setUp(self):
        self.local, self.whole = local_graph(), Net()
        cell = self.whole.cell("e")
        self.whole.link((cell, 0), self.whole.boundary("KEEP"))
        GraphSpec.from_net(self.local).instantiate(self.whole)
        self.core = {f"c{i}": f"c{i+1}" for i in range(3)}
        self.boundaries = {label: ("F", label) for _, label in self.local.free}

    def test_partial_seed_extends_to_all_local_cells_with_fresh_names(self):
        result = composition.correspondence(self.local, self.whole, {"c0": "c1"}, self.boundaries)
        self.assertEqual(result, self.core)
        self.assertEqual(self.whole.nodes["c0"], "e")

    def test_rejects_kind_mismatch(self):
        self.whole.nodes["c1"] = "d"
        with self.assertRaisesRegex(ValueError, "kind differs"):
            composition.correspondence(self.local, self.whole, self.core, self.boundaries)

    def test_rejects_port_number_mismatch(self):
        a, b = ("c1", 1), ("c2", 1)
        left, right = self.whole.adj[a], self.whole.adj[b]
        for port in (a, b, left, right):
            self.whole.adj[port] = None
        self.whole.link(a, right)
        self.whole.link(b, left)
        self.whole.check()
        with self.assertRaisesRegex(ValueError, "port numbers differ"):
            composition.correspondence(self.local, self.whole, self.core, self.boundaries)

    def test_rejects_noninjective_and_absent_maps(self):
        for bad in ({"c0": "c2", "c1": "c2"}, {"c0": "absent"}):
            with self.assertRaises(ValueError):
                composition.correspondence(self.local, self.whole, bad, self.boundaries)

    def test_rejects_incomplete_or_wrong_boundary_map(self):
        bad = dict(self.boundaries)
        del bad["LEFT"]
        with self.assertRaisesRegex(ValueError, "complete local interface"):
            composition.correspondence(self.local, self.whole, self.core, bad)
        bad["LEFT"] = ("F", "KEEP")
        with self.assertRaisesRegex(ValueError, "boundary mapping differs"):
            composition.correspondence(self.local, self.whole, self.core, bad)


class StagedCutoffIntegrity(unittest.TestCase):
    def test_budget_exhaustion_preserves_actual_prefix_and_status(self):
        library = load_control_library(ROOT / "results/structure_library.json.gz")
        compiler = CoherentICCompiler()
        for budget, status in (({"max_steps": 0}, "incomplete"),
                               ({"max_cells": 0}, "resource-violation")):
            pairs = composition.PairList()
            result = composition.staged_case([0], library, compiler, {}, pairs, budget=budget)
            self.assertEqual(result["status"], status)
            self.assertFalse(result["whole_graph_matches_reference"])
            self.assertEqual(result["primitive_interactions"], 0)
            self.assertEqual(result["resources"]["initial_cells"], len(result["final_graph"]["kinds"]))
            self.assertEqual(result["counterexample"]["reason"], status)
        with self.assertRaises(ValueError):
            composition.staged_case([0], library, compiler, {}, composition.PairList(), budget={"max_steps": True})


if __name__ == "__main__":
    unittest.main()
