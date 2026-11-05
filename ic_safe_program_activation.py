"""M2: whole-task suspension and native continuations in one prewired IC net.

One literal !Gamma is supplied initially. Native copying supplies the bare
source extensions and carries a fresh copy to each subsequent task. Runtime
never calls a source evaluator, reconstructs a net, or branches on readout.
"""
from dataclasses import dataclass
from itertools import product
from math import isqrt
import argparse
import hashlib
from pathlib import Path

from ic_bounded_synthesis import false_carrier
from ic_coherent_feedback import read_json, source_result_graph, spec_digest, write_json
from ic_coherent_output_decoder import port_graph_isomorphic
from ic_fast_reducer import FastNet
from ic_program_code_bridge import NativeTrace, load_discovery, _validate_data
from ic_research_artifacts import GraphSpec, capture_root
from ic_program_suspension import suspend_feedback, build_activation, append_spec
from ic_native_result_reader import build_reader
from lafont_ic_macro_builder import build_M_star, build_menu, build_selector, macro_connect
from ic_primitive_port_verifier import Net
from source_feedback_audit import run as source_run
from source_ic_coherent_compiler import CoherentICCompiler


M1_REPORT = Path(__file__).parent / "results/program_code_bridge.json.gz"
M1_SHA256 = "624976b188e7659a52a32e92fcd1c46db95a18f639c41909ddaf17eaac29ecf7"
MAX_INPUT = 4
MAX_TASKS = 3
UNARY_DEPTH = MAX_INPUT + 1
EXECUTION_BUDGET = {"max_steps": 2_000_000, "max_cells": 250_000}
CONTRACT = {
    "environment": "E_activation-v1",
    "inputs": "prewired finite natural inputs and independent Boolean flags",
    "max_input": MAX_INPUT, "max_tasks": MAX_TASKS, "unary_reader_depth": UNARY_DEPTH,
    "Boolean_input_adapter": "same supplied bit encoded as Loop/epsilon and S_2 selector; no task answer",
    "suspension": "bare source extensions; initial cut, output and code ports in one principal package",
    "program_supply": "one initial !Gamma; native copy to extensions and native continuation carry",
    "enabled": "independently compiled source result at TASK_i_OUT; Loop at STATUS_i",
    "disabled": "epsilon at TASK_i_OUT and STATUS_i; skip and continue after incoming grant",
    "continuation": "enabled: all result unary constructors recognized; disabled: incoming grant received",
    "readiness_boundary": "all original result constructors recognized; reconstruction and cleanup may overlap later stages",
    "final": "all task outputs/statuses, exact !Gamma at LIBRARY, Loop at DONE; no extra components/cycles",
    "runtime": "single prewired network; original IC rules and FIFO only; no rebuild or host-driven transition",
    "budget": EXECUTION_BUDGET,
    "measurement": "initial and post-atomic-interaction live cells, including all future tasks and retained code",
    "negative_probes": ["insufficient unary reader depth", "ready selector miswired to skip enabled work"],
}


def loop(net):
    cell = net.cell("g")
    net.link((cell, 1), (cell, 2))
    return cell, 0


def take(net, endpoint):
    """Remove a construction-only wire proxy, leaving its neighbor unpaired."""
    if endpoint[0] == "F" and net.adj.get(endpoint) is not None:
        neighbor = net.adj.pop(endpoint)
        net.free.remove(endpoint)
        net.adj[neighbor] = None
        return neighbor
    if endpoint not in net.adj or net.adj[endpoint] is not None:
        raise ValueError("expected a free composition endpoint")
    return endpoint


def gate_port(net, gate, control, data):
    """Import the discovered gate unchanged; return output hole and cell ID."""
    serial = getattr(net, "_activation_gate_serial", 0)
    net._activation_gate_serial = serial + 1
    output = net.boundary("activation-gate-" + str(serial))
    before = set(net.nodes)
    append_spec(gate, net, {"CTRL": take(net, control), "DATA": take(net, data), "OUT": output})
    ids = set(net.nodes) - before
    if len(ids) != 1:
        raise ValueError("this protocol requires the frozen one-cell gate interface")
    return take(net, output), next(iter(ids))


@dataclass
class BuiltSequence:
    net: Net
    stages: list
    program_ids: set


