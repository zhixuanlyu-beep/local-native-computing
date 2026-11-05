"""M3 finite composition witnesses, schedule comparisons and resource ledgers.

Written lemmas are separate from these executable finite certificates. Every
runtime rewrite is the original primitive IC interaction; source evaluation,
independent expected graphs and structural readout are verifier operations.
"""
from collections import Counter
import argparse
import hashlib
from pathlib import Path

from ic_coherent_feedback import read_json, write_json, spec_digest
from ic_coherent_output_decoder import port_graph_isomorphic, decode_source
from ic_composition_examples import macro_cases, bad_delta_copy
from ic_primitive_port_verifier import RULES as PRIMITIVE_RULES, isomorphic
from ic_program_code_bridge import load_discovery
from ic_program_suspension import suspend_feedback
from ic_research_artifacts import GraphSpec
from ic_rule_trace_lifting import (frozen_certificates, lift_all_rules, frame_context,
                                   translated_witness_pair, CERTIFICATE_HASHES)
from ic_safe_program_activation import build_sequence, expected as activation_expected, run_case as run_activation
from ic_schedule_audit import Schedule, ScheduledNet, ScheduleTrace
from source_feedback_audit import RULES as SOURCE_RULES
from source_ic_coherent_compiler import CoherentICCompiler, source_rule_lhs
import ic_typed_programs as typed


ROOT = Path(__file__).parent
POLICIES = (Schedule("fifo"), Schedule("lifo"), Schedule("seeded", 17))
BUDGET = {"max_steps": 2_000_000, "max_cells": 250_000}
M2_SHA256 = "589c1a3e49411e8304d31ee2790eaab414dcb1ba5da1bb1d51183c1760efcb50"
CONTRACT = {
    "environment": "E_composition-v1",
    "runtime": "original six primitive interactions; pair selection only is extended",
    "schedules": [p.to_dict() for p in POLICIES], "per_case_budget": BUDGET,
    "typed_programs": "bounded Nat/Check/Copy/Erase/Compare/Fanout/Parallel syntax; exact port typing",
    "expected": "independent source constructor diagrams compiled literally; entire labeled port graph including cycles",
    "lifting": "frozen local rule witnesses translated through fixed gamma boundary frames; context redexes deferred",
    "resource_unit": "symbolic cells at initial and post-atomic-interaction states; no host byte memory claim",
    "independence": "lineage projections only for syntactically disjoint Parallel parts",
    "proof_boundary": "written abstract arguments and conditional compiler simulation; finite implementation evidence separately recorded",
    "activation_scope": "selected prewired M2 sequences, first frozen gate/carrier pair; native readiness is constructor recognition",
}


def typed_cases():
    return [typed.Check(n) for n in (0, 1, 2)] + [typed.Copy(n) for n in (0, 2)] + [typed.Erase(2)] + [
        typed.Compare(n, m) for n, m in ((0, 0), (0, 1), (1, 0), (1, 2), (1, 1))] + [
        typed.Fanout(1, "check", "erase"), typed.Fanout(0, "check", "check"),
        typed.Parallel((typed.Check(0), typed.Copy(1)))]


def activation_cases():
    return [{"numbers": ns, "flags": bs} for ns, bs in (
        ([0], [True]), ([2, 0], [True, True]), ([1, 0], [False, True]),
        ([1, 2, 0], [True, False, True]))]


def full_match(left, right):
    """Linear rooted comparison, with exact closed-component fallback for tiny nets."""
    if port_graph_isomorphic(left, right):
        return True
    return len(left.nodes) <= 128 and len(right.nodes) <= 128 and isomorphic(left, right)


