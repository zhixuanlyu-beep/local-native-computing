"""A single-output tagged sum selected by primitive IC comparison and erasure.

Inputs: two independently specified natural numbers m,n and two opaque,
fully paired reduced gamma/epsilon packages A,B. Both packages are placed
in the initial network *regardless* of the relative sizes of m and n.

Only the six primitive Lafont IC interactions run. The single OUT port
normalizes to one of three *different constructor forms*:

    m > n : gamma(Tagged(A), epsilon)
    m = n : gamma(epsilon, epsilon)
    m < n : gamma(epsilon, Tagged(B))

where Tagged(X) = gamma(X, Loop), Loop = gamma with its two auxiliary
ports connected to each other. The winner tag prevents an epsilon-valued
payload from being confused with an absent branch. No result-dependent
wiring or observer-issued rewrite happens during execution.

The same result can be statically wired to native delta copying, epsilon
erasure, or a gamma/gamma and gamma/case *deconstructor*. In the last case
four labeled ports contain (positive flag, positive payload, negative
flag, negative payload), where flags are the distinguishable epsilon/Loop
tokens and inactive payloads are epsilon.

This is a *tagged-sum conditional datapath*, not the bare-root choice of
one payload and not the 14-symbol source GATE. There is no equality
payload or compiled source CMP/GATE. Source-rule coverage remains 4/15.
"""
import random

from ic_primitive_port_verifier import Net, isomorphic
from ic_signed_branch_pruning import HOLE, package, random_package


def loop_token(net):
    """One-port reduced IC token with a self-paired gamma auxiliary pair."""
    g = net.cell("g")
    net.link((g, 1), (g, 2))
    return (g, 0)


def cancellation_chain(net, n, side, tail):
    """Independent unary input. Left tags are loops; right tags are epsilon.

    Each side includes a zero sentinel. Opposite gamma principal collisions
    pair their tags; a loop/epsilon tag pair locally disappears without
    producing inert wire cycles. Unmatched left successors keep Loop tags.
    """
    assert type(n) is int and n >= 0 and side in ("L", "R")
    child = 1 if side == "L" else 2
    tag = 3 - child
    root = None
    for i in range(n + 1):
        g = net.cell("g")
        marker = loop_token(net) if side == "L" else (net.cell("e"), 0)
        net.link((g, tag), marker)
        net.link((g, child), tail if i == 0 else root)
        root = (g, 0)
    return root


def difference_channel(net, m, n, label):
    """Produce max(m-n,0) in unary gamma(child,Loop)/epsilon form."""
    left_probe = net.cell("e")
    right_probe = net.cell("d")
    sink = net.cell("e")
    left = cancellation_chain(net, m, "L", (left_probe, 0))
    right = cancellation_chain(net, n, "R", (right_probe, 0))
    net.link(left, right)
    output = net.boundary(label)
    net.link((right_probe, 1), output)
    net.link((right_probe, 2), (sink, 0))
    return output


def remove_boundary_and_link(net, boundary, consumer):
    """Build-time port splice only; never called during IC reduction."""
    context = net.adj.pop(boundary)
    net.free.remove(boundary)
    net.adj[context] = None
    net.link(context, consumer)


def guarded_option(net, difference, sum_port, description):
    """CASE(zero/successor) followed by gamma-probe conditional transport.

    With zero the probe connects epsilon to the sum slot and erases the
    candidate package; with successor the Loop token joins the slot to
    a tagged candidate, while the remaining predecessor is erased.
    """
    case = net.cell("g")
    remove_boundary_and_link(net, difference, (case, 0))
    erase_predecessor = net.cell("e")
    net.link((case, 2), (erase_predecessor, 0))
    probe = net.cell("g")
    net.link((case, 1), (probe, 0))
    root, ids, wires = package(net, *description)

    wrapper = net.cell("g")
    net.link((wrapper, 1), root)
    net.link((wrapper, 2), loop_token(net))
    net.link((probe, 1), sum_port)
    net.link((probe, 2), (wrapper, 0))
    return ids


