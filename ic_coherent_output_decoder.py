"""Structural output decoder for the coherent source-to-IC compiler.

This module never consults source rules or a source runtime.  It recognizes
compiled source cells by matching their complete primitive-IC footprint
against templates supplied by the compiler callback, then reconstructs the
ordinary source port graph and decodes unary outputs structurally.
"""

from collections import deque
import argparse
import json

from ic_primitive_port_verifier import AR, Net


Endpoint = tuple


def _boundary_label(endpoint):
    if endpoint[0] != "F":
        raise ValueError(f"expected boundary endpoint: {endpoint!r}")
    return endpoint[1]


def _template_boundaries(template):
    result = {}
    for endpoint in template.free:
        label = _boundary_label(endpoint)
        if label in result:
            raise ValueError(f"duplicate template boundary: {label}")
        result[label] = endpoint
    return result


def port_graph_isomorphic(left: Net, right: Net) -> bool:
    """Exact labeled-boundary port-graph isomorphism in linear time.

    Matching starts from uniquely labeled free boundaries.  Cell mappings are
    then forced by kind and port index, and every adjacent wire is traversed.
    A component with no free boundary is rejected; the coherent compiler's
    cell templates expose P0..Pn, so this is the intended complete case.
    """
    if not isinstance(left, Net) or not isinstance(right, Net):
        raise TypeError("both arguments must be Net instances")
    if left.cycles != right.cycles or len(left.nodes) != len(right.nodes):
        return False
    if len(left.free) != len(right.free):
        return False

    left_boundaries = _template_boundaries(left)
    right_boundaries = _template_boundaries(right)
    if set(left_boundaries) != set(right_boundaries):
        return False

    left_cells = set(left.nodes)
    right_cells = set(right.nodes)
    cell_map = {}
    mapped_left = set()
    mapped_right = set()
    queue = deque()

    for label, left_endpoint in left_boundaries.items():
        right_endpoint = right_boundaries[label]
        left_neighbor = left.adj[left_endpoint]
        right_neighbor = right.adj[right_endpoint]
        if left_neighbor == left_endpoint or right_neighbor == right_endpoint:
            return False
        if (left_neighbor[0] == "F") != (right_neighbor[0] == "F"):
            return False
        if left_neighbor[0] == "F":
            left_label = _boundary_label(left_neighbor)
            right_label = _boundary_label(right_neighbor)
            if left_label != right_label:
                return False
            if left_label not in left_boundaries or right_label not in right_boundaries:
                return False
            if right_boundaries[right_label] != right_neighbor:
                return False
            if left_boundaries[left_label] != left_neighbor:
                return False
            continue
        left_cell, left_port = left_neighbor
        right_cell, right_port = right_neighbor
        if left_port != right_port:
            return False
        if left.nodes[left_cell] != right.nodes[right_cell]:
            return False
        if left_cell in cell_map:
            if cell_map[left_cell] != right_cell:
                return False
        else:
            if right_cell in mapped_right:
                return False
            cell_map[left_cell] = right_cell
            mapped_right.add(right_cell)
            mapped_left.add(left_cell)
            queue.append((left_cell, right_cell))

    while queue:
        left_cell, right_cell = queue.popleft()
        if left.nodes[left_cell] != right.nodes[right_cell]:
            return False
        for port in range(AR[left.nodes[left_cell]] + 1):
            left_endpoint = (left_cell, port)
            right_endpoint = (right_cell, port)
            left_neighbor = left.adj[left_endpoint]
            right_neighbor = right.adj[right_endpoint]
            if left_neighbor == left_endpoint or right_neighbor == right_endpoint:
                return False
            if (left_neighbor[0] == "F") != (right_neighbor[0] == "F"):
                return False
            if left_neighbor[0] == "F":
                left_label = _boundary_label(left_neighbor)
                right_label = _boundary_label(right_neighbor)
                if left_label != right_label:
                    return False
                if left_label not in left_boundaries or right_label not in right_boundaries:
                    return False
                if left_boundaries[left_label] != left_neighbor:
                    return False
                if right_boundaries[right_label] != right_neighbor:
                    return False
                continue
            left_neighbor_cell, left_neighbor_port = left_neighbor
            right_neighbor_cell, right_neighbor_port = right_neighbor
            if left_neighbor_port != right_neighbor_port:
                return False
            if left.nodes[left_neighbor_cell] != right.nodes[right_neighbor_cell]:
                return False
            if left_neighbor_cell in cell_map:
                if cell_map[left_neighbor_cell] != right_neighbor_cell:
                    return False
            else:
                if right_neighbor_cell in mapped_right:
                    return False
                cell_map[left_neighbor_cell] = right_neighbor_cell
                mapped_right.add(right_neighbor_cell)
                mapped_left.add(left_neighbor_cell)
                queue.append((left_neighbor_cell, right_neighbor_cell))

    if mapped_left != left_cells or mapped_right != right_cells:
        return False
    if len(cell_map) != len(left_cells):
        return False
    return True


