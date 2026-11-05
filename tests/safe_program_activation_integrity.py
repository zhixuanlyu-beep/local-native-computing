"""M2 interface, causality and evidence-integrity checks.

The reduced end-to-end fixture runs real feedback input zero and both durable
negative probes. Its raw trace is actually replayed once; field mutations are
compared against that captured replay result. The complete frozen matrix is
replayed separately by CI. No fake program or expected-result runtime is used.
"""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ic_safe_program_activation as activation
from ic_fast_reducer import FastNet
from ic_package_codec import validate_package
from ic_program_suspension import append_spec, build_activation, suspend_feedback
from ic_research_artifacts import GraphSpec


class PairCounter:
    count = 0

    def record(self, pair):
        self.count += 1


class ActivationCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler = activation.CoherentICCompiler()
        _, cls.pairs = activation.load_discovery()
        cls.suspensions = {n: suspend_feedback(cls.compiler, n) for n in (0, 1)}

    def test_suspensions_are_dormant_principal_packages(self):
        for number, suspension in self.suspensions.items():
            for spec in (suspension.package, suspension.code):
                net = spec.instantiate()
                validate_package(net)
                self.assertFalse(net.active())
            self.assertNotIn("d", suspension.code.kinds)
            self.assertEqual(suspension.source_cells, number + 2)
            self.assertEqual(suspension.width, suspension.source_cells + 3)
        for number in (True, -1, 0.5):
            with self.assertRaises(ValueError):
                suspend_feedback(self.compiler, number)

    def test_interfaces_and_budget_rejections(self):
        gate, carrier = self.pairs[0]
        invalid = [([], []), ([0], []), ([0], [0]), ([activation.MAX_INPUT + 1], [True]),
                   ([True], [True]), ([0] * (activation.MAX_TASKS + 1), [True] * (activation.MAX_TASKS + 1))]
        for numbers, flags in invalid:
            with self.subTest(numbers=numbers), self.assertRaises(ValueError):
                activation.build_sequence(gate, carrier, numbers, flags, compiler=self.compiler)
        with self.assertRaises(ValueError):
            activation.build_sequence(gate, carrier, [0], [True], compiler=self.compiler, reader_depth=-1)
        with self.assertRaises(ValueError):
            build_activation(activation.Net(), 4, None, None, None)
        net = activation.Net()
        with self.assertRaises(ValueError):
            append_spec(carrier, net, {})
        with self.assertRaises(ValueError):
            append_spec(carrier, net, {"ROOT": ("absent", 0)})
        hole = net.boundary("SAME")
        with self.assertRaises(ValueError):
            append_spec(gate, net, {name: hole for name in gate.boundaries})
        built = activation.build_sequence(gate, carrier, [0], [True], compiler=self.compiler,
                                          suspensions=self.suspensions)
        target = activation.expected(self.compiler, [0], [True])
        for kwargs, status in (({"max_steps": 0}, "incomplete"), ({"max_cells": 0}, "resource-violation")):
            record = activation.run_case(built, target, PairCounter(), **kwargs)
            self.assertEqual(record["status"], status)
            self.assertIn("counterexample", record)
        with self.assertRaises(ValueError):
            activation.run_case(built, target, PairCounter(), max_cells=True)

    def test_one_literal_program_and_no_host_result_evaluation(self):
        literal_sources = []
        original = GraphSpec.open_root

        def observe(spec, net):
            if spec is self.compiler.code_spec:
                literal_sources.append(spec)
            return original(spec, net)

        # The builder may encode inputs and syntax, but may not evaluate an
        # answer or embed independently lowered source headers/programs.
        with patch.object(GraphSpec, "open_root", observe), \
                patch.object(self.compiler, "lower_symbol", side_effect=AssertionError("embedded program")), \
                patch.object(self.compiler, "compile", side_effect=AssertionError("host result compilation")), \
                patch.object(activation, "reference_result", side_effect=AssertionError("host answer")), \
                patch.object(activation, "source_run", side_effect=AssertionError("source evaluator")):
            built = activation.build_sequence(*self.pairs[0], [0, 1], [False, True],
                                              compiler=self.compiler, suspensions=self.suspensions)
        self.assertEqual(len(literal_sources), 1)
        self.assertEqual(len(built.stages), 2)
        self.assertEqual(len(built.program_ids), len(self.compiler.code_spec.kinds))
        for stage in built.stages:
            self.assertEqual(stage["reader"]["embedded_program_copies"], 0)
            for name in ("grant_receiver", "delivery_gate", "advance_gate"):
                self.assertIn(stage[name], built.net.nodes)
        built.net.check()


class ActivationEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ic-activation-integrity-")
        cls.trace = Path(cls.temp.name) / "fixture.ictrace.gz"
        cls.case_patch = patch.object(activation, "cases", lambda: [
            {"name": "fixture-disabled", "numbers": [0], "flags": [False]},
            {"name": "fixture-enabled", "numbers": [0], "flags": [True]},
        ])
        cls.case_patch.start()
        cls.report = activation.generate(cls.trace)
        cls.rebuilt = None
        real_suite = activation._suite

        def capture(*args, **kwargs):
            result = real_suite(*args, **kwargs)
            cls.rebuilt = result
            return result

        with patch.object(activation, "_suite", capture):
            cls.verified_count = activation.verify_report(cls.report, cls.trace)

    @classmethod
    def tearDownClass(cls):
        cls.case_patch.stop()
        cls.temp.cleanup()

    def test_real_fixture_replay_and_protocol_refutations(self):
        self.assertEqual(self.verified_count, len(self.report["cases"]))
        self.assertEqual(self.report["status"], "passed")
        for record in self.report["cases"]:
            self.assertTrue(record["initial_program_cells_consumed"])
            self.assertEqual(record["protocol_violations"], [])
            self.assertEqual(record["retained_program_cells"], len(self.report["bindings"]["program"]["kinds"]))
        bad_depth = self.report["negative_probes"]["insufficient_reader_depth"]
        self.assertEqual(bad_depth["status"], "wrong-normal-form")
        premature = self.report["negative_probes"]["premature_continuation"]
        self.assertTrue(premature["whole_graph_matches_reference"])
        self.assertEqual(premature["status"], "protocol-violation")
        self.assertTrue(premature["protocol_violations"])

    def test_report_mutations_against_the_actual_replay(self):
        mutations = {
            "missing case": lambda r: r["cases"].pop(),
            "duplicate case": lambda r: r["cases"].append(deepcopy(r["cases"][0])),
            "Boolean type": lambda r: r["cases"][0]["case"]["flags"].__setitem__(0, 0),
            "resource count": lambda r: r["cases"][0].update(peak_live_cells=0),
            "trace range": lambda r: r["cases"][0].update(trace_offset_records=1),
            "phase event": lambda r: r["cases"][0]["events"][0].update(step=1),
            "readiness provenance": lambda r: r["cases"][0]["stages"][0]["reader"].update(ready_emitters=[]),
            "retained program": lambda r: r["cases"][0]["retained_program"]["spec"].update(cycles=1),
            "extra component/cycle": lambda r: r["cases"][0]["final_graph"].update(cycles=1),
            "counterexample status": lambda r: r["negative_probes"]["premature_continuation"].update(status="passed"),
            "runtime bound": lambda r: r["bindings"]["contract"]["budget"].update(max_steps=1),
            "task input": lambda r: r["bindings"]["cases"][0].update(numbers=[1]),
            "program binding": lambda r: r["bindings"].update(program_sha256="forged"),
            "M1 binding": lambda r: r["bindings"].update(m1_report_sha256="forged"),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                changed = deepcopy(self.report)
                mutate(changed)
                with self.assertRaises(ValueError):
                    activation.compare_report(changed, self.rebuilt)
        changed = deepcopy(self.report)
        changed["bindings"]["program_sha256"] = "forged"
        with self.assertRaises(ValueError):
            activation.verify_report(changed, self.trace)


class RawTraceIntegrity(unittest.TestCase):
    def test_header_pair_order_truncation_and_trailing_records(self):
        metadata = {"scope": "tiny actual primitive trace", "schedule": "FIFO"}
        initial = FastNet()
        for _ in range(2):
            a, b = initial.cell("e"), initial.cell("e")
            initial.link((a, 0), (b, 0))
        spec = GraphSpec.from_net(initial)
        with tempfile.TemporaryDirectory(prefix="ic-activation-trace-") as directory:
            path = Path(directory) / "tiny.gz"
            writer = activation.NativeTrace(path, metadata)
            running = spec.instantiate(FastNet())
            while pair := running.next_active():
                writer.record(pair)
                running.reduce(*pair)
            writer.close()
            original = gzip.decompress(path.read_bytes())
            header, records = original.split(b"\n", 1)

            def replay():
                reader = activation.NativeTrace(path, metadata, replay=True)
                try:
                    running = spec.instantiate(FastNet())
                    while pair := running.next_active():
                        reader.record(pair)
                        running.reduce(*pair)
                except BaseException:
                    reader.stream.close()
                    raise
                reader.close()

            replay()
            changed_header = json.loads(header)
            changed_header["scope"] = "forged"
            variants = [original[:-1], original[:-8], original + b"\0" * 8,
                        header + b"\n" + records[8:] + records[:8],
                        json.dumps(changed_header).encode() + b"\n" + records]
            for variant in variants:
                with self.subTest(bytes=len(variant)):
                    path.write_bytes(gzip.compress(variant, mtime=0))
                    with self.assertRaises(ValueError):
                        replay()


if __name__ == "__main__":
    unittest.main(verbosity=2)