def build_sequence(gate, carrier, numbers, flags, *, compiler=None, suspensions=None,
                   reader_depth=UNARY_DEPTH):
    """Construct inputs and all future tasks; never compute their answers."""
    numbers, flags = tuple(numbers), tuple(flags)
    if not 1 <= len(numbers) <= MAX_TASKS or len(flags) != len(numbers):
        raise ValueError("supply matching nonempty task/input lists within the contract")
    if any(type(n) is not int or not 0 <= n <= MAX_INPUT for n in numbers):
        raise ValueError("input is outside the fixed natural-number contract")
    if any(type(flag) is not bool for flag in flags):
        raise ValueError("task flags must be Boolean")
    if type(reader_depth) is not int or reader_depth < 0:
        raise ValueError("reader depth must be a non-negative integer")
    if set(gate.boundaries) != {"CTRL", "DATA", "OUT"} or len(gate.kinds) != 1:
        raise ValueError("invalid discovered gate interface")
    _validate_data(carrier)
    compiler = compiler or CoherentICCompiler()
    suspensions = suspensions or {n: suspend_feedback(compiler, n) for n in set(numbers)}
    net, stages = Net(), []
    before = set(net.nodes)
    code = compiler.code_spec.open_root(net)
    program_ids = set(net.nodes) - before
    packet = net.cell("g")
    net.link((packet, 1), code)
    net.link((packet, 2), loop(net))
    incoming, incoming_packet = (packet, 0), packet
    for index, (number, enabled) in enumerate(zip(numbers, flags)):
        suspension = suspensions[number]
        unpack = build_M_star(net, 2)
        macro_connect(net, incoming, unpack.principal)
        program_fan, go_fan = net.cell("d"), net.cell("d")
        macro_connect(net, unpack.auxiliaries[0], (program_fan, 0))
        macro_connect(net, unpack.auxiliaries[1], (go_fan, 0))
        next_packet = net.cell("g")
        net.link((next_packet, 1), (program_fan, 2))
        net.link((next_packet, 2), loop(net))

        flag_fan = net.cell("d")
        token = (carrier if enabled else false_carrier()).open_root(net)
        net.link((flag_fan, 0), token)
        net.link((flag_fan, 2), net.boundary(f"STATUS_{index}"))
        payload = suspension.code.open_root(net)
        flagged, _ = gate_port(net, gate, (flag_fan, 1), payload)
        delivered, delivery_id = gate_port(net, gate, (go_fan, 1), flagged)

        ready_boundary = net.boundary(f"reader-ready-{index}")
        reader = build_reader(net, compiler, gate, reader_depth,
                              value_out=net.boundary(f"TASK_{index}_OUT"), ready_out=ready_boundary)
        reader_root = reader.principal
        build_activation(net, suspension.width, delivered, (program_fan, 1), reader_root)

        # The selector is an input representation of this bit. It selects a
        # readiness source, not a precomputed result. GO still guards skips.
        ready = take(net, ready_boundary)
        skip_ready = loop(net)
        menu = build_menu(net, [ready, skip_ready])
        selector = build_selector(net, 2, 1 if enabled else 2)
        macro_connect(net, menu.principal, selector.principal)
        permitted, _ = gate_port(net, gate, (go_fan, 2), selector.auxiliaries[0])
        incoming, advance_id = gate_port(net, gate, permitted, (next_packet, 0))
        stages.append({"index": index, "number": number, "enabled": enabled,
                       "incoming_packet": incoming_packet,
                       "grant_receiver": unpack.principal[0], "delivery_gate": delivery_id,
                       "advance_gate": advance_id, "program_copy_fan": program_fan,
                       "ready_selector": selector.principal[0],
                       "skip_ready": skip_ready[0], "reader": reader.metadata})
        incoming_packet = next_packet
    final_unpack = build_M_star(net, 2)
    macro_connect(net, incoming, final_unpack.principal)
    macro_connect(net, final_unpack.auxiliaries[0], net.boundary("LIBRARY"))
    macro_connect(net, final_unpack.auxiliaries[1], net.boundary("DONE"))
    net.check()
    return BuiltSequence(net, stages, program_ids)


def reference_result(number):
    """Independent specification, used only outside builders/runtime."""
    root = isqrt(number)
    return ("SQ", root) if root * root == number else ("BR", root, root + 1)


