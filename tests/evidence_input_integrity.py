"""Regressions for ambiguous JSON, graph schema aliases and reader boundaries."""
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ic_evidence_json import loads
from ic_research_artifacts import GraphSpec
from ic_primitive_port_verifier import Net
from ic_coherent_feedback import read_json
from ic_schedule_audit import ScheduleTrace
import ic_structure_library as structure_library
import ic_result_controlled_trace as trace_storage
import ic_boolean_size_family as boolean_family
import ic_size_family_audit as tree_family


class EvidenceInputIntegrity(unittest.TestCase):
    def test_boolean_endpoints_are_rejected_in_both_constructors(self):
        for endpoint in ((False, 0), (0, False), (True, 0), (1, False)):
            wires = ((("F", "A"), endpoint if endpoint[0] != 1 else (0, 0)),
                     (("F", "B"), endpoint if endpoint[0] == 1 else (1, 0)))
            with self.assertRaises(ValueError):
                GraphSpec(("e", "e"), ("A", "B"), wires)
        valid = GraphSpec(("e",), ("ROOT",), ((("F", "ROOT"), (0, 0)),)).to_dict()
        for endpoint in ([False, 0], [0, False]):
            bad = copy.deepcopy(valid)
            bad["wires"][0][1] = endpoint
            with self.assertRaises(ValueError):
                GraphSpec.from_dict(bad)

    def test_graph_array_schema_and_keys(self):
        valid = GraphSpec(("e",), ("X",), ((("F", "X"), (0, 0)),)).to_dict()
        for key, value in (("kinds", "e"), ("boundaries", "X"), ("wires", {})):
            bad = {**valid, key: value}
            with self.assertRaises(ValueError):
                GraphSpec.from_dict(bad)
        with self.assertRaises(ValueError):
            GraphSpec.from_dict({**valid, "undeclared": True})
        for key in ("kinds", "boundaries", "wires"):
            bad = dict(valid)
            bad.pop(key)
            with self.assertRaises(ValueError):
                GraphSpec.from_dict(bad)
        with self.assertRaises(ValueError):
            GraphSpec.from_dict({**valid, "wires": [{("F", "X"): None, (0, 0): None}]})
        with self.assertRaises(ValueError):
            GraphSpec.from_dict({**valid, "wires": [[['F', 'X'], bytearray((0, 0))]]})

    def test_valid_graph_roundtrips_remain_exact(self):
        specs = [GraphSpec((), (), (), 2),
                 GraphSpec(("e",), ("",), ((("F", ""), (0, 0)),)),
                 GraphSpec(("g",), ("ROOT",), ((("F", "ROOT"), (0, 0)), ((0, 1), (0, 2)))),
                 boolean_family.build_framework(3, "balanced")]
        for spec in specs:
            self.assertEqual(GraphSpec.from_dict(loads(json.dumps(spec.to_dict()))), spec)
        data = specs[2].to_dict()
        data.pop("cycles")
        self.assertEqual(GraphSpec.from_dict(data), specs[2])

    def test_runtime_binding_aliases_are_rejected_before_allocation(self):
        spec = GraphSpec(("e",), ("ROOT",), ((("F", "ROOT"), (0, 0)),))
        for port in (False, 0.0):
            net = Net()
            cell = net.cell("e")
            before = (dict(net.nodes), dict(net.adj), net.next)
            with self.assertRaises(ValueError):
                spec.instantiate(net, {"ROOT": (cell, port)})
            self.assertEqual((net.nodes, net.adj, net.next), before)

    def test_duplicate_keys_including_escaped_aliases(self):
        for text in ('{"x":1,"x":2}', '{"outer":{"x":1,"x":2}}',
                     r'{"a":1,"\u0061":2}'):
            with self.assertRaises(ValueError):
                loads(text)

    def test_nonfinite_numbers_are_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity", "1e999", "-1e999"):
            with self.assertRaises(ValueError):
                loads('{"x":' + value + '}')
        valid = '{"finite":1.25,"small":1e-30,"literal":"NaN","a":[true,null,2]}'
        self.assertEqual(loads(valid), json.loads(valid))
        self.assertEqual(loads(valid.encode()), json.loads(valid))

    def test_plain_and_gzip_report_readers_reject_duplicates(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            for suffix in (".json", ".json.gz"):
                path = Path(directory) / ("report" + suffix)
                raw = b'{"status":"failed","status":"passed"}'
                path.write_bytes(gzip.compress(raw) if suffix.endswith("gz") else raw)
                with self.assertRaises(ValueError):
                    read_json(path)
                raw = b'{"status":"passed","count":2}'
                path.write_bytes(gzip.compress(raw) if suffix.endswith("gz") else raw)
                self.assertEqual(read_json(path), {"status": "passed", "count": 2})

    def test_trace_reader_rejects_ambiguous_header(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / "trace.gz"
            with gzip.open(path, "wb") as stream:
                stream.write(b'{"format":"wrong","format":"IC-PAIR-U32LE-1","scope":"test"}\n')
            with self.assertRaises(ValueError):
                ScheduleTrace(path, {"scope": "test"}, replay=True)

    def test_new_audit_clis_reject_before_reconstruction(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / "report.json"
            path.write_text('{"format":"altered","format":"expected"}', encoding="utf-8")
            for module in (boolean_family, tree_family):
                with patch.object(sys, "argv", [module.__name__, "--verify-report", str(path)]), \
                     patch.object(module, "verify_report") as verify:
                    with self.assertRaises(ValueError):
                        module.main()
                    verify.assert_not_called()

    def test_failed_interval_reader_closes_its_stream(self):
        metadata = {"scope": "fixture", "bindings_sha256": "0" * 64}
        binding = {"metadata": metadata,
                   "trace": {"steps": 0, "sha256_of_pair_records": hashlib.sha256(b"").hexdigest()}}
        header = json.dumps({"format": "IC-PAIR-U32LE-1", **metadata}).encode() + b"\n"
        for raw in (b'{}\n', header + b"x", header + b"x" * 8):
            stream = io.BytesIO(raw)
            with patch.object(structure_library.gzip, "open", return_value=stream):
                with self.assertRaises(ValueError):
                    structure_library._IntervalTrace("unused.gz", binding)
            self.assertTrue(stream.closed)

    def test_failed_shard_header_closes_its_stream(self):
        compressed = b"fixture"
        metadata = {"format": "IC-PAIR-U32LE-1", "scope": "fixture"}
        manifest = {"format": "IC-PAIR-SHARDS-1", "metadata": metadata,
                    "trace": {"format": "IC-PAIR-U32LE-1", "steps": 1,
                              "sha256_of_pair_records": "0" * 64},
                    "shards": [{"file": "part.gz", "records": 1,
                                "sha256_of_pair_records": "0" * 64,
                                "compressed_file_sha256": hashlib.sha256(compressed).hexdigest()}]}
        for raw in (b'{}\n', b'{"format":"wrong","format":"IC-PAIR-U32LE-1"}\n'):
            reader = trace_storage._ShardReader("unused.gz", manifest)
            stream = io.BytesIO(raw)
            with patch.object(Path, "read_bytes", return_value=compressed), \
                 patch.object(trace_storage.gzip, "open", return_value=stream):
                with self.assertRaises(ValueError):
                    reader.read(8)
            self.assertTrue(stream.closed)
            self.assertIsNone(reader.stream)

    def test_existing_json_documents_remain_compatible(self):
        root = Path(__file__).resolve().parents[1]
        paths = [root / "lafont_15_rules_phi_psi_split.json",
                 root / "docs/M6_ACCEPTANCE_MATRIX.json"]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertEqual(loads(text), json.loads(text))


if __name__ == "__main__":
    unittest.main()
