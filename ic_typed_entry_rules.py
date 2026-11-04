"""Two additional *interface-typed, isolated-redex* source-to-IC certificates.

The source rules used are taken from source_feedback_audit.RULES:
  INIT-Z  : INIT( n ) -> SQ(Z), connected at output interface A1
  CMP0-Z  : CMP0(...) -> EQ at A1 and Z at A2

Only for these two interactions, the following target is used:
  INIT -> gamma(A1, epsilon-private-tag)
  CMP0 -> gamma(A1, A2)
  Z -> epsilon
  EQ -> epsilon in a T-typed interface
  SQ(Z) -> a Z-valued epsilon at the O-typed interface (type-directed
           transparent output wrapper, NOT an encoding of arbitrary SQ).

INIT-Z therefore reduces as gamma-epsilon, epsilon-epsilon (two steps).
CMP0-Z reduces as gamma-epsilon (one step). All reductions call the
original primitive Net.reduce. The independent RHS construction consults
the actual source rule specifications and verifies all specified ports.

WARNING: this is a typed interface projection of two isolated redexes, not
a single compositional lowering for all occurrences of INIT, CMP0, EQ, SQ
or Z in the full source program. EQ and Z collide as untyped epsilon; SQ
is transparent ONLY in the restricted RHS SQ(Z) output arrangement.
Neither the earlier 4/15 coherent unary fragment nor the 14-symbol source
compiler has been extended. The project should keep the conservative
operational *coherent-source-fragment* count at 4/15.
"""
import itertools
import random

from ic_primitive_port_verifier import Net, isomorphic
from source_feedback_audit import RULES, AR
from source_rule_audit_v3 import PORTS


PAIRS = (("INIT", "Z"), ("CMP0", "Z"))
STEPS = {("INIT", "Z"): 2, ("CMP0", "Z"): 1}


def spec_for(a, b):
    spec = RULES[frozenset((a, b))]
    assert spec[:2] == (a, b)
    return spec


def lhs(a, b):
    """Only public source auxiliary ports become free IC boundaries."""
    assert (a, b) in PAIRS
    net = Net()
    g = net.cell("g")
    z = net.cell("e")
    net.link((g, 0), (z, 0))
    for p in range(1, AR[a] + 1):
        free = net.boundary("A" + str(p))
        net.link((g, p), free)
    if a == "INIT":
        # INIT has one public aux; second gamma aux is *private*.
        private = net.cell("e")
        net.link((g, 2), (private, 0))
    net.check()
    return net


def rhs_from_source(a, b):
    """Independent rule-specific *typed projection* of the literal RHS.

    The test intentionally rejects any modified source shape or label,
    rather than silently accepting an output inferred from the LHS.
    SQ(Z) projects to its child datum through one O-typed transparent
    wrapper. EQ and Z project to e at differently typed ports.
    """
    assert (a, b) in PAIRS
    _, _, nodes, edges, exterior = spec_for(a, b)
    labels = tuple("A" + str(i) for i in range(1, AR[a] + 1))
    assert set(exterior) == set(labels)
    assert not any(k.startswith("B") for k in exterior)
    assert PORTS[a][0] == PORTS[b][0] or PORTS[a][0][0] != PORTS[b][0][0]
    net = Net()

    if a == "CMP0":
        assert nodes == {"e": "EQ", "z": "Z"}
        assert edges == []
        assert exterior == {"A1": ("e", 0), "A2": ("z", 0)}
        assert PORTS["CMP0"][1] == PORTS["EQ"][0]
        assert PORTS["CMP0"][2] == PORTS["Z"][0]
        for label in labels:
            cell = net.cell("e")
            net.link((cell, 0), net.boundary(label))
    else:
        assert nodes == {"sq": "SQ", "z": "Z"}
        assert edges == [("sq", 1, "z", 0)]
        assert exterior == {"A1": ("sq", 0)}
        assert PORTS["INIT"][1] == PORTS["SQ"][0]
        assert PORTS["SQ"][1] == PORTS["Z"][0]
        # The source SQ output is explicitly a transparent wrapper in this
        # PROJECTION; an independent general SQ semantics is NOT obtained.
        cell = net.cell("e")
        net.link((cell, 0), net.boundary("A1"))

    net.check()
    return net