def expected(compiler, numbers, flags):
    result = Net()
    for index, (number, enabled) in enumerate(zip(numbers, flags)):
        if enabled:
            specimen = compiler.compile(*source_result_graph(reference_result(number)))
            GraphSpec.from_net(specimen).instantiate(result, {"OUT": result.boundary(f"TASK_{index}_OUT")})
            result.link(loop(result), result.boundary(f"STATUS_{index}"))
        else:
            for label in (f"TASK_{index}_OUT", f"STATUS_{index}"):
                result.link((result.cell("e"), 0), result.boundary(label))
    compiler.code_spec.instantiate(result, {"ROOT": result.boundary("LIBRARY")})
    result.link(loop(result), result.boundary("DONE"))
    result.check()
    return result


def cases():
    result = [{"name": f"single-{number}-{int(bit)}", "numbers": [number], "flags": [bit]}
              for number in (0, 1, 2, 4) for bit in (False, True)]
    result.extend({"name": "sequence-21-" + "".join(str(int(b)) for b in bits),
                   "numbers": [2, 1], "flags": list(bits)} for bits in product((False, True), repeat=2))
    result.extend({"name": "sequence-120-" + "".join(str(int(b)) for b in bits),
                   "numbers": [1, 2, 0], "flags": list(bits)}
                  for bits in ((True, True, True), (True, False, True), (False, False, True)))
    return result


def binding(compiler, discovery, suspensions, case_specs):
    if hashlib.sha256(M1_REPORT.read_bytes()).hexdigest() != M1_SHA256:
        raise ValueError("accepted M1 evidence differs from the frozen report")
    return {"contract": CONTRACT, "contract_sha256": spec_digest(CONTRACT),
            "discovery": discovery, "m1_report_sha256": M1_SHA256,
            "program": compiler.code_spec.to_dict(),
            "program_sha256": spec_digest(compiler.code_spec.to_dict()),
            "cases": case_specs,
            "suspensions": {str(n): {"width": s.width, "package": s.package.to_dict(),
                                      "code": s.code.to_dict(),
                                      "code_sha256": spec_digest(s.code.to_dict())}
                            for n, s in suspensions.items()},
            "source_reference_checks": {str(n): {"expected": list(reference_result(n)),
                                                 "source_result": list(source_run(n)[1])}
                                        for n in suspensions}}


