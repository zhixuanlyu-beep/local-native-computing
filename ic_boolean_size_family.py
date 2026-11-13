"""Size-only AND frameworks with separately plugged A-representation inputs.

Builders do not evaluate the task. Execution uses the original primitive IC
rules; scalar references and bounded schedule exploration are offline checks.
"""
from collections import Counter
import argparse
import hashlib
from itertools import product
import json
from ic_evidence_json import loads as json_loads
from pathlib import Path

from ic_bounded_execution import explore
from ic_observation_contracts import value_spec
from ic_primitive_port_verifier import Net, RULES, isomorphic
from ic_research_artifacts import GraphSpec
from lafont_ic_macro_builder import macro_connect


WIDTHS = (1, 2, 3, 4, 8, 16, 32, 64)
SHAPES = ("balanced", "left-comb")
POLICIES = ("first-active", "last-active", "snapshot-rounds")
EXHAUSTIVE_INPUT_WIDTH = 4
EXHAUSTIVE_SCHEDULE_WIDTH = 3
MAX_WIDTH = 64
MAX_STEPS = 512
MAX_CELLS = 127
EXPLORATION_BOUNDS = {"max_states": 256, "max_transitions": 2048, "max_cells": 16}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _validate_width(width):
    if type(width) is not int or not 1 <= width <= MAX_WIDTH:
        raise ValueError("width must be an integer in 1..64")


def build_framework(width, shape):
    """Build only from size and shape; gamma ports are LEFT=0, RIGHT=1, OUT=2.

    A is epsilon for false and a gamma auxiliary self-wire for true. A true
    LEFT annihilates the gate and passes RIGHT. A false LEFT erases RIGHT and
    leaves epsilon at OUT. No truth-table operation is performed by this code.
    """
    _validate_width(width)
    if shape not in SHAPES:
        raise ValueError("unknown framework shape")
    net = Net()
    inputs = [net.boundary(f"INPUT_{i}") for i in range(width)]

    def subtree(start, count):
        if count == 1:
            return inputs[start]
        gate = net.cell("g")
        left = count // 2 if shape == "balanced" else count - 1
        net.link(subtree(start, left), (gate, 0))
        net.link(subtree(start + left, count - left), (gate, 1))
        return gate, 2

    net.link(subtree(0, width), net.boundary("OUT"))
    net.check()
    if net.active() or len(net.nodes) != width - 1:
        raise AssertionError("framework must have n-1 dormant gamma gates")
    return GraphSpec.from_net(net)


def plug_inputs(framework, bits):
    """Instantiate immutable framework syntax; encode each supplied bit locally."""
    if not isinstance(framework, GraphSpec):
        raise TypeError("framework must be a GraphSpec")
    if type(bits) is not tuple or any(type(bit) is not bool for bit in bits):
        raise TypeError("inputs must be a tuple of exact Booleans")
    _validate_width(len(bits))
    if set(framework.boundaries) != {"OUT", *(f"INPUT_{i}" for i in range(len(bits)))}:
        raise ValueError("input length and framework interface differ")
    if (len(framework.kinds) != len(bits) - 1 or framework.cycles
            or any(kind != "g" for kind in framework.kinds)):
        raise ValueError("framework must contain n-1 gamma cells and no detached wire cycles")
    net = framework.instantiate()
    for i, bit in enumerate(bits):
        root = value_spec("A", bit).open_root(net)
        macro_connect(net, ("F", f"INPUT_{i}"), root)
    net.check()
    return net


def reference(bits):
    """Offline scalar oracle; never used by framework or input construction."""
    return all(bits)


def expected_output(bit):
    net = Net()
    value_spec("A", bit).instantiate(net, {"ROOT": net.boundary("OUT")})
    return net


