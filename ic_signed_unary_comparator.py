"""An original, operational pure-IC signed-unary cancellation network.

Two complementary gamma/epsilon chains collide through their principal
ports. They normalize to a stable, *oriented* gamma/epsilon residual path
joining two named observation boundaries: A--B means zero; a path starting
at A with gamma auxiliary-1 means positive; gamma principal means negative.
The number of gamma cells on the path is the exact absolute difference.

ONLY the six primitive IC rules from ic_primitive_port_verifier.Net are
used. No source-level rule is called; no expected answer is embedded in the
network. An external read-only graph traversal decodes the stable output.

This is a comparator *component*, not a compilation of CMP/CMP0/CMPS or of
the 14-symbol square checker. In particular its unary encoding is different
from that of ic_unary_operational_fragment.py.
"""
from dataclasses import dataclass
import random

from ic_primitive_port_verifier import Net


@dataclass(frozen=True)
class Observation:
    sign: int      # -1, 0, +1
    magnitude: int # non-negative


def _unary(net, count, side, endpoint):
    """Create a zero sentinel and count successor cells, all gamma+epsilon.

    A sentinel has a gamma principal, one tagged epsilon at its reserved
    auxiliary port, and the external boundary on its other auxiliary.
    L: gamma(child at 1, epsilon at 2)
    R: gamma(epsilon at 1, child at 2)
    """
    assert count >= 0 and side in ('L', 'R')
    child_port = 1 if side == 'L' else 2
    tag_port = 3 - child_port
    root = None
    for i in range(count + 1):
        g = net.cell('g')
        e = net.cell('e')
        net.link((g, tag_port), (e, 0))
        net.link((g, child_port), endpoint if i == 0 else root)
        root = (g, 0)
    return root


def build(m, n):
    """Return an IC network and its two observation boundaries.

    The construction makes no comparison between m and n. Both integers
    only prescribe the lengths of independently built unary data chains.
    """
    assert isinstance(m, int) and not isinstance(m, bool) and m >= 0
    assert isinstance(n, int) and not isinstance(n, bool) and n >= 0
    net = Net()
    a = net.boundary('A')
    b = net.boundary('B')
    left = _unary(net, m, 'L', a)
    right = _unary(net, n, 'R', b)
    net.link(left, right)
    net.check()
    assert len(net.nodes) == 2*(m + n + 2)
    return net, a, b


def observe(net, a=('F', 'A'), b=('F', 'B')):
    """Read only the output path; return None until it is stabilized.

    After the collision frontier has cleared, this path contains no active
    pair even while independent epsilon-epsilon cleanup redexes remain.
    The traversal does not read or consume cells in disconnected parts.
    It is an observer operation, NOT an IC rewrite or an internal signal.
    """
    assert a in net.free and b in net.free and a != b
    head = net.adj[a]
    if head == b:
        return Observation(0, 0)
    if head[0] not in net.nodes:
        return None
    first, entry_port = head
    if net.nodes[first] != 'g' or entry_port not in (0, 1):
        return None
    sign = 1 if entry_port == 1 else -1
    tag_port = 2 if sign > 0 else 1
    continue_port = 0 if sign > 0 else 2
    expected_entry = 1 if sign > 0 else 0
    seen_gamma = set()
    seen_tags = set()
    cell = first
    while True:
        if cell in seen_gamma or net.nodes.get(cell) != 'g':
            return None
        seen_gamma.add(cell)
        tag_cell, tag_entry = net.adj[(cell, tag_port)]
        if (tag_entry != 0 or net.nodes.get(tag_cell) != 'e'
                or tag_cell in seen_tags):
            return None
        seen_tags.add(tag_cell)
        target = net.adj[(cell, continue_port)]
        if target == b:
            return Observation(sign, len(seen_gamma))
        if (target[0] not in net.nodes or net.nodes[target[0]] != 'g'
                or target[1] != expected_entry):
            return None
        cell = target[0]