def _template_index(compiler):
    symbols = tuple(compiler.symbols)
    if len(set(symbols)) != len(symbols):
        raise ValueError("compiler.symbols must be unique")
    templates = {}
    for symbol in symbols:
        template = compiler.symbol_template(symbol)
        if not isinstance(template, Net):
            raise TypeError("symbol_template must return a Net")
        template.check()
        if template.cycles:
            raise ValueError(f"template has cyclic wires: {symbol}")
        boundaries = _template_boundaries(template)
        arity = compiler.arity[symbol]
        expected = {"P0"} | {f"P{i}" for i in range(1, arity + 1)}
        if set(boundaries) != expected:
            raise ValueError(f"bad template boundaries for {symbol}: {sorted(boundaries)}")
        templates[symbol] = (template, boundaries)
    return symbols, templates


def _match_template_footprint(net: Net, template: Net, root_cell: str):
    """Match one complete source footprint rooted at its outer delta.

    The root cell is mapped to the template cell adjacent to boundary P0.
    Internal wires force the rest of the mapping.  Template boundary wires
    identify source ports; their compiled neighbors must leave this footprint.
    """
    if root_cell not in net.nodes:
        return None
    template_root_endpoint = template.adj[("F", "P0")]
    template_root = template_root_endpoint[0]
    if template_root == "F" or template_root not in template.nodes or template_root_endpoint[1] != 0:
        return None
    if net.nodes[root_cell] != template.nodes[template_root]:
        return None
    cell_map = {root_cell: template_root}
    reverse_map = {template_root: root_cell}
    boundary_ports = {}
    queue = deque([root_cell])
    while queue:
        actual_cell = queue.popleft()
        template_cell = cell_map[actual_cell]
        actual_kind = net.nodes[actual_cell]
        if template.nodes[template_cell] != actual_kind:
            return None
        if actual_kind not in AR:
            return None
        arity = AR[actual_kind]
        for port in range(arity + 1):
            actual_endpoint = (actual_cell, port)
            template_endpoint = (template_cell, port)
            actual_neighbor = net.adj[actual_endpoint]
            template_neighbor = template.adj[template_endpoint]
            if template_neighbor[0] == "F":
                label = _boundary_label(template_neighbor)
                if actual_endpoint in boundary_ports:
                    return None
                boundary_ports[actual_endpoint] = label
                continue
            if actual_neighbor[0] == "F":
                return None
            actual_neighbor_cell, actual_neighbor_port = actual_neighbor
            template_neighbor_cell, template_neighbor_port = template_neighbor
            if actual_neighbor_port != template_neighbor_port:
                return None
            if net.nodes.get(actual_neighbor_cell) != template.nodes.get(template_neighbor_cell):
                return None
            if actual_neighbor_cell in cell_map:
                if cell_map[actual_neighbor_cell] != template_neighbor_cell:
                    return None
            else:
                if template_neighbor_cell in reverse_map:
                    return None
                cell_map[actual_neighbor_cell] = template_neighbor_cell
                reverse_map[template_neighbor_cell] = actual_neighbor_cell
                queue.append(actual_neighbor_cell)

    footprint = set(cell_map)
    if len(footprint) != len(template.nodes) or set(cell_map.values()) != set(template.nodes):
        return None
    if set(boundary_ports.values()) != {label for _, label in template.free}:
        return None
    for endpoint in boundary_ports:
        neighbor = net.adj[endpoint]
        if neighbor[0] != "F" and neighbor[0] in footprint and neighbor not in boundary_ports:
            return None
    return footprint, boundary_ports


def _find_owner_root(net, endpoint):
    """Return the outer source delta from a source data auxiliary."""
    cell, port = endpoint
    if cell not in net.nodes:
        raise ValueError(f"context endpoint is not a primitive cell: {endpoint!r}")
    kind = net.nodes[cell]
    if kind == "d":
        if port != 0:
            raise ValueError("a source principal must enter delta port zero")
        return cell
    if kind != "g" or port == 0:
        raise ValueError(f"source context must enter gamma auxiliary: {endpoint!r}")
    visited = set()
    while cell not in visited:
        visited.add(cell)
        if net.nodes[cell] == "d":
            return cell
        if net.nodes[cell] != "g":
            raise ValueError("source principal chain entered a non-gamma cell")
        parent = net.adj[(cell, 0)]
        if parent[0] not in net.nodes or parent[1] == 0:
            raise ValueError("source principal chain escaped or entered an active pair")
        cell = parent[0]
    raise ValueError("source principal chain contains a cycle")


