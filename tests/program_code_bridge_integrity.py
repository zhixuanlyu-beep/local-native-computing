"""Adversarial bridge checks; real-Gamma evidence is replayed separately by CI.

The report-tampering fixture substitutes a small delta package for Gamma.
It exercises the complete report/replay plumbing without repeatedly running
the large experiment. Small exhaustive checks are cached only after actually
exploring their exact initial/reference graphs once in this process.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ic_program_code_bridge as bridge
from ic_coherent_feedback import read_json, spec_digest
from ic_coherent_output_decoder import port_graph_isomorphic
from ic_package_codec import build_decoding
from ic_research_artifacts import GraphSpec


class PairLog:
    def __init__(self):
        self.pairs = []
        self.count = 0

    def record(self, pair):
        self.pairs.append(pair)
        self.count += 1


class BridgeSemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.pairs = bridge.load_discovery()
        cls.data = bridge.payloads()

    def test_preconditions(self):
        gate, carrier = self.pairs[0]
        code = self.data["delta_ee"]["code"]
        invalid = [
            (gate, carrier, 1, code, "decode"),
            (gate, carrier, "true", code, "decode"),
            (code, carrier, True, code, "decode"),
            (gate, carrier, True, self.data["delta_ee"]["object"], "decode"),
            (gate, carrier, True, code, "unknown"),
            (gate, carrier, True, GraphSpec(code.kinds, code.boundaries, code.wires, 1), "decode"),
        ]
        disconnected = code.instantiate()
        for _ in range(2):
            cell = disconnected.cell("g")
            # Two internally wired gamma cells form a disconnected component.
            if _ == 0:
                first = cell
            else:
                disconnected.link((first, 0), (cell, 1))
                disconnected.link((first, 1), (cell, 0))
                disconnected.link((first, 2), (cell, 2))
        invalid.append((gate, carrier, True, GraphSpec.from_net(disconnected), "decode"))
        for args in invalid:
            with self.subTest(args=args[-1]), self.assertRaises((ValueError, TypeError)):
                bridge.build_bridge(*args)

    def test_cutoffs_are_not_success(self):
        gate, carrier = self.pairs[0]
        entry = self.data["delta_ee"]
        initial, _ = bridge.build_bridge(gate, carrier, True, entry["code"], "decode")
        target = bridge.expected(True, entry["object"], "decode")
        for kwargs, status in (({"max_steps": 0}, "incomplete"),
                               ({"max_cells": 0}, "resource-violation"),
                               ({"retained_cells": 20_000}, "resource-violation")):
            record, _ = bridge.run_case(initial, target, PairLog(), **kwargs)
            self.assertEqual(record["status"], status)
            self.assertIn("counterexample", record)
            GraphSpec.from_dict(record["counterexample"]["initial"])
        for kwargs in ({"max_steps": -1}, {"max_cells": True}, {"retained_cells": 0.5}):
            with self.assertRaises(ValueError):
                bridge.run_case(initial, target, PairLog(), **kwargs)
        for kwargs, status in (({"max_states": 1}, "incomplete"),
                               ({"max_transitions": 0}, "incomplete"),
                               ({"max_cells": 0}, "resource-violation")):
            result = bridge.check_schedules(initial, target, **kwargs)
            self.assertEqual(result["status"], status)
            self.assertFalse(result["execution"]["complete"])

    def test_whole_graph_observation(self):
        target = bridge.expected(True, self.data["delta_ee"]["object"], "decode")
        extra = deepcopy(target)
        a, b = extra.cell("g"), extra.cell("g")
        extra.link((a, 0), (b, 1))
        extra.link((a, 1), (b, 0))
        extra.link((a, 2), (b, 2))
        extra.check()
        self.assertFalse(port_graph_isomorphic(extra, target))
        extra = deepcopy(target)
        extra.cycles += 1
        self.assertFalse(port_graph_isomorphic(extra, target))
        changed = GraphSpec.from_net(target).to_dict()
        changed["boundaries"] = ["OTHER"]
        for wire in changed["wires"]:
            for endpoint in wire:
                if endpoint[0] == "F":
                    endpoint[1] = "OTHER"
        self.assertFalse(port_graph_isomorphic(GraphSpec.from_dict(changed).instantiate(), target))

    def test_saved_refutations_replay_with_original_reducer(self):
        report = read_json(Path(bridge.__file__).parent / "results/program_code_bridge.json.gz")
        encoded = gzip.decompress((Path(bridge.__file__).parent / "results/program_code_bridge.ictrace.gz").read_bytes())
        _, records = encoded.split(b"\n", 1)
        for name, case in report["counterexamples"].items():
            with self.subTest(probe=name):
                if name == "decoder_epsilon":
                    initial = build_decoding(bridge._object("e"))
                    target = bridge.expected(False, self.data["epsilon"]["object"], "decode")
                    self.assertEqual(case["status"], "passed")
                else:
                    witness = case["counterexample"]
                    initial = GraphSpec.from_dict(witness["initial"]).instantiate()
                    target = GraphSpec.from_dict(witness["expected"]).instantiate()
                    self.assertEqual(case["status"], "wrong-normal-form")
                # Net, rather than FastNet, provides this independent replay.
                running = GraphSpec.from_net(initial).instantiate()
                peak = len(running.nodes)
                start = case["trace_offset_records"] * 8
                stop = start + case["primitive_interactions"] * 8
                for a, b in struct.iter_unpack("<II", records[start:stop]):
                    running.reduce("c" + str(a), "c" + str(b))
                    peak = max(peak, len(running.nodes))
                self.assertFalse(running.active())
                self.assertEqual(peak, case["peak_live_cells"])
                self.assertEqual(GraphSpec.from_net(running).to_dict(), case["final_graph"])
                self.assertEqual(port_graph_isomorphic(running, target), name == "decoder_epsilon")
                if name == "wrong_gate_wiring":
                    self.assertEqual(len(running.nodes), len(target.nodes))
                if name == "epsilon_does_not_clear_INIT_extension":
                    self.assertGreater(len(running.nodes), len(target.nodes))


class EvidenceIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ic-bridge-integrity-")
        cls.trace = Path(cls.temp.name) / "fixture.ictrace.gz"
        cls.data = bridge.payloads()
        cls.data["Gamma"] = cls.data["delta_ee"]
        real_check = bridge.check_schedules
        cache = {}

        def cached_check(initial, target, **kwargs):
            key = (spec_digest(GraphSpec.from_net(initial).to_dict()),
                   spec_digest(GraphSpec.from_net(target).to_dict()), tuple(sorted(kwargs.items())))
            if key not in cache:
                cache[key] = real_check(initial, target, **kwargs)
            return deepcopy(cache[key])

        cls.patches = [patch.object(bridge, "payloads", lambda compiler=None: cls.data),
                       patch.object(bridge, "check_schedules", cached_check)]
        for context in cls.patches:
            context.start()
        cls.report = bridge.generate(cls.trace)
        cls.original_trace = cls.trace.read_bytes()

    @classmethod
    def tearDownClass(cls):
        for context in reversed(cls.patches):
            context.stop()
        cls.temp.cleanup()

    def test_valid_fixture(self):
        self.trace.write_bytes(self.original_trace)
        self.assertEqual(self.report["status"], "passed")
        self.assertEqual(bridge.verify_report(self.report, self.trace),
                         len(self.report["bridge_cases"]) + len(self.report["reuse_cases"]))

    def test_report_tampering(self):
        mutations = {
            "initial resource": lambda r: r["bridge_cases"][0].update(initial_cells=0),
            "trace interval": lambda r: r["bridge_cases"][0].update(trace_offset_records=1),
            "Boolean type": lambda r: r["bridge_cases"][0].update(bit=0),
            "missing bridge": lambda r: r["bridge_cases"].pop(),
            "duplicate reuse": lambda r: r["reuse_cases"].append(deepcopy(r["reuse_cases"][0])),
            "retained cost": lambda r: r["reuse_cases"][0].update(retained_cells=0),
            "artifact provenance": lambda r: r["artifacts"][0]["artifact"]["provenance"].update(first_input=True),
            "artifact fingerprint": lambda r: r["artifacts"][0]["artifact"].update(source_fingerprint="forged"),
            "artifact graph": lambda r: r["artifacts"][0]["artifact"]["spec"].update(cycles=1),
            "all schedules": lambda r: r["all_schedule_cases"][0]["execution"].update(states=0),
            "extra cyclic wire": lambda r: r["bridge_cases"][0]["final_graph"].update(cycles=1),
            "negative probe": lambda r: r["counterexamples"]["wrong_gate_wiring"].update(status="passed"),
            "contract": lambda r: r["bindings"]["contract"]["fifo_budget"].update(max_steps=1_000_000),
            "payload binding": lambda r: r["bindings"]["payloads"]["Gamma"]["code"].update(sha256="forged"),
            "consumer binding": lambda r: r["bindings"]["consumers"]["decode"].update(sha256="forged"),
        }
        self.trace.write_bytes(self.original_trace)
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                changed = deepcopy(self.report)
                mutate(changed)
                with self.assertRaises(ValueError):
                    bridge.verify_report(changed, self.trace)

    def test_trace_and_frozen_source_tampering(self):
        raw = gzip.decompress(self.original_trace)
        header, records = raw.split(b"\n", 1)
        changed_header = json.loads(header)
        changed_header["bindings_sha256"] = "forged"
        damaged = bytearray(records)
        damaged[len(damaged) // 2] ^= 1
        variants = [raw[:-8], raw[:-1], raw + b"\0" * 8,
                    json.dumps(changed_header).encode() + b"\n" + records,
                    header + b"\n" + damaged]
        try:
            for variant in variants:
                with self.subTest(size=len(variant)):
                    self.trace.write_bytes(gzip.compress(variant, mtime=0))
                    with self.assertRaises(ValueError):
                        bridge.verify_report(self.report, self.trace)
        finally:
            self.trace.write_bytes(self.original_trace)
        source = Path(self.temp.name) / "discovery.json.gz"
        source.write_bytes(bridge.DISCOVERY_PATH.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            bridge.load_discovery(source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