def run_case(framework, bits, policy, *, max_steps=MAX_STEPS, max_cells=MAX_CELLS):
    if policy not in POLICIES:
        raise ValueError("unknown execution policy")
    for name, bound in (("max_steps", max_steps), ("max_cells", max_cells)):
        if type(bound) is not int or bound < 0:
            raise ValueError(name + " must be a nonnegative integer")
    net = plug_inputs(framework, bits)
    initial = GraphSpec.from_net(net)
    initial_cells, first_runtime_id = len(net.nodes), net.next
    peak = initial_cells
    census = Counter({"".join(rule): 0 for rule in RULES})
    pairs, widths = [], []
    status = "resource-violation" if initial_cells > max_cells else None
    while status is None:
        active = net.active()
        if not active:
            status = "terminal"
            break
        if len(pairs) >= max_steps:
            status = "interaction-cutoff"
            break
        if policy == "first-active":
            selected = active[:1]
        elif policy == "last-active":
            selected = active[-1:]
        else:
            selected = active
            widths.append(0)
        for a, b in selected:
            if len(pairs) >= max_steps:
                status = "interaction-cutoff"
                break
            kinds = net.nodes[a], net.nodes[b]
            rule = kinds if kinds in RULES else kinds[::-1]
            census["".join(rule)] += 1
            pairs.append([a, b])
            net.reduce(a, b)
            if policy == "snapshot-rounds":
                widths[-1] += 1
            peak = max(peak, len(net.nodes))
            if len(net.nodes) > max_cells:
                status = "resource-violation"
                break

    expected = expected_output(reference(bits))
    matches = status == "terminal" and isomorphic(net, expected)
    if status == "terminal":
        status = "passed" if matches else "incorrect-terminal"
    allocation = net.next - first_runtime_id
    work, final = len(pairs), len(net.nodes)
    predicted = initial_cells + sum(census["".join(rule)] * (len(rhs[0]) - 2)
                                    for rule, rhs in RULES.items())
    if predicted != final or initial_cells + allocation != final + 2 * work:
        raise AssertionError("primitive allocation balance differs from actual graph")
    if peak != initial_cells or any(net.nodes[c] not in ("g", "e") for c in net.nodes):
        raise AssertionError("gamma/epsilon execution unexpectedly grew or used delta")
    return {"inputs": list(bits), "framework_sha256": digest(framework.to_dict()),
            "policy": policy, "status": status,
            "bounds": {"max_steps": max_steps, "max_cells": max_cells},
            "initial_graph_sha256": digest(initial.to_dict()),
            "resources": {"initial_cells": initial_cells, "primitive_interactions": work,
                          "runtime_cells_allocated": allocation,
                          "total_symbolic_cells_allocated": initial_cells + allocation,
                          "peak_live_cells": peak, "final_cells": final,
                          "rule_census": dict(census)},
            "synchronous_rounds": len(widths) if policy == "snapshot-rounds" and status == "passed" else None,
            "round_widths": widths if policy == "snapshot-rounds" else None,
            "expected_bit": reference(bits), "whole_terminal_matches": matches,
            "final": GraphSpec.from_net(net).to_dict(), "primitive_pairs": pairs}


def input_cases(width):
    _validate_width(width)
    if width <= EXHAUSTIVE_INPUT_WIDTH:
        return tuple(product((False, True), repeat=width))
    return ((False,) * width, (True,) * width,
            tuple(i % 2 == 1 for i in range(width)),
            (False,) + (True,) * (width - 1),
            (True,) * (width - 1) + (False,))


def exploration_record(framework, bits, *, bounds=None):
    initial = plug_inputs(framework, bits)
    expected = expected_output(reference(bits))
    bounds = dict(EXPLORATION_BOUNDS if bounds is None else bounds)
    result = explore(initial, **bounds)
    matches = bool(result.terminal_ids) and all(isomorphic(result.states[i], expected)
                                               for i in result.terminal_ids)
    passed = result.complete and not result.cycle and matches
    return {"inputs": list(bits), "framework_sha256": digest(framework.to_dict()),
            "status": "passed" if passed else "not-accepted",
            "bounds": bounds, "all_terminal_graphs_match": matches, "exploration": result.summary()}


