"""Exact M5 archive retrieval with distinct component and program interfaces."""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from ic_coherent_feedback import read_json, spec_digest
from ic_coherent_output_decoder import port_graph_isomorphic
from ic_research_artifacts import GraphSpec
from ic_program_code_bridge import _validate_data
from source_ic_coherent_compiler import CoherentICCompiler


ROOT = Path(__file__).parent
FROZEN = {
    "structure_library.json.gz": "0c5ed5643cfb73d0d17ee688a80b33296c3818394a59a561ae80b62082b71255",
    "structure_reuse.json.gz": "8c7d797a5ec3109cf2d5d4af724963367fa9914f0ad6613f8932450bab953f1b",
    "program_code_bridge.json.gz": "624976b188e7659a52a32e92fcd1c46db95a18f639c41909ddaf17eaac29ecf7",
}


def _frozen(path, role):
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != FROZEN[role]:
        raise ValueError("frozen " + role + " evidence changed")
    return read_json(path)


@dataclass(frozen=True)
class ControlLibrary:
    gate: GraphSpec
    copy_packet: GraphSpec
    workload: dict
    provenance: dict
    program: GraphSpec

    def program_code(self, compiler):
        if not isinstance(compiler, CoherentICCompiler):
            raise TypeError("program supply requires the coherent compiler")
        if compiler.code_spec != self.program:
            raise ValueError("program supply differs from the real compiler code_spec; Gamma data is not code")
        _validate_data(compiler.code_spec)
        return compiler.code_spec

    def require_program_code(self, candidate):
        if not isinstance(candidate, GraphSpec) or candidate != self.program:
            raise ValueError("Gamma data/component storage cannot satisfy the !Gamma program-code interface")
        return candidate


def load_control_library(path, report_path=None):
    manifest = _frozen(path, "structure_library.json.gz")
    report_path = report_path or ROOT / "results/structure_reuse.json.gz"
    report = _frozen(report_path, "structure_reuse.json.gz")
    if report["status"] != "passed" or report["library_sha256"] != spec_digest(manifest):
        raise ValueError("M5 archive/report binding mismatch")
    if report["metadata"]["bindings_sha256"] != spec_digest(report["bindings"]):
        raise ValueError("M5 report binding digest mismatch")
    candidates = [w for w in report["bindings"]["workloads"] if w["name"] == "copy_A"]
    artifacts = [a for a in manifest["native_artifacts"] if a["workload"] == "copy_A"]
    if len(candidates) != 1 or len(artifacts) != 1:
        raise ValueError("copy_A retrieval must be unique")
    workload, artifact = candidates[0], artifacts[0]
    if (artifact["source_id"] != workload["source_id"] or artifact["production_evidence"] != "fifo"
            or artifact["storage_representation"] != "native-code-grant-packet-v1"
            or artifact["storage_interface"] != ["ROOT"]
            or artifact["activation_interface"] != ["IN", "OUT1", "OUT2"]
            or artifact["input_reprs"] != ["A"] or artifact["output_reprs"] != ["A", "A"]):
        raise ValueError("copy_A representation/interface/evidence mismatch")
    packet = GraphSpec.from_dict(artifact["artifact"]["spec"])
    original = GraphSpec.from_dict(workload["packet"])
    if (spec_digest(packet.to_dict()) != artifact["produced_packet_sha256"]
            or spec_digest(original.to_dict()) != artifact["original_packet_sha256"]
            or not port_graph_isomorphic(packet.instantiate(), original.instantiate())):
        raise ValueError("native copy_A artifact differs from original packet")
    _validate_data(packet)
    bridge = _frozen(ROOT / "results/program_code_bridge.json.gz", "program_code_bridge.json.gz")
    program = GraphSpec.from_dict(bridge["bindings"]["payloads"]["Gamma"]["code"]["graph"])
    gate = GraphSpec.from_dict(report["bindings"]["gate"])
    if gate.kinds != ("g",) or set(gate.boundaries) != {"CTRL", "DATA", "OUT"}:
        raise ValueError("M5 gate does not match the control protocol")
    capsule = {key: workload[key] for key in ("width", "interface", "code", "package", "component")}
    capsule["ready_slot"] = 0
    provenance = {"library_file_sha256": FROZEN["structure_library.json.gz"],
                  "m5_report_file_sha256": FROZEN["structure_reuse.json.gz"],
                  "manifest_sha256": spec_digest(manifest), "source_id": artifact["source_id"],
                  "artifact_id": artifact["id"],
                  **{key: artifact[key] for key in ("storage_representation", "storage_interface",
                     "activation_interface", "production_evidence", "source_component_evidence",
                     "trace_start", "trace_steps", "original_packet_sha256", "produced_packet_sha256")},
                  "program_code_sha256": spec_digest(program.to_dict()),
                  "Gamma_data_scope": "M5 Gamma_erase is data erasure; not !Gamma program code"}
    return ControlLibrary(gate, packet, {**workload, "capsule": capsule}, provenance, program)
