"""Bounded synthesis of literal IC carriers and conditional retain/erase gates.

The input is a declared Boolean observation contract, not a source-rule table.
The finite search pairs small, reduced gamma/epsilon carriers with every
one-cell gamma/delta/epsilon port matching on CTRL, DATA, OUT.  Runtime steps
are exclusively Net.reduce.  This is bounded graph synthesis, not a general
compiler or an algorithm for arbitrary problem semantics.
"""
from dataclasses import asdict, dataclass
from itertools import product
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path

from ic_primitive_port_verifier import AR, Net, isomorphic, pairings
from ic_signed_branch_pruning import HOLE, package
from ic_research_artifacts import GraphSpec
from ic_bounded_execution import explore


@dataclass(frozen=True)
class SearchBudget:
    """Construction family, material bound, and algorithm budgets are separate."""
    carrier_cells: int = 3
    gate_cells: int = 1
    live_cells: int = 64
    screening_steps: int = 80
    reachable_states: int = 256
    transitions: int = 2048


EMPTY = (("e",), ())
LOOP = (("g", HOLE, HOLE), ((0, 1),))
TREE = (("g", ("e",), ("g", ("e",), ("e",))), ())
WIRED = (("g", ("g", HOLE, HOLE), ("g", HOLE, HOLE)),
         ((0, 2), (1, 3)))
TRAINING = (("epsilon", EMPTY), ("loop", LOOP))
HOLDOUT = (("tree", TREE), ("cross-wired", WIRED))
CONSUMERS = ("retain", "copy", "erase", "unpack")