def decode_source(net: Net, compiler):
    """Reconstruct source types and adjacency without source-rule execution."""
    if not isinstance(net, Net):
        raise TypeError("net must be a Net")
    symbols, templates = _template_index(compiler)
    if net.cycles:
        raise ValueError("decoded graph contains cyclic wires")
    if net.active():
        raise ValueError("decoded graph is not reduced")

    types = {}
    adjacency = {}
    covered = set()
    owner_ports = {}
    owner_roots = set()
    queue = deque()
    for free_endpoint in net.free:
        neighbor = net.adj[free_endpoint]
        if neighbor[0] == "F":
            raise ValueError(f"unconnected external boundary: {free_endpoint!r}")
        if neighbor[0] not in net.nodes:
            raise ValueError("external neighbor is not a primitive cell")
        if neighbor[1] == 0 and net.nodes[neighbor[0]] == "d":
            root = neighbor[0]
        else:
            root = _find_owner_root(net, neighbor)
        owner_roots.add(root)
        queue.append(root)

    while queue:
        root_cell = queue.popleft()
        if root_cell in types:
            continue
        match = None
        for symbol in symbols:
            template, _ = templates[symbol]
            candidate = _match_template_footprint(net, template, root_cell)
            if candidate is None:
                continue
            footprint, boundary_ports = candidate
            if footprint & covered:
                continue
            match = (symbol, footprint, boundary_ports)
            break
        if match is None:
            raise ValueError(f"primitive source footprint is unrecognized: {root_cell!r}")
        symbol, footprint, boundary_ports = match
        types[root_cell] = symbol
        covered |= footprint
        owner_roots.add(root_cell)
        logical_ports = {}
        for endpoint, label in boundary_ports.items():
            port_number = int(label[1:])
            logical_endpoint = (root_cell, port_number)
            logical_ports[logical_endpoint] = endpoint
            owner_ports[endpoint] = logical_endpoint
        for logical_endpoint, endpoint in logical_ports.items():
            neighbor = net.adj[endpoint]
            if neighbor[0] == "F":
                adjacency[logical_endpoint] = neighbor
                adjacency[neighbor] = logical_endpoint
            else:
                other_root = _find_owner_root(net, neighbor)
                if other_root not in types:
                    queue.append(other_root)
                    continue
                other_endpoint = owner_ports.get(neighbor)
                if other_endpoint is None:
                    raise ValueError(f"context endpoint is not a source port: {neighbor!r}")
                adjacency[logical_endpoint] = other_endpoint
                adjacency[other_endpoint] = logical_endpoint

    if covered != set(net.nodes):
        raise ValueError("primitive graph contains extra or disconnected cells")
    # Resolve contexts discovered after their owner was already parsed.
    for endpoint, logical_endpoint in owner_ports.items():
        if logical_endpoint in adjacency:
            continue
        neighbor = net.adj[endpoint]
        if neighbor[0] == "F":
            adjacency[logical_endpoint] = neighbor
            adjacency[neighbor] = logical_endpoint
        else:
            other_root = _find_owner_root(net, neighbor)
            other_endpoint = owner_ports.get(neighbor)
            if other_endpoint is None:
                raise ValueError(f"context endpoint is not a source port: {neighbor!r}")
            adjacency[logical_endpoint] = other_endpoint
            adjacency[other_endpoint] = logical_endpoint
    expected = set(owner_ports.values()) | set(net.free)
    if set(adjacency) != expected:
        raise ValueError("decoded source adjacency is incomplete")
    return types, adjacency


