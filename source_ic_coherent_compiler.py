"""Coherent literal IC compilation of the fixed source feedback rule system.

This implements the general Fig.10 construction from Lafont 1997.  The
source rule table is consulted only when constructing the finite genetic
package Gamma. Runtime reductions use gamma/delta/epsilon alone.

Gamma_i is COLUMN i: Gamma_(1,i) & ... & Gamma_(m,i).  The transpositor
exchanges a peer column and a symbol selector.  Thus a source interaction
(i,j) obtains half Gamma_(i,j) at the i-side frame, not Gamma_(j,i).
"""
from collections import Counter
from dataclasses import dataclass
import argparse
import json
from ic_evidence_json import loads as json_loads
from pathlib import Path

from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec
from ic_package_codec import build_decoder, encode_package, validate_package
from lafont_ic_macro_builder import (
    Macro, build_C_n, build_M, build_M_star, build_menu, build_selector,
    build_T_sigma, macro_connect,
)
from source_feedback_audit import AR, RULES


@dataclass(frozen=True)
class ExtendedCell:
    principal: tuple
    auxiliaries: tuple
    code_port: tuple


class CoherentICCompiler:
    def __init__(self):
        self.symbols = tuple(AR)
        self.arity = dict(AR)
        self.index = {symbol: index + 1 for index, symbol in enumerate(self.symbols)}
        self.width = len(self.symbols)
        source = json_loads(Path(__file__).with_name("lafont_15_rules_phi_psi_split.json").read_text(encoding="utf-8"))
        self.entries = {}
        for rule in source["rules"]:
            first, second = rule["lhs"]
            if rule["sigma"]["permutation"] != "identity":
                raise ValueError("this source split explicitly uses identity cross-strand permutations")
            self.entries[(first, second)] = (rule["phi"], rule["sigma"]["width"])
            self.entries[(second, first)] = (rule["psi"], rule["sigma"]["width"])
        if set(self.entries) != {(a, b) for spec in RULES.values()
                                  for a, b in (spec[:2], spec[:2][::-1])}:
            raise ValueError("the supplied split must cover exactly the source rule pairs")
        self.column_specs = {}
        for peer in self.symbols:
            column = Net()
            values = [self._half_package(column, owner, peer) for owner in self.symbols]
            menu = build_menu(column, values)
            macro_connect(column, menu.principal, column.boundary("ROOT"))
            validate_package(column)
            self.column_specs[peer] = GraphSpec.from_net(column)
        self.program = Net()
        roots = [self.column_specs[symbol].open_root(self.program) for symbol in self.symbols]
        program_root = build_menu(self.program, roots).principal
        macro_connect(self.program, program_root, self.program.boundary("ROOT"))
        validate_package(self.program)
        self.code = encode_package(self.program, label="ROOT")
        self.code_spec = GraphSpec.from_net(self.code)
        self._templates = {}

    def _frame_and_control(self, net, symbol):
        frame = build_M(net, self.arity[symbol] + 2)
        selector = build_selector(net, self.width, self.index[symbol])
        transpositor = build_T_sigma(net, {1: 2, 2: 1, 3: 3})
        macro_connect(net, selector.auxiliaries[0], frame.principal)
        macro_connect(net, selector.principal, transpositor.auxiliaries[1])
        macro_connect(net, frame.auxiliaries[-1], transpositor.auxiliaries[2])
        return frame, transpositor

    def _extension(self, net, symbol):
        """A literal <alpha> with one extra genetic-code input, no recursion."""
        frame, transpositor = self._frame_and_control(net, symbol)
        decoder = build_decoder(net)
        column_selector = build_selector(net, self.width, self.index[symbol])
        code_fan = net.cell("d")
        macro_connect(net, (code_fan, 1), decoder.principal)
        macro_connect(net, (code_fan, 2), frame.auxiliaries[0])
        macro_connect(net, decoder.auxiliaries[0], column_selector.principal)
        macro_connect(net, column_selector.auxiliaries[0], transpositor.auxiliaries[0])
        return ExtendedCell(transpositor.principal, frame.auxiliaries[1:-1], (code_fan, 0))

    def _half_package(self, net, owner, peer):
        entry = self.entries.get((owner, peer))
        if entry is None:
            return (net.cell("e"), 0)
        half, crossing = entry
        frame = build_M_star(net, self.arity[owner] + 2)
        cells = {name: self._extension(net, info["type"])
                 for name, info in half["nodes"].items()}
        copier = build_C_n(net, [cell.code_port for cell in cells.values()])
        cross = build_T_sigma(net, {index: index for index in range(1, crossing + 1)})
        macro_connect(net, frame.auxiliaries[0], copier.principal)
        macro_connect(net, frame.auxiliaries[-1], cross.principal)
        interfaces = dict(zip(half["boundary"], frame.auxiliaries[1:-1]))
        interfaces.update(zip(half["cuts"], cross.auxiliaries))

        def endpoint(label):
            if label in interfaces:
                return interfaces[label]
            name, number = label.rsplit(".", 1)
            cell, port = cells[name], int(number)
            return cell.principal if port == 0 else cell.auxiliaries[port - 1]
        for a, b in half["edges"]:
            macro_connect(net, endpoint(a), endpoint(b))
        return frame.principal

    def lower_symbol(self, net, symbol):
        """One consistent source-cell encoding with its ordered source ports."""
        frame, transpositor = self._frame_and_control(net, symbol)
        macro_connect(net, frame.auxiliaries[0], self.code_spec.open_root(net))
        macro_connect(net, transpositor.auxiliaries[0], self.column_specs[symbol].open_root(net))
        return Macro(transpositor.principal, frame.auxiliaries[1:-1])

    def symbol_template(self, symbol):
        if symbol not in self._templates:
            net = Net()
            cell = self.lower_symbol(net, symbol)
            macro_connect(net, cell.principal, net.boundary("P0"))
            for port, endpoint in enumerate(cell.auxiliaries, 1):
                macro_connect(net, endpoint, net.boundary("P" + str(port)))
            net.check()
            if net.active():
                raise AssertionError("a source symbol must have a reduced target template")
            self._templates[symbol] = GraphSpec.from_net(net)
        return self._templates[symbol].instantiate()

    def compile(self, types, adjacency, *, net_class=Net, boundary_labels=None):
        expected_ports = {(cell, p) for cell, kind in types.items() for p in range(self.arity[kind] + 1)}
        external = {endpoint for endpoint in adjacency if endpoint[0] not in types}
        if set(adjacency) != expected_ports | external:
            raise ValueError("source interface has missing or extra cell ports")
        if any(endpoint == other or other not in adjacency or adjacency[other] != endpoint
               for endpoint, other in adjacency.items()):
            raise ValueError("source wires must be a complete matching")
        if boundary_labels is None:
            boundary_labels = {ep: (str(ep[1]) if ep[0] == "F" else
                                    str(ep[0]) if ep[1] == 0 else repr(ep)) for ep in external}
        if set(boundary_labels) != external or len(set(boundary_labels.values())) != len(external):
            raise ValueError("each source boundary needs a distinct target label")
        net = net_class()
        lowered = {name: self.lower_symbol(net, kind) for name, kind in types.items()}
        boundaries = {ep: net.boundary(label) for ep, label in boundary_labels.items()}

        def port(endpoint):
            name, number = endpoint
            if name not in lowered:
                return boundaries[endpoint]
            cell = lowered[name]
            return cell.principal if number == 0 else cell.auxiliaries[number - 1]
        used = set()
        for a, b in adjacency.items():
            if a not in used:
                macro_connect(net, port(a), port(b))
                used.update((a, b))
        net.check()
        return net

    def statistics(self):
        return {"symbols": len(self.symbols), "rules": len(RULES),
                "decoded_program": dict(Counter(self.program.nodes.values())),
                "encoded_program": dict(Counter(self.code.nodes.values())),
                "program_cells": len(self.program.nodes), "code_cells": len(self.code.nodes)}


