"""Composable pure-IC signed unary outputs without an observer-controlled rewrite.

Two independent, oppositely oriented gamma/epsilon cancellation channels
produce positive and negative truncated differences:

    P = max(m - n, 0)    N = max(n - m, 0)

Each channel is constructed from *independent* m/n unary chains, with an
epsilon probe on its left observation endpoint and a delta probe on its
right observation endpoint. A single delta auxiliary is exposed at a fixed
output boundary; its other auxiliary is wired to an epsilon. This is a
local IC reification of the previous A-to-B residual path into a *rooted*
canonical S^k(Z) tree (S = gamma(child,epsilon), Z = epsilon).

Both outputs can be consumed by further IC contexts. This file uses only
Net.reduce and the original six IC rules. No source evaluator, external
observation trigger, comparison, or branch-selection action executes during
reduction. A read-only structural decoder is used only for assertions.

The construction uses two copies of each input, rather than a compiled
source DUP. It is NOT a three-way boolean selector, GATE, or any of the
remaining 11 source-rule certificates.
"""
import random
from ic_primitive_port_verifier import Net
from ic_signed_unary_comparator import _unary


def _channel(net, m, n, name):
    """Construct one oriented cancellation channel with fixed unary output."""
    left_probe = net.cell('e')
    right_probe = net.cell('d')
    sink = net.cell('e')
    left = _unary(net, m, 'L', (left_probe, 0))
    right = _unary(net, n, 'R', (right_probe, 0))
    net.link(left, right)
    out = net.boundary(name)
    net.link((right_probe, 1), out)
    net.link((right_probe, 2), (sink, 0))
    return out


def build(m, n):
    """No runtime comparison or output-dependent choices in this builder."""
    assert type(m) is int and type(n) is int and m >= 0 and n >= 0
    net = Net()
    p = _channel(net, m, n, 'P')
    q = _channel(net, n, m, 'N')
    net.check()
    return net, p, q


def read_unary(net, boundary):
    """Recognize canonical rooted S^k(Z); raise if not yet complete."""
    visited = set()
    cursor = net.adj[boundary]
    k = 0
    while True:
        name, port = cursor
        assert port == 0 and name in net.nodes and name not in visited
        visited.add(name)
        kind = net.nodes[name]
        if kind == 'e':
            return k, visited
        assert kind == 'g'
        tag, tag_port = net.adj[(name, 2)]
        assert tag_port == 0 and net.nodes.get(tag) == 'e'
        assert tag not in visited
        visited.add(tag)
        k += 1
        cursor = net.adj[(name, 1)]


def reduction(net, strategy, seed):
    """Unbiased primitive IC scheduler; strategy only chooses active pairs."""
    rng = random.Random(seed)
    steps = 0
    limit = 30 * (len(net.nodes) + 1)
    while net.active():
        pairs = net.active()
        if strategy == 'random':
            pair = rng.choice(pairs)
        elif strategy == 'gamma-first':
            pair = next((p for p in pairs if all(net.nodes[x] == 'g' for x in p)), pairs[0])
        elif strategy == 'epsilon-first':
            pair = next((p for p in pairs if all(net.nodes[x] == 'e' for x in p)), pairs[0])
        elif strategy == 'delta-first':
            pair = next((p for p in pairs if any(net.nodes[x] == 'd' for x in p)), pairs[0])
        else:
            raise ValueError(strategy)
        net.reduce(*pair)
        steps += 1
        # The exact bound is a test guard, not a scheduling rule.
        assert steps <= limit, ('step limit', strategy, steps)
    net.check()
    return steps


def verify_outputs(net, p, q, m, n):
    positive, seen_p = read_unary(net, p)
    negative, seen_n = read_unary(net, q)
    assert positive == max(m-n, 0)
    assert negative == max(n-m, 0)
    assert seen_p.isdisjoint(seen_n)
    assert seen_p | seen_n == set(net.nodes)
    assert net.cycles == 0
    assert len(net.nodes) == 2 * (positive + negative + 1)
    return positive, negative


def check(m, n, strategy='random', seed=0):
    net, p, q = build(m, n)
    initial = len(net.nodes)
    steps = reduction(net, strategy, seed)
    values = verify_outputs(net, p, q, m, n)
    return initial, steps, values


def _splice(net, boundary, other):
    """Connect a source output to another IC principal without an adapter.

    Only the *builder* removes the temporary boundary, before evolution.
    This is ordinary static wiring, not a runtime replacement.
    """
    context = net.adj.pop(boundary)
    net.free.remove(boundary)
    net.adj[context] = None
    net.link(context, other)


def build_consumers(m, n, copy_positive=True):
    """Copy one output twice; erase the other with native IC interactions.

    Consumer wiring is chosen independently of the eventual comparison.
    """
    net, positive, negative = build(m, n)
    copy = positive if copy_positive else negative
    erase = negative if copy_positive else positive
    d = net.cell('d')
    e = net.cell('e')
    _splice(net, copy, (d, 0))
    _splice(net, erase, (e, 0))
    prefix = 'P' if copy_positive else 'N'
    out1 = net.boundary(prefix + '1')
    out2 = net.boundary(prefix + '2')
    net.link((d, 1), out1)
    net.link((d, 2), out2)
    net.check()
    return net, out1, out2


def check_consumers(m, n, copy_positive=True, strategy='random', seed=0):
    net, out1, out2 = build_consumers(m, n, copy_positive)
    steps = reduction(net, strategy, seed)
    actual1, visited1 = read_unary(net, out1)
    actual2, visited2 = read_unary(net, out2)
    target = max((m-n) if copy_positive else (n-m), 0)
    assert (actual1, actual2) == (target, target)
    assert visited1.isdisjoint(visited2)
    assert visited1 | visited2 == set(net.nodes)
    assert net.cycles == 0
    return steps


def main():
    schedules = ('random', 'gamma-first', 'epsilon-first', 'delta-first')
    cases = 0
    for m in range(18):
        for n in range(18):
            for strategy in schedules:
                for seed in (0, 1):
                    check(m, n, strategy, seed)
                    for copy_positive in (True, False):
                        check_consumers(m, n, copy_positive, strategy, seed)
                    cases += 1
    print(f'PASS: {cases} dual-difference outputs and {2*cases} composed copy/erase programs')
    for m, n in ((0, 0), (1, 0), (0, 1), (81, 80),
                 (80, 81), (81, 81), (100, 120), (200, 200)):
        samples = {check(m, n, strategy, 0)
                   for strategy in schedules}
        assert len(samples) == 1, (m, n, samples)
        initial, steps, values = next(iter(samples))
        for chosen in (True, False):
            totals = {check_consumers(m, n, chosen, strategy, 0)
                      for strategy in schedules}
            assert len(totals) == 1, (m, n, chosen, totals)
        print(f'{m}:{n}: initial={initial}, IC-steps={steps}, '
              f'(positive,negative)={values}')
    print('PASS: the two integer outputs are actual local IC data consumable '
          'by unmodified delta and epsilon; no external observer directs evolution')
    print('LIMIT: no source CMP/CMP0/CMPS/GATE certificate or square solver')


if __name__ == '__main__':
    main()
