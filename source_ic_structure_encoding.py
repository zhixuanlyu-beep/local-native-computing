"""Lossless source port-net storage as a literal, delta-free IC reduced package.

This is a structural encoding, NOT a source-rule evaluator or a Lafont
source-to-IC interaction compiler. Source node types are encoded in unary
as gamma/epsilon syntax; source edges remain literal auxiliary-to-auxiliary
IC wires. All generated cells are primitive gamma/epsilon, and a delta can
copy the package by primitive IC reductions alone.

The encoding is deliberately independent of the output of the source square
checker. It accepts ANY finite, fully paired source port graph with the
supported source symbols; no rule table is consulted by the encoder.
"""
from dataclasses import dataclass
import random

from ic_primitive_port_verifier import Net
from source_feedback_audit import AR, RULES, make_sim

SYMBOLS = ('Z', 'S', 'DUP', 'ERA', 'INIT', 'CMP', 'CMP0',
           'CMPS', 'GATE', 'EQ', 'GT', 'LT', 'SQ', 'BR')
assert set(SYMBOLS) == set(AR)
BOUNDARY_TAG = len(SYMBOLS)


@dataclass(frozen=True)
class Snapshot:
    """An ordered source graph; boundary identity is its positional index.

    Each node has arity+1 ports, followed by one port per external boundary.
    matching is a complete, sorted involution on those indexed ports.
    """
    symbols: tuple[str, ...]
    boundaries: int
    matching: tuple[tuple[int, int], ...]

    def validate(self):
        assert all(s in AR for s in self.symbols)
        assert isinstance(self.boundaries, int) and self.boundaries >= 0
        count = sum(AR[s] + 1 for s in self.symbols) + self.boundaries
        assert count % 2 == 0
        assert all(isinstance(a, int) and isinstance(b, int) and
                   0 <= a < b < count for a, b in self.matching)
        assert self.matching == tuple(sorted(self.matching))
        seen = [p for pair in self.matching for p in pair]
        assert sorted(seen) == list(range(count)), (count, seen)
        return count


def snapshot_from_adjacency(types, adj, boundary_order=None):
    """Read a *source* state without performing any source reduction.

    If boundary_order is omitted, order the free endpoints by repr; never
    rely on incidental Python dictionary traversal of output boundaries.
    """
    nodes = list(types)
    external = [ep for ep in adj if ep[0] not in types]
    boundary = sorted(external, key=repr) if boundary_order is None else list(boundary_order)
    assert set(external) == set(boundary) and len(boundary) == len(external)
    ports = [(c, p) for c in nodes for p in range(AR[types[c]] + 1)] + boundary
    assert set(ports) == set(adj) and len(ports) == len(adj)
    positions = {p: i for i, p in enumerate(ports)}
    matching = []
    for i, ep in enumerate(ports):
        other = adj[ep]
        assert other in positions and other != ep and adj[other] == ep
        j = positions[other]
        if i < j:
            matching.append((i, j))
    snap = Snapshot(tuple(types[c] for c in nodes), len(boundary), tuple(matching))
    snap.validate()
    return snap


def snapshot_from_rule(spec):
    """Represent a source RHS as a port graph with ordered LHS interface."""
    A, B, nodes, edges, ext = spec
    labels = [f'A{i}' for i in range(1, AR[A]+1)] + [f'B{i}' for i in range(1, AR[B]+1)]
    assert set(labels) == set(ext)
    adj = {(node, p): None for node, typ in nodes.items() for p in range(AR[typ] + 1)}
    for lab in labels:
        adj[('FREE', lab)] = None

    def link(x, y):
        assert x != y and x in adj and y in adj
        assert adj[x] is None and adj[y] is None
        adj[x] = y
        adj[y] = x

    for x, p, y, q in edges:
        link((x, p), (y, q))
    for lab, ep in ext.items():
        link(('FREE', lab), tuple(ep))
    return snapshot_from_adjacency(nodes, adj, [('FREE', lab) for lab in labels])