def build(m, n, positive, negative, consumer="sum"):
    """Construct all source data and candidate packages before evolution.

    The builder does not calculate sign(m-n), select a package, or delete
    a package. Only consumer mode (an interface choice) changes wiring.
    """
    assert type(m) is int and type(n) is int and m >= 0 and n >= 0
    assert consumer in ("sum", "copy", "erase", "unpack")
    net = Net()
    p = difference_channel(net, m, n, "P")
    q = difference_channel(net, n, m, "N")
    result = net.cell("g")
    positive_ids = guarded_option(net, p, (result, 1), positive)
    negative_ids = guarded_option(net, q, (result, 2), negative)

    if consumer == "sum":
        net.link((result, 0), net.boundary("OUT"))
    elif consumer == "copy":
        d = net.cell("d")
        net.link((result, 0), (d, 0))
        for port in (1, 2):
            net.link((d, port), net.boundary("OUT" + str(port)))
    elif consumer == "erase":
        eraser = net.cell("e")
        net.link((result, 0), (eraser, 0))
    else:
        split = net.cell("g")
        net.link((result, 0), (split, 0))
        # gamma-gamma swaps A1<->B2 and A2<->B1.
        for name, slot in (("POS", 2), ("NEG", 1)):
            case = net.cell("g")
            net.link((split, slot), (case, 0))
            net.link((case, 1), net.boundary(name + "_FLAG"))
            net.link((case, 2), net.boundary(name + "_DATA"))
    net.check()
    return net, positive_ids, negative_ids


def expected_normal_form(m, n, positive, negative, consumer):
    """Independent structural specification: no IC reductions are invoked."""
    net = Net()
    if consumer == "erase":
        return net

    def option(is_selected, description):
        if not is_selected:
            return (net.cell("e"), 0)
        payload, _, _ = package(net, *description)
        wrapper = net.cell("g")
        net.link((wrapper, 1), payload)
        net.link((wrapper, 2), loop_token(net))
        return (wrapper, 0)

    def sum_value(boundary):
        root = net.cell("g")
        net.link((root, 1), option(m > n, positive))
        net.link((root, 2), option(m < n, negative))
        net.link((root, 0), net.boundary(boundary))

    if consumer == "sum":
        sum_value("OUT")
    elif consumer == "copy":
        sum_value("OUT1")
        sum_value("OUT2")
    elif consumer == "unpack":
        for side, present, description in (
            ("POS", m > n, positive),
            ("NEG", m < n, negative),
        ):
            flag = loop_token(net) if present else (net.cell("e"), 0)
            data = package(net, *description)[0] if present else (net.cell("e"), 0)
            net.link(flag, net.boundary(side + "_FLAG"))
            net.link(data, net.boundary(side + "_DATA"))
    else:
        raise ValueError(consumer)
    net.check()
    return net


def reduce_native(net, strategy="random", seed=0):
    """A schedule choice, never a semantic operation or sign inspection."""
    limit = 40 * (len(net.nodes) + 1)
    rng = random.Random(seed)
    count = 0
    while net.active():
        pairs = net.active()
        if strategy == "random":
            pair = rng.choice(pairs)
        elif strategy == "first":
            pair = pairs[0]
        elif strategy == "last":
            pair = pairs[-1]
        elif strategy == "epsilon-first":
            pair = next((p for p in pairs
                         if all(net.nodes[x] == "e" for x in p)), pairs[0])
        elif strategy == "delta-first":
            pair = next((p for p in pairs
                         if any(net.nodes[x] == "d" for x in p)), pairs[0])
        else:
            raise ValueError(strategy)
        net.reduce(*pair)
        count += 1
        assert count <= limit, ("non-termination guard", strategy, count)
    net.check()
    return count


