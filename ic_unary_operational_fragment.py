"""Operational refinement for the {Z,S,DUP,ERA} source subsystem into pure IC.

Unlike source_ic_structure_encoding.py, this is an EXECUTABLE translation:
source active pairs become literal IC active pairs. Four source rules are
witnessed by one or two of Lafont's six *primitive* interactions.

    Z       -> epsilon
    ERA     -> epsilon   (distinguished by source typing/polarity)
    DUP     -> delta
    S(x)    -> gamma(x, epsilon)  (epsilon is a fixed local tag)

These images are valid for well-typed source nets of this four-symbol
subsystem. They do not encode/execute the remaining 11 source rules.
The type-erasing Z/ERA representation is not an injective encoding of
arbitrary untyped source graphs.
"""
import random

from ic_primitive_port_verifier import Net, isomorphic
from source_feedback_audit import RULES, AR, apply as source_apply, FRESH

FRAGMENT = frozenset(('Z', 'S', 'DUP', 'ERA'))
SOURCE_PAIRS = (('ERA', 'Z'), ('ERA', 'S'),
                ('DUP', 'Z'), ('DUP', 'S'))
EXPECTED = {
    ('ERA', 'Z'): ('e-e',),
    ('ERA', 'S'): ('e-g', 'e-e'),
    ('DUP', 'Z'): ('d-e',),
    ('DUP', 'S'): ('d-g', 'd-e'),
}
POLARITY = {
    'Z': ('out',),
    'S': ('out', 'in'),
    'DUP': ('in', 'out', 'out'),
    'ERA': ('in',),
}
assert set(POLARITY) == FRAGMENT
assert all(AR[t] + 1 == len(POLARITY[t]) for t in FRAGMENT)


def lower_cell(net, typ):
    """Return root, source auxiliary ports and optional private S-tag."""
    assert typ in FRAGMENT
    if typ in ('Z', 'ERA'):
        c = net.cell('e')
        return {'root': (c, 0), 'aux': {}, 'tag': None}
    if typ == 'DUP':
        c = net.cell('d')
        return {'root': (c, 0), 'aux': {1: (c, 1), 2: (c, 2)}, 'tag': None}
    g = net.cell('g')
    tag = net.cell('e')
    net.link((g, 2), (tag, 0))
    return {'root': (g, 0), 'aux': {1: (g, 1)}, 'tag': tag}


def port(lowered, name, p):
    return lowered[name]['root'] if p == 0 else lowered[name]['aux'][p]


def source_rule(A, B):
    spec = RULES[frozenset((A, B))]
    assert spec[0:2] == (A, B)
    return spec


def rule_lhs(spec):
    """Translate a source LHS into a real IC graph with labeled free ports."""
    A, B, _, _, _ = spec
    net = Net()
    left = lower_cell(net, A)
    right = lower_cell(net, B)
    net.link(left['root'], right['root'])
    for label, cell, typ in (('A', left, A), ('B', right, B)):
        for i in range(1, AR[typ] + 1):
            boundary = net.boundary(f'{label}{i}')
            net.link(cell['aux'][i], boundary)
    net.check()
    return net, {'a': left, 'b': right}


def rule_rhs(spec):
    """Translate the *independent* source RHS, preserving interface labels."""
    _, _, nodes, edges, exterior = spec
    net = Net()
    lowered = {name: lower_cell(net, typ) for name, typ in nodes.items()}
    for a, i, b, j in edges:
        net.link(port(lowered, a, i), port(lowered, b, j))
    for label, (name, i) in exterior.items():
        free = net.boundary(label)
        net.link(free, port(lowered, name, i))
    net.check()
    return net


def describe_pair(net, u, v):
    return '-'.join(sorted((net.nodes[u], net.nodes[v])))


