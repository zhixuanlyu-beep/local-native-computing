"""Three-way, one-port, native Interaction Combinators tagged selection.

The constructor allocates *all* three opaque reduced gamma/epsilon packages
(A, B, C) and independently builds three unary comparison channels:
  - positive difference, m - n, activates A;
  - a direct sentinel-equality channel activates B iff m == n;
  - negative difference, n - m, activates C.

All selection and losing-package erasure is done by the original SIX IC
rewrites, never by the constructor or by a Python runtime conditional.

The fixed output has the ordered representation

  gamma(Option(A), gamma(Option(B), Option(C)))

where Option(X) = gamma(X, Loop), Loop = gamma(aux1--aux2) when selected,
and Option(X) = epsilon otherwise. Exactly ONE option is present, including
at equality, and empty (epsilon) payloads remain distinguishable.

Downstream consumers are fixed in the initial net. Tests exercise:
  sum:         retain a single port with the tagged three-way result;
  copy:        native delta duplicates that entire result;
  erase:       native epsilon erases the whole result;
  unpack:      gamma interaction exposes six typed flag/data ports;
  unpack_copy: delta immediately duplicates the unpacked data payloads.

Crucial boundary: this is not an unwrapped bare-output selector and not an
operational lowering for the source CMP/GATE nodes. The original 4/15 source
rule certificates remain unchanged. The three integer chains are constructed
from independent copies; this is not an optimized/shared-input compiler.
"""
import random

from ic_primitive_port_verifier import Net, isomorphic
from ic_signed_branch_pruning import HOLE, package, random_package
from ic_signed_sum_selector import (difference_channel, guarded_option,
                                    loop_token, reduce_native)


MODES = ("sum", "copy", "erase", "unpack", "unpack_copy")
SCHEDULES = ("first", "last", "epsilon-first", "delta-first", "random")


def equality_channel(net, m, n, candidate, slot):
    """Native equality-only channel without computing or inspecting m == n.

    All successor tags are epsilon. Each zero sentinel holds a distinguished
    gamma tag. Its left tag carries a prebuilt Tagged(candidate), while the
    right tag has the fixed output slot as an auxiliary. When *both* zero
    sentinels meet, gamma-gamma and gamma-gamma interactions connect the
    candidate wrapper directly to the slot. If a sentinel meets an opposing
    successor first, a gamma-epsilon interaction erases the candidate and
    supplies epsilon at the slot.

    The unmatched continuation is erased by epsilon originating at the
    sentinel tail. No observation or conditional scheduling is needed.
    """
    assert type(m) is int and type(n) is int and m >= 0 and n >= 0
    root, ids, _ = package(net, *candidate)
    wrapper = net.cell("g")
    net.link((wrapper, 1), root)
    net.link((wrapper, 2), loop_token(net))

    left_tag = net.cell("g")
    right_tag = net.cell("g")
    net.link((left_tag, 1), (wrapper, 0))
    net.link((left_tag, 2), (net.cell("e"), 0))
    net.link((right_tag, 1), (net.cell("e"), 0))
    net.link((right_tag, 2), slot)

    left_zero = net.cell("g")
    right_zero = net.cell("g")
    net.link((left_zero, 1), (net.cell("e"), 0))
    net.link((left_zero, 2), (left_tag, 0))
    net.link((right_zero, 1), (right_tag, 0))
    net.link((right_zero, 2), (net.cell("e"), 0))

    left, right = (left_zero, 0), (right_zero, 0)
    for _ in range(m):
        g = net.cell("g")
        net.link((g, 1), left)
        net.link((g, 2), (net.cell("e"), 0))
        left = (g, 0)
    for _ in range(n):
        g = net.cell("g")
        net.link((g, 1), (net.cell("e"), 0))
        net.link((g, 2), right)
        right = (g, 0)
    net.link(left, right)
    return ids