def decode_feedback(net: Net, compiler):
    types, adjacency = decode_source(net, compiler)
    external = [endpoint for endpoint in adjacency if endpoint[0] == "F"]
    if len(external) != 1:
        raise ValueError(f"feedback graph must have one output boundary, got {len(external)}")
    output_endpoint = adjacency[external[0]]
    output_cell, output_port = output_endpoint
    if output_port != 0 or output_cell not in types:
        raise ValueError(f"bad feedback output root: {output_endpoint!r}")
    kind = types[output_cell]

    def unary(start):
        value = 0
        seen = set()
        current = adjacency[start]
        while True:
            if current[0] == "F" or current[0] not in types:
                raise ValueError(f"unary chain escaped source graph: {current!r}")
            cell, port = current
            if cell in seen:
                raise ValueError("cyclic source numeral")
            seen.add(cell)
            symbol = types[cell]
            if symbol == "Z" and port == 0:
                return value
            if symbol != "S" or port != 0:
                raise ValueError(f"bad unary link: {current!r}")
            value += 1
            current = adjacency[(cell, 1)]

    if kind == "SQ":
        return ("SQ", unary((output_cell, 1)))
    if kind == "BR":
        return ("BR", unary((output_cell, 1)), unary((output_cell, 2)))
    raise ValueError(f"feedback root must be SQ or BR, got {kind}")


def _test_port_graph_isomorphic():
    a = Net()
    a_cell = a.cell("g")
    a0 = a.boundary("P0")
    a1 = a.boundary("P1")
    a2 = a.boundary("P2")
    a.link((a_cell, 1), a1)
    a.link((a_cell, 2), a2)
    a.link((a_cell, 0), a0)
    a.check()

    b = Net()
    b_cell = b.cell("g")
    b0 = b.boundary("P0")
    b1 = b.boundary("P1")
    b2 = b.boundary("P2")
    b.link((b_cell, 1), b1)
    b.link((b_cell, 2), b2)
    b.link((b_cell, 0), b0)
    b.check()
    assert port_graph_isomorphic(a, b)

    c = Net()
    c_cell = c.cell("g")
    c0 = c.boundary("P0")
    c1 = c.boundary("P2")
    c2 = c.boundary("P1")
    c.link((c_cell, 1), c1)
    c.link((c_cell, 2), c2)
    c.link((c_cell, 0), c0)
    c.check()
    assert not port_graph_isomorphic(a, c)
    def wired(pairs):
        graph = Net()
        ports = {label: graph.boundary(label) for label in ("A", "B", "C", "D")}
        for x, y in pairs:
            graph.link(ports[x], ports[y])
        graph.check()
        return graph
    straight = wired((("A", "B"), ("C", "D")))
    assert port_graph_isomorphic(straight, wired((("D", "C"), ("B", "A"))))
    assert not port_graph_isomorphic(straight, wired((("A", "C"), ("B", "D"))))
    print("PASS: linear boundary-rooted port-graph matcher")


if __name__ == "__main__":
    _test_port_graph_isomorphic()
    from source_ic_coherent_compiler import CoherentICCompiler
    compiler = CoherentICCompiler()
    for symbol in ("Z", "S", "SQ"):
        template = compiler.symbol_template(symbol)
        copy = compiler.symbol_template(symbol)
        assert port_graph_isomorphic(template, copy)
        print(f"PASS: decoder template matcher {symbol}: {len(template.nodes)} cells")
    for kind in ("Z", "S", "ERA", "DUP", "INIT", "CMP", "CMP0", "CMPS",
                 "GATE", "EQ", "GT", "LT", "SQ", "BR"):
        adjacency = {}
        for port in range(compiler.arity[kind] + 1):
            boundary = ("F", f"P{port}")
            adjacency[(kind, port)] = boundary
            adjacency[boundary] = (kind, port)
        net = compiler.compile({kind: kind}, adjacency)
        decoded = decode_source(net, compiler)
        assert set(decoded[0].values()) == {kind}
        logical_root = next(iter(decoded[0]))
        for port in range(compiler.arity[kind] + 1):
            assert decoded[1][(logical_root, port)] == ("F", f"P{port}")
        print(f"PASS: structural decode {kind}: {len(net.nodes)} primitive cells")
    corrupted = compiler.symbol_template("SQ")
    marker = next(cell for cell, kind in corrupted.nodes.items() if kind == "e")
    corrupted.nodes[marker] = "g"
    corrupted.adj[(marker, 1)] = (marker, 2)
    corrupted.adj[(marker, 2)] = (marker, 1)
    corrupted.check()
    extra = compiler.symbol_template("SQ")
    g, e = extra.cell("g"), extra.cell("e")
    extra.link((g, 0), (g, 1))
    extra.link((g, 2), (e, 0))
    extra.check()
    for malformed in (corrupted, extra):
        try:
            decode_source(malformed, compiler)
        except ValueError:
            pass
        else:
            raise AssertionError("decoder accepted a corrupted or extra primitive component")
    print("PASS: malformed source-image and disconnected-garbage rejection")
