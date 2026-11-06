"""Reduced M6 fixtures for exact M5 library retrieval and program identity."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ic_result_controlled_library as library
from ic_coherent_feedback import read_json, spec_digest
from ic_research_artifacts import GraphSpec
from source_ic_coherent_compiler import CoherentICCompiler


class ResultControlledLibraryIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library_path = library.ROOT / "results/structure_library.json.gz"
        cls.report_path = library.ROOT / "results/structure_reuse.json.gz"
        cls.control = library.load_control_library(cls.library_path, cls.report_path)
        cls.manifest = read_json(cls.library_path)
        cls.report = read_json(cls.report_path)
        cls.workload = next(row for row in cls.report["bindings"]["workloads"]
                            if row["name"] == "copy_A")
        cls.artifact = next(row for row in cls.manifest["native_artifacts"]
                            if row["workload"] == "copy_A")

    def write_pair(self, directory, manifest=None, report=None, rebind_metadata=True):
        """Write detached archives and patch only the file/digest binding checks."""
        manifest = copy.deepcopy(self.manifest if manifest is None else manifest)
        report = copy.deepcopy(self.report if report is None else report)
        report["library_sha256"] = spec_digest(manifest)
        if rebind_metadata:
            report["metadata"]["bindings_sha256"] = spec_digest(report["bindings"])
        library_path = Path(directory) / "structure_library.json.gz"
        report_path = Path(directory) / "structure_reuse.json.gz"
        for path, value in ((library_path, manifest), (report_path, report)):
            raw = json.dumps(value, sort_keys=True, indent=2).encode("utf-8") + b"\n"
            path.write_bytes(gzip.compress(raw, mtime=0))
        frozen = dict(library.FROZEN)
        frozen["structure_library.json.gz"] = hashlib.sha256(library_path.read_bytes()).hexdigest()
        frozen["structure_reuse.json.gz"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
        return library_path, report_path, frozen

    def test_loads_exact_copy_a_archive_and_path_independent_provenance(self):
        control = self.control
        self.assertEqual(control.gate, GraphSpec.from_dict(self.report["bindings"]["gate"]))
        self.assertEqual(control.copy_packet,
                         GraphSpec.from_dict(self.artifact["artifact"]["spec"]))
        self.assertEqual(control.workload["capsule"]["width"], self.workload["width"])
        self.assertEqual(tuple(control.workload["capsule"]["interface"]),
                         tuple(self.workload["interface"]))
        for key in ("code", "package", "component"):
            self.assertEqual(control.workload["capsule"][key], self.workload[key])
        self.assertEqual(control.provenance["source_id"], self.artifact["source_id"])
        self.assertEqual(control.provenance["artifact_id"], self.artifact["id"])
        self.assertEqual(control.provenance["produced_packet_sha256"],
                         self.artifact["produced_packet_sha256"])
        self.assertEqual(control.provenance["production_evidence"], "fifo")
        self.assertEqual(control.provenance["source_component_evidence"],
                         "all-schedules-finite")
        self.assertNotIn("library_path", control.provenance)
        self.assertNotIn("report_path", control.provenance)

    def test_program_code_is_compiler_code_not_gamma_data(self):
        compiler = CoherentICCompiler()
        self.assertEqual(self.control.program, compiler.code_spec)
        self.assertEqual(self.control.program_code(compiler), compiler.code_spec)
        bridge = read_json(library.ROOT / "results/program_code_bridge.json.gz")
        gamma_data = GraphSpec.from_dict(bridge["bindings"]["payloads"]["Gamma"]["object"]["graph"])
        with self.assertRaisesRegex(ValueError, "Gamma data"):
            self.control.require_program_code(gamma_data)
        with self.assertRaisesRegex(ValueError, "Gamma data"):
            self.control.require_program_code(self.control.copy_packet)
        gamma_workload = next(row for row in self.report["bindings"]["workloads"]
                              if row["name"] == "Gamma_erase")
        with self.assertRaisesRegex(ValueError, "Gamma data"):
            self.control.require_program_code(GraphSpec.from_dict(gamma_workload["code"]))

    def test_representation_interface_and_evidence_tampering_is_rejected(self):
        fields = ("storage_representation", "storage_interface", "activation_interface",
                  "input_reprs", "output_reprs", "production_evidence", "source_id")
        values = ("literal-capsule-v1", ["OUT"], ["IN", "OUT"], ["B"], ["B"],
                  "all-schedules-finite", "wrong-source")
        for field, value in zip(fields, values):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                manifest = copy.deepcopy(self.manifest)
                row = next(row for row in manifest["native_artifacts"]
                           if row["workload"] == "copy_A")
                row[field] = value
                library_path, report_path, frozen = self.write_pair(directory, manifest=manifest)
                with patch.object(library, "FROZEN", frozen):
                    with self.assertRaises(ValueError):
                        library.load_control_library(library_path, report_path)

    def test_packet_graph_and_archive_binding_tampering_is_rejected(self):
        mutations = (
            lambda row: row["artifact"]["spec"].__setitem__("kinds", ["e"] + row["artifact"]["spec"]["kinds"][1:]),
            lambda row: row.__setitem__("produced_packet_sha256", "0" * 64),
            lambda row: row.__setitem__("original_packet_sha256", "1" * 64),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index), tempfile.TemporaryDirectory() as directory:
                manifest = copy.deepcopy(self.manifest)
                row = next(row for row in manifest["native_artifacts"]
                           if row["workload"] == "copy_A")
                mutate(row)
                library_path, report_path, frozen = self.write_pair(directory, manifest=manifest)
                with patch.object(library, "FROZEN", frozen):
                    with self.assertRaises(ValueError):
                        library.load_control_library(library_path, report_path)

        with tempfile.TemporaryDirectory() as directory:
            library_path, report_path, frozen = self.write_pair(directory)
            raw = bytearray(library_path.read_bytes())
            raw[-1] ^= 1
            library_path.write_bytes(raw)
            with patch.object(library, "FROZEN", frozen):
                with self.assertRaises(ValueError):
                    library.load_control_library(library_path, report_path)

    def test_report_status_and_binding_digest_must_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            report = copy.deepcopy(self.report)
            report["status"] = "not-accepted"
            library_path, report_path, frozen = self.write_pair(directory, report=report)
            with patch.object(library, "FROZEN", frozen):
                with self.assertRaises(ValueError):
                    library.load_control_library(library_path, report_path)

            report = copy.deepcopy(self.report)
            report["metadata"]["bindings_sha256"] = "2" * 64
            library_path, report_path, frozen = self.write_pair(directory, report=report, rebind_metadata=False)
            with patch.object(library, "FROZEN", frozen):
                with self.assertRaises(ValueError):
                    library.load_control_library(library_path, report_path)


if __name__ == "__main__":
    unittest.main()