def macro_reduce(net, a, b, typ_a, typ_b):
    """Witness a SOURCE redex by IC local steps; no source rewrite here.

    The second step, if any, uses the privately attached epsilon tag as
    a local address. During free IC execution that step needs no scheduler.
    """
    assert (typ_a, typ_b) in EXPECTED
    u, v = a['root'][0], b['root'][0]
    trace = [describe_pair(net, u, v)]
    net.reduce(u, v)
    if 'S' in (typ_a, typ_b):
        marker = a['tag'] if typ_a == 'S' else b['tag']
        assert marker in net.nodes and net.nodes[marker] == 'e'
        neighbor = net.adj[(marker, 0)]
        assert neighbor[1] == 0 and neighbor[0] in net.nodes
        other = neighbor[0]
        trace.append(describe_pair(net, marker, other))
        net.reduce(marker, other)
    assert tuple(trace) == EXPECTED[(typ_a, typ_b)], (typ_a, typ_b, trace)
    net.check()
    return tuple(trace)


def certify_four_rules():
    report = {}
    for A, B in SOURCE_PAIRS:
        spec = source_rule(A, B)
        lhs, roots = rule_lhs(spec)
        expected = rule_rhs(spec)
        before = len(lhs.nodes)
        steps = macro_reduce(lhs, roots['a'], roots['b'], A, B)
        assert isomorphic(lhs, expected), ('wrong target interface', A, B)
        assert lhs.cycles == expected.cycles == 0
        report[f'{A}-{B}'] = {
            'primitive_trace': steps, 'initial_ic_cells': before,
            'final_ic_cells': len(lhs.nodes),
        }
        print(f'CERT {A}-{B}: IC trace {steps}; '
              f'{before} -> {len(lhs.nodes)} IC cells; exact interface PASS')
    return report


def lower_complete_source(types, adj):
    """Translate any fully paired, well-typed, CLOSED fragment source net."""
    assert all(t in FRAGMENT for t in types.values())
    assert set(adj) == {(c, p) for c, t in types.items() for p in range(AR[t]+1)}
    for endpoint, neighbor in adj.items():
        assert neighbor in adj and neighbor != endpoint and adj[neighbor] == endpoint
        a, p = endpoint
        b, q = neighbor
        assert POLARITY[types[a]][p] != POLARITY[types[b]][q]
    net = Net()
    lowered = {c: lower_cell(net, typ) for c, typ in types.items()}
    consumed = set()
    for x, y in adj.items():
        if x in consumed:
            continue
        net.link(port(lowered, *x), port(lowered, *y))
        consumed.update((x, y))
    assert len(consumed) == len(adj)
    net.check()
    return net, lowered


def random_context(A, B, rng):
    """A typed closed source net with the requested principal redex.

    Other source redexes and feedback cycles are deliberately permitted.
    """
    names = [A, B] + [rng.choice(tuple(sorted(FRAGMENT)))
                       for _ in range(rng.randrange(7))]
    balance = sum(POLARITY[t].count('out') - POLARITY[t].count('in') for t in names)
    names.extend(['ERA'] * max(balance, 0))
    names.extend(['Z'] * max(-balance, 0))
    types = {f'n{i}': typ for i, typ in enumerate(names)}
    adj = {(c, p): None for c, typ in types.items() for p in range(AR[typ] + 1)}

    def link(x, y):
        assert x != y and adj[x] is None and adj[y] is None
        adj[x] = y
        adj[y] = x

    assert POLARITY[A][0] != POLARITY[B][0]
    link(('n0', 0), ('n1', 0))
    outputs = [(c, p) for c, typ in types.items()
               for p, direction in enumerate(POLARITY[typ])
               if direction == 'out' and adj[(c, p)] is None]
    inputs = [(c, p) for c, typ in types.items()
              for p, direction in enumerate(POLARITY[typ])
              if direction == 'in' and adj[(c, p)] is None]
    assert len(outputs) == len(inputs)
    rng.shuffle(outputs)
    rng.shuffle(inputs)
    for x, y in zip(outputs, inputs):
        link(x, y)
    return types, adj, 'n0', 'n1'