def spec_id(spec):
    raw = json.dumps(spec.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def connected(net):
    """Construction-time connectedness check, not an IC-cell capability."""
    vertices = set(net.nodes) | set(net.free)
    graph = {v: set() for v in vertices}
    for x, y in net.adj.items():
        a = x if x in net.free else x[0]
        b = y if y in net.free else y[0]
        graph[a].add(b)
    if not vertices:
        return True
    seen, todo = set(), [next(iter(vertices))]
    while todo:
        v = todo.pop()
        if v not in seen:
            seen.add(v)
            todo.extend(graph[v] - seen)
    return seen == vertices


def carrier_candidates(max_cells=3):
    """Enumerate connected reduced one-root g/e nets, up to exact isomorphism.

    ROOT must meet a principal port.  Odd cell counts follow from port parity.
    The first cell is the root cell; all remaining port matchings are tried.
    No Loop or other successful truth protocol is privileged by the generator.
    """
    if type(max_cells) is not int or max_cells < 1:
        raise ValueError("carrier_cells must be a positive integer")
    representatives = []
    syntax_count = 0
    for count in range(1, max_cells + 1, 2):
        for kinds in product(("e", "g"), repeat=count):
            ports = [(i, p) for i, kind in enumerate(kinds)
                     for p in range(AR[kind] + 1) if (i, p) != (0, 0)]
            for matching in pairings(ports):
                wires = ((("F", "ROOT"), (0, 0)),) + tuple(matching)
                spec = GraphSpec(tuple(kinds), ("ROOT",), wires)
                net = spec.instantiate()
                syntax_count += 1
                if net.active() or not connected(net):
                    continue
                if any(isomorphic(net, old) for _, old in representatives):
                    continue
                representatives.append((spec, net))
    return [s for s, _ in representatives], syntax_count


def gate_candidates():
    """Every one-cell IC graph with the three distinct declared boundaries."""
    result = []
    for kind in ("e", "g", "d"):
        ports = [(0, p) for p in range(AR[kind] + 1)]
        ports += [("F", label) for label in ("CTRL", "DATA", "OUT")]
        for matching in pairings(ports):
            spec = GraphSpec((kind,), ("CTRL", "DATA", "OUT"),
                             tuple(matching))
            spec.validate()
            result.append(spec)
    return result


def false_carrier():
    return GraphSpec(("e",), ("ROOT",),
                     ((("F", "ROOT"), (0, 0)),))


def attach_consumer(net, root, consumer, prefix="OUT"):
    """Prewire a consumer; no observations are used to choose runtime steps."""
    if consumer == "retain":
        net.link(root, net.boundary(prefix))
    elif consumer == "copy":
        d = net.cell("d")
        net.link(root, (d, 0))
        for p in (1, 2):
            net.link((d, p), net.boundary(prefix + str(p)))
    elif consumer == "erase":
        net.link(root, (net.cell("e"), 0))
    elif consumer == "unpack":
        g = net.cell("g")
        net.link(root, (g, 0))
        net.link((g, 1), net.boundary(prefix + "_1"))
        net.link((g, 2), net.boundary(prefix + "_2"))
    else:
        raise ValueError("unknown consumer: " + consumer)


def build(gate, true_carrier, bit, description, consumer="retain"):
    """Encode the supplied input object; do not precompute its task output."""
    if bit not in (False, True):
        raise ValueError("the information objects are Boolean")
    net = Net()
    token = (true_carrier if bit else false_carrier()).open_root(net)
    payload, ids, _ = package(net, *description)
    # A temporary build-time boundary permits the same gate interface to be
    # attached to any declared consumer without changing its internal wiring.
    output = net.boundary("GATE_OUTPUT")
    gate.instantiate(net, {"CTRL": token, "DATA": payload, "OUT": output})
    neighbor = net.adj.pop(output)
    net.free.remove(output)
    net.adj[neighbor] = None
    attach_consumer(net, neighbor, consumer)
    net.check()
    return net, ids


def expected(bit, description, consumer="retain"):
    """Independent output specification; never used by the runtime builder."""
    net = Net()
    chosen = description if bit else EMPTY
    if consumer == "erase":
        return net
    if consumer in ("retain", "copy"):
        names = ("OUT",) if consumer == "retain" else ("OUT1", "OUT2")
        for name in names:
            net.link(package(net, *chosen)[0], net.boundary(name))
    elif consumer == "unpack":
        # Independently inspect only the provided package construction syntax:
        # a gamma consumer swaps constructor auxiliaries; epsilon yields two e.
        root, _, _ = package(net, *chosen)
        c, p = root
        if net.nodes[c] == "e":
            del net.nodes[c]
            del net.adj[(c, 0)]
            for index in (1, 2):
                net.link((net.cell("e"), 0), net.boundary("OUT_" + str(index)))
        else:
            children = [net.adj[(c, p)] for p in (2, 1)]
            if children == [(c, 1), (c, 2)]:
                # Loop's two auxiliary ports join the two output boundaries.
                for p in range(3):
                    del net.adj[(c, p)]
                del net.nodes[c]
                net.link(net.boundary("OUT_1"), net.boundary("OUT_2"))
            else:
                for child in children:
                    if child[0] == c:
                        raise ValueError("unsupported root self-wire in reference")
                    net.adj[child] = None
                for p in range(3):
                    del net.adj[(c, p)]
                del net.nodes[c]
                for index, child in enumerate(children, 1):
                    net.link(child, net.boundary("OUT_" + str(index)))
    else:
        raise ValueError(consumer)
    net.check()
    if net.active():
        raise ValueError("reference consumer requires a reduced rooted package")
    return net


def screen(initial, target, budget):
    """A failed concrete run is a witness; a passed run is only screening."""
    net = copy.deepcopy(initial)
    trace = []
    peak = len(net.nodes)
    while net.active():
        if len(trace) >= budget.screening_steps:
            return "incomplete", net, trace, peak
        pair = net.active()[0]
        trace.append(list(pair))
        net.reduce(*pair)
        peak = max(peak, len(net.nodes))
        if len(net.nodes) > budget.live_cells:
            return "resource-violation", net, trace, peak
    return ("pass" if isomorphic(net, target) else "wrong-normal-form"), net, trace, peak


def witness(initial, actual, target, trace, case, reason):
    """Keep a replayable concrete initial graph, redex trace and observation."""
    return {"reason": reason, "case": case,
            "initial": GraphSpec.from_net(initial).to_dict(),
            "trace": [list(pair) for pair in trace],
            "actual": GraphSpec.from_net(actual).to_dict(),
            "expected": GraphSpec.from_net(target).to_dict()}


def verify_case(gate, carrier, bit, description, consumer, budget):
    initial, _ = build(gate, carrier, bit, description, consumer)
    # Execute from this exact serialized syntax so saved traces replay even if
    # the serializer chooses a different order from the original builder.
    initial = GraphSpec.from_net(initial).instantiate()
    target = expected(bit, description, consumer)
    case = {"bit": bool(bit), "consumer": consumer}
    status, actual, trace, peak = screen(initial, target, budget)
    if status in ("wrong-normal-form", "resource-violation"):
        return {"status": "rejected", "witness": witness(
            initial, actual, target, trace, case, status)}
    result = explore(initial, max_states=budget.reachable_states,
                     max_transitions=budget.transitions, max_cells=budget.live_cells)
    for state_id in result.terminal_ids:
        actual = result.states[state_id]
        if not isomorphic(actual, target):
            return {"status": "rejected", "witness": witness(
                initial, actual, target, result.trace_to(state_id), case,
                "wrong-normal-form")}
    if not result.complete:
        return {"status": "inconclusive", "exploration": result.summary()}
    if result.cycle:
        return {"status": "rejected", "reason": "reachable-infinite-execution",
                "initial": GraphSpec.from_net(initial).to_dict(),
                "exploration": result.summary()}
    if not result.terminal_ids:
        raise AssertionError("a complete finite acyclic execution graph needs a terminal")
    return {"status": "verified", "case": case,
            "exploration": result.summary(), "screening_peak": peak}


def synthesize(budget=None):
    budget = budget or SearchBudget()
    if budget.gate_cells != 1:
        raise ValueError("this explicitly bounded family has exactly one gate cell")
    materials, syntax_count = carrier_candidates(budget.carrier_cells)
    gates = gate_candidates()
    false_net = false_carrier().instantiate()
    records, survivors = [], []
    for material in materials:
        material_key = spec_id(material)
        for gate in gates:
            record = {"material": material_key, "gate": spec_id(gate), "cases": []}
            if isomorphic(material.instantiate(), false_net):
                record.update(status="rejected-storage",
                              reason="false and true carriers coincide in isolated storage")
            else:
                record["status"] = "verified"
                for name, description in TRAINING:
                    for bit in (False, True):
                        case = verify_case(gate, material, bit, description, "retain", budget)
                        case["payload"] = name
                        record["cases"].append(case)
                        if case["status"] != "verified":
                            record["status"] = case["status"]
                            break
                    if record["status"] != "verified":
                        break
            records.append(record)
            if record["status"] == "verified":
                survivors.append((gate, material))
    report = {
        "contract": {
            "information_objects": [False, True],
            "false_carrier": false_carrier().to_dict(),
            "observation": "exact OUT normal form: payload if true, epsilon if false; no extra cells/cycles",
            "visible": ["complete normal-form topology with labeled output boundaries", "cyclic-wire count"],
            "hidden": ["cell names", "redex order"],
            "allowed_environments": {"consumers": list(CONSUMERS), "payloads": [n for n, _ in TRAINING + HOLDOUT]},
            "initial_discovery_probes": {"consumer": "retain", "payloads": [n for n, _ in TRAINING]},
            "scheduling": "all maximal primitive reductions for completely explored finite cases; no fairness filter",
            "resource_bound": {"peak_live_cells": budget.live_cells},
            "readiness": "quiescent exact output; no claim of a local completion token",
        },
        "search_budget": asdict(budget),
        "candidate_accounting": {"raw_carrier_matchings": syntax_count,
                                 "unique_reduced_connected_carriers": len(materials),
                                 "gate_matchings": len(gates),
                                 "joint_candidates": len(records)},
        "materials": [{"id": spec_id(s), "graph": s.to_dict()} for s in materials],
        "gates": [{"id": spec_id(s), "graph": s.to_dict()} for s in gates],
        "candidates": records,
        "survivors": [{"gate": spec_id(g), "material": spec_id(m)} for g, m in survivors],
    }
    assert survivors, "no verified candidate in the declared family and budget"
    return survivors, report


def validate_survivors(survivors, report, budget=None):
    """Refine the initial probe classes within the fixed declared environment.

    The held-out cases were not used by initial screening.  A counterexample
    rejects an overfit candidate, rather than weakening or changing E.
    """
    budget = budget or SearchBudget(reachable_states=4096, transitions=32768)
    report["context_refinement_budget"] = asdict(budget)
    results, verified = [], []
    report["initial_survivors"] = list(report["survivors"])
    by_key = {(r["gate"], r["material"]): r for r in report["candidates"]}
    for gate, material in survivors:
        record = by_key[(spec_id(gate), spec_id(material))]
        accepted = True
        for name, description in TRAINING + HOLDOUT:
            for bit, consumer in product((False, True), CONSUMERS):
                result = verify_case(gate, material, bit, description, consumer, budget)
                case = {"gate": spec_id(gate), "material": spec_id(material),
                        "payload": name, "phase": "context-refinement", **result}
                results.append(case)
                record["cases"].append(case)
                if result["status"] != "verified":
                    record["initial_status"] = record["status"]
                    record["status"] = result["status"]
                    accepted = False
                    break
            if not accepted:
                break
        if accepted:
            verified.append((gate, material))
    report["survivors"] = [{"gate": spec_id(g), "material": spec_id(m)} for g, m in verified]
    assert verified, "no candidate satisfies the full finite environment contract"
    def interface_features(gate, material):
        attached = {}
        for a, b in gate.wires:
            if a[0] == "F" and b[0] != "F":
                attached[a[1]] = b
            elif b[0] == "F" and a[0] != "F":
                attached[b[1]] = a
        return {
            "one_gamma_gate": gate.kinds == ("g",),
            "control_at_principal": attached.get("CTRL") == (0, 0),
            "data_and_output_at_auxiliaries": {attached.get("DATA"), attached.get("OUT")} == {(0, 1), (0, 2)},
            "true_is_single_self_paired_gamma": material.kinds == ("g",) and
                any({a, b} == {(0, 1), (0, 2)} for a, b in material.wires),
        }
    features = [interface_features(g, m) for g, m in verified]
    report["refinement"] = {
        "environment_unchanged": True,
        "initial_probe_coordinates": len(TRAINING) * 2,
        "full_probe_coordinates": len(TRAINING + HOLDOUT) * 2 * len(CONSUMERS),
        "forgetting_map": "project full observation vectors onto retain with the initial training payloads",
        "shared_constraints_of_verified_candidates": [key for key in features[0]
                                                        if all(f[key] for f in features)],
        "scope": "the enumerated finite family, not necessary constraints for arbitrary IC implementations",
    }
    return verified, results


def verify_saved_witnesses(report):
    """Re-execute recorded counterexamples, independently of candidate search."""
    count = 0
    payloads = dict(TRAINING + HOLDOUT)
    gates = {entry["id"]: GraphSpec.from_dict(entry["graph"]) for entry in report["gates"]}
    materials = {entry["id"]: GraphSpec.from_dict(entry["graph"]) for entry in report["materials"]}
    for record in report["candidates"]:
        for case in record["cases"]:
            w = case.get("witness")
            if w is None:
                continue
            net = GraphSpec.from_dict(w["initial"]).instantiate()
            bit, consumer = w["case"]["bit"], w["case"]["consumer"]
            description = payloads[case["payload"]]
            independently_built, _ = build(gates[record["gate"]], materials[record["material"]],
                                            bit, description, consumer)
            assert isomorphic(net, independently_built)
            independent_target = expected(bit, description, consumer)
            assert isomorphic(independent_target, GraphSpec.from_dict(w["expected"]).instantiate())
            for pair in w["trace"]:
                assert tuple(pair) in net.active() or tuple(reversed(pair)) in net.active()
                net.reduce(*pair)
            assert isomorphic(net, GraphSpec.from_dict(w["actual"]).instantiate())
            target = GraphSpec.from_dict(w["expected"]).instantiate()
            if w["reason"] == "wrong-normal-form":
                assert not net.active() and not isomorphic(net, target)
            elif w["reason"] == "resource-violation":
                assert len(net.nodes) > report["contract"]["resource_bound"]["peak_live_cells"]
            else:
                raise AssertionError(w["reason"])
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    survivors, report = synthesize()
    survivors, report["context_refinement"] = validate_survivors(survivors, report)
    report["replayed_counterexamples"] = verify_saved_witnesses(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        args.report.write_bytes(gzip.compress(encoded, mtime=0) if args.report.suffix == ".gz" else encoded)
    print("PASS: bounded native IC synthesis", report["candidate_accounting"])
    print("PASS: initial survivors", len(report["initial_survivors"]),
          "refined survivors", len(survivors), "context cases",
          len(report["context_refinement"]), "replayed counterexamples",
          report["replayed_counterexamples"])
    print("LIMIT: declared finite family and contexts only; coherent source coverage unchanged")


if __name__ == "__main__":
    main()