def certify(m, n, positive, negative, consumer, strategy="random", seed=0):
    net, pids, nids = build(m, n, positive, negative, consumer)
    initial = dict(net.adj)
    target = expected_normal_form(m, n, positive, negative, consumer)
    assert not target.active()
    steps = reduce_native(net, strategy, seed)
    assert isomorphic(net, target), (m, n, consumer, strategy, steps)
    assert net.cycles == 0
    if consumer == "sum":
        for ids, chosen in ((pids, m > n), (nids, m < n)):
            assert (ids & set(net.nodes)) == (ids if chosen else set())
            if chosen:
                # Opaque package internal structure is untouched, even if
                # it contains gamma auxiliary-to-auxiliary wire matchings.
                for c in ids:
                    typ = net.nodes[c]
                    for port in range(1 if typ == "e" else 3):
                        assert net.adj[(c, port)] == initial[(c, port)]
    return steps, len(net.nodes)


def probe_token(old_style):
    """Compare the old gamma(e,e) vs a genuine loop-gamma token.

    One primitive gamma probe sees old gamma(e,e) exactly as epsilon: both
    yield two epsilon outputs. The loop-gamma instead connects those two
    outputs directly. This is a *specific distinguishing context*, not a
    global contextual-equivalence theorem about arbitrary IC nets.
    """
    def probe(tag):
        net = Net()
        g = net.cell("g")
        if tag == "epsilon":
            root = (net.cell("e"), 0)
        elif tag == "old":
            old = net.cell("g")
            a, b = net.cell("e"), net.cell("e")
            net.link((old, 1), (a, 0))
            net.link((old, 2), (b, 0))
            root = (old, 0)
        else:
            root = loop_token(net)
        net.link((g, 0), root)
        net.link((g, 1), net.boundary("L"))
        net.link((g, 2), net.boundary("R"))
        reduce_native(net, "first")
        return net

    false = probe("epsilon")
    old = probe("old")
    genuine = probe("loop")
    assert isomorphic(false, old)
    assert not isomorphic(false, genuine)
    assert len(genuine.nodes) == 0
    assert genuine.adj[("F", "L")] == ("F", "R")
    assert len(false.nodes) == 2
    return True


def main():
    probe_token(False)
    print("PASS: loop-gamma truth token is distinguishable by a gamma probe;"
          " gamma(e,e) is not distinguishable in that probe")

    # Including a candidate that is exactly epsilon is essential: the
    # guarded payload wrapper must retain sign information even for it.
    empty = (("e",), ())
    wired = (("g", ("g", HOLE, HOLE), ("g", HOLE, HOLE)),
             ((0, 2), (1, 3)))
    tree = (("g", ("e",), ("g", ("e",), ("e",))), ())
    inputs = ((wired, tree), (empty, wired), (tree, empty), (empty, empty))
    strategies = ("first", "last", "epsilon-first", "delta-first", "random")
    modes = ("sum", "copy", "erase", "unpack")

    count = 0
    for m in range(11):
        for n in range(11):
            pos, neg = inputs[(m + 2*n) % len(inputs)]
            for mode in modes:
                totals = {certify(m, n, pos, neg, mode, schedule,
                                  179*m + 131*n)
                          for schedule in strategies}
                assert len(totals) == 1, (m, n, mode, totals)
                count += len(strategies)
    print("PASS:", count, "small complete signed-sum reductions including"
          " copy, erase, and typed unpacking")

    rng = random.Random(20261104)
    for case in range(100):
        m, n = rng.randrange(19), rng.randrange(19)
        pos, neg = random_package(rng), random_package(rng)
        for mode in modes:
            for seed in (case, case + 37):
                certify(m, n, pos, neg, mode, "random", seed)
    print("PASS: 800 randomized fully paired reduced-package contexts")

    for m, n in ((0, 0), (0, 200), (200, 0),
                 (81, 80), (80, 81), (81, 81), (100, 120), (200, 200)):
        measures = {mode: certify(m, n, wired, empty, mode, "random", m+n)
                    for mode in modes}
        for mode in modes:
            other = certify(m, n, wired, empty, mode, "last", m+n)
            assert other == measures[mode]
        print(f"CASE {m}:{n} full IC steps/cells: {measures}")

    print("PASS: one fixed tagged-sum output, exact independently constructed"
          " normal forms and native IC downstream consumers")
    print("LIMIT: no equality payload, no bare-payload unified output,"
          " no source CMP or GATE certificate (still 4/15)")


if __name__ == "__main__":
    main()
