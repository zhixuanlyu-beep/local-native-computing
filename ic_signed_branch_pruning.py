"""Primitive-IC conditional *pruning*, with an explicit control-port boundary.

A complementary gamma/epsilon cancellation front meets two gamma probes.
Each probe protects a fanout delta with two finite gamma/epsilon packages.
If m>n only positive packages survive, if m<n only negative packages
survive, and if m==n both sets are erased. No Boolean is read by the
scheduler and no source-level rewrite is invoked. Runtime = Net.reduce.

This is not a general three-way selector: it has no equality payload, and
surviving packages remain tethered to a passive control port. External
contexts can erase those survivors by interacting with that port.
"""
import random
from ic_primitive_port_verifier import Net

HOLE = "H"


def cancellation_chain(net, length, side, tail):
    assert side in ("L", "R") and type(length) is int and length >= 0
    child = 1 if side == "L" else 2
    tag = 3 - child
    root = None
    for k in range(length + 1):
        g, e = net.cell("g"), net.cell("e")
        net.link((g, tag), (e, 0))
        net.link((g, child), tail if k == 0 else root)
        root = (g, 0)
    return root


def package(net, shape, matching):
    """Build a reduced gamma/epsilon package, including paired leaf wires."""
    holes = []

    def walk(s):
        assert s != HOLE
        assert s[0] in ("g", "e")
        c = net.cell(s[0])
        if s[0] == "g":
            assert len(s) == 3
            for i, part in ((1, s[1]), (2, s[2])):
                if part == HOLE:
                    holes.append((c, i))
                else:
                    net.link((c, i), walk(part))
        else:
            assert s == ("e",)
        return (c, 0)

    before = set(net.nodes)
    root = walk(shape)
    assert len(holes) == 2 * len(matching)
    assert sorted(x for a, b in matching for x in (a, b)) == list(range(len(holes)))
    for a, b in matching:
        net.link(holes[a], holes[b])
    return root, set(net.nodes) - before, len(matching)


def guarded_pair(net, incoming, descriptions):
    """A guarded delta routes a possible epsilon signal to two packages."""
    assert len(descriptions) == 2
    gate, fanout, tag = net.cell("g"), net.cell("d"), net.cell("e")
    net.link(incoming, (gate, 0))
    net.link((gate, 1), (fanout, 0))
    net.link((gate, 2), (tag, 0))
    packages = []
    for port, (shape, matching) in enumerate(descriptions, 1):
        root, ids, wires = package(net, shape, matching)
        net.link((fanout, port), root)
        packages.append((ids, wires))
    return {"gate": gate, "fanout": fanout, "tag": tag, "packages": packages}


def build(m, n, positive, negative):
    """Build without inspecting m>n: all four candidate packages exist."""
    assert type(m) is int and type(n) is int and m >= 0 and n >= 0
    net = Net()
    left, right = net.cell("g"), net.cell("g")
    x, v = net.boundary("X"), net.boundary("V")
    net.link((left, 1), x)
    net.link((right, 2), v)
    plus = guarded_pair(net, (left, 2), positive)
    minus = guarded_pair(net, (right, 1), negative)
    l = cancellation_chain(net, m, "L", (left, 0))
    r = cancellation_chain(net, n, "R", (right, 0))
    net.link(l, r)
    net.check()
    return net, plus, minus, x, v


def reduce_all(net, strategy="random", seed=0):
    rng = random.Random(seed)
    limit = 20 * (len(net.nodes) + 1)
    steps = 0
    while net.active():
        pairs = net.active()
        if strategy == "random":
            pair = rng.choice(pairs)
        elif strategy == "first":
            pair = pairs[0]
        elif strategy == "last":
            pair = pairs[-1]
        elif strategy == "epsilon-first":
            pair = next((p for p in pairs if all(net.nodes[c] == "e" for c in p)), pairs[0])
        elif strategy == "delta-first":
            pair = next((p for p in pairs if any(net.nodes[c] == "d" for c in p)), pairs[0])
        else:
            raise ValueError(strategy)
        net.reduce(*pair)
        steps += 1
        assert steps <= limit, ("step bound", steps, limit)
    net.check()
    return steps