def encode(net, snapshot):
    """Allocate an honest IC gamma/epsilon net with one unattached root.

    The list spine and unary type markers are constructor trees. A source
    edge is represented by exactly ONE IC wire joining two tree holes.
    The only free port is the principal port returned by this function;
    callers must connect it to a boundary, delta, or epsilon before check().
    """
    snapshot.validate()

    def type_marker(code):
        if code == 0:
            return net.cell('e')
        g = net.cell('g')
        e = net.cell('e')
        net.link((g, 1), (e, 0))
        tail = type_marker(code - 1)
        net.link((g, 2), (tail, 0))
        return g

    def port_holes(parent_port, arity_plus_one):
        if arity_plus_one == 1:
            return [parent_port]
        g = net.cell('g')
        net.link(parent_port, (g, 0))
        return [(g, 1)] + port_holes((g, 2), arity_plus_one - 1)

    tags = [SYMBOLS.index(s) for s in snapshot.symbols] + [BOUNDARY_TAG] * snapshot.boundaries
    tail = net.cell('e')
    all_holes = [None] * len(tags)
    for i in reversed(range(len(tags))):
        cons = net.cell('g')
        item = net.cell('g')
        net.link((cons, 1), (item, 0))
        net.link((cons, 2), (tail, 0))
        marker = type_marker(tags[i])
        net.link((item, 1), (marker, 0))
        width = 1 if tags[i] == BOUNDARY_TAG else AR[SYMBOLS[tags[i]]] + 1
        all_holes[i] = port_holes((item, 2), width)
        tail = cons
    holes = [ep for group in all_holes for ep in group]
    assert len(holes) == 2 * len(snapshot.matching)
    for a, b in snapshot.matching:
        net.link(holes[a], holes[b])
    return (tail, 0)


def decode(net, root_connector):
    """Read the primitive IC topology; return (source graph, visited IC cells).

    This only observes the reduced *data representation*. It neither
    performs source interactions nor guesses square-checker outputs.
    """
    visited = set()
    def enter(connector):
        c, p = net.adj[connector]
        assert p == 0 and c in net.nodes and c not in visited, (connector, c, p)
        visited.add(c)
        return c, net.nodes[c]

    def marker(from_port):
        value = 0
        while True:
            c, typ = enter(from_port)
            if typ == 'e':
                return value
            assert typ == 'g' and value <= BOUNDARY_TAG
            _, marker_left = enter((c, 1))
            assert marker_left == 'e'
            value += 1
            from_port = (c, 2)

    def read_holes(from_port, count):
        if count == 1:
            return [from_port]
        c, typ = enter(from_port)
        assert typ == 'g'
        return [(c, 1)] + read_holes((c, 2), count - 1)

    tags = []
    ports = []
    from_port = root_connector
    while True:
        cons, typ = enter(from_port)
        if typ == 'e':
            break
        assert typ == 'g'
        item, item_type = enter((cons, 1))
        assert item_type == 'g'
        tag = marker((item, 1))
        assert 0 <= tag <= BOUNDARY_TAG
        tags.append(tag)
        width = 1 if tag == BOUNDARY_TAG else AR[SYMBOLS[tag]] + 1
        ports.extend(read_holes((item, 2), width))
        from_port = (cons, 2)

    first_boundary = next((i for i, tag in enumerate(tags) if tag == BOUNDARY_TAG), len(tags))
    assert all(tag == BOUNDARY_TAG for tag in tags[first_boundary:])
    pos = {p: i for i, p in enumerate(ports)}
    assert len(pos) == len(ports)
    pairs = []
    for i, ep in enumerate(ports):
        other = net.adj[ep]
        assert other in pos and other != ep, ('wire escaped payload', ep, other)
        j = pos[other]
        if i < j:
            pairs.append((i, j))
    snapshot = Snapshot(tuple(SYMBOLS[tag] for tag in tags[:first_boundary]),
                        len(tags) - first_boundary, tuple(pairs))
    snapshot.validate()
    return snapshot, visited


