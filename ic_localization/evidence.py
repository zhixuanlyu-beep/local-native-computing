"""M7 complete native execution, bounded foundations, and frozen bindings."""
import hashlib
from pathlib import Path
from time import perf_counter

from ic_bounded_execution import explore
from ic_coherent_feedback import spec_digest
from ic_coherent_output_decoder import port_graph_isomorphic
from ic_observation_contracts import value_spec
from ic_primitive_port_verifier import Net, RULES
from ic_research_artifacts import GraphSpec
from ic_schedule_audit import Schedule, ScheduledNet

VERSION = "M7-chain-localization-v1"
BUDGET = {"max_steps": 2_000_000, "max_cells": 250_000}
SMALL_BUDGET = {"max_states": 4096, "max_transitions": 32768, "max_cells": 128}
POLICIES = (Schedule(), Schedule("lifo"), Schedule("seeded", 17))
ROOT = Path(__file__).resolve().parents[1]


def expected_value(bit, label="OUT"):
    net = Net()
    value_spec("A", bit).instantiate(net, {"ROOT": net.boundary(label)})
    return GraphSpec.from_net(net)


def run_network(initial, expected, policy=POLICIES[0], *, trace=None, budget=None):
    started = perf_counter()
    limits = {**BUDGET, **(budget or {})}
    if set(limits) != set(BUDGET) or any(type(v) is not int or v < 0 for v in limits.values()):
        raise ValueError("invalid execution budget")
    net = initial.instantiate(ScheduledNet(policy))
    net.begin_audit()
    start = trace.count if trace is not None else None
    steps, status = 0, None
    if len(net.nodes) > limits["max_cells"]:
        status = "resource-exhausted"
    while status is None and net.active():
        if steps >= limits["max_steps"]:
            status = "incomplete"
            break
        pair = net.next_active()
        if trace is not None:
            trace.record(pair)
        net.reduce(*pair)
        steps += 1
        if len(net.nodes) > limits["max_cells"]:
            status = "resource-exhausted"
    execution_seconds = perf_counter() - started
    started = perf_counter()
    resources = net.statistics()
    census = resources["rule_census"]
    allocations = sum(census["".join(rule)] * len(rhs[0]) for rule, rhs in RULES.items())
    if (sum(census.values()) != steps or resources["primitive_interactions"] != steps
            or resources["runtime_cells_allocated"] != allocations
            or resources["initial_cells"] + allocations != resources["final_cells"] + 2 * steps):
        raise ValueError("primitive interaction and allocation accounts disagree")
    matches = not net.active() and port_graph_isomorphic(net, expected.instantiate())
    status = status or ("passed" if matches else "wrong-normal-form")
    initial_data, final_data = initial.to_dict(), GraphSpec.from_net(net).to_dict()
    result = {"status": status, "initial_graph_sha256": spec_digest(initial_data),
              "whole_graph_matches_reference": matches, "resources": resources,
              "final_graph_sha256": spec_digest(final_data),
              "host_seconds": {"native_execution": execution_seconds,
                               "validation": perf_counter()-started}}
    if trace is not None:
        result.update(trace_offset_records=start, trace_records=trace.count-start,
                      initial=initial_data, expected=expected.to_dict(), final=final_data)
    return result


def foundation_evidence(trace):
    from .backend import foundation_cases
    records = []
    for case in foundation_cases():
        initial, expected = case["initial"], case["expected"]
        exploration = explore(initial.instantiate(), **SMALL_BUDGET)
        matches = bool(exploration.terminal_ids) and all(
            port_graph_isomorphic(exploration.states[i], expected.instantiate())
            for i in exploration.terminal_ids)
        runs = [run_network(initial, expected, policy, trace=trace) for policy in POLICIES]
        accepted = exploration.complete and not exploration.cycle and matches and all(
            r["status"] == "passed" for r in runs)
        records.append({"name": case["name"], "status": "passed" if accepted else "not-accepted",
                        "exploration": exploration.summary(), "all_terminal_graphs_match": matches,
                        "runs": runs})
    if len(records) != 32:
        raise ValueError("foundation matrix must contain exactly 32 cases")
    return records


