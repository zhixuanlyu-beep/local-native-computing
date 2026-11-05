"""E_code: frozen discovered gates controlling literal compiler program code.

Construction, observation and archive/import are offline research tools.
Execution and trace replay use only the original six primitive IC rules.
This is a program-code bridge, not a complete-program activation protocol.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

from ic_bounded_execution import explore
from ic_bounded_synthesis import false_carrier, spec_id
from ic_coherent_feedback import PrimitiveTrace, read_json, spec_digest, write_json
from ic_coherent_output_decoder import port_graph_isomorphic
from ic_fast_reducer import FastNet
from ic_package_codec import build_decoder, build_decoding, encode_package, validate_package
from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec, RetainedArtifact, capture_root
from lafont_ic_macro_builder import macro_connect
from source_ic_coherent_compiler import CoherentICCompiler


DISCOVERY_PATH = Path(__file__).parent / "results/native_ic_research.json.gz"
DISCOVERY_SHA256 = "6a13e33619aabd340e55ac57448e1e6efe3633767654ed2cd407b60941a7f71d"
CONSUMERS = ("retain_code", "copy_code", "decode", "copy_decode")
FIFO_BUDGET = {"max_steps": 100_000, "max_cells": 20_000}
EXPLORATION_BUDGET = {"max_states": 4096, "max_transitions": 32768, "max_cells": 128}
CONTRACT = {
    "environment": "E_code-v1; extension of, not a replacement for, discovery environment",
    "inputs": "independent Boolean and delta-free principal package code",
    "outputs": {"retain_code": "code or epsilon at OUT",
                "copy_code": "two codes or two epsilons at OUT1, OUT2",
                "decode": "original object or epsilon at OUT",
                "copy_decode": "two original objects or two epsilons at OUT1, OUT2"},
    "observation": "complete labeled-port graph, all components and cyclic wires",
    "runtime": "primitive IC interactions only; FIFO for large networks",
    "fifo_budget": FIFO_BUDGET,
    "small_all_schedule_budget": EXPLORATION_BUDGET,
    "archive": "offline reconstruction; retained producer plus fresh instance charged together",
    "boundary": "D(epsilon)=epsilon does not imply erasure of a source-symbol extension",
    "negative_probes": ["wrong control token", "CTRL/DATA swap",
                        "epsilon at INIT code input does not erase its extension"],
}


def load_discovery(path=DISCOVERY_PATH):
    """Import every verified pair from the unchanged, frozen discovery file."""
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != DISCOVERY_SHA256:
        raise ValueError("discovery report differs from the frozen evidence")
    report = json.loads(gzip.decompress(raw))
    synthesis = report["synthesis"]
    gates = {r["id"]: GraphSpec.from_dict(r["graph"]) for r in synthesis["gates"]}
    carriers = {r["id"]: GraphSpec.from_dict(r["graph"]) for r in synthesis["materials"]}
    for key, graph in list(gates.items()) + list(carriers.items()):
        if spec_id(graph) != key:
            raise ValueError("discovery graph fingerprint mismatch")
    survivors = synthesis["survivors"]
    keys = [(r["gate"], r["material"]) for r in survivors]
    verified = {(r["gate"], r["material"]) for r in synthesis["candidates"]
                if r["status"] == "verified"}
    if len(set(keys)) != len(keys) or set(keys) != verified or not keys:
        raise ValueError("discovery survivor accounting mismatch")
    pairs = [(gates[g], carriers[c]) for g, c in keys]
    binding = {"frozen_file_sha256": DISCOVERY_SHA256,
               "report_sha256": spec_digest(report),
               "verified_pairs": [{"gate": g.to_dict(), "carrier": c.to_dict(),
                                   "gate_sha256": spec_digest(g.to_dict()),
                                   "carrier_sha256": spec_digest(c.to_dict())}
                                  for g, c in pairs]}
    return binding, pairs


def _object(kind):
    net = Net()
    root = net.cell(kind)
    if kind != "e":
        for port in (1, 2):
            net.link((root, port), (net.cell("e"), 0))
    net.link((root, 0), net.boundary("ROOT"))
    return net


def payloads(compiler=None):
    compiler = compiler or CoherentICCompiler()
    objects = {"epsilon": _object("e"), "gamma_ee": _object("g"),
               "delta_ee": _object("d"), "Gamma": compiler.program}
    result = {}
    for name, obj in objects.items():
        code = compiler.code if name == "Gamma" else encode_package(obj, label="ROOT")
        result[name] = {"object": GraphSpec.from_net(obj), "code": GraphSpec.from_net(code)}
    return result


def attach_consumer(net, root, consumer):
    if consumer not in CONSUMERS:
        raise ValueError("unknown E_code consumer")
    copies = 2 if consumer in ("copy_code", "copy_decode") else 1
    if copies == 2:
        fan = net.cell("d")
        net.link(root, (fan, 0))
        roots = [(fan, 1), (fan, 2)]
    else:
        roots = [root]
    for index, endpoint in enumerate(roots, 1):
        if consumer in ("decode", "copy_decode"):
            decoder = build_decoder(net)
            macro_connect(net, endpoint, decoder.principal)
            endpoint = decoder.auxiliaries[0]
        macro_connect(net, endpoint, net.boundary("OUT" + (str(index) if copies == 2 else "")))


def consumer_spec(consumer):
    net = Net()
    attach_consumer(net, net.boundary("IN"), consumer)
    return GraphSpec.from_net(net)


def _validate_data(spec):
    if not isinstance(spec, GraphSpec) or spec.boundaries != ("ROOT",):
        raise ValueError("code/carrier must expose exactly ROOT")
    validate_package(spec.instantiate())
    if any(k not in ("g", "e") for k in spec.kinds):
        raise ValueError("code/carrier must be delta-free")


def build_bridge(gate, carrier, bit, code_spec, consumer):
    """Prewire literal imported syntax; return initial net and payload IDs.

    No expected output or decoded object is consulted by this constructor.
    Well-formed but semantically incorrect gates remain executable probes.
    """
    if type(bit) is not bool:
        raise ValueError("the control input must be a Boolean")
    if not isinstance(gate, GraphSpec) or set(gate.boundaries) != {"CTRL", "DATA", "OUT"}:
        raise ValueError("gate must expose CTRL, DATA, OUT")
    if consumer not in CONSUMERS:
        raise ValueError("unknown E_code consumer")
    _validate_data(carrier)
    _validate_data(code_spec)
    net = Net()
    token = (carrier if bit else false_carrier()).open_root(net)
    before = set(net.nodes)
    payload = code_spec.open_root(net)
    payload_ids = set(net.nodes) - before
    output = net.boundary("GATE_OUTPUT")
    gate.instantiate(net, {"CTRL": token, "DATA": payload, "OUT": output})
    neighbor = net.adj.pop(output)
    net.free.remove(output)
    net.adj[neighbor] = None
    attach_consumer(net, neighbor, consumer)
    net.check()
    return net, payload_ids


def expected(bit, object_spec, consumer):
    """Build the postcondition from the original object, never from a run."""
    if type(bit) is not bool or consumer not in CONSUMERS:
        raise ValueError("invalid reference interface")
    if bit:
        specimen = (GraphSpec.from_net(encode_package(object_spec.instantiate(), label="ROOT"))
                    if consumer in ("retain_code", "copy_code") else object_spec)
    else:
        specimen = GraphSpec.from_net(_object("e"))
    net = Net()
    labels = ("OUT1", "OUT2") if consumer in ("copy_code", "copy_decode") else ("OUT",)
    for label in labels:
        specimen.instantiate(net, {"ROOT": net.boundary(label)})
    net.check()
    return net


def bindings(discovery, data):
    return {"discovery": discovery, "contract": CONTRACT,
            "contract_sha256": spec_digest(CONTRACT),
            "payloads": {name: {key: {"graph": spec.to_dict(),
                                      "sha256": spec_digest(spec.to_dict())}
                                for key, spec in entry.items()}
                         for name, entry in data.items()},
            "consumers": {name: {"graph": consumer_spec(name).to_dict(),
                                  "sha256": spec_digest(consumer_spec(name).to_dict())}
                          for name in CONSUMERS}}


class NativeTrace:
    """Existing primitive trace format, with strict sequential FIFO replay."""
    def __init__(self, path, metadata, replay=False):
        self.count, self.replay = 0, replay
        self.digest = hashlib.sha256()
        if replay:
            self.stream = gzip.open(path, "rb")
            try:
                if json.loads(self.stream.readline()) != {"format": "IC-PAIR-U32LE-1", **metadata}:
                    raise ValueError("trace header binding mismatch")
            except BaseException:
                self.stream.close()
                raise
        else:
            self.writer = PrimitiveTrace(path, metadata)

    def record(self, pair):
        if self.replay:
            raw = self.stream.read(8)
            if len(raw) != 8:
                raise ValueError("truncated primitive trace")
            recorded = tuple("c" + str(i) for i in struct.unpack("<II", raw))
            if recorded != pair:
                raise ValueError("trace pair differs from rebuilt FIFO execution")
            self.digest.update(raw)
        else:
            self.writer.record(pair)
        self.count += 1

    def close(self):
        if not self.replay:
            return self.writer.close()
        try:
            if self.stream.read(1):
                raise ValueError("unaccounted primitive trace records")
        finally:
            self.stream.close()
        return {"format": "IC-PAIR-U32LE-1", "steps": self.count,
                "sha256_of_pair_records": self.digest.hexdigest()}


def run_case(initial, target, trace, retained_cells=0, *, max_steps=100_000, max_cells=20_000):
    """Bounded FIFO execution. A cutoff is never a successful result."""
    if any(type(v) is not int or v < 0 for v in (retained_cells, max_steps, max_cells)):
        raise ValueError("resource and search bounds must be non-negative integers")
    initial_spec = GraphSpec.from_net(initial)
    running = initial_spec.instantiate(FastNet())
    start = trace.count
    peak = len(running.nodes)
    status = None
    while True:
        if retained_cells + len(running.nodes) > max_cells:
            status = "resource-violation"
            break
        pair = running.next_active()
        if pair is None:
            status = "passed" if port_graph_isomorphic(running, target) else "wrong-normal-form"
            break
        if trace.count - start >= max_steps:
            status = "incomplete"
            break
        trace.record(pair)
        running.reduce(*pair)
        peak = max(peak, len(running.nodes))
    running.final_check()
    final_spec = GraphSpec.from_net(running).to_dict()
    record = {"status": status, "schedule": "FIFO",
              "trace_offset_records": start, "primitive_interactions": trace.count - start,
              "initial_cells": len(initial.nodes), "initial_graph_sha256": spec_digest(initial_spec.to_dict()),
              "peak_live_cells": peak, "retained_cells": retained_cells,
              "combined_peak_live_cells": retained_cells + peak,
              "final_cells": len(running.nodes), "cyclic_wires": running.cycles,
              "terminal": not bool(running.active()), "final_graph": final_spec,
              "final_graph_sha256": spec_digest(final_spec),
              "expected_graph_sha256": spec_digest(GraphSpec.from_net(target).to_dict())}
    if status != "passed":
        record["counterexample"] = {"initial": initial_spec.to_dict(),
                                    "expected": GraphSpec.from_net(target).to_dict(),
                                    "actual": final_spec,
                                    "trace_range": [start, trace.count], "reason": status}
    return record, running


def check_schedules(initial, target, **budget):
    result = explore(initial, **(budget or EXPLORATION_BUDGET))
    wrong = [i for i in result.terminal_ids if not port_graph_isomorphic(result.states[i], target)]
    material = any(c["reason"] == "material-bound" for c in result.cutoffs)
    status = ("resource-violation" if material else "wrong-normal-form" if wrong else
              "reachable-cycle" if result.cycle else "incomplete" if not result.complete else
              "passed" if result.terminal_ids else "incomplete")
    record = {"status": status, "execution": result.summary()}
    if wrong:
        i = wrong[0]
        record["counterexample"] = {"initial": GraphSpec.from_net(initial).to_dict(),
                                    "trace": [list(p) for p in result.trace_to(i)],
                                    "actual": GraphSpec.from_net(result.states[i]).to_dict(),
                                    "expected": GraphSpec.from_net(target).to_dict()}
    # Explorer cutoffs include concrete states/pairs; retain them on failure.
    if result.cutoffs or result.cycle:
        record["failure_states"] = [GraphSpec.from_net(n).to_dict() for n in result.states]
        record["failure_prefixes"] = [[list(p) for p in result.trace_to(i)]
                                      for i in range(len(result.states))]
    return record


def counterexamples(trace, pairs, data, compiler):
    """Preserve explicit refutations; these are not accepted bridge cases."""
    gate, carrier = pairs[0]
    entry = data["delta_ee"]
    wrong_token = GraphSpec.from_net(_object("g"))
    initial, _ = build_bridge(gate, wrong_token, True, entry["code"], "decode")
    wrong_control, _ = run_case(initial, expected(True, entry["object"], "decode"), trace, **FIFO_BUDGET)
    renamed = {"CTRL": "DATA", "DATA": "CTRL"}
    wrong_gate = GraphSpec(gate.kinds, gate.boundaries,
                          tuple(tuple(("F", renamed.get(e[1], e[1])) if e[0] == "F" else e
                                      for e in wire) for wire in gate.wires), gate.cycles)
    initial, _ = build_bridge(wrong_gate, carrier, True, entry["code"], "decode")
    wrong_wiring, _ = run_case(initial, expected(True, entry["object"], "decode"), trace, **FIFO_BUDGET)
    epsilon = _object("e")
    # D accepts erased code as epsilon, independently of the source extension.
    decoder_case, _ = run_case(build_decoding(epsilon), expected(False, entry["object"], "decode"),
                               trace, **FIFO_BUDGET)
    extension = Net()
    cell = compiler._extension(extension, "INIT")
    macro_connect(extension, (extension.cell("e"), 0), cell.code_port)
    macro_connect(extension, cell.principal, extension.boundary("P0"))
    for i, port in enumerate(cell.auxiliaries, 1):
        macro_connect(extension, port, extension.boundary("P" + str(i)))
    extension.check()
    erroneous_target = Net()
    for _, label in sorted(extension.free):
        erroneous_target.link((erroneous_target.cell("e"), 0), erroneous_target.boundary(label))
    extension_case, _ = run_case(extension, erroneous_target, trace, **FIFO_BUDGET)
    return {"wrong_control_token": wrong_control, "wrong_gate_wiring": wrong_wiring,
            "decoder_epsilon": decoder_case, "epsilon_does_not_clear_INIT_extension": extension_case}


def _suite(trace_path, discovery_path, replay=False):
    discovery, pairs = load_discovery(discovery_path)
    compiler = CoherentICCompiler()
    data = payloads(compiler)
    binding = bindings(discovery, data)
    metadata = {"scope": "E_code bridge and offline artifact reuse", "schedule": "FIFO",
                "bindings_sha256": spec_digest(binding)}
    trace = NativeTrace(trace_path, metadata, replay)
    bridge, archives, reuse, small = [], [], [], []
    try:
        for pair_index, (gate, carrier) in enumerate(pairs):
            for bit in (False, True):
                for name, entry in data.items():
                    for consumer in CONSUMERS:
                        initial, payload_ids = build_bridge(gate, carrier, bit, entry["code"], consumer)
                        # run_case reconstructs GraphSpec syntax with fresh c0..
                        # names. Track payload identity in that exact namespace.
                        replay_payload_ids = {"c" + str(i) for i, cell in enumerate(initial.nodes)
                                              if cell in payload_ids}
                        target = expected(bit, entry["object"], consumer)
                        record, terminal = run_case(initial, target, trace, **FIFO_BUDGET)
                        record.update({"pair": pair_index, "bit": bit, "payload": name, "consumer": consumer})
                        bridge.append(record)
                        if name in ("epsilon", "delta_ee") and consumer in ("decode", "copy_decode"):
                            schedule = check_schedules(initial, target)
                            small.append({"pair": pair_index, "bit": bit, "payload": name,
                                          "consumer": consumer, **schedule})
                        if name != "Gamma" or consumer != "copy_code" or record["status"] != "passed":
                            continue
                        before = GraphSpec.from_net(terminal).to_dict()
                        provenance = {"producer_case": len(bridge) - 1, "pair": pair_index,
                                      "first_input": bit, "payload": name,
                                      "initial_graph_sha256": record["initial_graph_sha256"],
                                      "trace_offset_records": record["trace_offset_records"],
                                      "primitive_interactions": record["primitive_interactions"],
                                      "bindings_sha256": metadata["bindings_sha256"],
                                      "source_boundary": ["F", "OUT1"]}
                        contract = {"representation": "delta-free principal code package or epsilon",
                                    "interface": ["ROOT"], "allowed_consumers": ["decode", "copy_decode"],
                                    "construction": "native IC copy product; original payload consumed",
                                    "import": "offline fresh allocation; original producer retained",
                                    "evidence_scope": "recorded FIFO cases only",
                                    "cost": {"producer_initial_cells": record["initial_cells"],
                                             "producer_peak_cells": record["peak_live_cells"],
                                             "producer_terminal_cells": len(terminal.nodes)}}
                        artifact, ids = capture_root(terminal, ("F", "OUT1"), provenance, contract)
                        other, other_ids = capture_root(terminal, ("F", "OUT2"), provenance, contract)
                        if not ids.isdisjoint(other_ids) or ids | other_ids != set(terminal.nodes):
                            raise AssertionError("copy products overlap or omit components")
                        if replay_payload_ids & set(terminal.nodes):
                            raise AssertionError("native copying did not consume original payload")
                        if not port_graph_isomorphic(artifact.instantiate(), other.instantiate()):
                            raise AssertionError("copy products differ")
                        serialized = json.loads(artifact.export_json())
                        restored = RetainedArtifact.from_dict(serialized)
                        archive_index = len(archives)
                        archives.append({"pair": pair_index, "first_input": bit, "artifact": serialized,
                                         "native_copies_disjoint": True, "original_payload_consumed": True,
                                         "source_specimen_unchanged": True})
                        for new_bit in (False, True):
                            for next_consumer in ("decode", "copy_decode"):
                                instance, _ = build_bridge(gate, carrier, new_bit, restored.spec, next_consumer)
                                reference = expected(bit and new_bit, entry["object"], next_consumer)
                                reused, _ = run_case(instance, reference, trace, len(terminal.nodes), **FIFO_BUDGET)
                                reused.update({"artifact": archive_index, "new_bit": new_bit,
                                               "consumer": next_consumer})
                                reuse.append(reused)
                                if GraphSpec.from_net(terminal).to_dict() != before:
                                    raise AssertionError("offline reconstruction mutated retained producer")
        negative = counterexamples(trace, pairs, data, compiler)
    except BaseException:
        # Do not mask a replay mismatch with the expected unread suffix.
        if replay:
            trace.stream.close()
        else:
            trace.writer.close()
        raise
    else:
        summary = trace.close()
    passed = (all(r["status"] == "passed" for r in bridge + reuse + small)
              and len(archives) == len(pairs) * 2 and len(reuse) == len(archives) * 4
              and negative["decoder_epsilon"]["status"] == "passed"
              and all(negative[k]["status"] == "wrong-normal-form"
                      for k in ("wrong_control_token", "wrong_gate_wiring",
                                "epsilon_does_not_clear_INIT_extension")))
    return {"format": "ic-program-code-bridge-v1", "bindings": binding, "metadata": metadata,
            "bridge_cases": bridge, "artifacts": archives, "reuse_cases": reuse,
            "all_schedule_cases": small, "counterexamples": negative, "trace": summary,
            "status": "passed" if passed else "not-accepted",
            "limitations": ["large networks: recorded FIFO evidence only",
                            "archive/import: offline tooling, not continuous reuse in one network",
                            "no complete-program activation/disable semantics or arbitrary-context proof"]}


def generate(trace_path, discovery_path=DISCOVERY_PATH):
    return _suite(trace_path, discovery_path)


def verify_report(report, trace_path, discovery_path=DISCOVERY_PATH):
    """Rebuild every initial graph, replay every pair and rederive all fields.

    Archived syntax, producer provenance, small schedule graphs, budgets and
    complete matrix coverage are checked by exact comparison with the rebuilt
    report. Replayed producer products, rather than trusted saved metadata,
    supply the independent reuse specimens.
    """
    if report.get("format") != "ic-program-code-bridge-v1":
        raise ValueError("unknown bridge report format")
    discovery, _ = load_discovery(discovery_path)
    if spec_digest(report.get("bindings")) != spec_digest(bindings(discovery, payloads())):
        raise ValueError("report binding differs from the frozen contract and input syntax")
    rebuilt = _suite(trace_path, discovery_path, replay=True)
    # Canonical JSON also distinguishes Boolean inputs from numeric 0/1 and
    # integer resource counts from floats; Python container equality does not.
    if spec_digest(rebuilt) != spec_digest(report):
        raise ValueError("bridge report differs from independently rebuilt evidence")
    if rebuilt["status"] != "passed":
        raise ValueError("bridge evidence is reproducible but does not meet acceptance")
    return len(rebuilt["bridge_cases"]) + len(rebuilt["reuse_cases"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--verify-report", type=Path)
    args = parser.parse_args()
    if args.report and args.verify_report:
        parser.error("choose --report or --verify-report")
    if args.verify_report:
        count = verify_report(read_json(args.verify_report), args.trace)
        print("PASS: program-code bridge evidence, raw trace replay and resource accounting", count)
        return
    if not args.report:
        parser.error("generation requires --report to preserve evidence")
    report = generate(args.trace)
    write_json(args.report, report)
    if report["status"] != "passed":
        raise SystemExit("NOT ACCEPTED: report preserves failed or incomplete cases")
    print("PASS: program-code bridge; detailed coverage and evidence scope belong in docs/CLAIM_LEDGER.md")


if __name__ == "__main__":
    main()