def build(m, n, positive, equal, negative, mode="sum"):
    """Prewire all comparison chains, all three candidates and the consumer.

    There is NO conditional on m versus n in the constructor. Values are
    used only as sizes of independently allocated unary chains.
    """
    assert type(m) is int and type(n) is int and m >= 0 and n >= 0
    assert mode in MODES
    net = Net()

    positive_diff = difference_channel(net, m, n, "POS_DIFF")
    negative_diff = difference_channel(net, n, m, "NEG_DIFF")

    top = net.cell("g")
    mid = net.cell("g")
    net.link((top, 2), (mid, 0))
    positive_ids = guarded_option(net, positive_diff, (top, 1), positive)
    equal_ids = equality_channel(net, m, n, equal, (mid, 1))
    negative_ids = guarded_option(net, negative_diff, (mid, 2), negative)

    if mode == "sum":
        net.link((top, 0), net.boundary("OUT"))
    elif mode == "copy":
        d = net.cell("d")
        net.link((top, 0), (d, 0))
        for i in (1, 2):
            net.link((d, i), net.boundary("OUT" + str(i)))
    elif mode == "erase":
        net.link((top, 0), (net.cell("e"), 0))
    else:
        # gamma-gamma cross-link:
        # outer splitter port2 -> positive option;
        # outer splitter port1 -> inner triple's gamma principal.
        outer = net.cell("g")
        net.link((top, 0), (outer, 0))
        inner = net.cell("g")
        net.link((outer, 1), (inner, 0))
        for label, source in (
            ("POS", (outer, 2)),
            ("EQ", (inner, 2)),
            ("NEG", (inner, 1)),
        ):
            # For option gamma(payload, Loop), gamma-gamma passes the Loop
            # to FLAG and the selected payload to DATA. For absent epsilon,
            # gamma-epsilon produces epsilon on *both* ports.
            case = net.cell("g")
            net.link((case, 0), source)
            net.link((case, 1), net.boundary(label + "_FLAG"))
            if mode == "unpack":
                net.link((case, 2), net.boundary(label + "_DATA"))
            else:
                d = net.cell("d")
                net.link((case, 2), (d, 0))
                for i in (1, 2):
                    net.link((d, i),
                             net.boundary(label + "_DATA" + str(i)))

    net.check()
    return net, (positive_ids, equal_ids, negative_ids)


def expected_normal_form(m, n, positive, equal, negative, mode):
    """Build the target independently; do not run any IC interactions."""
    assert mode in MODES
    net = Net()
    if mode == "erase":
        return net

    selected = (m > n, m == n, m < n)
    packages = (positive, equal, negative)

    def option(is_present, description):
        if not is_present:
            return (net.cell("e"), 0)
        payload, _, _ = package(net, *description)
        wrapper = net.cell("g")
        net.link((wrapper, 1), payload)
        net.link((wrapper, 2), loop_token(net))
        return (wrapper, 0)

    def sum_value(name):
        root = net.cell("g")
        inner = net.cell("g")
        net.link((root, 1), option(selected[0], positive))
        net.link((root, 2), (inner, 0))
        net.link((inner, 1), option(selected[1], equal))
        net.link((inner, 2), option(selected[2], negative))
        net.link((root, 0), net.boundary(name))

    if mode == "sum":
        sum_value("OUT")
    elif mode == "copy":
        sum_value("OUT1")
        sum_value("OUT2")
    else:
        for label, is_present, description in zip(
            ("POS", "EQ", "NEG"), selected, packages
        ):
            flag = (loop_token(net) if is_present
                    else (net.cell("e"), 0))
            net.link(flag, net.boundary(label + "_FLAG"))
            if mode == "unpack":
                payload = (package(net, *description)[0] if is_present
                           else (net.cell("e"), 0))
                net.link(payload, net.boundary(label + "_DATA"))
            else:
                for i in (1, 2):
                    payload = (package(net, *description)[0] if is_present
                               else (net.cell("e"), 0))
                    net.link(payload,
                             net.boundary(label + "_DATA" + str(i)))
    net.check()
    return net


