"""Literal delta-cut package code and decoder (Lafont 1997, Figs. 8-9).

For a principal reduced one-root package pi, remove its n delta cells and
group their principal, auxiliary-1, and auxiliary-2 cuts.  A delta-free frame
stores these groups with M_n, M_n*, M_n*, and the original root.  Decoder D
uses one delta to recreate all removed deltas by native gamma/delta copying.

Logical frame order is (principal cuts, auxiliary-1 cuts, auxiliary-2 cuts,
original root).  M_n and M_n* expose corresponding logical leaf orders, so
the decoder connects these slots to delta ports 0, 1, 2, and the output.
This states the port convention independently of a drawing's left/right.
All runtime operations are the original Net.reduce rules.
"""
from collections import Counter
import copy
import random

from ic_primitive_port_verifier import AR, Net, isomorphic
from ic_research_artifacts import GraphSpec
from lafont_ic_macro_builder import Macro, build_M, build_M_star, macro_connect


def validate_package(package):
    """Require a Lafont principal package, not merely absence of active pairs."""
    package.check()
    if len(package.free) != 1 or package.cycles or package.active():
        raise ValueError("a package must have one root, no cuts, and no cyclic wires")
    boundary = next(iter(package.free))
    root = package.adj[boundary]
    if root[0] not in package.nodes or root[1] != 0:
        raise ValueError("the package root must expose a principal cell port")
    # Every principal path must reach ROOT.  This excludes vicious circles
    # and disconnected components, which Net.active() alone does not detect.
    settled = set()
    for start in package.nodes:
        path = set()
        current = start
        while current not in settled:
            if current in path:
                raise ValueError("package contains a cyclic principal path")
            path.add(current)
            parent = package.adj[(current, 0)]
            if parent == boundary:
                break
            if parent[0] not in package.nodes or parent[1] == 0:
                raise ValueError("principal path fails to reach the declared root")
            current = parent[0]
        settled.update(path)
    return boundary


def _cut_port(net):
    serial = getattr(net, "_codec_port_serial", 0)
    while ("F", f"codec-cut-{serial}") in net.adj:
        serial += 1
    net._codec_port_serial = serial + 1
    return net.boundary(f"codec-cut-{serial}")


def build_code(net, package):
    """Append the literal code of package; return its unconnected principal.

    This is an offline constructor, independent of any source-rule table or
    task result.  It copies syntax without mutating the source specimen.
    """
    if net is package:
        raise ValueError("source package and construction target must be distinct")
    source_root = validate_package(package)
    deltas = [cell for cell, kind in package.nodes.items() if kind == "d"]
    count = len(deltas)
    delta_index = {cell: i for i, cell in enumerate(deltas)}
    copied = {cell: net.cell(kind) for cell, kind in package.nodes.items() if kind != "d"}
    cuts = [[_cut_port(net) for _ in range(count)] for _ in range(3)]
    original_root = _cut_port(net)

    def translate(endpoint):
        if endpoint == source_root:
            return original_root
        cell, port = endpoint
        if cell in delta_index:
            return cuts[port][delta_index[cell]]
        return (copied[cell], port)

    visited = set()
    for a, b in package.adj.items():
        if a not in visited:
            net.link(translate(a), translate(b))
            visited.update((a, b))
    principal_group = build_M(net, count)
    first_group = build_M_star(net, count)
    second_group = build_M_star(net, count)
    for index in range(count):
        macro_connect(net, cuts[0][index], principal_group.auxiliaries[index])
        macro_connect(net, cuts[1][index], first_group.auxiliaries[index])
        macro_connect(net, cuts[2][index], second_group.auxiliaries[index])
    frame = build_M(net, 4)
    for slot, endpoint in zip(frame.auxiliaries,
                              (principal_group.principal, first_group.principal,
                               second_group.principal, original_root)):
        macro_connect(net, slot, endpoint)
    return frame.principal


def build_decoder(net):
    """A fixed D with one input principal and one output auxiliary."""
    frame = build_M_star(net, 4)
    delta = net.cell("d")
    for slot, port in zip(frame.auxiliaries[:3], range(3)):
        macro_connect(net, slot, (delta, port))
    return Macro(frame.principal, (frame.auxiliaries[3],))


def encode_package(package, label="CODE"):
    result = Net()
    root = build_code(result, package)
    macro_connect(result, root, result.boundary(label))
    validate_package(result)
    assert all(kind != "d" for kind in result.nodes.values())
    return result