def negative_probes():
    framework = build_framework(4, "balanced")
    bits = (True,) * 4
    wrong = GraphSpec(("g",), ("INPUT_0", "INPUT_1", "OUT"),
                      ((("F", "OUT"), (0, 0)), (("F", "INPUT_0"), (0, 1)),
                       (("F", "INPUT_1"), (0, 2))))
    small = build_framework(2, "balanced")
    records = []
    fixtures = (
        ("zero-interaction-budget", framework, bits, {"max_steps": 0}, "interaction-cutoff"),
        ("partial-snapshot", framework, bits, {"max_steps": 1}, "interaction-cutoff"),
        ("initial-material-bound", framework, bits, {"max_cells": 6}, "resource-violation"),
        ("quiescent-wrong-output", wrong, (True, False), {}, "incorrect-terminal"),
    )
    for name, spec, values, bounds, expected_status in fixtures:
        record = run_case(spec, values, "snapshot-rounds", **bounds)
        if record["status"] != expected_status:
            raise AssertionError("negative probe classification changed")
        records.append({"probe": name, "framework": spec.to_dict(), "record": record})
    record = exploration_record(small, (True, True), bounds={
        "max_states": 1, "max_transitions": 0, "max_cells": 16})
    if record["status"] != "not-accepted" or record["exploration"]["complete"]:
        raise AssertionError("unfinished exploration was accepted")
    records.append({"probe": "exploration-budget", "framework": small.to_dict(), "record": record})
    return records


def source_digests():
    root = Path(__file__).resolve().parent
    names = ("ic_boolean_size_family.py", "ic_primitive_port_verifier.py",
             "ic_research_artifacts.py", "ic_observation_contracts.py",
             "lafont_ic_macro_builder.py", "ic_bounded_execution.py", "ic_evidence_json.py")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def build_report():
    frameworks, cases, explorations = [], [], []
    for width in WIDTHS:
        for shape in SHAPES:
            framework = build_framework(width, shape)
            spec = framework.to_dict()
            entry = {"width": width, "shape": shape, "spec": spec, "sha256": digest(spec),
                     "construction": {"cells": len(spec["kinds"]),
                                      "boundaries": len(spec["boundaries"]),
                                      "wires": len(spec["wires"]), "primitive_interactions": 0}}
            frameworks.append(entry)
            for bits in input_cases(width):
                policy_resources = []
                for policy in POLICIES:
                    case = run_case(framework, bits, policy)
                    if case["status"] != "passed":
                        raise AssertionError("declared positive case did not pass")
                    policy_resources.append(canonical(case["resources"]))
                    cases.append({"width": width, "shape": shape, **case})
                if len(set(policy_resources)) != 1:
                    raise AssertionError("selected policies disagree on gamma/epsilon resource census")
                if width <= EXHAUSTIVE_SCHEDULE_WIDTH:
                    record = exploration_record(framework, bits)
                    if record["status"] != "passed":
                        raise AssertionError("small schedule exploration not complete/correct")
                    explorations.append({"width": width, "shape": shape, **record})
    return {"format": "IC-BOOLEAN-SIZE-FAMILY-1", "source_sha256": source_digests(),
            "contract": {"task": "ordered AND fold on representation A",
                         "widths": list(WIDTHS), "shapes": list(SHAPES),
                         "policies": list(POLICIES), "exhaustive_inputs_through": EXHAUSTIVE_INPUT_WIDTH,
                         "exhaustive_schedules_through": EXHAUSTIVE_SCHEDULE_WIDTH,
                         "large_inputs": ["all-false", "all-true", "alternating-false-first",
                                          "only-first-false", "only-last-false"],
                         "bounds": {"max_steps": MAX_STEPS, "max_cells": MAX_CELLS},
                         "exploration_bounds": dict(EXPLORATION_BOUNDS),
                         "round_unit": "all pairs present at snapshot start; new pairs deferred",
                         "scope": "finite input/policy matrix; exhaustive schedules only in recorded small cases"},
            "frameworks": frameworks, "cases": cases, "explorations": explorations,
            "negative_probes": negative_probes()}


def verify_report(report):
    if canonical(report) != canonical(build_report()):
        raise ValueError("Boolean family report differs from independent reconstruction")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--report", type=Path)
    group.add_argument("--verify-report", type=Path)
    args = parser.parse_args()
    if args.verify_report:
        verify_report(json_loads(args.verify_report.read_text(encoding="utf-8")))
        print("PASS: exact Boolean-family report, primitive pairs and small schedule explorations")
        return
    report = build_report()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(canonical(report) + "\n", encoding="utf-8")
    print("PASS: %d size-only frameworks; %d concrete executions; %d complete small schedule explorations" %
          (len(report["frameworks"]), len(report["cases"]), len(report["explorations"])))
    print("LIMIT: larger widths use five declared inputs and three policies")


if __name__ == "__main__":
    main()