def run_case(built, target, trace, *, max_steps=2_000_000, max_cells=250_000):
    if any(type(v) is not int or v < 0 for v in (max_steps, max_cells)):
        raise ValueError("execution bounds must be non-negative integers")
    original = GraphSpec.from_net(built.net)
    renamed = {name: "c" + str(i) for i, name in enumerate(built.net.nodes)}
    running = original.instantiate(FastNet())
    watches, events = {}, []
    for stage in built.stages:
        for kind, key in (("grant", "grant_receiver"), ("delivery", "delivery_gate"),
                          ("advance", "advance_gate")):
            watches[renamed[stage[key]]] = (stage["index"], kind)
        for cell in stage["reader"].get("join_gates", []):
            watches[renamed[cell]] = (stage["index"], "argument-join")
    start, steps, peak = trace.count, 0, len(running.nodes)
    while True:
        if len(running.nodes) > max_cells:
            status = "resource-violation"
            break
        pair = running.next_active()
        if pair is None:
            status = "passed" if port_graph_isomorphic(running, target) else "wrong-normal-form"
            break
        if steps >= max_steps:
            status = "incomplete"
            break
        for cell in pair:
            if cell in watches:
                stage, kind = watches[cell]
                events.append({"stage": stage, "kind": kind, "step": steps,
                               "pair": list(pair), "kinds": [running.nodes[c] for c in pair]})
        trace.record(pair)
        running.reduce(*pair)
        steps += 1
        peak = max(peak, len(running.nodes))
    running.final_check()
    violations = []
    if status == "passed":
        for stage in built.stages:
            index = stage["index"]
            observed = {kind: [e for e in events if e["stage"] == index and e["kind"] == kind]
                        for kind in ("grant", "delivery", "advance")}
            if any(len(es) != 1 or es[0]["kinds"] != ["g", "g"] for es in observed.values()):
                violations.append({"stage": index, "reason": "missing or invalid native protocol event"})
                continue
            grant, delivery, advance = (observed[k][0] for k in ("grant", "delivery", "advance"))
            if renamed[stage["incoming_packet"]] not in grant["pair"]:
                violations.append({"stage": index, "reason": "grant did not consume its predecessor packet"})
            if grant["step"] >= delivery["step"] or grant["step"] >= advance["step"]:
                violations.append({"stage": index, "reason": "stage progressed before incoming grant"})
            if stage["enabled"] and delivery["step"] >= advance["step"]:
                violations.append({"stage": index, "reason": "enabled stage advanced before delivery"})
            if index:
                previous = next(e for e in events if e["stage"] == index - 1 and e["kind"] == "advance")
                if previous["step"] >= grant["step"]:
                    violations.append({"stage": index, "reason": "grant preceded prior stage advancement"})
            if not stage["enabled"] and renamed[stage["skip_ready"]] not in advance["pair"]:
                violations.append({"stage": index, "reason": "skip did not use its native readiness token"})
            if stage["enabled"]:
                emitters = {renamed[c] for c in stage["reader"].get("ready_emitters", [])}
                if not emitters.intersection(advance["pair"]):
                    violations.append({"stage": index, "reason": "advance lacked a native result-readiness token"})
                joins = [e for e in events if e["stage"] == index and e["kind"] == "argument-join"
                         and e["kinds"] == ["g", "g"]]
                expected_joins = int(reference_result(stage["number"])[0] == "BR")
                if len(joins) != expected_joins or any(e["step"] >= advance["step"] for e in joins):
                    violations.append({"stage": index, "reason": "result arguments were not joined before advance"})
        source_ids = {renamed[c] for c in built.program_ids}
        if source_ids & set(running.nodes):
            violations.append({"reason": "initial program-code cells survived native copying"})
    if status == "passed" and violations:
        status = "protocol-violation"
    final = GraphSpec.from_net(running).to_dict()
    record = {"status": status, "initial_cells": len(built.net.nodes),
              "initial_graph_sha256": spec_digest(original.to_dict()),
              "trace_offset_records": start, "primitive_interactions": steps,
              "peak_live_cells": peak, "final_cells": len(running.nodes), "cyclic_wires": running.cycles,
              "terminal": not bool(running.active()), "events": events, "protocol_violations": violations,
              "stages": built.stages,
              "final_graph": final, "final_graph_sha256": spec_digest(final),
              "expected_graph_sha256": spec_digest(GraphSpec.from_net(target).to_dict()),
              "whole_graph_matches_reference": port_graph_isomorphic(running, target),
              "initial_program_cells_consumed": not bool({renamed[c] for c in built.program_ids} & set(running.nodes))}
    if status == "passed":
        retained, ids = capture_root(running, ("F", "LIBRARY"),
                                    {"initial_graph_sha256": record["initial_graph_sha256"],
                                     "trace_offset_records": start, "primitive_interactions": steps},
                                    {"representation": "native copied delta-free !Gamma",
                                     "construction": "one initial program source; prewired native continuation chain",
                                     "runtime_reconstruction": False, "interface": ["ROOT"]})
        record["retained_program"] = retained.to_dict()
        record["retained_program_cells"] = len(ids)
    if status != "passed":
        record["counterexample"] = {"initial": original.to_dict(),
                                    "expected": GraphSpec.from_net(target).to_dict(),
                                    "actual": final, "reason": status,
                                    "trace_range": [start, trace.count]}
    return record


def negative_probes(compiler, gate, carrier, suspensions, trace):
    insufficient = build_sequence(gate, carrier, [1], [True], compiler=compiler,
                                  suspensions=suspensions, reader_depth=0)
    depth_record = run_case(insufficient, expected(compiler, [1], [True]), trace, **EXECUTION_BUDGET)
    premature = build_sequence(gate, carrier, [0, 0], [True, True], compiler=compiler,
                               suspensions=suspensions)
    # A well-formed offline wiring fault chooses the immediate skip token
    # for an enabled stage. Whole-graph output can still be correct, so the
    # recorded native continuation evidence must be checked independently.
    cell = premature.stages[0]["ready_selector"]
    a, b = (cell, 1), (cell, 2)
    left, right = premature.net.adj[a], premature.net.adj[b]
    for port in (a, b, left, right):
        premature.net.adj[port] = None
    premature.net.link(a, right)
    premature.net.link(b, left)
    premature.net.check()
    phase_record = run_case(premature, expected(compiler, [0, 0], [True, True]), trace, **EXECUTION_BUDGET)
    return {"insufficient_reader_depth": depth_record, "premature_continuation": phase_record}


