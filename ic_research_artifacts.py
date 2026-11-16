"""Literal IC graph templates and retained research artifacts.

A GraphSpec is an exact, serializable port-graph *syntax*: cell kinds,
boundary labels, ordered wires, and wire cycles.  It deliberately does not
canonicalize isomorphic graphs.  This matters for research artifacts whose
chosen construction and interface labels are part of the evidence.

A RetainedArtifact captures the ROOT-connected component produced by an IC
run.  Garbage and unrelated output components can remain outside the spec
and be accounted separately.  Captured artifacts are structural records,
not contextual-equivalence proofs; every proof or invariant claim must be
validated by the caller before it is placed in the contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from ic_evidence_json import loads as json_loads
from typing import Any, Mapping, Sequence

from ic_primitive_port_verifier import AR, Net


CellEndpoint = tuple[int, int]
BoundaryEndpoint = tuple[str, str]
Endpoint = CellEndpoint | BoundaryEndpoint


@dataclass(frozen=True)
class GraphSpec:
    """An exact literal port graph, including boundary labels and cycles."""

    kinds: tuple[str, ...]
    boundaries: tuple[str, ...]
    wires: tuple[tuple[Endpoint, Endpoint], ...]
    cycles: int = 0

    def __post_init__(self):
        self.validate()

    def _endpoint_port_count(self, endpoint: Endpoint) -> int:
        if isinstance(endpoint, tuple) and len(endpoint) == 2:
            if (isinstance(endpoint[0], int) and not isinstance(endpoint[0], bool)
                    and isinstance(endpoint[1], int) and not isinstance(endpoint[1], bool)):
                if (0 <= endpoint[0] < len(self.kinds)
                        and 0 <= endpoint[1] <= AR[self.kinds[endpoint[0]]]):
                    return AR[self.kinds[endpoint[0]]] + 1
            if (isinstance(endpoint[0], str) and endpoint[0] == "F"
                    and isinstance(endpoint[1], str)):
                if endpoint[1] in self.boundaries:
                    return 1
        raise ValueError(f"invalid or out-of-range endpoint: {endpoint!r}")

    def validate(self) -> None:
        """Validate complete matching, arity, and cycle accounting."""
        if not isinstance(self.kinds, tuple) or not isinstance(self.boundaries, tuple):
            raise TypeError("kinds and boundaries must be tuples")
        if not isinstance(self.wires, tuple):
            raise TypeError("wires must be a tuple")
        if any(kind not in AR for kind in self.kinds):
            raise ValueError(f"unknown cell kind in {self.kinds!r}")
        if any(not isinstance(label, str) for label in self.boundaries):
            raise ValueError("boundary labels must be strings")
        if len(set(self.boundaries)) != len(self.boundaries):
            raise ValueError(f"duplicate boundary labels: {self.boundaries!r}")

        expected = {
            (i, p)
            for i, kind in enumerate(self.kinds)
            for p in range(AR[kind] + 1)
        } | {("F", label) for label in self.boundaries}
        seen: set[Endpoint] = set()
        for left, right in self.wires:
            if left == right:
                raise ValueError(f"self-paired endpoint: {left!r}")
            for endpoint in (left, right):
                if endpoint in seen:
                    raise ValueError(f"port used twice: {endpoint!r}")
                self._endpoint_port_count(endpoint)
                seen.add(endpoint)
        if seen != expected:
            missing = sorted(expected - seen, key=repr)
            extra = sorted(seen - expected, key=repr)
            raise ValueError(f"incomplete exact matching; missing={missing}, extra={extra}")
        if isinstance(self.cycles, bool) or not isinstance(self.cycles, int) or self.cycles < 0:
            raise ValueError("cycles must be a non-negative integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kinds": list(self.kinds),
            "boundaries": list(self.boundaries),
            "wires": [[list(a), list(b)] for a, b in self.wires],
            "cycles": self.cycles,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GraphSpec":
        if not isinstance(data, Mapping):
            raise TypeError("GraphSpec data must be a mapping")
        required = {"kinds", "boundaries", "wires"}
        if not required <= set(data) or set(data) - required - {"cycles"}:
            raise ValueError("GraphSpec keys must be kinds, boundaries, wires and optional cycles")
        for key in required:
            if not isinstance(data[key], Sequence) or isinstance(data[key], (str, bytes, bytearray)):
                raise ValueError(f"GraphSpec {key} must be an array")
        if any(not isinstance(wire, Sequence) or isinstance(wire, (str, bytes, bytearray))
               or len(wire) != 2 for wire in data["wires"]):
            raise ValueError("GraphSpec wires must be two-endpoint arrays")
        try:
            kinds = tuple(data["kinds"])
            boundaries = tuple(data["boundaries"])
            raw_wires = data["wires"]
            cycles = data.get("cycles", 0)
            wires = tuple(
                (
                    cls._decode_endpoint(a),
                    cls._decode_endpoint(b),
                )
                for a, b in raw_wires
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid GraphSpec record: {exc}") from exc
        return cls(kinds, boundaries, wires, cycles)

    @staticmethod
    def _decode_endpoint(value: Sequence[Any]) -> Endpoint:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)) or len(value) != 2:
            raise ValueError(f"invalid endpoint encoding: {value!r}")
        first, second = value
        if isinstance(first, str):
            if first != "F" or not isinstance(second, str):
                raise ValueError(f"invalid boundary endpoint: {value!r}")
            return ("F", second)
        if isinstance(first, bool) or not isinstance(first, int) or isinstance(second, bool) or not isinstance(second, int):
            raise ValueError(f"invalid cell endpoint: {value!r}")
        return (first, second)

    @classmethod
    def from_net(cls, net: Net) -> "GraphSpec":
        """Capture an exact graph without mutating or reducing it."""
        if not isinstance(net, Net):
            raise TypeError("from_net expects an ic_primitive_port_verifier.Net")
        net.check()
        cells = list(net.nodes)
        cell_index = {name: index for index, name in enumerate(cells)}
        boundaries = tuple(label for _, label in sorted(net.free, key=lambda x: (x[1], x)))
        wires: list[tuple[Endpoint, Endpoint]] = []
        seen: set[Endpoint] = set()
        for source_left, source_right in net.adj.items():
            left = (("F", source_left[1]) if source_left[0] == "F"
                    else (cell_index[source_left[0]], source_left[1]))
            right = (("F", source_right[1]) if source_right[0] == "F"
                     else (cell_index[source_right[0]], source_right[1]))
            if right[0] == "F" and left[0] != "F":
                left, right = right, left
            if left in seen or right in seen:
                continue
            wires.append((left, right))
            seen.update((left, right))
        return cls(tuple(net.nodes[name] for name in cells), boundaries, tuple(wires), net.cycles)

    def _allocate(self, net: Net) -> tuple[list[str], dict[str, BoundaryEndpoint]]:
        names = [net.cell(kind) for kind in self.kinds]
        return names, {label: net.boundary(label) for label in self.boundaries}

    def instantiate(
        self,
        net: Net | None = None,
        bindings: Mapping[str, Endpoint] | None = None,
    ) -> Net:
        """Instantiate this exact syntax in a new or existing Net.

        Without bindings, all spec boundaries are created with their labels.
        With bindings, the mapping must supply every spec boundary.  Each
        target endpoint must be free, allowing static composition without a
        hidden adapter.  Existing cells and boundaries are never mutated
        except by the requested links.
        """
        if net is None:
            if bindings is not None:
                raise ValueError("bindings require an existing net")
            net = Net()
        if not isinstance(net, Net):
            raise TypeError("net must be an ic_primitive_port_verifier.Net")
        before_cycles = net.cycles

        if bindings is None:
            names, boundary_ports = self._allocate(net)
        else:
            # Boundaries are interfaces to existing target holes, so do not
            # create physical Net boundaries for them.
            if not isinstance(bindings, Mapping):
                raise TypeError("bindings must be a mapping")
            missing = set(self.boundaries) - set(bindings)
            extra = set(bindings) - set(self.boundaries)
            if missing or extra:
                raise ValueError(f"binding mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
            boundary_ports = {}
            for label, endpoint in bindings.items():
                if not isinstance(endpoint, tuple) or len(endpoint) != 2:
                    raise ValueError(f"invalid bound endpoint: {label} -> {endpoint!r}")
                cell, port = endpoint
                if cell == "F":
                    valid = isinstance(port, str) and endpoint in net.free
                else:
                    valid = (isinstance(cell, str) and cell in net.nodes
                             and isinstance(port, int) and not isinstance(port, bool)
                             and 0 <= port <= AR[net.nodes[cell]])
                if not valid:
                    raise ValueError(f"invalid bound endpoint: {label} -> {endpoint!r}")
                if endpoint not in net.adj or net.adj[endpoint] is not None:
                    raise ValueError(f"bound target is not a free port: {label} -> {endpoint!r}")
                boundary_ports[label] = endpoint
            if len(set(boundary_ports.values())) != len(boundary_ports):
                raise ValueError("distinct interface ports require distinct target holes")
            names = [net.cell(kind) for kind in self.kinds]

        def target(endpoint: Endpoint) -> Endpoint:
            if endpoint[0] == "F":
                return boundary_ports[endpoint[1]]
            return (names[endpoint[0]], endpoint[1])

        for left, right in self.wires:
            net.link(target(left), target(right))
        # Net represents detached wire circles by this count, without port
        # objects.  Reconstructing their literal syntax must restore the count.
        net.cycles = before_cycles + self.cycles
        net.check()
        return net

    def open_root(self, net: Net) -> CellEndpoint:
        """Instantiate internal edges and expose ROOT's neighbor as a root.

        The single ROOT boundary must be connected to a cell principal port.
        No ROOT boundary is created.  This is useful for token material whose
        root will be connected by the caller.
        """
        if not isinstance(net, Net):
            raise TypeError("open_root expects an existing Net")
        if "ROOT" not in self.boundaries:
            raise ValueError("open_root requires exactly one ROOT boundary")
        if any(label != "ROOT" for label in self.boundaries):
            raise ValueError(f"open_root permits only ROOT, got {self.boundaries!r}")
        if self.cycles != 0:
            raise ValueError("open_root token material must have no wire cycles")

        root_wires = [wire for wire in self.wires if "F" in (wire[0][0], wire[1][0])]
        if len(root_wires) != 1:
            raise ValueError(f"open_root requires exactly one ROOT wire, got {len(root_wires)}")
        boundary_side, cell_side = (
            root_wires[0] if root_wires[0][0][0] == "F"
            else (root_wires[0][1], root_wires[0][0])
        )
        if boundary_side != ("F", "ROOT"):
            raise ValueError(f"unexpected ROOT boundary: {boundary_side!r}")
        if cell_side[1] != 0:
            raise ValueError(f"ROOT must connect to a principal port: {cell_side!r}")

        names = [net.cell(kind) for kind in self.kinds]
        open_endpoint: CellEndpoint = (
            names[cell_side[0]], cell_side[1]
        )
        for left, right in self.wires:
            if left == boundary_side or right == boundary_side:
                continue
            def target(endpoint: Endpoint) -> Endpoint:
                return (names[endpoint[0]], endpoint[1])
            net.link(target(left), target(right))
        allocated = {
            (name, port)
            for name, kind in zip(names, self.kinds)
            for port in range(AR[kind] + 1)
        }
        unpaired = {
            endpoint for endpoint in allocated
            if endpoint != open_endpoint and net.adj.get(endpoint) is None
        }
        if unpaired:
            raise ValueError(f"open_root left non-root ports unpaired: {sorted(unpaired, key=repr)}")
        if net.adj.get(open_endpoint) is not None:
            raise ValueError("open_root root endpoint was unexpectedly paired")
        return open_endpoint


@dataclass
class RetainedArtifact:
    """A serializable ROOT-component specimen and its research contract."""

    spec: GraphSpec
    source_fingerprint: str
    provenance: dict[str, Any]
    contract: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.spec, GraphSpec):
            raise TypeError("spec must be a GraphSpec")
        if "ROOT" not in self.spec.boundaries or any(
                label != "ROOT" for label in self.spec.boundaries):
            raise ValueError("retained artifact must expose exactly one ROOT boundary")
        if self.spec.cycles != 0:
            raise ValueError("retained rooted artifact must have zero wire cycles")
        root_neighbor = self._root_neighbor()
        if root_neighbor[1] != 0:
            raise ValueError(f"ROOT must connect to a principal port: {root_neighbor!r}")
        if self.spec.kinds[root_neighbor[0]] not in ("g", "e"):
            raise ValueError("retained artifact root cell must be gamma or epsilon")
        if not isinstance(self.source_fingerprint, str) or not self.source_fingerprint:
            raise ValueError("source_fingerprint must be a non-empty string")
        if not isinstance(self.provenance, Mapping):
            raise TypeError("provenance must be a mapping")
        if not isinstance(self.contract, Mapping):
            raise TypeError("contract must be a mapping")

        # A retained artifact must be one reduced, ROOT-connected component.
        # This also rejects disconnected deltas or active pairs smuggled in
        # through serialized records, matching capture_root's guarantees.
        if any(kind not in ("g", "e") for kind in self.spec.kinds):
            raise ValueError("retained artifact cells must all be gamma or epsilon")
        graph: dict[Endpoint, set[Endpoint]] = {}
        for left, right in self.spec.wires:
            graph.setdefault(left, set()).add(right)
            graph.setdefault(right, set()).add(left)
        for index, kind in enumerate(self.spec.kinds):
            cell_ports = [(index, port) for port in range(AR[kind] + 1)]
            for endpoint in cell_ports:
                graph.setdefault(endpoint, set()).update(cell_ports)
        root = ("F", "ROOT")
        reachable: set[Endpoint] = set()
        stack = [root]
        while stack:
            endpoint = stack.pop()
            if endpoint in reachable:
                continue
            reachable.add(endpoint)
            stack.extend(graph.get(endpoint, ()))
        expected = {
            (index, port)
            for index, kind in enumerate(self.spec.kinds)
            for port in range(AR[kind] + 1)
        } | {root}
        if reachable != expected:
            raise ValueError("retained artifact graph is not fully ROOT-connected")
        wire_set = set(self.spec.wires)
        active_pairs = [
            (left[0], right[0])
            for left, right in wire_set
            if left[1] == right[1] == 0 and left[0] != "F" and right[0] != "F"
        ]
        if active_pairs:
            raise ValueError(f"retained artifact contains an active pair: {active_pairs!r}")

    def _root_neighbor(self) -> CellEndpoint:
        wire = next((wire for wire in self.spec.wires
                     if "F" in (wire[0][0], wire[1][0])), None)
        if wire is None:
            raise ValueError("ROOT boundary is not wired")
        return wire[1] if wire[0][0] == "F" else wire[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "source_fingerprint": self.source_fingerprint,
            "provenance": dict(self.provenance),
            "contract": dict(self.contract),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RetainedArtifact":
        if not isinstance(data, Mapping):
            raise TypeError("RetainedArtifact data must be a mapping")
        try:
            return cls(
                spec=GraphSpec.from_dict(data["spec"]),
                source_fingerprint=data["source_fingerprint"],
                provenance=dict(data.get("provenance", {})),
                contract=dict(data.get("contract", {})),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"invalid RetainedArtifact record: {exc}") from exc

    def instantiate(self, net: Net | None = None) -> Net:
        """Instantiate a fresh specimen without consuming the record."""
        return self.spec.instantiate(net)

    def open_root(self, net: Net) -> CellEndpoint:
        return self.spec.open_root(net)

    def export_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def _graph_fingerprint(net: Net) -> str:
    canonical = json.dumps(GraphSpec.from_net(net).to_dict(), sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _root_component_spec(net: Net, source_boundary: BoundaryEndpoint,
                         require_gamma_epsilon: bool = True) -> tuple[GraphSpec, set[str]]:
    """Return the exact ROOT-connected component and its cell IDs."""
    if source_boundary not in net.free:
        raise ValueError(f"boundary is not free: {source_boundary!r}")
    net.check()
    start = net.adj[source_boundary]
    if start[0] not in net.nodes:
        raise ValueError("ROOT boundary is not connected to a cell")

    # Build a port-incidence graph.  Wire edges alone cannot reach all ports
    # of a cell; every physical port must remain in the captured component.
    graph: dict[Endpoint, set[Endpoint]] = {}
    for left, right in net.adj.items():
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set()).add(left)
    for name, kind in net.nodes.items():
        cell_ports = [(name, port) for port in range(AR[kind] + 1)]
        for endpoint in cell_ports:
            graph.setdefault(endpoint, set()).update(cell_ports)

    stack = [source_boundary, start]
    component: set[Endpoint] = set()
    while stack:
        endpoint = stack.pop()
        if endpoint in component:
            continue
        component.add(endpoint)
        stack.extend(graph.get(endpoint, ()))

    cells = sorted({endpoint[0] for endpoint in component
                    if endpoint[0] in net.nodes}, key=lambda name: int(name[1:]))
    cell_index = {name: index for index, name in enumerate(cells)}
    other_boundaries = sorted({endpoint for endpoint in component if endpoint[0] == "F"})
    if other_boundaries != [source_boundary]:
        raise ValueError(f"root component has non-source open boundaries: {other_boundaries!r}")

    active = [pair for pair in net.active() if all(cell in cells for cell in pair)]
    if active:
        raise ValueError(f"root component contains an active pair: {active!r}")
    if require_gamma_epsilon and any(net.nodes[cell] not in ("g", "e") for cell in cells):
        raise ValueError("root component contains a non-gamma/epsilon cell")

    wires: list[tuple[Endpoint, Endpoint]] = []
    seen: set[Endpoint] = set()
    for left, right in net.adj.items():
        if left not in component and right not in component:
            continue
        if left not in component or right not in component:
            raise ValueError(f"root component is not closed: {left!r} -- {right!r}")
        if left in seen:
            continue
        def encode(endpoint: Endpoint) -> Endpoint:
            if endpoint[0] in cell_index:
                return (cell_index[endpoint[0]], endpoint[1])
            if endpoint[0] == "F":
                return ("F", "ROOT" if endpoint == source_boundary else endpoint[1])
            return endpoint
        encoded_wire = (encode(left), encode(right))
        if encoded_wire[1][0] == "F" and encoded_wire[0][0] != "F":
            encoded_wire = (encoded_wire[1], encoded_wire[0])
        wires.append(encoded_wire)
        seen.update((left, right))
    kinds = tuple(net.nodes[cell] for cell in cells)
    return GraphSpec(kinds, ("ROOT",), tuple(wires), 0), set(cells)


def capture_root(
    net: Net,
    boundary: BoundaryEndpoint,
    provenance: Mapping[str, Any],
    contract: Mapping[str, Any] | None = None,
    require_gamma_epsilon: bool = True,
) -> tuple[RetainedArtifact, set[str]]:
    """Capture a reduced ROOT-connected component as a fresh specimen.

    The source Net is not mutated.  The caller supplies provenance and any
    contract; this function validates only graph structure.  It does not
    prove contextual equivalence, replacement legality, or contract claims.
    """
    if not isinstance(net, Net):
        raise TypeError("capture_root expects an ic_primitive_port_verifier.Net")
    spec, cell_ids = _root_component_spec(net, boundary, require_gamma_epsilon)
    return RetainedArtifact(
        spec=spec,
        source_fingerprint=_graph_fingerprint(net),
        provenance=dict(provenance),
        contract=dict(contract or {}),
    ), cell_ids


def _build_sample(net: Net) -> tuple[Endpoint, Endpoint]:
    """A tiny reduced package with internal wiring and one ROOT."""
    # gamma(aux1, aux2) with each auxiliary connected to an epsilon leaf.
    root = net.cell("g")
    a = net.cell("e")
    b = net.cell("e")
    net.link((root, 1), (a, 0))
    net.link((root, 2), (b, 0))
    root_boundary = net.boundary("ROOT")
    net.link((root, 0), root_boundary)
    net.check()
    return (root, 0), root_boundary


def _check_roundtrip(spec: GraphSpec) -> None:
    net = spec.instantiate()
    roundtrip = GraphSpec.from_net(net)
    assert roundtrip == spec
    encoded = GraphSpec.from_dict(json_loads(json.dumps(spec.to_dict())))
    assert encoded == spec


def _check_bindings_and_capture() -> None:
    net = Net()
    _, root_boundary = _build_sample(net)
    artifact, cell_ids = capture_root(
        net,
        root_boundary,
        provenance={"kind": "sample", "trace": []},
        contract={"allowed_consumers": ["passive", "epsilon", "delta"]},
    )
    assert cell_ids == {"c0", "c1", "c2"}
    fresh = artifact.instantiate()
    assert GraphSpec.from_net(fresh) == artifact.spec
    artifact.from_dict(json_loads(artifact.export_json()))

    # Composition must use explicitly provided free target ports.  A host may
    # be intentionally incomplete before binding; the final graph is checked
    # only after all declared interface holes are consumed.
    gate = GraphSpec(
        ("g",), ("CTRL", "DATA", "OUT"),
        ((("F", "CTRL"), (0, 0)),
         (("F", "DATA"), (0, 1)),
         (("F", "OUT"), (0, 2))),
    )
    gate_host = Net()
    host_gate = gate_host.cell("g")
    gate.instantiate(gate_host, {
        "CTRL": (host_gate, 0),
        "DATA": (host_gate, 1),
        "OUT": (host_gate, 2),
    })
    gate_host.check()

    # A retained specimen can likewise be attached to one intentionally open
    # principal port.  The resulting active pair is legal syntax; reduction
    # semantics are the caller's responsibility.
    target_net = Net()
    target_gate = target_net.cell("g")
    target_net.link((target_gate, 1), (target_gate, 2))
    artifact.spec.instantiate(target_net, bindings={"ROOT": (target_gate, 0)})
    target_net.check()


def _check_open_root() -> None:
    net = Net()
    # Loop = gamma(aux1--aux2), exposed through ROOT at its principal port.
    loop = net.cell("g")
    net.link((loop, 1), (loop, 2))
    root = net.boundary("ROOT")
    net.link((loop, 0), root)
    spec = GraphSpec.from_net(net)
    host = Net()
    root_port = spec.open_root(host)
    assert host.nodes[root_port[0]] == "g" and root_port[1] == 0
    assert host.adj[(root_port[0], 1)] == (root_port[0], 2)
    # The returned principal endpoint is intentionally open.


def _check_malformed_artifact() -> None:
    """A disconnected active pair must not survive artifact import."""
    # ROOT epsilon plus a disconnected epsilon-epsilon active pair.  This
    # would be structurally valid as a raw GraphSpec, but not as a retained
    # reduced ROOT-component artifact.
    malformed = {
        "kinds": ["e", "e", "e"],
        "boundaries": ["ROOT"],
        "wires": [
            [["F", "ROOT"], [0, 0]],
            [[1, 0], [2, 0]],
        ],
        "cycles": 0,
    }
    try:
        RetainedArtifact.from_dict({
            "spec": malformed,
            "source_fingerprint": "negative-check",
            "provenance": {},
            "contract": {},
        })
    except ValueError:
        return
    raise AssertionError("malformed retained artifact was accepted")


def main() -> None:
    # Rejection witnesses may contain detached cyclic wires.  They must
    # survive serialization and accumulate when another spec is appended.
    cycle_spec = GraphSpec((), (), (), 2)
    _check_roundtrip(cycle_spec)
    cycle_host = cycle_spec.instantiate()
    cycle_spec.instantiate(cycle_host)
    assert cycle_host.cycles == 4
    # A complete one-gamma/two-epsilon package with ROOT at the principal
    # port has even total arity and exercises exact matching.
    _check_roundtrip(GraphSpec(
        ("g", "e", "e"),
        ("ROOT",),
        (
            (("F", "ROOT"), (0, 0)),
            ((0, 1), (1, 0)),
            ((0, 2), (2, 0)),
        ),
        0,
    ))
    _check_bindings_and_capture()
    _check_open_root()
    _check_malformed_artifact()
    print("PASS: literal GraphSpec roundtrip, binding, ROOT capture, and open-root material")
    print("SCOPE: structural templates and artifacts; no contextual-equivalence proof")


if __name__ == "__main__":
    main()
