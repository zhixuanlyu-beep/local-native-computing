"""Actual local-stage witnesses lifted into the complete prewired M6 graph."""
from collections import deque

from ic_coherent_feedback import spec_digest, source_result_graph
from ic_coherent_output_decoder import port_graph_isomorphic
from ic_fast_reducer import FastNet
from ic_native_control_packets import control_packet
from ic_observation_contracts import value_spec
from ic_primitive_port_verifier import Net, AR
from ic_research_artifacts import GraphSpec
from ic_result_controlled_execution import (
    BuiltResultSequence, build_result_stage, frame, loop, reference_states,
    BUDGET, UNARY_DEPTH, build_result_sequence, expected,
)
from ic_schedule_audit import ScheduledNet, Schedule
from lafont_ic_macro_builder import macro_connect


def copy_code(library):
    capsule = library.workload["capsule"]
    return GraphSpec.from_dict(capsule["code"]) if isinstance(capsule, dict) else capsule.code


def build_local(number, bit, library, compiler, *, reader_depth=UNARY_DEPTH):
    if type(bit) is not bool:
        raise ValueError("local contract requires a Boolean control input")
    net = Net()
    program = library.program_code(compiler).open_root(net)
    program_ids = set(net.nodes)
    incoming = frame(net, [program, loop(net), control_packet(bit).open_root(net)])
    code = copy_code(library).open_root(net)
    outgoing, stage, cells = build_result_stage(net, number, incoming, code,
                                               library=library, compiler=compiler,
                                               reader_depth=reader_depth)
    stage["incoming_packet"] = incoming[0]
    macro_connect(net, outgoing, net.boundary("CONTINUATION"))
    net.check()
    return BuiltResultSequence(net, [stage], program_ids, set(), library, (number,), [cells])


def local_expected(number, bit, library, compiler):
    net = Net()
    states, results, next_enable = reference_states([number], bit)
    if bit:
        spec = GraphSpec.from_net(compiler.compile(*source_result_graph(results[0])))
    else:
        spec = value_spec("A", False)
    spec.instantiate(net, {spec.boundaries[0]: net.boundary("TASK_0_OUT")})
    value_spec("A", bit).instantiate(net, {"ROOT": net.boundary("STATUS_0")})
    output = frame(net, [compiler.code_spec.open_root(net), loop(net), control_packet(next_enable).open_root(net)])
    macro_connect(net, output, net.boundary("CONTINUATION"))
    net.check()
    return net


class PairList:
    def __init__(self, delegate=None):
        self.count = delegate.count if delegate else 0
        self.pairs = []
        self.delegate = delegate

    def record(self, pair):
        self.pairs.append(tuple(pair))
        if self.delegate:
            self.delegate.record(pair)
        self.count += 1


def correspondence(local, whole, core_map, boundaries):
    """Extend an explicit core/port map by forced kind-and-port traversal."""
    if not set(core_map).issubset(local.nodes) or not set(core_map.values()).issubset(whole.nodes):
        raise ValueError("stage map names an absent local/context cell")
    if set(boundaries) != {label for _, label in local.free}:
        raise ValueError("stage boundary mapping must cover the complete local interface")
    mapping, reverse = dict(core_map), {v: k for k, v in core_map.items()}
    if len(reverse) != len(mapping):
        raise ValueError("noninjective stage core map")
    pending = deque(mapping)
    processed = set()
    while pending:
        old = pending.popleft()
        if old in processed:
            continue
        processed.add(old)
        new = mapping[old]
        if local.nodes[old] != whole.nodes.get(new):
            raise ValueError("local stage kind differs from plugged context")
        for port in range(AR[local.nodes[old]] + 1):
            left, right = local.adj[(old, port)], whole.adj[(new, port)]
            if left[0] == "F":
                if boundaries.get(left[1]) != right:
                    raise ValueError("local boundary mapping differs from plugged context")
                continue
            if right[0] == "F" or left[1] != right[1]:
                raise ValueError("local/context port numbers differ")
            if left[0] in mapping:
                if mapping[left[0]] != right[0]:
                    raise ValueError("inconsistent stage cell map")
            else:
                if right[0] in reverse:
                    raise ValueError("stage input map overlaps")
                mapping[left[0]], reverse[right[0]] = right[0], left[0]
                pending.append(left[0])
    if set(mapping) != set(local.nodes):
        raise ValueError("local stage contains an unmapped component")
    return mapping


class _StagedCutoff(Exception):
    def __init__(self, status, whole, syntax, start, phases):
        self.status, self.whole, self.syntax = status, whole, syntax
        self.start, self.phases = start, phases


def staged_case(numbers, library, compiler, witnesses, trace, *, budget=None):
    limits = {**BUDGET, **(budget or {})}
    if set(limits) != set(BUDGET) or any(type(v) is not int or v < 0 for v in limits.values()):
        raise ValueError("staged bounds must be nonnegative integers")
    try:
        return _staged_case(numbers, library, compiler, witnesses, trace, limits)
    except _StagedCutoff as cutoff:
        final = GraphSpec.from_net(cutoff.whole).to_dict()
        return {"status": cutoff.status, "numbers": list(numbers),
                "initial_graph_sha256": spec_digest(cutoff.syntax.to_dict()),
                "trace_offset_records": cutoff.start,
                "primitive_interactions": trace.count - cutoff.start,
                "phases": cutoff.phases, "resources": cutoff.whole.statistics(),
                "final_graph": final, "final_graph_sha256": spec_digest(final),
                "whole_graph_matches_reference": False,
                "counterexample": {"initial": cutoff.syntax.to_dict(), "actual": final,
                                   "reason": cutoff.status}}