def attach(net, label, kind):
    """Pre-wire identical passive IC contexts to either side of a redex.

    'free' leaves the labeled boundary alone. 'erase' connects epsilon.
    'copy' connects a native delta and exposes two labeled boundaries.
    These contexts are not source-level typed nodes, so correctness here
    is IC contextual robustness, not a source contextual simulation.
    """
    if kind == "free":
        return
    boundary = ("F", label)
    assert boundary in net.free
    endpoint = net.adj.pop(boundary)
    net.free.remove(boundary)
    net.adj[endpoint] = None

    if kind == "erase":
        c = net.cell("e")
        net.link(endpoint, (c, 0))
    elif kind == "copy":
        c = net.cell("d")
        net.link(endpoint, (c, 0))
        for p in (1, 2):
            net.link((c, p), net.boundary(label + "_copy" + str(p)))
    else:
        raise ValueError(kind)
    net.check()


def reduce_all(net, schedule, seed):
    """Runtime uses ONLY primitive IC redexes; source RULES never execute."""
    rng = random.Random(seed)
    limit = 12 * (len(net.nodes) + 1)
    steps = 0
    while net.active():
        pairs = net.active()
        if schedule == "first":
            pair = pairs[0]
        elif schedule == "last":
            pair = pairs[-1]
        elif schedule == "random":
            pair = rng.choice(pairs)
        else:
            raise ValueError(schedule)
        net.reduce(*pair)
        steps += 1
        assert steps <= limit, ("did not normalize", schedule, steps)
    assert net.cycles == 0
    net.check()
    return steps


def primitive_certificate(a, b):
    net = lhs(a, b)
    target = rhs_from_source(a, b)
    assert len(net.active()) == 1
    count = reduce_all(net, "first", 0)
    assert count == STEPS[a, b], (a, b, count)
    assert isomorphic(net, target), (a, b, "isolated mismatch")
    return count


def contextual_certificates():
    checks = 0
    for a, b in PAIRS:
        labels = tuple("A" + str(i) for i in range(1, AR[a] + 1))
        for contexts in itertools.product(("free", "erase", "copy"),
                                          repeat=len(labels)):
            for schedule in ("first", "last", "random"):
                for seed in range(5):
                    left = lhs(a, b)
                    target = rhs_from_source(a, b)
                    for label, context in zip(labels, contexts):
                        attach(left, label, context)
                        attach(target, label, context)
                    reduce_all(left, schedule, seed)
                    reduce_all(target, schedule, seed)
                    assert isomorphic(left, target), (a, b, contexts, schedule, seed)
                    checks += 1
    return checks


def adversarial_limit():
    """Document two concrete distinctions that prevent a full compiler claim."""
    # At a T-typed interface EQ and a Z-typed interface Z have identical
    # primitive IC representations; source typing is essential.
    for a, b in PAIRS:
        assert PORTS[a][0][0] != PORTS[b][0][0]
    # Source SQ has arity 1, yet the projected SQ(Z) graph has zero gamma
    # cells: the wrapper is not represented as an independently reactive
    # source node. This is intentionally not a source-node encoding.
    net = rhs_from_source("INIT", "Z")
    assert len(net.nodes) == 1 and list(net.nodes.values()) == ["e"]
    assert PORTS["SQ"][0][1] == "O"
    return True


def main():
    for a, b in PAIRS:
        count = primitive_certificate(a, b)
        print(f"CERT (typed isolated): {a}-{b}, {count} primitive IC reductions")
    checks = contextual_certificates()
    assert checks == (3 + 9) * 3 * 5
    adversarial_limit()
    print(f"PASS: {checks} pre-wired IC context/schedule/refinement checks")
    print("LIMIT: transparent SQ(Z), typed EQ/Z and isolated redexes only;")
    print("LIMIT: coherent unary source subsystem remains 4/15; no new")
    print("       full-program 14-symbol compiler or IC SQ(9) computation")


if __name__ == "__main__":
    main()
