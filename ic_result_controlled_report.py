"""Bound, independently reconstructible M6 reports and raw pair archives."""
import argparse
from itertools import product
from pathlib import Path

from ic_coherent_feedback import read_json, write_json, spec_digest
from ic_result_controlled_execution import (
    CONTRACT, DOMAIN, BUDGET, cases, build_result_sequence, reference_states, expected,
)
from ic_result_controlled_composition import build_local, local_expected, PairList, staged_case
from ic_result_controlled_evidence import run_case, POLICIES
from ic_result_controlled_library import load_control_library
from ic_result_controlled_trace import M6Trace as ScheduleTrace
from ic_research_artifacts import GraphSpec
from source_feedback_audit import run as source_run
from source_ic_coherent_compiler import CoherentICCompiler
from ic_native_control_packets import protocol_evidence, validate_control_packet
from ic_observation_contracts import value_spec


ROOT = Path(__file__).parent


def inputs(library_path):
    library, compiler = load_control_library(library_path), CoherentICCompiler()
    source = {}
    for n in DOMAIN:
        result = reference_states([n])[1][0]
        actual = source_run(n)[1]
        if tuple(actual) != tuple(result):
            raise ValueError("independent source reference disagrees")
        source[str(n)] = list(actual)
    matrix = read_json(ROOT / "docs/M6_ACCEPTANCE_MATRIX.json")
    if matrix["execution_budget"] != BUDGET or matrix["local_numbers"] != list(DOMAIN):
        raise ValueError("frozen acceptance matrix differs from implementation")
    fixed_cases = ([[n] for n in matrix["single_numbers"]]
                   + [list(pair) for pair in product(matrix["ordered_pair_domain"], repeat=2)]
                   + matrix["triples"])
    if [case["numbers"] for case in cases()] != fixed_cases or any(
            matrix[key] != CONTRACT[key] for key in ("max_input", "max_tasks", "reader_depth")):
        raise ValueError("sequence set or interface bounds differ from the frozen acceptance matrix")
    if [(p.policy, p.seed) for p in POLICIES] != [(p["policy"], p.get("seed")) for p in matrix["policies"]]:
        raise ValueError("schedule set differs from the frozen acceptance matrix")
    bound = {"contract": CONTRACT, "acceptance_matrix": matrix, "cases": cases(),
             "local_cases": [{"number": n, "enabled": bit} for n in DOMAIN for bit in (False, True)],
             "policies": [p.to_dict() for p in POLICIES],
             "library": library.provenance, "program": compiler.code_spec.to_dict(),
             "program_sha256": spec_digest(compiler.code_spec.to_dict()),
             "source_reference": source}
    return library, compiler, bound


def _suite(trace_path, library_path, *, replay=False, context=None, replay_counts=None,
           parallel=True):
    library, compiler, bound = context or inputs(library_path)
    metadata = {"scope": "M6 result-controlled complete programs and actual local-stage lifts",
                "bindings_sha256": spec_digest(bound)}
    trace = ScheduleTrace(trace_path, metadata, replay=replay)
    locals_, records, staged, witnesses = [], [], [], {}
    try:
        control = protocol_evidence(trace)
        for case in bound["local_cases"]:
            n, bit = case["number"], case["enabled"]
            built = build_local(n, bit, library, compiler)
            tee = PairList(trace)
            record = run_case(built, local_expected(n, bit, library, compiler), tee,
                              POLICIES[0], expected_states=[bit])
            record["case"] = case
            locals_.append(record)
            witnesses[(n, bit)] = {"initial": GraphSpec.from_net(built.net),
                                   "core": built.stage_cells[0], "pairs": tee.pairs}
            print("LOCAL", n, bit, record["status"], record["primitive_interactions"], flush=True)
        if parallel and len(bound["cases"]) > 1:
            from ic_result_controlled_parallel import run_parallel
            records, staged = run_parallel(bound["cases"], library, compiler, witnesses,
                                            metadata, trace, replay_counts=replay_counts)
        else:
            for case in bound["cases"]:
                numbers = case["numbers"]
                states = reference_states(numbers)[0]
                for policy in POLICIES:
                    built = build_result_sequence(numbers, library=library, compiler=compiler)
                    record = run_case(built, expected(compiler, numbers, library), trace, policy,
                                      expected_states=states)
                    record.update({"case": case, "reference_states": states})
                    records.append(record)
                    print("CASE", case["name"], policy.policy, record["status"], record["primitive_interactions"], flush=True)
                record = staged_case(numbers, library, compiler, witnesses, trace)
                staged.append(record)
                print("LIFT", case["name"], record["status"], record["primitive_interactions"], flush=True)
        negative = negative_probes(library, compiler, trace)
    except BaseException:
        trace.abort()
        raise
    summary = trace.close()
    positive = control + locals_ + records + staged
    accepted = (all(r["status"] == "passed" for r in positive)
                and negative["wrong_control_encoding"]["status"] == "precondition-rejected"
                and negative["Gamma_data_as_program"]["status"] == "precondition-rejected"
                and negative["shallow_reader"]["status"] == "wrong-normal-form"
                and negative["premature_handoff"]["status"] == "protocol-violation"
                and negative["premature_handoff"]["whole_graph_matches_reference"])
    return {"format": "ic-result-controlled-v1", "bindings": bound, "metadata": metadata,
            "control_cases": control, "local_cases": locals_, "cases": records, "staged": staged,
            "negative_probes": negative, "trace": summary,
            "status": "passed" if accepted else "not-accepted"}