def certify(m, n, positive, equal, negative, mode="sum",
            strategy="random", seed=0):
    """Check independently specified exact normal form and package identity."""
    net, candidates = build(m, n, positive, equal, negative, mode)
    initial = dict(net.adj)
    expected = expected_normal_form(m, n, positive, equal, negative, mode)
    assert not expected.active()
    steps = reduce_native(net, strategy, seed)
    assert isomorphic(net, expected), (m, n, mode, strategy, steps)
    assert net.cycles == expected.cycles == 0

    if mode == "sum":
        # Each opaque candidate is built exactly once; only winner survives.
        for ids, chosen in zip(candidates, (m > n, m == n, m < n)):
            assert (ids & set(net.nodes)) == (ids if chosen else set())
            if chosen:
                for c in ids:
                    assert c in net.nodes
                    arity = 0 if net.nodes[c] == "e" else 2
                    for port in range(arity + 1):
                        assert net.adj[(c, port)] == initial[(c, port)]
    return steps, len(net.nodes)


def certify_equality_only(m, n, description, strategy="random", seed=0):
    """A separate local certificate for the zero-sentinel equality lemma."""
    net = Net()
    out = net.boundary("EQ")
    original = dict(net.adj)
    ids = equality_channel(net, m, n, description, out)
    original = dict(net.adj)
    net.check()

    expected = Net()
    output = expected.boundary("EQ")
    if m == n:
        payload, _, _ = package(expected, *description)
        wrapper = expected.cell("g")
        expected.link((wrapper, 1), payload)
        expected.link((wrapper, 2), loop_token(expected))
        expected.link((wrapper, 0), output)
    else:
        expected.link((expected.cell("e"), 0), output)
    expected.check()
    steps = reduce_native(net, strategy, seed)
    assert isomorphic(net, expected), (m, n, strategy, steps)
    assert (ids & set(net.nodes)) == (ids if m == n else set())
    if m == n:
        for c in ids:
            for port in range(1 if net.nodes[c] == "e" else 3):
                assert net.adj[(c, port)] == original[(c, port)]
    assert net.cycles == 0
    return steps


def main():
    empty = (("e",), ())
    wired = (("g", ("g", HOLE, HOLE), ("g", HOLE, HOLE)),
             ((0, 2), (1, 3)))
    tree = (("g", ("e",), ("g", ("e",), ("e",))), ())
    examples = ((wired, empty, tree),
                (empty, wired, tree),
                (tree, empty, wired))

    # Isolate the new equality lemma, including equality and near misses.
    equality_count = 0
    for m in range(10):
        for n in range(10):
            desc = examples[(m + n) % len(examples)][1]
            for strategy in ("first", "last", "random"):
                certify_equality_only(m, n, desc, strategy, m * 73 + n)
                equality_count += 1
    print("PASS:", equality_count,
          "independent native IC zero-sentinel equality certificates")

    count = 0
    for m in range(8):
        for n in range(8):
            descriptions = examples[(m + 2*n) % len(examples)]
            for mode in MODES:
                measures = {
                    certify(m, n, *descriptions, mode,
                            strategy, seed=101*m + 131*n)
                    for strategy in SCHEDULES
                }
                assert len(measures) == 1, (m, n, mode, measures)
                count += len(SCHEDULES)
    print("PASS:", count,
          "full three-way tests over all modes and five IC schedules")

    rng = random.Random(20261104)
    random_count = 0
    for case in range(80):
        m, n = rng.randrange(19), rng.randrange(19)
        descriptions = tuple(random_package(rng) for _ in range(3))
        for mode in MODES:
            for seed in (case, case + 37):
                certify(m, n, *descriptions, mode, "random", seed)
                random_count += 1
    print("PASS:", random_count,
          "randomized fully paired reduced three-package contexts")

    for m, n in ((0, 0), (0, 200), (200, 0),
                 (81, 80), (80, 81), (81, 81),
                 (100, 120), (200, 200)):
        measures = {}
        for mode in MODES:
            outcome = certify(m, n, wired, empty, tree, mode, "random",
                              m+n)
            assert certify(m, n, wired, empty, tree, mode, "last", m+n) == outcome
            measures[mode] = outcome
        print(f"CASE {m}:{n} primitive steps/final cells: {measures}")

    print("PASS: three alternatives on ONE output; two losers erased, "
          "one winner retained, including at equality")
    print("PASS: real native IC copy, erase, unpack and unpacked-data copy")
    print("LIMIT: tagged union, NOT a bare-output 3-way GATE or complete "
          "source-square-checker compiler; 4/15 source rules unchanged")


if __name__ == "__main__":
    main()
