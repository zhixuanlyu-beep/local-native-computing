"""M9 holdout coverage and rejection of incomplete or altered evidence."""
from copy import deepcopy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ic_coherent_feedback import read_json, write_json
import ic_m9
import ic_m9_core
import ic_m9_search


class M9Integrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates, cls.abstraction = ic_m9_core.candidate_catalog()
        cls.m8 = read_json(ic_m9.M8_REPORT)
        cls.ranking = ic_m9_search.freeze_ranking(cls.m8["library"])
        cls.orders = ic_m9_search.build_orders(
            cls.candidates, cls.abstraction, cls.ranking
        )

    def test_frozen_candidate_and_class_counts(self):
        self.assertEqual(len(self.candidates), 770)
        self.assertEqual(len({row["id"] for row in self.candidates}), 770)
        self.assertEqual(len({row["canonical"] for row in self.candidates}), 770)
        self.assertEqual(self.abstraction["classes"], 290)
        self.assertEqual(
            len(set(self.abstraction["members"].values())),
            self.abstraction["classes"],
        )
        self.assertEqual(
            set(self.abstraction["members"]),
            {row["canonical"] for row in self.candidates},
        )

    def test_domains_are_complete_and_ordered(self):
        domains = ic_m9_core.frozen_domains()
        self.assertEqual([domain["id"] for domain in domains], ["D1", "D2", "D3", "D4"])
        for domain in domains:
            self.assertEqual(len(domain["inputs"]), 64)
            self.assertEqual(
                len(domain["free_slots"]), 6,
                "each frozen domain exposes exactly six Boolean slots",
            )
            expected = [
                [any(index == slot for index, bit in enumerate(bits) if bit)
                 for slot in domain["free_slots"]]
                for bits in domain["inputs"]
            ]
            self.assertEqual(
                expected,
                sorted(expected),
                "domain inputs must follow Boolean dictionary order",
            )
            free = set(domain["free_slots"])
            fixed = set(domain["fixed_slots"])
            self.assertEqual(len(fixed), ic_m9_core.INPUT_BITS - 6)
            self.assertTrue(free.isdisjoint(fixed))
            self.assertEqual(free | fixed, set(range(ic_m9_core.INPUT_BITS)))

    def test_strict_ranking_contains_exactly_twenty_one_rules(self):
        self.assertEqual(len(self.ranking["rules"]), 21)
        self.assertEqual(
            self.ranking["counts"]["recognition_host_operations"],
            sum(rule["identification_overhead"]["host_operations"]
                for rule in self.ranking["rules"]),
        )
        for rule in self.ranking["rules"]:
            self.assertEqual(rule["direction"], "before-to-after")
            self.assertGreaterEqual(rule["conservative_saving"], 0)
            self.assertGreater(rule["identification_overhead"]["host_operations"], 0)

    def test_orders_cover_declared_raw_or_representative_spaces_once(self):
        expected = {row["id"] for row in self.candidates}
        self.assertEqual(self.orders["class_count"], 290)
        for name, record in self.orders["orders"].items():
            expected_count = 290 if "abstraction" in name else 770
            self.assertEqual(len(record["candidates"]), expected_count, name)
            self.assertEqual(len(record["visiting_order"]), expected_count, name)
            self.assertEqual(len(record["raw_order"]), expected_count, name)
            if expected_count == 770:
                self.assertEqual(set(record["visiting_order"]), expected, name)
            else:
                representatives = {
                    record["canonical"]
                    for record in self.abstraction["representatives"].values()
                }
                self.assertEqual({row["canonical"] for row in record["candidates"]},
                                 representatives, name)

    def test_abstraction_orders_visit_one_representative_per_class(self):
        for name in ("abstraction-only", "abstraction-and-ranking"):
            records = self.orders["orders"][name]["candidates"]
            self.assertEqual(len(records), 290)
            self.assertEqual(len({record["class_id"] for record in records}), 290)
            self.assertEqual({record["canonical"] for record in records},
                             {record["canonical"]
                              for record in self.abstraction["representatives"].values()})

    def test_unranked_orders_do_not_read_rule_savings(self):
        changed = deepcopy(self.ranking)
        changed["rules"][0]["conservative_saving"] = 0
        changed.pop("sha256")
        changed["sha256"] = ic_m9_search._digest(changed)
        orders = ic_m9_search.build_orders(self.candidates, self.abstraction, changed)
        for name in ("no-concepts", "abstraction-only"):
            self.assertEqual(orders["orders"][name]["raw_order"],
                             self.orders["orders"][name]["raw_order"])
            self.assertEqual(orders["orders"][name]["recognition"]["host_operations"], 0)

    def test_ranking_digest_detects_rule_tampering(self):
        changed = deepcopy(self.ranking)
        changed["rules"][0]["conservative_saving"] += 1
        with self.assertRaisesRegex(ValueError, "digest"):
            ic_m9_search.build_orders(self.candidates, self.abstraction, changed)

    def test_layered_graph_has_exact_terminal_cost_and_zero_internal_cost(self):
        graph = self.orders["graph"]
        self.assertEqual(graph["nodes"]["ROOT"]["layer"], "root")
        self.assertEqual(graph["nodes"]["GOAL"]["layer"], "goal")
        self.assertTrue({"representation", "elimination-order", "materialization"}
                        .issubset({node["layer"] for node in graph["nodes"].values()}))
        for edge in graph["edges"]:
            if edge["kind"] == "terminal":
                canonical = next(row["canonical"] for row in self.candidates
                                 if row["id"] == edge["candidate"])
                self.assertEqual(edge["cost"],
                                 graph["candidate_terminal_costs"][canonical])
            else:
                self.assertEqual(edge["cost"], 0)

    def test_order_timings_are_excluded_from_semantic_digest(self):
        import hashlib
        import json

        semantic = deepcopy(self.orders)
        semantic.pop("sha256")
        for record in semantic["orders"].values():
            record["host_seconds"].pop("preparation")
        semantic["work"].pop("preparation_seconds", None)
        encoded = json.dumps(semantic, sort_keys=True, separators=(",", ":"))
        self.assertEqual(self.orders["sha256"],
                         hashlib.sha256(encoded.encode("utf-8")).hexdigest())

    def test_tampered_abstraction_rejected(self):
        members = dict(self.abstraction["members"])
        removed = next(iter(members))
        del members[removed]
        changed = {**self.abstraction, "members": members}
        with self.assertRaisesRegex(ValueError, "cover"):
            ic_m9_search.build_orders(self.candidates, changed, self.ranking)
        members = dict(self.abstraction["members"])
        first, second = sorted(set(members.values()))[:2]
        for key, value in members.items():
            if value == first:
                members[key] = second
                break
        changed = {**self.abstraction, "members": members}
        with self.assertRaises(ValueError):
            ic_m9_search.build_orders(self.candidates, changed, self.ranking)

    def test_target_leakage_cannot_be_added_to_search_inputs(self):
        leaked = {
            **self.orders,
            "orders": deepcopy(self.orders["orders"]),
        }
        for record in leaked["orders"].values():
            record["candidates"][0]["worst_fifo_interactions"] = 0
        with TemporaryDirectory() as folder:
            frozen_path = Path(folder) / "freeze.json"
            write_json(frozen_path, {
                **ic_m9.frozen_bindings(),
                "leaked": leaked,
            })
            with self.assertRaisesRegex(ValueError, "manifest"):
                ic_m9.require_frozen(frozen_path)

    def test_search_scorer_charges_every_visited_prefix(self):
        rows = {
            candidate: {
                "candidate": candidate,
                "status": "complete",
                "worst_fifo_interactions": candidate + 1,
                "verification_interactions": 10 + candidate,
                "host_seconds": {"native": 0.25},
            }
            for candidate in range(4)
        }
        result = ic_m9.score_search([3, 1, 2, 0], rows.__getitem__, 2)
        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["visited"], [3, 1])
        self.assertEqual(result["verification_interactions"], 24)
        self.assertEqual(result["compile_calls"], 2)
        self.assertEqual(result["host_seconds"]["attributed_evaluator"], 0.5)

    def test_missing_target_is_not_a_successful_search(self):
        rows = {
            candidate: {
                "candidate": candidate,
                "status": "complete",
                "worst_fifo_interactions": 10,
                "verification_interactions": 1,
                "host_seconds": {"native": 0.0},
            }
            for candidate in range(3)
        }
        result = ic_m9.score_search([0, 1, 2], rows.__getitem__, 9)
        self.assertEqual(result["status"], "target-not-reached")
        self.assertIsNone(result["selected"])
        self.assertEqual(result["visits"], 3)

    def test_unfinished_domain_is_not_exact(self):
        rows = [
            {"candidate": 0, "status": "complete", "worst_fifo_interactions": 8},
            {"candidate": 1, "status": "incomplete", "worst_fifo_interactions": None},
        ]
        summary = ic_m9.summarize_domain(rows)
        self.assertEqual(summary["status"], "best-known")
        self.assertIsNone(summary["exact_target"])
        self.assertEqual(summary["best_known_worst_fifo_interactions"], 8)
        self.assertEqual(summary["unresolved_candidates"], [1])
        self.assertEqual(
            ic_m9.summarize_domain([rows[1]])["status"],
            "incomplete",
        )

    def test_real_archive_rejects_candidate_cost_and_prefix_mutation(self):
        if not ic_m9.REPORT.exists():
            self.skipTest("M9 report has not been generated yet")
        frozen = ic_m9.require_frozen()
        claimed = read_json(ic_m9.REPORT)
        method = next(iter(claimed["domains"][0]["methods"]))
        mutations = (
            ("omitted", claimed["domains"][0]["candidates"], "pop", -1),
            ("charge", claimed["domains"][0]["candidates"][0],
             "verification_interactions", 1),
            ("target", claimed["domains"][0]["summary"], "exact_target", 1),
            ("prefix", claimed["domains"][0]["methods"][method], "visits", 1),
            ("target leakage", claimed["orders"]["orders"]["no-concepts"]
             ["candidates"][0], "+target", 0),
            ("incomplete", claimed["domains"][0]["candidates"][0]
             ["records"][0], "status", "incomplete"),
        )
        for label, target, field, replacement in mutations:
            with self.subTest(change=label):
                if field == "pop":
                    removed = target.pop()
                    try:
                        with self.assertRaises(ValueError):
                            ic_m9.validate_report(claimed, frozen)
                    finally:
                        target.append(removed)
                    continue
                if field.startswith("+"):
                    field = field[1:]
                    target[field] = replacement
                    try:
                        with self.assertRaises(ValueError):
                            ic_m9.validate_report(claimed, frozen)
                    finally:
                        del target[field]
                    continue
                original = target[field]
                target[field] = (
                    original + replacement
                    if isinstance(original, int) and type(replacement) is int
                    else replacement
                )
                try:
                    with self.assertRaises(ValueError):
                        ic_m9.validate_report(claimed, frozen)
                finally:
                    target[field] = original
        ic_m9.validate_report(claimed, frozen)

    def test_verifier_does_not_call_producer(self):
        if not ic_m9.REPORT.exists():
            self.skipTest("M9 report has not been generated yet")
        frozen = ic_m9.require_frozen()
        claimed = read_json(ic_m9.REPORT)
        with (patch.object(ic_m9, "generate", side_effect=AssertionError("producer called")),
              patch.object(ic_m9, "require_frozen", return_value=frozen),
              patch.object(ic_m9, "_run", return_value=claimed)):
            self.assertEqual(ic_m9.verify(ic_m9.REPORT), claimed)


if __name__ == "__main__":
    unittest.main()
