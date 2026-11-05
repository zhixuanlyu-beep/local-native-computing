"""Integrity tests for the M5 evidence-indexed structure library."""

from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(REPO))

import ic_structure_library as library


class StructureLibraryIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = library.build_catalog()

    def test_catalog_imports_all_verified_assignments(self):
        self.assertEqual(len(self.catalog.entries), 170)
        self.assertEqual(sum(len(entry.cases) for entry in self.catalog.entries), 352)
        self.assertEqual(len({entry.id for entry in self.catalog.entries}), 170)
        self.assertTrue(all(len(entry.all_schedule_checks) > 0 for entry in self.catalog.entries))
        self.assertTrue(all(entry.evidence_scope == library.EVIDENCE_TIERS
                            for entry in self.catalog.entries))

    def test_query_is_exact_and_evidence_ordered(self):
        a_to_b = self.catalog.query(("A",), ("B",), ("IN", "OUT"))
        self.assertTrue(a_to_b)
        self.assertTrue(all(entry.input_reprs == ("A",) and entry.output_reprs == ("B",)
                            for entry in a_to_b))
        self.assertFalse(self.catalog.query(("A",), ("B",), ("LEFT", "RIGHT", "OUT")))
        self.assertTrue(self.catalog.query(("B",), ("A",), ("IN", "OUT"),
                                           minimum_evidence="all-schedules-finite"))
        self.assertTrue(self.catalog.query(("A",), ("A",), ("IN", "OUT"),
                                           task_name="unary-A-A-2"))
        self.assertFalse(self.catalog.query(("A",), ("A",), ("IN", "OUT"),
                                           task_name="unary-B-A-2"))
        with self.assertRaises(ValueError):
            self.catalog.query(("A",), ("A",), ("IN", "OUT"), minimum_evidence="raw-copyable")

    def test_round_trip_and_get_entry(self):
        data = self.catalog.to_dict()
        rebuilt = library.Catalog.from_dict(deepcopy(data))
        self.assertEqual(library.spec_digest(data), library.spec_digest(rebuilt.to_dict()))
        entry = rebuilt.entries[0]
        self.assertIs(rebuilt.get_entry(entry.id), entry)
        with self.assertRaises(KeyError):
            rebuilt.get_entry("not-an-entry")

    def test_owned_json_is_frozen_and_to_dict_is_detached(self):
        entry = self.catalog.entries[0]
        source_case = entry.cases[0]
        proof = entry.all_schedule_checks[0]
        nested_owned = (
            lambda: entry.graph["wires"][0].__setitem__(0, ["tampered"]),
            lambda: source_case.resources["components"]["network"].__setitem__("final_cells", 999),
            lambda: self.catalog.source_binding["frozen_reports"].__setitem__("native_ic_research.json.gz", "0" * 64),
        )
        for mutate in nested_owned:
            with self.subTest(mutate=mutate):
                with self.assertRaises((TypeError, AttributeError)):
                    mutate()
        owned_mutations = (
            lambda: entry.graph.__setitem__("cycles", 1),
            lambda: entry.task_descriptor.__setitem__("name", "tampered"),
            lambda: source_case.initial_graph.__setitem__("cycles", 1),
            lambda: source_case.resources.__setitem__("final_cells", 999),
            lambda: proof.execution.__setitem__("states", 999),
            lambda: self.catalog.source_binding.__setitem__("format", "tampered"),
            lambda: self.catalog.source_binding["trace"].__setitem__("steps", 0),
        )
        for mutate in owned_mutations:
            with self.subTest(mutate=mutate):
                with self.assertRaises((TypeError, AttributeError)):
                    mutate()

        before = library.spec_digest(self.catalog.to_dict())
        exported = self.catalog.to_dict()
        exported["source_binding"]["metadata"]["scope"] = "tampered"
        exported["entries"][0]["graph"]["cycles"] += 1
        exported["entries"][0]["task_descriptor"]["name"] = "tampered"
        exported["entries"][0]["cases"][0]["initial_graph"]["cycles"] += 1
        exported["entries"][0]["cases"][0]["resources"]["final_cells"] = 999
        exported["entries"][0]["all_schedule_checks"][0]["execution"]["states"] = 999
        self.assertEqual(library.spec_digest(self.catalog.to_dict()), before)
        library.verify_catalog(self.catalog)

    def test_strict_malformed_entry_schemas(self):
        base = self.catalog.entries[0].to_dict()
        mutations = []
        for key in ("id", "task_name", "task_descriptor", "input_reprs", "output_reprs",
                    "interface", "graph", "graph_sha256", "candidate_id",
                    "source_report_sha256", "cases", "all_schedule_checks", "evidence_scope"):
            bad = deepcopy(base)
            del bad[key]
            mutations.append(bad)
        bad = deepcopy(base)
        bad["extra"] = True
        mutations.append(bad)
        bad = deepcopy(base)
        bad["graph"]["cycles"] += 1
        mutations.append(bad)
        bad = deepcopy(base)
        bad["evidence_scope"] = ["fifo"]
        mutations.append(bad)
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertRaises(ValueError, library.LibraryEntry.from_dict, mutation)

        bad = deepcopy(base)
        bad["cases"][0]["trace"]["pair_digest"] = "0" * 64
        stale = library.Catalog.from_dict({**self.catalog.to_dict(), "entries": [bad]})
        with self.assertRaises(ValueError):
            library.verify_catalog(stale)

    def test_stale_fingerprints_and_report_sources_are_rejected(self):
        base = self.catalog.entries[0].to_dict()
        bad = deepcopy(base)
        bad["graph_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            library.LibraryEntry.from_dict(bad)
        bad = deepcopy(base)
        bad["source_report_sha256"] = "1" * 64
        with self.assertRaises(ValueError):
            library.Catalog.from_dict({**self.catalog.to_dict(), "entries": [bad]})
        bad = deepcopy(base)
        bad["all_schedule_checks"][0]["status"] = "incomplete"
        with self.assertRaises(ValueError):
            library.LibraryEntry.from_dict(bad)

        bad = deepcopy(base)
        bad["cases"].pop()
        with self.assertRaises(ValueError):
            library.LibraryEntry.from_dict(bad)

        bad = deepcopy(base)
        bad["source_report_sha256"] = "1" * 64
        with self.assertRaises(ValueError):
            library.Catalog.from_dict({**self.catalog.to_dict(),
                                       "entries": [bad]})

    def test_catalog_reconstruction_and_full_fifo_replay(self):
        summary = library.verify_catalog(self.catalog)
        self.assertEqual(summary["entries"], 170)
        self.assertEqual(summary["verified_assignments"], 352)
        self.assertEqual(summary["replayed_observations"], 352)
        self.assertEqual(summary["primitive_interactions"], 1204)
        self.assertEqual(summary["source_report_sha256"], library.M4_REPORT_SHA256)

    def test_report_digest_and_schema_mutation_are_rejected(self):
        raw = (REPO / library.REPORT_PATH.relative_to(REPO)).read_bytes()
        self.assertEqual(library.M4_REPORT_SHA256, __import__("hashlib").sha256(raw).hexdigest())
        report = json.loads(gzip.decompress(raw))
        report["status"] = "not-accepted"
        encoded = json.dumps(report, sort_keys=True).encode()
        with tempfile.TemporaryDirectory() as directory:
            mutated = Path(directory) / "mutated.json.gz"
            mutated.write_bytes(gzip.compress(encoded, mtime=0))
            with self.assertRaises(ValueError):
                library.build_catalog(mutated)

    def test_trace_header_summary_and_interval_digest_mutation(self):
        catalog = self.catalog
        payload = gzip.decompress(library.TRACE_PATH.read_bytes())
        newline = payload.index(b"\n")
        header, pairs = payload[:newline + 1], payload[newline + 1:]
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.ictrace.gz"
            trace.write_bytes(library.TRACE_PATH.read_bytes())
            library.verify_catalog(catalog, trace_path=trace)

            # Retain the exact pair payload but mutate the header binding.
            mutated_header = json.loads(header)
            mutated_header["scope"] = "tampered"
            trace.write_bytes(gzip.compress(
                json.dumps(mutated_header, sort_keys=True).encode() + b"\n" + pairs))
            with self.assertRaises(ValueError):
                library.verify_catalog(catalog, trace_path=trace)

            # Mutate one byte in a referenced interval's last pair record.
            mutated_pairs = bytearray(pairs)
            entry = catalog.entries[0]
            source_case = entry.cases[-1]
            offset = 8 * (source_case.trace.start_record + source_case.trace.length_records - 1)
            self.assertLess(offset, len(mutated_pairs))
            mutated_pairs[offset] ^= 1
            trace.write_bytes(gzip.compress(header + bytes(mutated_pairs)))
            with self.assertRaises(ValueError):
                library.verify_catalog(catalog, trace_path=trace)


if __name__ == "__main__":
    unittest.main()