def execute(initial, target, schedule, trace, *, owners=None, max_steps=2_000_000, max_cells=250_000):
    if any(type(v) is not int or v < 0 for v in (max_steps, max_cells)):
        raise ValueError("execution bounds must be non-negative integers")
    syntax = GraphSpec.from_net(initial)
    running = syntax.instantiate(ScheduledNet(schedule))
    if owners is not None:
        owners = {new: owners[old] for old, new in zip(initial.nodes, running.nodes)}
    running.begin_audit(owners)
    start, steps = trace.count, 0
    while True:
        if len(running.nodes) > max_cells:
            status = "resource-violation"
            break
        active = running.next_active()
        if active is None:
            status = "passed" if full_match(running, target) else "wrong-normal-form"
            break
        if steps >= max_steps:
            status = "incomplete"
            break
        trace.record(active)
        running.reduce(*active)
        steps += 1
    resources = running.statistics()
    final = GraphSpec.from_net(running).to_dict()
    record = {"status": status, "schedule": schedule.to_dict(), "trace_offset_records": start,
              "primitive_interactions": steps, "initial_graph_sha256": spec_digest(syntax.to_dict()),
              "expected_graph_sha256": spec_digest(GraphSpec.from_net(target).to_dict()),
              "final_graph": final, "final_graph_sha256": spec_digest(final),
              "terminal": not bool(running.active()), "whole_graph_matches_reference": full_match(running, target),
              "resources": resources}
    if status != "passed":
        record["counterexample"] = {"initial": syntax.to_dict(), "expected": GraphSpec.from_net(target).to_dict(),
                                    "actual": final, "reason": status}
    return record


def compile_diagram(compiler, diagram):
    return compiler.compile(diagram.types, diagram.adjacency,
                            boundary_labels={endpoint: str(endpoint[1]) for endpoint in diagram.adjacency
                                             if endpoint[0] not in diagram.types})


def _source_equal(left, right):
    """Exact source graph check with labeled boundaries and ordered ports."""
    import networkx as nx
    if hasattr(left, "boundary_types") and hasattr(right, "boundary_types") and dict(left.boundary_types) != dict(right.boundary_types):
        return False
    def graph(diagram):
        g = nx.Graph()
        for name, kind in diagram.types.items():
            g.add_node(("cell", name), kind="cell:" + kind)
        for endpoint in diagram.adjacency:
            if endpoint[0] in diagram.types:
                g.add_node(("port", endpoint), kind="port:" + str(endpoint[1]))
                g.add_edge(("cell", endpoint[0]), ("port", endpoint))
            else:
                g.add_node(("port", endpoint), kind="boundary:" + str(endpoint[1]))
        for a, b in diagram.adjacency.items():
            g.add_edge(("port", a), ("port", b))
        return g
    return nx.is_isomorphic(graph(left), graph(right), node_match=lambda a, b: a["kind"] == b["kind"])


def source_witness_bound(compiler, reference, certificates):
    by_name = {record["rule"]: record for record in certificates["certificates"]}
    sizes = {kind: len(compiler.symbol_template(kind).nodes) for kind in compiler.symbols}
    costs, peaks, census = [], [], Counter()
    for step in reference.rule_trace:
        cert = by_name[step["rule"]]
        first, second = step["rule"].split("-")
        footprint = sum(sizes[k] * n for k, n in step["before_symbols"].items())
        costs.append(cert["primitive_interactions"])
        census.update(cert["rule_census"])
        peaks.append(footprint - sizes[first] - sizes[second] + cert["peak_live_cells"])
    return {"predicted_primitive_interactions": sum(costs),
            "predicted_primitive_rule_census": dict(census),
            "constructive_staged_peak_bound": max(peaks, default=sum(sizes[k] for k in reference.types.values())),
            "source_rule_census": dict(Counter(step["rule"] for step in reference.rule_trace)),
            "source_steps": reference.source_steps,
            "source_trace": reference.rule_trace,
            "scope": "forward-simulation witness bound; staged peak need not bound other interleavings"}