def source_rule_lhs(spec):
    first, second = spec[:2]
    types = {"A": first, "B": second}
    adjacency = {(name, p): None for name, kind in types.items() for p in range(AR[kind] + 1)}
    adjacency[("A", 0)], adjacency[("B", 0)] = ("B", 0), ("A", 0)
    for name in ("A", "B"):
        for p in range(1, AR[types[name]] + 1):
            boundary = ("F", name + str(p))
            adjacency[(name, p)] = boundary
            adjacency[boundary] = (name, p)
    return types, adjacency


def source_rule_rhs(spec):
    _, _, types, edges, interface = spec
    adjacency = {(name, p): None for name, kind in types.items() for p in range(AR[kind] + 1)}
    for left, lp, right, rp in edges:
        adjacency[(left, lp)], adjacency[(right, rp)] = (right, rp), (left, lp)
    for label, endpoint in interface.items():
        boundary = ("F", label)
        adjacency[boundary], adjacency[endpoint] = endpoint, boundary
    if any(other is None for other in adjacency.values()):
        raise AssertionError("literal source RHS has unmatched ports")
    return dict(types), adjacency


def reduce_compiled(net, limit=10_000_000, progress=None, trace=None):
    steps, peak = 0, len(net.nodes)
    while net.active():
        if steps >= limit:
            raise RuntimeError(f"IC reduction budget exhausted at {steps} steps")
        redex = net.next_active() if hasattr(net, "next_active") else net.active()[0]
        if trace is not None:
            trace.record(redex)
        net.reduce(*redex)
        steps += 1
        peak = max(peak, len(net.nodes))
        if progress and steps % progress == 0:
            print(f"IC progress: {steps} reductions, {len(net.nodes)} live cells", flush=True)
    net.check()
    return {"primitive_interactions": steps, "peak_live_cells": peak,
            "final_cells": len(net.nodes), "cyclic_wires": net.cycles,
            "schedule": "FIFO indexed active pairs" if hasattr(net, "next_active") else "first active pair"}


def certify_rule(compiler, spec, *, net_class=Net, trace=None):
    from ic_coherent_output_decoder import port_graph_isomorphic
    left = compiler.compile(*source_rule_lhs(spec), net_class=net_class)
    right = compiler.compile(*source_rule_rhs(spec))
    initial = len(left.nodes)
    if right.active():
        raise AssertionError("source RHS is supposed to compile to a reduced graph")
    stats = reduce_compiled(left, trace=trace)
    if not port_graph_isomorphic(left, right):
        raise AssertionError((spec[:2], "compiled RHS mismatch", stats))
    return {"rule": "-".join(spec[:2]), "initial_cells": initial, **stats}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule", help="certify one literal source rule, e.g. INIT-Z")
    parser.add_argument("--all-rules", action="store_true")
    args = parser.parse_args()
    compiler = CoherentICCompiler()
    print(json.dumps(compiler.statistics(), sort_keys=True), flush=True)
    if args.rule or args.all_rules:
        from ic_fast_reducer import FastNet
        for spec in RULES.values():
            if args.all_rules or args.rule == "-".join(spec[:2]):
                print(json.dumps(certify_rule(compiler, spec, net_class=FastNet), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
