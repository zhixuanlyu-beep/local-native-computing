"""A native one-step IC zero/successor *case* on a tagged unary representation.

Alternative typed encoding of the 4-symbol {Z,S,DUP,ERA} fragment:
    Z   := epsilon
    ERA := epsilon (source polarity distinguishes ERA from Z)
    DUP := delta
    S(x):= gamma(x, T), T := gamma(epsilon,epsilon)

A FIXED gamma destructor distinguishes zero from a successor in ONE
primitive interaction:
    case(Z)     -> (false=epsilon, predecessor=epsilon)
    case(S(x))  -> (true=T, predecessor=x)

The same tagged encoding also operationally implements all FOUR original
unary source rules, with certificates comparing independently translated
rule RHS port graphs. A literal delta can copy the resulting Boolean token
and a literal epsilon can erase it. Every runtime transformation calls
Net.reduce; the observer is used only for test assertions.

Important scope: this is a NEW tagged unary encoding, not a pure-IC adapter
for the legacy epsilon-tagged S or the signed-comparator output. It does
NOT implement CMP, GATE, a three-way selector, or a square checker.
"""
import random

from ic_primitive_port_verifier import Net, isomorphic
from source_feedback_audit import RULES, AR


SOURCE_PAIRS = (('ERA', 'Z'), ('ERA', 'S'),
                ('DUP', 'Z'), ('DUP', 'S'))
EXPECTED_STEPS = {
    ('ERA', 'Z'): 1,
    ('ERA', 'S'): 4,
    ('DUP', 'Z'): 1,
    ('DUP', 'S'): 4,
}


def tagged_true(net):
    """Canonical one-free-port true constructor T=gamma(epsilon,epsilon)."""
    g = net.cell('g')
    a, b = net.cell('e'), net.cell('e')
    net.link((g, 1), (a, 0))
    net.link((g, 2), (b, 0))
    return (g, 0)


def lower_cell(net, typ):
    """Lower one source cell, exposing only its source-relevant ports."""
    if typ in ('Z', 'ERA'):
        e = net.cell('e')
        return {'root': (e, 0), 'aux': {}}
    if typ == 'DUP':
        d = net.cell('d')
        return {'root': (d, 0), 'aux': {1: (d, 1), 2: (d, 2)}}
    assert typ == 'S', ('unknown source cell', typ)
    g = net.cell('g')
    net.link((g, 2), tagged_true(net))
    return {'root': (g, 0), 'aux': {1: (g, 1)}}


def lowered_port(obj, port):
    return obj['root'] if port == 0 else obj['aux'][port]


def build_rule_lhs(spec):
    A, B, _, _, _ = spec
    net = Net()
    left, right = lower_cell(net, A), lower_cell(net, B)
    net.link(left['root'], right['root'])
    for label, obj, typ in (('A', left, A), ('B', right, B)):
        for p in range(1, AR[typ] + 1):
            net.link(obj['aux'][p], net.boundary(label + str(p)))
    net.check()
    return net


def build_rule_rhs(spec):
    _, _, nodes, edges, exterior = spec
    net = Net()
    objects = {name: lower_cell(net, typ) for name, typ in nodes.items()}
    for a, i, b, j in edges:
        net.link(lowered_port(objects[a], i),
                 lowered_port(objects[b], j))
    for label, (name, p) in exterior.items():
        net.link(net.boundary(label), lowered_port(objects[name], p))
    net.check()
    return net


def reduce_all(net, strategy='random', seed=0, bound=None):
    """Only picks active IC pairs; never executes a source-language rule."""
    rng = random.Random(seed)
    limit = bound if bound is not None else 16 * (len(net.nodes) + 1)
    steps = 0
    while net.active():
        assert steps < limit, ('step limit', steps, limit)
        pairs = net.active()
        if strategy == 'random':
            pair = rng.choice(pairs)
        elif strategy == 'first':
            pair = pairs[0]
        elif strategy == 'last':
            pair = pairs[-1]
        else:
            raise ValueError(strategy)
        net.reduce(*pair)
        steps += 1
    net.check()
    return steps


def certify_source_rules():
    """Reconstruct source RHS *independently* and check literal IC reduction."""
    for A, B in SOURCE_PAIRS:
        spec = RULES[frozenset((A, B))]
        assert spec[0:2] == (A, B)
        target = build_rule_rhs(spec)
        for strategy in ('first', 'last', 'random'):
            for seed in range(8):
                lhs = build_rule_lhs(spec)
                steps = reduce_all(lhs, strategy, seed)
                assert steps == EXPECTED_STEPS[(A, B)], (A, B, steps)
                assert isomorphic(lhs, target), (A, B, strategy, seed)
                assert lhs.cycles == target.cycles == 0
        print(f'CERT {A}-{B}: {EXPECTED_STEPS[(A, B)]} primitive IC steps;'
              ' exact boundary-labeled source RHS')


def unary(net, n):
    """S^n(Z) as an independent constructor structure with no active pair."""
    assert type(n) is int and n >= 0
    root = lower_cell(net, 'Z')['root']
    for _ in range(n):
        s = lower_cell(net, 'S')
        net.link(s['aux'][1], root)
        root = s['root']
    return root