def frozen_bindings():
    from .model import ChainProblem, enumerate_transforms
    from .backend import foundation_cases
    sources = ["ic_primitive_port_verifier.py", "ic_fast_reducer.py", "ic_schedule_audit.py",
               "lafont_ic_macro_builder.py", "ic_research_artifacts.py", "ic_observation_contracts.py",
               "ic_coherent_output_decoder.py", "ic_bounded_execution.py", "ic_coherent_feedback.py",
               "ic_evidence_json.py",
               "ic_localization/__init__.py", "ic_localization/__main__.py",
               "ic_localization/model.py", "ic_localization/backend.py",
               "ic_localization/evidence.py", "ic_localization/report.py"]
    domains = []
    for n, count in ((2, 18), (3, 98)):
        problem = ChainProblem(n)
        transforms = list(enumerate_transforms(problem))
        if len(transforms) != count or len(set(transforms)) != count:
            raise ValueError("candidate space differs from frozen grammar")
        domains.append({"n": n, "inputs": [list(x) for x in problem.inputs()],
                        "candidates": [t.to_dict() for t in transforms]})
    return {"version": VERSION, "objective": "min_tau max_x complete FIFO primitive interactions",
            "grammar": {"direct": "lexicographic assignments; left-associated AND and OR",
                        "elimination": "all zero-based variable permutations; incident factors in ascending source ID; OR values 0 then 1",
                        "new_factor_ids": "n, n+1, ... in elimination order",
                        "materialization": "one Boolean for every complete generated table including the final table",
                        "representations": ["S", "P"], "implicit_cse": False,
                        "input_loading": "one literal per input slot; native delta fanout or epsilon erase"},
            "budget": BUDGET, "small_budget": SMALL_BUDGET,
            "policies": [p.to_dict() for p in POLICIES], "domains": domains,
            "expected_fifo_checks": 101504,
            "rules": [{"lhs": list(k), "rhs": v} for k, v in RULES.items()],
            "sources": {name: hashlib.sha256((ROOT/name).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
                        for name in sources},
            "components": [{"name": c["name"], "initial": c["initial"].to_dict(),
                            "expected": c["expected"].to_dict()} for c in foundation_cases()]}


def negative_evidence(trace):
    """Concrete wrong branch, residual cycle, early stop, and resource witnesses."""
    from .backend import literal, decode, validate_literal, _select, _a
    from lafont_ic_macro_builder import build_M, build_selector, macro_connect
    net = Net()
    decode(net, "S", literal(net, "S", False), net.boundary("OUT"))
    initial = GraphSpec.from_net(net)
    swapped = Net()
    wrong_port = _select(swapped, "S", literal(swapped, "S", True), _a(swapped, False), _a(swapped, True))
    macro_connect(swapped, wrong_port, swapped.boundary("OUT"))
    wrong = run_network(GraphSpec.from_net(swapped), expected_value(True), trace=trace)
    early = run_network(initial, expected_value(False), trace=trace, budget={"max_steps": 0})
    resource = run_network(initial, expected_value(False), trace=trace, budget={"max_cells": 0})
    cyclic = GraphSpec(initial.kinds, initial.boundaries, initial.wires, 1)
    cycle = run_network(cyclic, expected_value(False), trace=trace)
    malformed = Net()
    selector = build_selector(malformed, 2, 1)
    frame = build_M(malformed, 3)
    for slot, port in zip(frame.auxiliaries, ((malformed.cell("e"), 0),
                                            selector.principal, selector.auxiliaries[0])):
        macro_connect(malformed, slot, port)
    macro_connect(malformed, frame.principal, malformed.boundary("ROOT"))
    malformed = GraphSpec.from_net(malformed)
    try:
        validate_literal(malformed, "P")
        inconsistent = {"status": "unexpected-acceptance"}
    except ValueError:
        inconsistent = {"status": "precondition-rejected", "initial": malformed.to_dict(),
                        "reason": "P A=false disagrees with selector=true"}
    nonlinear = Net()
    port = literal(nonlinear, "S", True)
    decode(nonlinear, "S", port, nonlinear.boundary("OUT1"))
    try:
        decode(nonlinear, "S", port, nonlinear.boundary("OUT2"))
        omitted = {"status": "unexpected-acceptance"}
    except AssertionError:
        omitted = {"status": "precondition-rejected", "reason": "same linear port used twice without delta"}
    return {"wrong_truth_branch": wrong, "early_stop": early,
            "initial_resource_exhaustion": resource, "residual_bare_cycle": cycle,
            "inconsistent_P_views": inconsistent, "omitted_copy": omitted}