def roundtrip(source):
    net = Net()
    root = encode(net, source)
    b = net.boundary('root')
    net.link(root, b)
    net.check()
    decoded, cells = decode(net, b)
    assert decoded == source
    assert cells == set(net.nodes)
    assert all(t in ('g', 'e') for t in net.nodes.values())
    assert net.cycles == 0
    return len(cells)


def copy_audit(source, seed=0):
    """Reduce an IC delta against the payload; verify two exact source copies."""
    net = Net()
    root = encode(net, source)
    payload_cells = len(net.nodes)
    duplicator = net.cell('d')
    net.link((duplicator, 0), root)
    out = [net.boundary('copy0'), net.boundary('copy1')]
    net.link((duplicator, 1), out[0])
    net.link((duplicator, 2), out[1])
    net.check()
    rng = random.Random(seed)
    steps = 0
    while net.active():
        net.reduce(*rng.choice(net.active()))
        steps += 1
        assert steps <= payload_cells + len(source.matching)
    assert steps == payload_cells + len(source.matching)
    assert len(net.nodes) == 2 * payload_cells
    assert net.cycles == 0
    decoded = [decode(net, b) for b in out]
    assert decoded[0][0] == decoded[1][0] == source
    assert decoded[0][1].isdisjoint(decoded[1][1])
    assert decoded[0][1] | decoded[1][1] == set(net.nodes)
    return payload_cells, steps


def erase_audit(source, seed=0):
    """Reduce one IC epsilon against a closed package with internal wires."""
    net = Net()
    root = encode(net, source)
    payload_cells = len(net.nodes)
    eraser = net.cell('e')
    net.link((eraser, 0), root)
    net.check()
    rng = random.Random(seed)
    steps = 0
    while net.active():
        net.reduce(*rng.choice(net.active()))
        steps += 1
        assert steps <= payload_cells + len(source.matching)
    assert steps == payload_cells + len(source.matching)
    assert not net.nodes and net.cycles == 0
    return payload_cells, steps


def main():
    total = 0
    for spec in RULES.values():
        source = snapshot_from_rule(spec)
        total += roundtrip(source)
        for seed in (0, 1, 2):
            copy_audit(source, seed)
            erase_audit(source, seed)
    print('PASS: all 15 source RHS nets losslessly embedded as primitive IC; 3 copy/erase schedules each')
    print('Total IC payload cells across the 15 rule RHS:', total)

    for n in range(201):
        source = snapshot_from_adjacency(*make_sim(n))
        assert source.symbols == ('INIT',) + ('S',)*n + ('Z',)
        assert source.boundaries == 1
        roundtrip(source)
    print('PASS: all 201 initial source nets N=0..200 round-trip without source evaluation')
    for n in (0, 1, 2, 9, 81, 82):
        source = snapshot_from_adjacency(*make_sim(n))
        size, steps = copy_audit(source, n)
        assert erase_audit(source, n + 1) == (size, steps)
        print(f'N={n}: IC payload={size} cells, source wires={len(source.matching)},'
              f' IC copy and erase={steps} interactions each')
    rng = random.Random(20261104)
    for case in range(60):
        names = tuple(rng.choice(SYMBOLS) for _ in range(rng.randrange(6)))
        boundary_count = rng.randrange(4)
        if (sum(AR[s] + 1 for s in names) + boundary_count) % 2:
            boundary_count += 1
        count = sum(AR[s] + 1 for s in names) + boundary_count
        ports = list(range(count))
        rng.shuffle(ports)
        matching = tuple(sorted((min(a,b), max(a,b)) for a,b in zip(ports[::2],ports[1::2])))
        source = Snapshot(names, boundary_count, matching)
        roundtrip(source)
        copy_audit(source, case)
        erase_audit(source, case + 100)
    print('PASS: 60 arbitrary typed, possibly disconnected/cyclic source wire matchings')
    print('PASS: structural source->IC encoding/copy/erase only; NOT IC square checking')


if __name__ == '__main__':
    main()
