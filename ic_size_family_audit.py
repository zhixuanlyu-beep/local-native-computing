"""Finite size-family audit using the unchanged literal primitive IC reducer.

Construction API calls, primitive work, atomic-state space, and synchronous
rounds have different units. This is tree-copy evidence, not a new compiler.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from ic_gamma_tree_copy_demo import build_shape, decode_tree
from ic_primitive_port_verifier import Net, RULES


LEAF_COUNTS = (1, 2, 3, 4, 8, 16, 32, 64)
SHAPES = ("balanced", "comb")
POLICIES = ("first-active", "snapshot-rounds")
MAX_LEAVES = 64


def family_shape(leaves, shape):
    """A fixed finite generator; n counts epsilon leaves, not descriptor bits."""
    if type(leaves) is not int or not 1 <= leaves <= MAX_LEAVES:
        raise ValueError("leaf count must be an integer in 1..64")
    if shape not in SHAPES:
        raise ValueError("unknown shape family")
    if leaves == 1:
        return ("e",)
    left = leaves // 2 if shape == "balanced" else 1
    return ("g", family_shape(left, shape), family_shape(leaves - left, shape))


class ConstructionNet(Net):
    """Count builder calls without changing Net's rewrite semantics."""
    def __init__(self):
        super().__init__()
        self.builder_calls = Counter(cell=0, boundary=0, link=0)
        self.constructing = True

    def cell(self, kind):
        if self.constructing:
            self.builder_calls["cell"] += 1
        return super().cell(kind)

    def boundary(self, label):
        if self.constructing:
            self.builder_calls["boundary"] += 1
        return super().boundary(label)

    def link(self, a, b):
        if self.constructing:
            self.builder_calls["link"] += 1
        return super().link(a, b)


def run_case(leaves, shape, policy):
    if policy not in POLICIES:
        raise ValueError("unknown policy")
    reference = family_shape(leaves, shape)
    net = ConstructionNet()
    root = build_shape(net, reference)
    copier = net.cell("d")
    net.link((root, 0), (copier, 0))
    outputs = [net.boundary(label) for label in ("left", "right")]
    for port, boundary in enumerate(outputs, 1):
        net.link((copier, port), boundary)
    net.check()
    net.constructing = False
    initial, built_ids = len(net.nodes), net.next
    construction = {"graph_api_calls": dict(net.builder_calls),
                    "cells": initial, "boundaries": len(net.free),
                    "wires": len(net.adj) // 2,
                    "primitive_interactions": 0}
    census = Counter({"".join(rule): 0 for rule in RULES})
    trace, widths = [], []
    peak = initial
    while True:
        pairs = net.active()
        if not pairs:
            break
        if policy == "first-active":
            pairs = pairs[:1]
        else:
            widths.append(len(pairs))
        # New pairs wait until the next snapshot. Distinct current pairs have
        # disjoint cells; Net.reduce still validates each selected pair.
        for a, b in pairs:
            kinds = (net.nodes[a], net.nodes[b])
            rule = kinds if kinds in RULES else kinds[::-1]
            census["".join(rule)] += 1
            trace.append([a, b])
            net.reduce(a, b)
            peak = max(peak, len(net.nodes))

    seen = set()
    for boundary in outputs:
        if decode_tree(net, boundary, seen) != reference:
            raise AssertionError("copy does not match the ordered input tree")
    if seen != set(net.nodes) or net.cycles != 0:
        raise AssertionError("unobserved cells or cyclic wires in terminal graph")
    work = len(trace)
    runtime_allocation = net.next - built_ids
    total_allocation = initial + runtime_allocation
    final = len(net.nodes)
    # Independent tree combinatorics and primitive-rule inventory checks.
    if (initial, work, runtime_allocation, total_allocation, final, peak) != (
            2 * leaves, 2 * leaves - 1, 6 * leaves - 4,
            8 * leaves - 4, 4 * leaves - 2, 4 * leaves - 2):
        raise AssertionError("tree-copy resource formula mismatch")
    if census["gd"] != leaves - 1 or census["de"] != leaves:
        raise AssertionError("unexpected primitive census")
    if sum(census.values()) != work or total_allocation != final + 2 * work:
        raise AssertionError("allocation balance mismatch")
    if policy == "snapshot-rounds":
        expected_rounds = (leaves - 1).bit_length() + 1 if shape == "balanced" else leaves
        if len(widths) != expected_rounds or sum(widths) != work:
            raise AssertionError("synchronous round formula mismatch")
    return {"leaves": leaves, "shape": shape, "policy": policy,
            "input_tree_cells": 2 * leaves - 1,
            "construction": construction,
            "execution": {"primitive_interactions": work,
                          "runtime_cells_allocated": runtime_allocation,
                          "total_symbolic_cells_allocated": total_allocation,
                          "peak_live_cells": peak, "final_cells": final,
                          "rule_census": dict(census),
                          "synchronous_rounds": len(widths) if widths else None,
                          "round_widths": widths if widths else None},
            "readout": {"visited_cells": len(seen), "ordered_copies": 2,
                        "whole_graph_accounted_for": True},
            "primitive_pairs": trace}


def source_digests():
    root = Path(__file__).resolve().parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("ic_size_family_audit.py", "ic_gamma_tree_copy_demo.py",
                         "ic_primitive_port_verifier.py")}


def build_report():
    return {"format": "IC-SIZE-FAMILY-1", "source_sha256": source_digests(),
            "contract": {
                "leaf_counts": list(LEAF_COUNTS), "shapes": list(SHAPES),
                "policies": list(POLICIES), "primitive_rule_count": len(RULES),
                "size_unit": "epsilon leaves in a full binary gamma/epsilon input tree",
                "build_unit": "host graph API calls; not host time or native reductions",
                "space_unit": "cells at initial/post-atomic-rewrite states; not host bytes",
                "round_unit": "all pairs active at snapshot start, new pairs deferred",
                "scope": "finite structural tree families; no arbitrary-input or all-schedule claim"},
            "cases": [run_case(n, shape, policy) for n in LEAF_COUNTS
                      for shape in SHAPES for policy in POLICIES]}


def canonical(report):
    return json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False)


def verify_report(report):
    # Rebuild, rerun the actual primitive rules, recheck the complete graph and
    # compare every field, pair and source binding, including JSON value types.
    if canonical(report) != canonical(build_report()):
        raise ValueError("size-family report differs from independent reconstruction")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--report", type=Path)
    group.add_argument("--verify-report", type=Path)
    args = parser.parse_args()
    if args.verify_report:
        verify_report(json.loads(args.verify_report.read_text(encoding="utf-8")))
        print("PASS: exact size-family report, source bindings and primitive pairs")
        return
    report = build_report()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for case in report["cases"]:
        if case["policy"] == "snapshot-rounds":
            e = case["execution"]
            print("n={leaves:2d} {shape:8s} I={initial:3d} W={work:3d} P={peak:3d} rounds={rounds:2d}".format(
                **case, initial=case["construction"]["cells"], work=e["primitive_interactions"],
                peak=e["peak_live_cells"], rounds=e["synchronous_rounds"]))
    print("PASS: %d finite native tree-copy cases" % len(report["cases"]))


if __name__ == "__main__":
    main()