def _staged_case(numbers, library, compiler, witnesses, trace, limits):
    """Supply natively, lift each independently run local trace, then finish.

    Only this certificate deliberately defers context interactions. The normal
    policy runs are independent and never use these witnesses as a scheduler.
    """
    built = build_result_sequence(numbers, library=library, compiler=compiler)
    syntax = GraphSpec.from_net(built.net)
    whole = syntax.instantiate(ScheduledNet(Schedule("witness")))
    rename = dict(zip(built.net.nodes, whole.nodes))
    whole.begin_audit()
    core = {rename[c] for group in built.stage_cells for c in group}
    start, phases = trace.count, []

    def reduce(pair):
        if len(whole.nodes) > limits["max_cells"]:
            raise _StagedCutoff("resource-violation", whole, syntax, start, phases)
        if trace.count - start >= limits["max_steps"]:
            raise _StagedCutoff("incomplete", whole, syntax, start, phases)
        trace.record(pair)
        whole.reduce(*pair)
        if len(whole.nodes) > limits["max_cells"]:
            raise _StagedCutoff("resource-violation", whole, syntax, start, phases)

    # Freeze all stages and finishing machinery while the small archive is
    # copied/erased and all actual component code copies become passive.
    while True:
        candidates = [p for p in whole.active() if not core.intersection(p)]
        if not candidates:
            break
        reduce(candidates[0])
    phases.append({"kind": "native-component-supply", "end": trace.count})
    states, _, _ = reference_states(numbers)
    for index, (number, bit) in enumerate(zip(numbers, states)):
        witness = witnesses[(number, bit)]
        local = witness["initial"].instantiate(FastNet())
        old_core = witness["core"]
        new_core = [rename[c] for c in built.stage_cells[index]]
        if len(old_core) != len(new_core):
            raise ValueError("local and contextual stage inventories differ")
        seed = dict(zip(old_core, new_core))
        # OUT's context endpoint is determined by the actual prewired wire.
        local_out = local.adj[("F", "CONTINUATION")]
        out_neighbor = whole.adj[(seed[local_out[0]], local_out[1])]
        boundary_map = {"CONTINUATION": out_neighbor,
                        "TASK_0_OUT": ("F", f"TASK_{index}_OUT"),
                        "STATUS_0": ("F", f"STATUS_{index}")}
        mapping = correspondence(local, whole, seed, boundary_map)
        phase_start = trace.count
        context_ids = set(whole.nodes) - set(mapping.values())
        context_kinds = {c: whole.nodes[c] for c in context_ids}
        context_wires = {port: neighbor for port, neighbor in whole.adj.items()
                         if port[0] in context_ids and neighbor[0] in context_ids}
        for pair in witness["pairs"]:
            if local.next_active() != pair:
                raise ValueError("local trace is not its frozen FIFO witness")
            mapped = tuple(mapping[c] for c in pair)
            if mapped not in whole.active():
                raise ValueError("lifted stage pair is not active")
            old_next, new_next = local.next, whole.next
            reduce(mapped)
            local.reduce(*pair)
            if local.next - old_next != whole.next - new_next:
                raise ValueError("local and contextual primitive allocations differ")
            for a, b in zip(range(old_next, local.next), range(new_next, whole.next)):
                mapping[f"c{a}"] = f"c{b}"
            del mapping[pair[0]], mapping[pair[1]]
        if local.active() or any(whole.nodes.get(c) != k for c, k in context_kinds.items()):
            raise ValueError("local trace did not terminate or altered context cells")
        if any(whole.adj.get(p) != q for p, q in context_wires.items()):
            raise ValueError("lifted witness altered an internal context wire")
        # Recheck every surviving local wire, including mapped context ports.
        correspondence(local, whole, mapping, boundary_map)
        phases.append({"kind": "lifted-local-stage", "index": index, "number": number,
                       "enabled": bit, "trace_offset_records": phase_start,
                       "primitive_interactions": trace.count - phase_start,
                       "local_initial_sha256": spec_digest(witness["initial"].to_dict()),
                       "context_cells": len(context_ids), "boundary_map": {k: list(v) for k, v in boundary_map.items()},
                       "initial_map_sha256": spec_digest(seed), "fresh_renaming_verified": True})
    # Remaining finishing and reserve cleanup interactions are still primitive.
    while whole.active():
        reduce(next(iter(whole.active())))
    target = expected(compiler, numbers, library)
    matched = port_graph_isomorphic(whole, target)
    resources = whole.statistics()
    final = GraphSpec.from_net(whole).to_dict()
    record = {"status": "passed" if matched else "wrong-normal-form", "numbers": list(numbers),
            "initial_graph_sha256": spec_digest(syntax.to_dict()),
            "trace_offset_records": start, "primitive_interactions": trace.count - start,
            "phases": phases, "resources": resources,
            "final_graph_sha256": spec_digest(final), "whole_graph_matches_reference": matched}
    if not matched:
        record["final_graph"] = final
        record["counterexample"] = {"initial": syntax.to_dict(), "actual": final,
                                    "expected": GraphSpec.from_net(target).to_dict(),
                                    "reason": "wrong-normal-form"}
    return record