def build_decoding(encoded, copies=1):
    if copies not in (1, 2):
        raise ValueError("this certificate builder uses one or two decoded outputs")
    source_root = validate_package(encoded)
    if any(kind == "d" for kind in encoded.nodes.values()):
        raise ValueError("encoded data must be delta-free")
    result = copy.deepcopy(encoded)
    if copies == 1:
        decoder = build_decoder(result)
        macro_connect(result, source_root, decoder.principal)
        macro_connect(result, decoder.auxiliaries[0], result.boundary("OUT"))
    else:
        fan = result.cell("d")
        macro_connect(result, source_root, (fan, 0))
        for index in (1, 2):
            decoder = build_decoder(result)
            macro_connect(result, (fan, index), decoder.principal)
            macro_connect(result, decoder.auxiliaries[0], result.boundary("OUT" + str(index)))
    result.check()
    return result


def normalize_native(net, strategy="first", seed=0, limit=None):
    """Schedule only already-active primitive IC pairs; report actual work."""
    limit = limit if limit is not None else 100 * (len(net.nodes) + 1)
    rng = random.Random(seed)
    steps, peak = 0, len(net.nodes)
    while net.active():
        pairs = net.active()
        if steps >= limit:
            raise RuntimeError("normalization search budget exhausted")
        if strategy == "first":
            redex = pairs[0]
        elif strategy == "last":
            redex = pairs[-1]
        elif strategy == "random":
            redex = rng.choice(pairs)
        elif strategy == "delta-first":
            redex = next((p for p in pairs if any(net.nodes[c] == "d" for c in p)), pairs[0])
        elif strategy == "epsilon-first":
            redex = next((p for p in pairs if all(net.nodes[c] == "e" for c in p)), pairs[0])
        else:
            raise ValueError(strategy)
        net.reduce(*redex)
        steps += 1
        peak = max(peak, len(net.nodes))
    net.check()
    return {"steps": steps, "peak_cells": peak, "final_cells": len(net.nodes),
            "cyclic_wires": net.cycles, "strategy": strategy}


def _example(shape, matching=()):
    net, holes = Net(), []

    def node(part):
        kind = part[0]
        cell = net.cell(kind)
        if kind != "e":
            for port, child in enumerate(part[1:], 1):
                if child == "H":
                    holes.append((cell, port))
                else:
                    net.link((cell, port), node(child))
        return (cell, 0)
    root = node(shape)
    assert sorted(i for edge in matching for i in edge) == list(range(len(holes)))
    for a, b in matching:
        net.link(holes[a], holes[b])
    net.link(root, net.boundary("ROOT"))
    validate_package(net)
    return net


def certify_codec(package, copies=1, strategy="first", seed=0):
    original = GraphSpec.from_net(package)
    encoded = encode_package(package)
    source_counts = Counter(package.nodes.values())
    code_counts = Counter(encoded.nodes.values())
    delta_count = source_counts["d"]
    assert code_counts["g"] == source_counts["g"] + (3 * delta_count if delta_count else 3)
    assert code_counts["e"] == source_counts["e"] + (0 if delta_count else 3)
    assert code_counts["d"] == 0
    running = build_decoding(encoded, copies)
    expected = Net()
    for label in (("OUT",) if copies == 1 else ("OUT1", "OUT2")):
        original.instantiate(expected, {"ROOT": expected.boundary(label)})
    stats = normalize_native(running, strategy, seed)
    assert isomorphic(running, expected), (copies, strategy, stats)
    assert GraphSpec.from_net(package) == original
    if copies == 1:
        assert stats["steps"] == (3 * delta_count if delta_count else 6)
    return stats


def main():
    e = ("e",)
    cases = [
        _example(e),
        _example(("g", e, e)),
        _example(("g", "H", "H"), ((0, 1),)),
        _example(("d", ("g", e, e), e)),
        _example(("d", "H", "H"), ((0, 1),)),
        _example(("g", ("d", e, ("g", e, e)), ("d", e, e))),
        _example(("d", ("g", "H", "H"), ("g", "H", "H")), ((0, 2), (1, 3))),
    ]
    checked = 0
    for package in cases:
        for copies in (1, 2):
            for strategy in ("first", "last", "random", "delta-first", "epsilon-first"):
                certify_codec(package, copies, strategy, checked)
                checked += 1
    print("PASS: delta-cut code, native decoder, prewired code-copy/decode certificates", checked)
    print("SCOPE: principal package codec; full source compiler certificates remain separate")


if __name__ == "__main__":
    main()