def compiled_owners(compiler, ast, diagram, initial):
    source_owners = typed.cell_owners(ast)
    if set(source_owners) != set(diagram.types):
        raise AssertionError("source ownership does not cover the literal program")
    for a, b in diagram.adjacency.items():
        if a[0] in diagram.types and b[0] in diagram.types and source_owners[a[0]] != source_owners[b[0]]:
            raise ValueError("declared independent source components are wired together")
    names, offset, owners = list(initial.nodes), 0, {}
    # compile() lowers types in insertion order, allocating each complete
    # template before the next. Check the contiguous kind sequence as well
    # as its size before relying on that implementation-specific partition.
    for source_name, kind in diagram.types.items():
        template = compiler.symbol_template(kind)
        size = len(template.nodes)
        if [initial.nodes[name] for name in names[offset:offset + size]] != list(template.nodes.values()):
            raise AssertionError("compiler allocation order differs from the ownership partition")
        for name in names[offset:offset + size]:
            owners[name] = source_owners[source_name]
        offset += size
    if offset != len(names):
        raise AssertionError("compiled template footprints do not partition the initial graph")
    return owners


def renaming_probe(compiler, trace):
    """A stale source-witness ID is rejected before any wrong pair is executed."""
    rule = next(iter(SOURCE_RULES.values()))
    old = compiler.compile(*source_rule_lhs(rule), net_class=ScheduledNet)
    built = compiler.compile(*source_rule_lhs(rule))
    core_count = len(built.nodes)
    frame_context(built)
    initial = GraphSpec.from_net(built)
    new = initial.instantiate(ScheduledNet(Schedule("witness")))
    rename = dict(zip(old.nodes, list(new.nodes)[:core_count]))
    start = trace.count
    while active := old.next_active():
        if trace.count - start >= BUDGET["max_steps"] or len(new.nodes) > BUDGET["max_cells"]:
            raise ValueError("fresh-renaming probe exceeded its fixed evidence budget")
        mapped = translated_witness_pair(active, rename, new)
        if mapped != active:
            try:
                translated_witness_pair(active, rename, new, proposed=active)
            except ValueError:
                pass
            else:
                raise AssertionError("stale witness IDs were accepted")
            final = GraphSpec.from_net(new).to_dict()
            return {"status": "rejected-stale-renaming", "rule": "-".join(rule[:2]),
                    "trace_offset_records": start, "primitive_interactions": trace.count - start,
                    "initial_graph_sha256": spec_digest(initial.to_dict()),
                    "stale_pair": list(active), "required_renamed_pair": list(mapped),
                    "stale_pair_happens_to_be_active": active in new.active(),
                    "terminal": not bool(new.active()), "final_graph": final,
                    "resources": new.statistics(),
                    "scope": "valid contextual prefix; attempted unrenamed next witness pair rejected"}
        old_next, new_next = old.next, new.next
        trace.record(mapped)
        new.reduce(*mapped)
        old.reduce(*active)
        for a, b in zip(range(old_next, old.next), range(new_next, new.next)):
            rename["c" + str(a)] = "c" + str(b)
        del rename[active[0]], rename[active[1]]
    raise AssertionError("renaming probe failed to encounter fresh certificate cells")


def inputs():
    if CONTRACT["schedules"] != [policy.to_dict() for policy in POLICIES]:
        raise ValueError("runtime schedules differ from the trace-bound contract")
    compiler = CoherentICCompiler()
    discovery, pairs = load_discovery()
    certs = frozen_certificates(compiler)
    if hashlib.sha256((ROOT / "results/safe_program_activation.json.gz").read_bytes()).hexdigest() != M2_SHA256:
        raise ValueError("frozen M2 evidence changed")
    cases = typed_cases()
    # Reject malformed representations and inconsistent verifier inputs before
    # opening a native trace. Source evaluation is verification, never runtime.
    for ast in cases:
        typed.build_program(ast)
        if not _source_equal(typed.source_reference(ast), typed.expected_diagram(ast)):
            raise ValueError("independent typed source expectations disagree before execution")
    macros = macro_cases(compiler)
    bound = {"contract": CONTRACT, "contract_sha256": spec_digest(CONTRACT),
             "compiler": compiler.statistics(), "program_code_sha256": spec_digest(compiler.code_spec.to_dict()),
             "discovery": discovery, "m2_report_sha256": M2_SHA256, "local_certificates": CERTIFICATE_HASHES,
             "typed_cases": [typed.to_dict(ast) for ast in cases], "activation_cases": activation_cases(),
             "grammar_bounds": {key: getattr(typed, key) for key in
                                ("MAX_NAT_DEPTH", "MAX_PARALLEL_TASKS", "MAX_AST_NODES", "MAX_AST_DEPTH")},
             "primitive_rules": [{"lhs": list(k), "rhs_kinds": v[0], "wires": v[1]} for k, v in PRIMITIVE_RULES.items()],
             "macros": [{"name": c["name"], "initial_sha256": spec_digest(GraphSpec.from_net(c["initial"]).to_dict()),
                         "expected_sha256": spec_digest(GraphSpec.from_net(c["expected"]).to_dict()),
                         "expected_interactions": c["expected_interactions"], "hypothesis": c["hypothesis"]} for c in macros]}
    return compiler, pairs, certs, cases, macros, bound