def choose_redex(net, strategy, rng):
    active = net.active()
    if strategy == 'random':
        return rng.choice(active)
    if strategy == 'gamma-first':
        return next((p for p in active if net.nodes[p[0]] == 'g'), active[0])
    if strategy == 'epsilon-first':
        return next((p for p in active if net.nodes[p[0]] == 'e'), active[0])
    raise ValueError(strategy)


def audit_pair(m, n, strategy='random', seed=0):
    """Validate every intermediate read and the final IC normal form."""
    net, a, b = build(m, n)
    expected = Observation((m > n) - (m < n), abs(m - n))
    frontier = min(m, n) + 1
    rng = random.Random(seed)
    main = cleanup = steps = 0
    first_read_step = None
    while net.active():
        pair = choose_redex(net, strategy, rng)
        kinds = tuple(sorted(net.nodes[x] for x in pair))
        assert kinds in (('g', 'g'), ('e', 'e')), kinds
        net.reduce(*pair)
        steps += 1
        if kinds == ('g', 'g'):
            main += 1
        else:
            cleanup += 1
        observation = observe(net, a, b)
        if main < frontier:
            assert observation is None, (m, n, main, observation)
        else:
            assert observation == expected, (m, n, observation, expected)
            if first_read_step is None:
                first_read_step = steps
                # The final gamma-gamma collision just created a tag pair:
                # the output is visible strictly BEFORE global quiescence.
                assert net.active(), (m, n, 'unexpected quiescence')
                assert all(net.nodes[x] == net.nodes[y] == 'e'
                           for x, y in net.active())
        assert steps <= 2*frontier
    assert main == cleanup == frontier
    assert steps == 2*frontier
    assert frontier <= first_read_step < 2*frontier
    assert observe(net, a, b) == expected
    assert net.cycles == 0
    assert len(net.nodes) == 2*abs(m - n)
    assert set(net.nodes.values()) <= {'g', 'e'}
    assert sum(v == 'g' for v in net.nodes.values()) == abs(m - n)
    assert sum(v == 'e' for v in net.nodes.values()) == abs(m - n)
    net.check()
    return {'m': m, 'n': n, 'observation': expected,
            'steps': steps, 'frontier_steps': main,
            'first_read_step': first_read_step,
            'cells_final': len(net.nodes)}


def audit_head_first(m, n):
    """Expose exactly how much cleanup remains at the first readable state."""
    net, a, b = build(m, n)
    frontier = min(m, n) + 1
    for _ in range(frontier):
        gamma_pairs = [(u, v) for u, v in net.active()
                       if net.nodes[u] == net.nodes[v] == 'g']
        assert len(gamma_pairs) == 1
        net.reduce(*gamma_pairs[0])
    expected = Observation((m > n) - (m < n), abs(m-n))
    assert observe(net, a, b) == expected
    assert len(net.active()) == frontier
    assert all(net.nodes[u] == net.nodes[v] == 'e' for u, v in net.active())
    for _ in range(frontier):
        assert observe(net, a, b) == expected
        pairs = net.active()
        assert pairs
        net.reduce(*pairs[0])
    assert not net.active()
    assert observe(net, a, b) == expected
    return frontier


def main():
    cases = 0
    for m in range(25):
        for n in range(25):
            for strategy in ('random', 'gamma-first', 'epsilon-first'):
                audit_pair(m, n, strategy, seed=113*m+131*n)
                cases += 1
    print(f'PASS: {cases} complete native IC comparisons for 0<=m,n<25')
    for m, n in ((0, 200), (200, 0), (81, 80), (80, 81),
                 (81, 81), (144, 143), (144, 144), (200, 200)):
        for seed in range(16):
            audit_pair(m, n, seed=seed)
        pending = audit_head_first(m, n)
        result = audit_pair(m, n, strategy='epsilon-first')
        print(f'PAIR {m}:{n} -> {result["observation"]}; '
              f'gamma collisions {pending}; all-IC steps {result["steps"]}; '
              f'output available with {pending} independent cleanup redexes')
    print('PASS: signed unary difference emerges as stable IC output topology, '
          'observable strictly before all local IC reductions finish')
    print('SCOPE: comparator component only, not a CMP rule or square-checker compiler')


if __name__ == '__main__':
    main()
