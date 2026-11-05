"""Literal Lafont 1997 macro builders for primitive interaction combinators.

The builders in this module construct explicit gamma/delta/epsilon port
graphs. They do not use source-system cells and do not rely on a source
runtime during reduction. The initial scope is the exact Fig. 4 multiplexer
family M_n and M_n*, plus generic self-certificates.
"""

from dataclasses import dataclass

from ic_primitive_port_verifier import Net


@dataclass(frozen=True)
class Macro:
    principal: object
    auxiliaries: tuple

    @property
    def arity(self):
        return len(self.auxiliaries)


def _fresh_boundary(net, label):
    index = 0
    while ("F", f"{label}-{index}") in net.adj:
        index += 1
    return net.boundary(f"{label}-{index}")


def _build_M(net, arity, mirror):
    if arity == 0:
        return Macro((net.cell("e"), 0), ())
    if arity == 1:
        # M_1 is a wire. Represent it as a package free port; the caller may
        # link it directly as the principal.
        port = _fresh_boundary(net, "M1-wire")
        return Macro(port, (port,))

    leaves = [
        _fresh_boundary(net, f"M{arity}-auxiliary")
        for _ in range(arity)
    ]
    cells = []
    remaining = list(leaves)
    while len(remaining) > 1:
        left, right, *rest = remaining
        cell = net.cell("g")
        if mirror:
            left, right = right, left
        net.link((cell, 1), (left, 0) if isinstance(left, str) else left)
        net.link((cell, 2), (right, 0) if isinstance(right, str) else right)
        cells.append(cell)
        remaining = [(cell, 0)] + rest
    return Macro((cells[-1], 0), tuple(leaves))


def build_M(net, arity):
    return _build_M(net, arity, mirror=False)


def build_M_star(net, arity):
    return _build_M(net, arity, mirror=True)


def build_M0(net):
    return build_M(net, 0)


def is_free_endpoint(endpoint):
    return isinstance(endpoint, tuple) and len(endpoint) == 2 and endpoint[0] == "F"


def macro_connect(net, a, b):
    """Connect macro endpoints, eliminating one-port wire proxies."""
    a_free = is_free_endpoint(a)
    b_free = is_free_endpoint(b)
    a_neighbor = net.adj.get(a)
    b_neighbor = net.adj.get(b)

    # Unpaired macro ports remain ordinary visible free endpoints.
    if not a_free and not b_free:
        net.link(a, b)
        return

    # A private proxy is a free endpoint already wired to another endpoint.
    a_proxy = a_free and a_neighbor is not None
    b_proxy = b_free and b_neighbor is not None
    if not a_proxy and not b_proxy:
        if a == b and a_free:
            del net.adj[a]
            net.free.remove(a)
            net.cycles += 1
            return
        net.link(a, b)
        return

    if a_proxy != b_proxy:
        proxy, neighbor, other = ((a, a_neighbor, b) if a_proxy
                                   else (b, b_neighbor, a))
        net.adj[neighbor] = None
        del net.adj[proxy]
        net.free.remove(proxy)
        net.link(neighbor, other)
        return

    # Two proxies wired directly to each other become one closed wire.
    if a_neighbor == b and b_neighbor == a:
        del net.adj[a]
        del net.adj[b]
        net.free.remove(a)
        net.free.remove(b)
        net.cycles += 1
        return

    # Otherwise remove both proxies and connect their two neighbors.
    net.adj[a_neighbor] = None
    net.adj[b_neighbor] = None
    del net.adj[a]
    del net.adj[b]
    net.free.remove(a)
    net.free.remove(b)
    if a_neighbor == b_neighbor:
        net.cycles += 1
        return
    net.link(a_neighbor, b_neighbor)


def build_menu(net, package_roots):
    arity = len(package_roots)
    if arity == 0:
        raise ValueError("an empty menu is M_0, not a gamma tree")
    if arity == 1:
        return Macro(package_roots[0], tuple(package_roots))
    cells = []
    remaining = list(package_roots)
    while len(remaining) > 1:
        left, right, *rest = remaining
        cell = net.cell("g")
        net.link((cell, 1), left)
        net.link((cell, 2), right)
        cells.append(cell)
        remaining = [(cell, 0)] + rest
    return Macro((cells[-1], 0), tuple(package_roots))


def build_selector(net, arity, index):
    if not 1 <= index <= arity:
        raise ValueError((arity, index))
    leaves = [
        _fresh_boundary(net, f"S{arity}^{index}-output")
        if position == index
        else net.cell("e")
        for position in range(1, arity + 1)
    ]
    if arity == 1:
        return Macro(leaves[0], (leaves[0],))
    # Selector is the vertical mirror M_n*: reverse child ports in each gamma.
    cells = []
    remaining = list(leaves)
    while len(remaining) > 1:
        left, right, *rest = remaining
        cell = net.cell("g")
        net.link((cell, 1), (right, 0) if isinstance(right, str) else right)
        net.link((cell, 2), (left, 0) if isinstance(left, str) else left)
        cells.append(cell)
        remaining = [(cell, 0)] + rest
    return Macro((cells[-1], 0), (leaves[index - 1],))


def _build_delta_tree(net, arity):
    if arity == 0:
        return Macro((net.cell("e"), 0), ())
    if arity == 1:
        port = _fresh_boundary(net, "T1-wire")
        return Macro(port, (port,))
    leaves = [
        _fresh_boundary(net, f"T{arity}-auxiliary")
        for _ in range(arity)
    ]
    cells = []
    remaining = list(leaves)
    while len(remaining) > 1:
        left, right, *rest = remaining
        cell = net.cell("d")
        net.link((cell, 1), (left, 0) if isinstance(left, str) else left)
        net.link((cell, 2), (right, 0) if isinstance(right, str) else right)
        cells.append(cell)
        remaining = [(cell, 0)] + rest
    return Macro((cells[-1], 0), tuple(leaves))