def _suite(trace_path, replay=False, context=None):
    compiler, pairs, certs, cases, macros, bound = context or inputs()
    metadata = {"scope": "M3 compositional IC finite evidence", "bindings_sha256": spec_digest(bound)}
    trace = ScheduleTrace(trace_path, metadata, replay)
    macro_records, programs, activations = [], [], []
    try:
        for case in macros:
            for schedule in POLICIES:
                record = execute(case["initial"], case["expected"], schedule, trace, **BUDGET)
                record.update({"name": case["name"], "hypothesis": case["hypothesis"],
                               "predicted_interactions": case["expected_interactions"]})
                if record["status"] == "passed" and case["expected_interactions"] is not None and record["primitive_interactions"] != case["expected_interactions"]:
                    record["status"] = "cost-formula-violation"
                    record["counterexample"] = {"initial": GraphSpec.from_net(case["initial"]).to_dict(),
                                                "expected": GraphSpec.from_net(case["expected"]).to_dict(),
                                                "actual": record["final_graph"], "reason": record["status"]}
                macro_records.append(record)
                print("MACRO", case["name"], schedule.policy, record["status"], flush=True)
        lifted = lift_all_rules(compiler, trace, **BUDGET)
        lifted_by_rule = {record["rule"]: record for record in lifted}
        certs = {**certs, "certificates": [
            {**record, "rule_census": lifted_by_rule[record["rule"]]["resources"]["rule_census"]}
            for record in certs["certificates"]]}
        for index, ast in enumerate(cases):
            diagram = typed.build_program(ast)
            reference = typed.source_reference(ast)
            independent = typed.expected_diagram(ast)
            if not _source_equal(reference, independent):
                raise ValueError("source oracle disagrees with independent typed constructor result")
            initial, target = compile_diagram(compiler, diagram), compile_diagram(compiler, independent)
            owners = compiled_owners(compiler, ast, diagram, initial)
            witness = source_witness_bound(compiler, reference, certs)
            for schedule in POLICIES:
                record = execute(initial, target, schedule, trace, owners=owners, **BUDGET)
                record.update({"case": index, "program": typed.to_dict(ast), "source_witness": witness})
                if record["status"] == "passed" and (record["primitive_interactions"] != witness["predicted_primitive_interactions"] or
                        record["resources"]["rule_census"] != witness["predicted_primitive_rule_census"]):
                    record["status"] = "source-cost-violation"
                if record["status"] == "passed":
                    from types import SimpleNamespace
                    decoded_types, decoded_adjacency = decode_source(GraphSpec.from_dict(record["final_graph"]).instantiate(), compiler)
                    typed.validate_source_graph(decoded_types, decoded_adjacency, independent.boundary_types)
                    record["structural_readout_matches_source_reference"] = _source_equal(
                        SimpleNamespace(types=decoded_types, adjacency=decoded_adjacency), independent)
                    if not record["structural_readout_matches_source_reference"]:
                        record["status"] = "structural-readout-violation"
                if record["status"] != "passed" and "counterexample" not in record:
                    record["counterexample"] = {"initial": GraphSpec.from_net(initial).to_dict(),
                                                "expected": GraphSpec.from_net(target).to_dict(),
                                                "actual": record["final_graph"], "reason": record["status"]}
                programs.append(record)
                print("TYPED", index, schedule.policy, record["status"], flush=True)
        suspensions = {n: suspend_feedback(compiler, n) for n in (0, 1, 2)}
        for index, case in enumerate(activation_cases()):
            built = build_sequence(*pairs[0], case["numbers"], case["flags"], compiler=compiler, suspensions=suspensions)
            target = activation_expected(compiler, case["numbers"], case["flags"])
            for schedule in POLICIES:
                running = []
                def factory():
                    net = ScheduledNet(schedule)
                    running.append(net)
                    return net
                record = run_activation(built, target, trace, net_factory=factory, **BUDGET)
                record.update({"case": index, "input": case, "gate_pair": 0,
                               "schedule": schedule.to_dict(), "resources": running[0].statistics()})
                activations.append(record)
                print("ACTIVATION", index, schedule.policy, record["status"], flush=True)
        bad = bad_delta_copy()
        negative = execute(bad["initial"], bad["expected"], Schedule(), trace, **BUDGET)
        negative["scope"] = "delta-bearing data violates primitive-copy precondition; bypass tested deliberately"
        renaming = renaming_probe(compiler, trace)
        peak_records = [r for r in activations if r["case"] == 0]
        comparable = len(peak_records) == len(POLICIES) and all(
            r["status"] == "passed" and r["whole_graph_matches_reference"] for r in peak_records)
        peaks = {r["schedule"]["policy"]: r["resources"]["peak_live_cells"] for r in peak_records}
        work = {r["primitive_interactions"] for r in peak_records}
        peak_probe = {"status": "refuted" if comparable and len(set(peaks.values())) > 1 and len(work) == 1 else "not-refuted",
                      "claim": "equal terminal graph and interaction count imply equal peak live cells",
                      "activation_case": 0, "peak_live_cells": peaks, "primitive_interactions": sorted(work)}
    except BaseException:
        trace.abort()
        raise
    summary = trace.close()
    accepted = (all(r["status"] == "passed" for r in macro_records + programs + activations)
                and all(r["status"] == "matched-prefix" for r in lifted)
                and negative["status"] == "wrong-normal-form"
                and renaming["status"] == "rejected-stale-renaming" and peak_probe["status"] == "refuted")
    return {"format": "ic-composition-certificates-v1", "bindings": bound, "metadata": metadata,
            "status": "passed" if accepted else "not-accepted", "macro_cases": macro_records,
            "contextual_rule_prefixes": lifted, "typed_programs": programs, "activations": activations,
            "negative_probes": {"delta_copy_precondition": negative, "fresh_renaming": renaming,
                                "schedule_independent_peak": peak_probe}, "trace": summary,
            "limitations": ["written lemmas concern the abstract port-graph calculus; finite tests do not prove all Python executions correct",
                            "context frames demonstrate selected lifted prefixes, not arbitrary-context observational equivalence",
                            "selected finite schedules and bounded source syntax; no exhaustive large-network schedule exploration",
                            "symbolic interaction/cell accounting; no physical finite stock, host-memory bound, or demonstrated reuse benefit"]}


def compare_report(report, rebuilt):
    if spec_digest(report) != spec_digest(rebuilt):
        raise ValueError("composition report differs from reconstructed raw primitive evidence")
    if rebuilt["status"] != "passed":
        raise ValueError("reproducible composition evidence does not satisfy the frozen contract")
    return len(rebuilt["typed_programs"])


def verify_report(report, trace_path):
    if report.get("format") != "ic-composition-certificates-v1":
        raise ValueError("unknown composition report format")
    context = inputs()
    if spec_digest(report.get("bindings")) != spec_digest(context[-1]):
        raise ValueError("composition contract or input binding mismatch")
    return compare_report(report, _suite(trace_path, True, context))


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
        report = _suite(args.trace)
        write_json(args.report, report)
        if report["status"] != "passed":
            raise SystemExit("NOT ACCEPTED: incomplete/failed evidence preserved")
    print("PASS: M3 evidence; measured coverage and boundaries in docs/CLAIM_LEDGER.md")


if __name__ == "__main__":
    main()