def read_token(net, boundary):
    """Read-only check: F=epsilon or T=gamma(epsilon,epsilon)."""
    cell, port = net.adj[boundary]
    assert port == 0 and cell in net.nodes
    if net.nodes[cell] == 'e':
        return False, {cell}
    assert net.nodes[cell] == 'g'
    visited = {cell}
    for p in (1, 2):
        e, entry = net.adj[(cell, p)]
        assert entry == 0 and net.nodes.get(e) == 'e' and e not in visited
        visited.add(e)
    return True, visited


def read_tagged_unary(net, boundary):
    """Check an exact tagged unary constructor and return its visited cells."""
    seen = set()
    cursor = net.adj[boundary]
    n = 0
    while True:
        cell, port = cursor
        assert port == 0 and cell in net.nodes and cell not in seen
        seen.add(cell)
        if net.nodes[cell] == 'e':
            return n, seen
        assert net.nodes[cell] == 'g'
        t, entry = net.adj[(cell, 2)]
        assert entry == 0 and net.nodes.get(t) == 'g' and t not in seen
        seen.add(t)
        for p in (1, 2):
            e, ep = net.adj[(t, p)]
            assert ep == 0 and net.nodes.get(e) == 'e' and e not in seen
            seen.add(e)
        cursor = net.adj[(cell, 1)]
        n += 1


def build_case(n, consumer='none'):
    """Fixed front-end with optional pre-wired local flag consumer.

    'copy' attaches delta to the flag; 'erase' attaches epsilon. Neither
    choice is made at runtime or depends on n.
    """
    net = Net()
    data = unary(net, n)
    case = net.cell('g')
    net.link((case, 0), data)
    pred = net.boundary('pred')
    net.link((case, 2), pred)
    flags = []
    if consumer == 'none':
        flag = net.boundary('flag')
        net.link((case, 1), flag)
        flags.append(flag)
    elif consumer == 'copy':
        d = net.cell('d')
        net.link((case, 1), (d, 0))
        for p in (1, 2):
            flag = net.boundary('flag' + str(p))
            net.link((d, p), flag)
            flags.append(flag)
    elif consumer == 'erase':
        e = net.cell('e')
        net.link((case, 1), (e, 0))
    else:
        raise ValueError(consumer)
    net.check()
    return net, pred, flags


def check_case(n, consumer='none', strategy='random', seed=0):
    net, pred, flags = build_case(n, consumer)
    steps = reduce_all(net, strategy, seed, bound=8)
    target_steps = (1 if consumer == 'none' else
                    (4 if n else 2) if consumer == 'copy' else
                    (4 if n else 2))
    assert steps == target_steps, (n, consumer, steps, target_steps)
    seen = set()
    for boundary in flags:
        actual, cells = read_token(net, boundary)
        assert actual == (n > 0)
        assert cells.isdisjoint(seen)
        seen.update(cells)
    residual, remaining = read_tagged_unary(net, pred)
    assert residual == max(n - 1, 0)
    assert remaining.isdisjoint(seen)
    seen.update(remaining)
    assert seen == set(net.nodes)
    assert net.cycles == 0
    return steps


def check_dup_or_erase(n, consumer='copy', seed=0):
    """End-to-end tagged source DUP/ERA behaviour for arbitrary unary size."""
    assert consumer in ('copy', 'erase')
    net = Net()
    root = unary(net, n)
    op = net.cell('d' if consumer == 'copy' else 'e')
    net.link((op, 0), root)
    outs = []
    if consumer == 'copy':
        for port in (1, 2):
            b = net.boundary('out' + str(port))
            net.link((op, port), b)
            outs.append(b)
    net.check()
    steps = reduce_all(net, 'random', seed, bound=4 * n + 2)
    assert steps == 4 * n + 1
    seen = set()
    for b in outs:
        value, cells = read_tagged_unary(net, b)
        assert value == n
        assert seen.isdisjoint(cells)
        seen.update(cells)
    assert seen == set(net.nodes)
    assert net.cycles == 0
    return steps


def main():
    certify_source_rules()
    strategies = ('first', 'last', 'random')
    count = 0
    for n in range(201):
        for strategy in strategies:
            for consumer in ('none', 'copy', 'erase'):
                check_case(n, consumer, strategy, seed=n)
                count += 1
        check_dup_or_erase(n, 'copy', seed=n)
        check_dup_or_erase(n, 'erase', seed=n + 1)
    print(f'PASS: {count} native IC tagged zero/successor case audits for n=0..200')
    for n in (0, 1, 2, 9, 81, 200):
        for seed in range(30):
            check_case(n, 'copy', 'random', seed)
            check_case(n, 'erase', 'random', seed)
        print(f'n={n}: 1-step case, then copied/erased flag in '
              f'{2 if n == 0 else 4} total primitive interactions;'
              f' predecessor={max(n-1, 0)}')
    print('PASS: alternative tagged {Z,S,DUP,ERA} refinement remains 4/15;'
          ' no full CMP or three-way GATE compiled')


if __name__ == '__main__':
    main()