def build_T_sigma(net, sigma):
    if not sigma:
        return Macro((net.cell("e"), 0), ())
    domain = set(sigma)
    if any(not isinstance(i, int) or i < 1 for i in domain):
        raise ValueError(sigma)
    n = max(domain)
    if domain != set(range(1, n + 1)):
        raise ValueError(sigma)
    if any(sigma.get(sigma.get(i), None) != i for i in domain):
        raise ValueError("sigma must be an involutive permutation")
    boundaries = {
        i: _fresh_boundary(net, f"Tsigma-{i}")
        for i in range(1, n + 1)
    }
    inputs = []
    visited = set()
    for i in range(1, n + 1):
        if i in visited:
            continue
        target = sigma[i]
        if target == i:
            inputs.append(boundaries[i])
            visited.add(i)
            continue
        gamma = net.cell("g")
        net.link((gamma, 1), boundaries[i])
        net.link((gamma, 2), boundaries[target])
        inputs.append((gamma, 0))
        visited.update((i, target))
    if len(inputs) == 1:
        return Macro(inputs[0], tuple(boundaries[i] for i in range(1, n + 1)))
    delta_tree = _build_delta_tree(net, len(inputs))
    for leaf, source in zip(delta_tree.auxiliaries, inputs):
        macro_connect(net, leaf, source)
    return Macro(
        delta_tree.principal,
        tuple(boundaries[i] for i in range(1, n + 1)),
    )


def build_C_n(net, code_roots):
    arity = len(code_roots)
    if arity == 0:
        return Macro((net.cell("e"), 0), ())
    if arity == 1:
        return Macro(code_roots[0], tuple(code_roots))
    cells = []
    remaining = list(code_roots)
    while len(remaining) > 1:
        left, right, *rest = remaining
        cell = net.cell("d")
        net.link((cell, 1), left)
        net.link((cell, 2), right)
        cells.append(cell)
        remaining = [(cell, 0)] + rest
    return Macro((cells[-1], 0), tuple(code_roots))


def selector_certificate(arity, index):
    """Build a menu/select test with distinguishable package roots."""
    net = Net()
    package_roots = [
        (net.cell("e"), 0) if position != index else _fresh_boundary(net, f"package-{position}")
        for position in range(1, arity + 1)
    ]
    menu = build_menu(net, package_roots)
    selector = build_selector(net, arity, index)
    net.link(menu.principal, selector.principal)
    _reduce_all(net)
    expected = {tuple(sorted((package_roots[index - 1], selector.auxiliaries[0]), key=repr))}
    # Non-selected roots are consumed by erasure interactions.
    return net, expected


def T_sigma_certificate(sigma):
    """Pair two transpositors and verify the boundary involution."""
    net = Net()
    left = build_T_sigma(net, sigma)
    right = build_T_sigma(net, sigma)
    macro_connect(net, left.principal, right.principal)
    expected = {
        tuple(sorted((left.auxiliaries[i], right.auxiliaries[sigma[i + 1] - 1]), key=repr))
        for i in range(len(sigma))
    }
    return net, expected


def _reduce_all(net):
    steps = 0
    while net.active():
        net.reduce(*net.active()[0])
        steps += 1
    return steps


def _wires(net):
    seen = set()
    result = set()
    for x, y in net.adj.items():
        if x not in seen:
            result.add(tuple(sorted((x, y), key=repr)))
            seen.update((x, y))
    return result


def _visible_wires(net):
    """All wires, excluding free package roots pending external connection."""
    return _wires(net)


def self_certificate(arity, mirror=True):
    """Return (net, expected_wire_set) for an M_n--M_n* active pair."""
    net = Net()
    m = build_M(net, arity)
    star = build_M_star(net, arity)
    net.link(m.principal, star.principal)
    expected = {
        tuple(sorted((m.auxiliaries[i], star.auxiliaries[i]), key=repr))
        for i in range(arity)
    }
    return net, expected


def run_self_certificates(max_arity=8):
    for arity in range(1, max_arity + 1):
        net, expected = self_certificate(arity)
        steps = _reduce_all(net)
        actual = _wires(net)
        assert actual == expected, (arity, actual, expected)
        assert not net.nodes, (arity, net.nodes)
        print(f"M_{arity}/M_{arity}*: steps={steps}, identity wires={arity}")
    print(f"PASS: M/M* self-certificates for n=1..{max_arity}")


def run_selector_certificates(max_arity=6):
    for arity in range(1, max_arity + 1):
        for index in range(1, arity + 1):
            net, expected = selector_certificate(arity, index)
            actual = _wires(net)
            assert actual == expected, (arity, index, actual, expected)
    print(f"PASS: menu/selector certificates for n=1..{max_arity}, all indices")


def run_T_sigma_certificates():
    cases = [
        {},
        {1: 1},
        {1: 2, 2: 1},
        {1: 2, 2: 1, 3: 3},
        {1: 2, 2: 1, 3: 4, 4: 3, 5: 5, 6: 6},
        {1: 3, 2: 4, 3: 1, 4: 2, 5: 5, 6: 7, 7: 6},
    ]
    for sigma in cases:
        net, expected = T_sigma_certificate(sigma)
        _reduce_all(net)
        actual = _wires(net)
        assert actual == expected, (sigma, actual, expected)
        assert not net.nodes, (sigma, net.nodes)
        print(f"T_sigma n={len(sigma)}: PASS")
    print("PASS: T_sigma certificates for empty, identity, and mixed involutions")


if __name__ == "__main__":
    run_self_certificates()
    run_selector_certificates()
    run_T_sigma_certificates()