def certify_contextual_steps():
    """Check E(source-step) == IC-macro(E(source)) for 4 x 100 contexts."""
    rng = random.Random(20261104)
    number = 0
    for A, B in SOURCE_PAIRS:
        for _ in range(100):
            types, adj, u, v = random_context(A, B, rng)
            net, lowering = lower_complete_source(types, adj)
            target_types, target_adj = dict(types), dict(adj)
            # Source evaluator is used ONLY on the independently generated
            # expected graph, never to run or change the IC graph.
            FRESH[0] = 0
            source_apply(target_types, target_adj, u, v)
            target, _ = lower_complete_source(target_types, target_adj)
            macro_reduce(net, lowering[u], lowering[v], A, B)
            assert isomorphic(net, target), (A, B, types, adj)
            number += 1
    print(f'PASS: {number} typed whole-graph contextual one-step refinements')
    return number


def unary(net, n):
    """S^n(Z) using the same literal source-to-IC cell translation."""
    assert n >= 0
    root = lower_cell(net, 'Z')['root']
    for _ in range(n):
        s = lower_cell(net, 'S')
        net.link(s['aux'][1], root)
        root = s['root']
    return root


def read_unary(net, boundary, visited):
    """Independently recognize an S/epsilon chain including every tag."""
    cur = net.adj[boundary]
    n = 0
    while True:
        c, p = cur
        assert p == 0 and c in net.nodes and c not in visited
        visited.add(c)
        if net.nodes[c] == 'e':
            return n
        assert net.nodes[c] == 'g'
        tag, port_id = net.adj[(c, 2)]
        assert port_id == 0 and tag in net.nodes and net.nodes[tag] == 'e'
        assert tag not in visited
        visited.add(tag)
        n += 1
        cur = net.adj[(c, 1)]


def reduce_all(net, seed, bound):
    rng = random.Random(seed)
    steps = 0
    while net.active():
        assert steps < bound, ('non-termination', steps)
        net.reduce(*rng.choice(net.active()))
        steps += 1
    net.check()
    return steps


def copy_unary(n, seed):
    net = Net()
    root = unary(net, n)
    duplicator = lower_cell(net, 'DUP')
    net.link(root, duplicator['root'])
    left = net.boundary('left')
    right = net.boundary('right')
    net.link(duplicator['aux'][1], left)
    net.link(duplicator['aux'][2], right)
    net.check()
    steps = reduce_all(net, seed, 2*n + 2)
    assert steps == 2*n + 1
    seen = set()
    assert read_unary(net, left, seen) == n
    assert read_unary(net, right, seen) == n
    assert len(seen) == len(net.nodes) == 2*(2*n + 1)
    assert net.cycles == 0
    return steps


def erase_unary(n, seed):
    net = Net()
    root = unary(net, n)
    eraser = lower_cell(net, 'ERA')
    net.link(root, eraser['root'])
    net.check()
    steps = reduce_all(net, seed, 2*n + 2)
    assert steps == 2*n + 1
    assert not net.nodes and net.cycles == 0
    return steps


def copy_then_erase(n, seed):
    """A complete, closed source-fragment program, executed *only* in IC."""
    net = Net()
    root = unary(net, n)
    d = lower_cell(net, 'DUP')
    net.link(root, d['root'])
    for p in (1, 2):
        e = lower_cell(net, 'ERA')
        net.link(d['aux'][p], e['root'])
    net.check()
    steps = reduce_all(net, seed, 6*n + 4)
    assert steps == 6*n + 3, (n, steps)
    assert not net.nodes and net.cycles == 0
    return steps


def main():
    certify_four_rules()
    certify_contextual_steps()
    for n in range(201):
        copy_unary(n, n)
        erase_unary(n, n + 1)
    print('PASS: unary n=0..200 native IC copy/erase, 2*n+1 reductions')
    for n in (0, 1, 2, 9, 81, 200):
        for seed in range(12):
            copy_unary(n, seed + 1000)
            erase_unary(n, seed + 2000)
            copy_then_erase(n, seed + 3000)
        print(f'Un{n}: copying/erasing={2*n+1} IC steps, '
              f'closed copy-then-erase={6*n+3} IC steps')
    print('PASS: 4/15 source rules have literal operational IC certificates;'
          ' 11 other rules remain UNCOMPILED, including INIT and CMP.')


if __name__ == '__main__':
    main()
