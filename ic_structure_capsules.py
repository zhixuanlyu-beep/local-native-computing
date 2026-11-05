"""Native multiport component capsules for the M5 structure library.

A capsule stores an exact component behind one ordered principal frame.  The
first logical slot is a READY gamma Loop; the remaining slots follow the
component's original interface order.  ``build_capsule`` performs only static
construction and package validation.  ``build_activation`` decodes the stored
code before unpacking the frame; ``build_unpack`` supplies the literal package
baseline.  Both defer the whole-net audit because an enclosing benchmark may
still have unconnected ports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ic_package_codec import build_decoder, encode_package, validate_package
from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec
from lafont_ic_macro_builder import build_M, build_M_star, macro_connect


@dataclass(frozen=True)
class Capsule:
    """One frozen component, its ordered interface, and package/code syntax."""

    component: GraphSpec
    interface: tuple[str, ...]
    width: int
    ready_slot: int | None
    package: GraphSpec
    code: GraphSpec

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component.to_dict(),
            "interface": list(self.interface),
            "width": self.width,
            "ready_slot": self.ready_slot,
            "package": self.package.to_dict(),
            "code": self.code.to_dict(),
        }


def _validate_component(component: GraphSpec, *, with_ready: bool) -> tuple[tuple[str, ...], int | None]:
    if not isinstance(component, GraphSpec):
        raise TypeError("component must be a GraphSpec")
    if type(component.boundaries) is not tuple or not component.boundaries:
        raise ValueError("a capsule component needs at least one boundary")
    interface = tuple(component.boundaries)
    if len(set(interface)) != len(interface):
        raise ValueError("component boundary labels must be distinct")
    if with_ready:
        if type(component.cycles) is not int or component.cycles:
            raise ValueError("a capsule component must have no detached wire cycles")
        return interface, 0
    return interface, None


def _component_body(net: Net, component: GraphSpec) -> dict[str, Any]:
    """Append the component literally and return its ordered boundary wires.

    Each component boundary is represented by a fresh physical free port.
    GraphSpec.instantiate requires a complete net, so the internal component
    edges are copied by the same append technique used by program suspension:
    allocate unique cells, map every boundary to an unpaired target, and link
    the exact original wires.  The whole destination audit remains deferred.
    """
    if not isinstance(net, Net):
        raise TypeError("capsule construction requires a primitive IC Net")
    if not isinstance(component, GraphSpec):
        raise TypeError("component must be a GraphSpec")
    labels = tuple(component.boundaries)
    stubs = {label: net.boundary("CAPSULE::" + label) for label in labels}
    names = [net.cell(kind) for kind in component.kinds]

    def port(endpoint):
        if endpoint[0] == "F":
            return stubs[endpoint[1]]
        return (names[endpoint[0]], endpoint[1])

    for left, right in component.wires:
        net.link(port(left), port(right))
    net.cycles += component.cycles
    return {"names": names, "stubs": stubs}


def build_capsule(component: GraphSpec, *, with_ready: bool = True) -> Capsule:
    """Build a principal package capsule without rewriting the component.

    With READY enabled, logical slot 0 is a literal gamma Loop and the
    component's original boundaries occupy slots 1..width-1 in exact order.
    READY marks native frame-extraction readiness, never whole-task completion.
    """
    interface, ready_slot = _validate_component(component, with_ready=with_ready)
    net = Net()
    body = _component_body(net, component)
    slots: list[Any] = []
    if with_ready:
        ready = net.cell("g")
        net.link((ready, 1), (ready, 2))
        slots.append((ready, 0))
    slots.extend(body["stubs"][label] for label in interface)
    frame = build_M(net, len(slots))
    for leaf, slot in zip(frame.auxiliaries, slots):
        macro_connect(net, leaf, slot)
    root = net.boundary("ROOT")
    macro_connect(net, frame.principal, root)
    net.check()
    validate_package(net)
    package_net = encode_package(net, label="ROOT")
    package = GraphSpec.from_net(net)
    code = GraphSpec.from_net(package_net)
    return Capsule(
        component=component,
        interface=interface,
        width=len(slots),
        ready_slot=ready_slot,
        package=package,
        code=code,
    )


def assess_capsule(component: GraphSpec) -> dict[str, Any]:
    """Report whether the exact component representation can be capsuled.

    This is a representation check only.  It does not filter the structure
    library, evaluate task semantics, or normalize an unsupported graph.
    """
    try:
        capsule = build_capsule(component)
    except (TypeError, ValueError) as error:
        return {
            "status": "unsupported",
            "reason": str(error),
            "interface": tuple(component.boundaries) if isinstance(component, GraphSpec) else None,
            "width": None,
            "ready_slot": None,
        }
    return {
        "status": "eligible",
        "reason": None,
        "interface": capsule.interface,
        "width": capsule.width,
        "ready_slot": capsule.ready_slot,
    }


def _validate_ports(net: Net, width: int, ports: tuple[Any, ...], ready_endpoint: Any) -> None:
    if not isinstance(net, Net):
        raise TypeError("activation must be appended to a primitive IC Net")
    if type(width) is not int or width < 1:
        raise ValueError("width must be a positive integer")
    if type(ports) is not tuple:
        raise TypeError("ports must be an ordered tuple of distinct endpoints")
    if len(ports) + 1 != width:
        raise ValueError("width must equal len(ports) + 1")
    endpoints = (ready_endpoint, *ports)
    if len({repr(endpoint) for endpoint in endpoints}) != len(endpoints):
        raise ValueError("activation endpoints must be distinct")
    for endpoint in endpoints:
        if endpoint not in net.adj:
            raise ValueError("activation endpoints must exist in the target net")
        if endpoint[0] != "F" and net.adj[endpoint] is not None:
            raise ValueError("cell endpoints must be unpaired; paired free-boundary proxies are allowed")


def _head(endpoint: Any) -> str | None:
    if (isinstance(endpoint, tuple) and endpoint and isinstance(endpoint[0], str)
            and endpoint[0].startswith("c") and endpoint[0][1:].isdigit()):
        return endpoint[0]
    return None


def build_activation(net: Net, width: int, code_endpoint: Any, ports: tuple[Any, ...], ready_endpoint: Any) -> dict[str, str | int | None]:
    """Append code decoding and then frame unpacking; defer ``net.check``.

    ``ports`` are the original physical targets in interface order.  READY
    occupies slot 0.  The returned head names are actual Net cell IDs at
    construction time; they are consumed by the primitive reducer.
    """
    _validate_ports(net, width, ports, ready_endpoint)
    if code_endpoint is None:
        raise ValueError("build_activation requires a code endpoint")
    if code_endpoint not in net.adj or net.adj[code_endpoint] is not None:
        raise ValueError("code endpoint must be an unpaired port or construction proxy")
    frame = build_M_star(net, width)
    decoder = build_decoder(net)
    macro_connect(net, code_endpoint, decoder.principal)
    macro_connect(net, decoder.auxiliaries[0], frame.principal)
    for leaf, endpoint in zip(frame.auxiliaries, (ready_endpoint, *ports)):
        macro_connect(net, leaf, endpoint)
    return {
        "decoder_head": decoder.principal[0],
        "unpack_head": _head(frame.principal),
        "width": width,
        "ready_slot": 0,
    }


def build_unpack(net: Net, width: int, package_endpoint: Any, ports: tuple[Any, ...], ready_endpoint: Any) -> dict[str, str | int | None]:
    """Append literal package unpacking without a decoder; defer ``net.check``."""
    _validate_ports(net, width, ports, ready_endpoint)
    if package_endpoint is None:
        raise ValueError("build_unpack requires a package endpoint")
    if package_endpoint not in net.adj or net.adj[package_endpoint] is not None:
        raise ValueError("package endpoint must be an unpaired port or construction proxy")
    frame = build_M_star(net, width)
    for leaf, endpoint in zip(frame.auxiliaries, (ready_endpoint, *ports)):
        macro_connect(net, leaf, endpoint)
    macro_connect(net, package_endpoint, frame.principal)
    return {
        "decoder_head": None,
        "unpack_head": _head(frame.principal),
        "width": width,
        "ready_slot": 0,
    }