def inputs():
    compiler = CoherentICCompiler()
    discovery, pairs = load_discovery()
    specs = cases()
    numbers = sorted({0, 1} | {n for case in specs for n in case["numbers"]})
    suspensions = {n: suspend_feedback(compiler, n) for n in numbers}
    bound = binding(compiler, discovery, suspensions, specs)
    for check in bound["source_reference_checks"].values():
        if check["expected"] != check["source_result"]:
            raise ValueError("independent source simulator disagrees with specification")
    return compiler, pairs, specs, suspensions, bound


def _suite(trace_path, replay=False, context=None):
    compiler, pairs, specs, suspensions, bound = context or inputs()
    metadata = {"scope": "M2 safe activation and native prewired task continuations", "schedule": "FIFO",
                "bindings_sha256": spec_digest(bound)}
    trace = NativeTrace(trace_path, metadata, replay)
    records = []
    try:
        for pair_index, (gate, carrier) in enumerate(pairs):
            for case in specs:
                built = build_sequence(gate, carrier, case["numbers"], case["flags"],
                                       compiler=compiler, suspensions=suspensions)
                reference = expected(compiler, case["numbers"], case["flags"])
                record = run_case(built, reference, trace, **EXECUTION_BUDGET)
                record.update({"pair": pair_index, "case": case})
                records.append(record)
                print(("REPLAY" if replay else "CASE"), pair_index, case["name"], record["status"], flush=True)
        negative = negative_probes(compiler, *pairs[0], suspensions, trace)
    except BaseException:
        trace.stream.close() if replay else trace.writer.close()
        raise
    else:
        summary = trace.close()
    return {"format": "ic-safe-program-activation-v1", "bindings": bound, "metadata": metadata,
            "cases": records, "negative_probes": negative, "trace": summary,
            "status": ("passed" if all(r["status"] == "passed" for r in records)
                       and negative["insufficient_reader_depth"]["status"] == "wrong-normal-form"
                       and negative["premature_continuation"]["status"] == "protocol-violation"
                       and negative["premature_continuation"]["whole_graph_matches_reference"] else "not-accepted"),
            "limitations": ["finite input and bounded result-reader grammar; FIFO evidence only",
                            "readiness is source-constructor recognition; output reconstruction and cleanup may overlap",
                            "no arbitrary-context proof, physical inventory, or demonstrated cost benefit"]}


def generate(trace_path):
    return _suite(trace_path)


def compare_report(report, rebuilt):
    """Compare saved metadata with already replayed, independently rebuilt evidence."""
    if spec_digest(rebuilt) != spec_digest(report):
        raise ValueError("activation report differs from rebuilt primitive evidence")
    if rebuilt["status"] != "passed":
        raise ValueError("reproducible evidence does not satisfy the activation contract")
    return len(rebuilt["cases"])


def verify_report(report, trace_path):
    if report.get("format") != "ic-safe-program-activation-v1":
        raise ValueError("unknown activation report format")
    context = inputs()
    if spec_digest(report.get("bindings")) != spec_digest(context[-1]):
        raise ValueError("activation contract or input binding mismatch")
    rebuilt = _suite(trace_path, replay=True, context=context)
    return compare_report(report, rebuilt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verify-report", type=Path)
    parser.add_argument("--trace", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.report) == bool(args.verify_report):
        parser.error("choose --report or --verify-report")
    if args.verify_report:
        verify_report(read_json(args.verify_report), args.trace)
    else:
        report = generate(args.trace)
        write_json(args.report, report)
        if report["status"] != "passed":
            raise SystemExit("NOT ACCEPTED: failed/incomplete activation evidence preserved")
    print("PASS: M2 evidence; coverage and boundaries are recorded in docs/CLAIM_LEDGER.md")


if __name__ == "__main__":
    main()
