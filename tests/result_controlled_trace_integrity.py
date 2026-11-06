"""Exact pair-stream shards reject truncation, append and metadata changes."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ic_native_control_packets import protocol_evidence
from ic_result_controlled_trace import M6Trace, pack_trace


class TraceStorageIntegrity(unittest.TestCase):
    def test_lossless_shards_replay_all_actual_control_interactions(self):
        with tempfile.TemporaryDirectory() as directory:
            path, metadata = Path(directory) / "trace.gz", {"fixture": "real control shards"}
            trace = M6Trace(path, metadata)
            expected = protocol_evidence(trace)
            summary = trace.close()
            sharded = pack_trace(path, summary, shard_bytes=16)
            self.assertIn("storage_manifest_sha256", sharded)
            replay = M6Trace(path, metadata, replay=True)
            self.assertEqual(expected, protocol_evidence(replay))
            self.assertEqual(sharded, replay.close())
            manifest = json.loads(gzip.decompress(path.read_bytes()))
            self.assertGreater(len(manifest["shards"]), 1)
            self.assertTrue(all(p["records"] <= 2 for p in manifest["shards"]))

    def test_changed_shards_and_manifest_cannot_hide_extra_or_missing_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path, metadata = Path(directory) / "trace.gz", {"fixture": "shard faults"}
            trace = M6Trace(path, metadata)
            protocol_evidence(trace)
            summary = trace.close()
            pack_trace(path, summary, shard_bytes=16)
            original = path.read_bytes()
            manifest = json.loads(gzip.decompress(original))
            shard_path = path.parent / manifest["shards"][0]["file"]
            saved = shard_path.read_bytes()
            raw = gzip.decompress(saved)
            for invalid in (raw[:-8], raw + b"\0" * 8):
                shard_path.write_bytes(gzip.compress(invalid))
                replay = M6Trace(path, metadata, replay=True)
                try:
                    with self.assertRaises(ValueError):
                        protocol_evidence(replay)
                finally:
                    replay.abort()
            shard_path.write_bytes(saved)
            for name in ("../outside.gz", "C:outside.gz"):
                changed = deepcopy(manifest)
                changed["shards"][0]["file"] = name
                path.write_bytes(gzip.compress((json.dumps(changed) + "\n").encode()))
                with self.assertRaises(ValueError):
                    M6Trace(path, metadata, replay=True)
            path.write_bytes(gzip.compress(json.dumps(manifest).encode() + b"\nextra"))
            with self.assertRaises(ValueError):
                M6Trace(path, metadata, replay=True)


if __name__ == "__main__":
    unittest.main()
