"""Finite typed source-context refinement audit for the coherent compiler."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from ic_fast_reducer import FastNet
from ic_coherent_output_decoder import port_graph_isomorphic
from source_feedback_audit import AR, RULES
from source_rule_audit_v3 import PORTS
from source_ic_coherent_compiler import (
    CoherentICCompiler, reduce_compiled, source_rule_lhs, source_rule_rhs,
)


def _unary_source(types, adjacency, value, prefix):
    """Append S^n(Z), expose its principal port, and return the source cell name."""
    if type(value) is not int or value < 0:
        raise ValueError(value)
    if value == 0:
        name = f"{prefix}-Z"
        types[name] = "Z"
        adjacency[(name, 0)] = None
        return name
    names = []
    for index in range(value):
        name = f"{prefix}-S{index}"
        names.append(name)
        types[name] = "S"
        adjacency[(name, 0)] = None
        adjacency[(name, 1)] = None
    terminal = f"{prefix}-Z"
    types[terminal] = "Z"
    adjacency[(terminal, 0)] = None
    for index, name in enumerate(names):
        child = names[index + 1] if index + 1 < len(names) else terminal
        adjacency[(name, 1)] = (child, 0)
        adjacency[(child, 0)] = (name, 1)
    return names[0]


def _attach_unary(types, adjacency, boundary, value, prefix):
    source = _unary_source(types, adjacency, value, prefix)
    target = adjacency.pop(boundary)
    del adjacency[target]
    adjacency[target] = None
    adjacency[(source, 0)] = target
    adjacency[target] = (source, 0)


def _input_labels(spec):
    first, second = spec[:2]
    result = []
    for side, symbol in (("A", first), ("B", second)):
        for port in range(1, AR[symbol] + 1):
            direction, semantic = PORTS[symbol][port]
            if direction == "in" and semantic == "N":
                result.append((f"{side}{port}", semantic))
    return result


def _visible_boundary_types(spec):
    first, second = spec[:2]
    result = {}
    for side, symbol in (("A", first), ("B", second)):
        for port in range(1, AR[symbol] + 1):
            label = f"{side}{port}"
            result[label] = list(PORTS[symbol][port])
    return result


def _input_vectors(labels):
    if not labels:
        return [()]
    count = len(labels)
    if count > 3:
        raise AssertionError((labels, "only 0..3 typed N inputs are supported"))
    return [tuple(index % 3 for index in range(count)),
            tuple((index + 2) % 3 for index in range(count))]


def _build_context(compiler, spec, vector):
    types, adjacency = source_rule_lhs(spec)
    labels = [label for label, _ in _input_labels(spec)]
    if len(vector) != len(labels):
        raise AssertionError((labels, vector))
    for label, value in zip(labels, vector):
        _attach_unary(types, adjacency, ("F", label), value, prefix=label)
    return compiler.compile(types, adjacency, net_class=FastNet)


def _build_rhs_context(compiler, spec, vector):
    types, adjacency = source_rule_rhs(spec)
    labels = [label for label, _ in _input_labels(spec)]
    if len(vector) != len(labels):
        raise AssertionError((labels, vector))
    for label, value in zip(labels, vector):
        _attach_unary(types, adjacency, ("F", label), value, prefix=label)
    return compiler.compile(types, adjacency, net_class=FastNet)


def run_contexts(compiler=None, rules=None):
    compiler = compiler or CoherentICCompiler()
    rules = rules or list(RULES.values())
    records = []
    for spec in rules:
        key = "-".join(spec[:2])
        inputs = _input_labels(spec)
        all_ports = _visible_boundary_types(spec)
        passive_non_n_inputs = {
            label: kind for label, kind in all_ports.items()
            if kind[0] == "in" and kind[1] != "N"
        }
        assert not passive_non_n_inputs, (key, passive_non_n_inputs)
        visible = _visible_boundary_types(spec)
        for vector in _input_vectors(inputs):
            left = _build_context(compiler, spec, vector)
            right = _build_rhs_context(compiler, spec, vector)
            initial_cells = len(left.nodes)
            left_stats = reduce_compiled(left)
            right_stats = reduce_compiled(right)
            matched = port_graph_isomorphic(left, right)
            records.append({
                "rule": key,
                "input_vector": list(vector),
                "input_labels": [label for label, _ in inputs],
                "passive_non_n_inputs": passive_non_n_inputs,
                "source_interface_types": visible,
                "initial_cells": initial_cells,
                "left_native": left_stats,
                "right_native": right_stats,
                "final_match": matched,
            })
            if not matched:
                raise AssertionError((key, vector, left_stats, right_stats))
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verify-report", type=Path,
                        default=Path(__file__).with_name("results") / "coherent_context_cases.json.gz")
    args = parser.parse_args()
    records = run_contexts()
    if not args.report:
        encoded = args.verify_report.read_bytes()
        saved = json.loads(gzip.decompress(encoded) if args.verify_report.suffix == ".gz" else encoded)
        assert records == saved, "finite-context results differ from the archived evidence"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(records, indent=2, sort_keys=True) + chr(10)).encode("utf-8")
        if args.report.suffix == ".gz":
            encoded = gzip.compress(encoded, mtime=0)
        args.report.write_bytes(encoded)
    print("PASS: coherent typed finite-context refinement cases", len(records))
    print("SCOPE: passive outputs and bounded unary inputs; not arbitrary-context equivalence")


if __name__ == "__main__":
    main()