def negative_probes(library, compiler, trace):
    rejected = {}
    for label, candidate, validator in (
            ("wrong_control_encoding", value_spec("B", True), validate_control_packet),
            ("Gamma_data_as_program", GraphSpec.from_net(compiler.program), library.require_program_code)):
        try:
            validator(candidate)
        except ValueError as error:
            rejected[label] = {"status": "precondition-rejected", "candidate": candidate.to_dict(),
                               "reason": str(error)}
        else:
            rejected[label] = {"status": "unexpectedly-admitted", "candidate": candidate.to_dict()}
    shallow = build_result_sequence([1], library=library, compiler=compiler, reader_depth=0)
    shallow_record = run_case(shallow, expected(compiler, [1], library), trace,
                              POLICIES[0], expected_states=[True])
    premature = build_result_sequence([1], library=library, compiler=compiler)
    # Change just the readiness selector menu, leaving the Boolean A enable
    # input true. Input 1 emits SQ, so the skip progress gives the same final
    # true control. Only causality distinguishes this from a correct run.
    cell = premature.stages[0]["ready_menu"]
    a, b = (cell, 1), (cell, 2)
    left, right = premature.net.adj[a], premature.net.adj[b]
    for port in (a, b, left, right):
        premature.net.adj[port] = None
    premature.net.link(a, right)
    premature.net.link(b, left)
    premature.net.check()
    premature_record = run_case(premature, expected(compiler, [1], library), trace,
                                POLICIES[0], expected_states=[True])
    return {**rejected, "shallow_reader": shallow_record, "premature_handoff": premature_record}


def compare_report(report, rebuilt):
    if spec_digest(report) != spec_digest(rebuilt):
        raise ValueError("M6 report differs from reconstructed primitive evidence")
    if rebuilt["status"] != "passed":
        raise ValueError("M6 evidence is reproducible but not accepted")
    return len(rebuilt["cases"])


def verify_report(report, trace_path, library_path):
    if report.get("format") != "ic-result-controlled-v1":
        raise ValueError("unknown M6 report format")
    context = inputs(library_path)
    if spec_digest(report.get("bindings")) != spec_digest(context[2]):
        raise ValueError("M6 contract/library/program binding mismatch")
    count = len(context[2]["cases"])
    rows, staged = report.get("cases", []), report.get("staged", [])
    if len(rows) != count * len(POLICIES) or len(staged) != count:
        raise ValueError("saved report does not cover the frozen complete matrix")
    counts = []
    for index in range(count):
        sizes = [r.get("primitive_interactions") for r in rows[index * 3:(index + 1) * 3]]
        sizes.append(staged[index].get("primitive_interactions"))
        if any(type(size) is not int or size < 0 for size in sizes):
            raise ValueError("invalid saved trace interval")
        counts.append(sum(sizes))
    return compare_report(report, _suite(trace_path, library_path, replay=True, context=context,
                                         replay_counts=counts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--report", type=Path)
    group.add_argument("--verify-report", type=Path)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    args = parser.parse_args()
    if args.verify_report:
        verify_report(read_json(args.verify_report), args.trace, args.library)
    else:
        report = _suite(args.trace, args.library)
        write_json(args.report, report)
        if report["status"] != "passed":
            raise SystemExit("NOT ACCEPTED: original failures preserved")
    print("PASS: M6 finite result-driven execution; scope in docs/CLAIM_LEDGER.md")


if __name__ == "__main__":
    main()