def check(m, n, positive, negative, strategy="random", seed=0):
    net, plus, minus, x, v = build(m, n, positive, negative)
    original = dict(net.adj)
    pids = set().union(*(ids for ids, wires in plus["packages"]))
    nids = set().union(*(ids for ids, wires in minus["packages"]))
    assert pids.isdisjoint(nids)
    steps = reduce_all(net, strategy, seed)
    for ctx, ids, selected in ((plus, pids, m > n), (minus, nids, m < n)):
        assert ids & set(net.nodes) == (ids if selected else set())
        for c in ids if selected else ():
            for port in range(1 if net.nodes[c] == "e" else 3):
                assert net.adj[(c, port)] == original[(c, port)]
        for component in ("gate", "fanout", "tag"):
            assert (ctx[component] in net.nodes) == selected

    # The signed residual path retains one of the two outer gamma probes
    # when unequal, hence the additional -1 compared with a standalone
    # unguarded signed-difference path.
    expected_nodes = sum(len(ids) for ids, _ in plus["packages"]) + 3 if m > n else 0
    expected_nodes += sum(len(ids) for ids, _ in minus["packages"]) + 3 if m < n else 0
    expected_nodes += max(0, 2 * abs(m - n) - 1)
    assert len(net.nodes) == expected_nodes, (m, n, len(net.nodes), expected_nodes)
    assert net.cycles == 0
    assert (net.adj[x] == v) == (m == n)
    k = min(m, n) + 1
    work_p = sum(len(ids) + wires for ids, wires in plus["packages"])
    work_n = sum(len(ids) + wires for ids, wires in minus["packages"])
    expected_steps = 2 * k + 4 + (
        work_n if m > n else work_p if m < n else work_p + work_n
    )
    assert steps == expected_steps, (m, n, steps, expected_steps)
    return steps, len(net.nodes)


def random_shape(rng, depth):
    if depth == 0:
        return HOLE if rng.random() < 0.4 else ("e",)
    if rng.random() < 0.15:
        return ("e",)
    return ("g", random_shape(rng, depth - 1), random_shape(rng, depth - 1))


def hole_count(shape):
    if shape == HOLE:
        return 1
    return 0 if shape[0] == "e" else hole_count(shape[1]) + hole_count(shape[2])


def random_package(rng):
    while True:
        shape = ("g", random_shape(rng, 3), random_shape(rng, 3)) if rng.random() < 0.85 else ("e",)
        count = hole_count(shape)
        if count % 2 == 0:
            break
    ports = list(range(count))
    rng.shuffle(ports)
    return shape, tuple(zip(ports[::2], ports[1::2]))


def adversarial_context():
    """A real counterexample: control-port epsilon can erase a 'winner'."""
    sample = (("g", ("g", HOLE, HOLE), ("g", HOLE, HOLE)), ((0, 2), (1, 3)))
    tree = (("g", ("e",), ("g", ("e",), ("e",))), ())
    for m, n, label in ((2, 0, "V"), (0, 2, "X"),
                         (81, 80, "V"), (80, 81, "X")):
        net, plus, minus, x, v = build(m, n, [sample, tree], [tree, sample])
        candidate_ids = set().union(*(ids for ctx in (plus, minus)
                                      for ids, wires in ctx["packages"]))
        boundary = v if label == "V" else x
        neighbor = net.adj.pop(boundary)
        net.free.remove(boundary)
        net.adj[neighbor] = None
        eraser = net.cell("e")
        net.link(neighbor, (eraser, 0))
        net.check()
        reduce_all(net, "random", m + n)
        assert not (candidate_ids & set(net.nodes))
    print("PASS: counterexample shows retention is NOT stable under arbitrary control-port contexts")


def main():
    sample = (("g", ("g", HOLE, HOLE), ("g", HOLE, HOLE)), ((0, 2), (1, 3)))
    tree = (("g", ("e",), ("g", ("e",), ("e",))), ())
    positive, negative = [sample, tree], [tree, sample]
    count = 0
    for m in range(18):
        for n in range(18):
            for strategy in ("random", "first", "last", "epsilon-first", "delta-first"):
                check(m, n, positive, negative, strategy, m * 31 + n)
                count += 1
    print("PASS:", count, "IC guarded branch pruning tests with non-tree package wiring")
    rng = random.Random(20261104)
    for case in range(160):
        m, n = rng.randrange(25), rng.randrange(25)
        p, q = [random_package(rng) for _ in range(2)], [random_package(rng) for _ in range(2)]
        for i in range(3):
            check(m, n, p, q, "random", case * 17 + i)
    print("PASS: 480 randomized multi-package wiring tests")
    for m, n in ((0, 0), (0, 200), (200, 0), (81, 80), (80, 81),
                 (81, 81), (82, 80), (80, 82), (200, 200)):
        results = {check(m, n, positive, negative, schedule)
                   for schedule in ("first", "last", "epsilon-first", "delta-first", "random")}
        assert len(results) == 1, (m, n, results)
        print(f"{m}:{n}: IC steps and surviving cells {next(iter(results))}")
    adversarial_context()
    print("SCOPE: conditional pruning, not unified-output switching or the source GATE")


if __name__ == "__main__":
    main()
