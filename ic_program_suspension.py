"""Safe suspension of a complete compiled feedback program.

This module turns a compiled source program into a dormant principal
package.  It does not embed ``!Gamma`` in the suspension: each source cell
uses the compiler bare extension and exposes its genetic-code input as a
package leaf.  Activation supplies the shared program code natively, decodes
the suspension, restores the initial active pair, and exposes the original
program output.

Construction is offline.  Activation and reduction use only primitive IC
interaction rules.
"""

from dataclasses import dataclass
from collections.abc import Mapping

from ic_package_codec import build_decoder, encode_package, validate_package
from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec
from lafont_ic_macro_builder import build_C_n, build_M, build_M_star, macro_connect
from source_feedback_audit import make_sim
from source_ic_coherent_compiler import CoherentICCompiler


@dataclass(frozen=True)
class Suspension:
    """A dormant source program and its package encoding."""

    number: int
    source_cells: int
    width: int
    package: GraphSpec
    code: GraphSpec


def append_spec(spec, net, bindings):
    """Append exact GraphSpec syntax while the enclosing builder has holes.

    GraphSpec.instantiate audits the entire destination immediately. Native
    protocol assembly deliberately has other unpaired ports until its final
    net.check(), so this adapter validates the imported syntax and matching
    interface but defers that whole-network audit to the enclosing builder.
    """
    if not isinstance(spec, GraphSpec) or not isinstance(net, Net) or not isinstance(bindings, Mapping):
        raise TypeError("literal composition requires GraphSpec, Net and port bindings")
    spec.validate()
    if set(bindings) != set(spec.boundaries):
        raise ValueError("literal graph bindings differ from its interface")
    if len(set(bindings.values())) != len(bindings):
        raise ValueError("literal graph boundaries need distinct target ports")
    if any(endpoint not in net.adj or net.adj[endpoint] is not None for endpoint in bindings.values()):
        raise ValueError("literal graph bindings must be unpaired ports")
    names = [net.cell(kind) for kind in spec.kinds]

    def port(endpoint):
        return bindings[endpoint[1]] if endpoint[0] == "F" else (names[endpoint[0]], endpoint[1])

    for left, right in spec.wires:
        net.link(port(left), port(right))
    net.cycles += spec.cycles
    return names


def _source_endpoint(cells, endpoint):
    name, port = endpoint
    if name not in cells:
        raise ValueError(f"unknown source cell in suspension: {endpoint!r}")
    cell = cells[name]
    if port < 0 or port > len(cell.auxiliaries):
        raise ValueError(f"source port out of range: {endpoint!r}")
    return cell.principal if port == 0 else cell.auxiliaries[port - 1]


def _wire_source_edges(net, cells, adjacency, init_name):
    init = cells[init_name]
    cutA = init.principal
    cutB = None
    output = None
    handled = set()
    for left, right in adjacency.items():
        if left in handled:
            continue
        handled.update((left, right))
        if left == (init_name, 0) or right == (init_name, 0):
            if cutB is not None:
                raise ValueError("INIT principal appears in multiple wires")
            cutB = _source_endpoint(
                cells, right if left == (init_name, 0) else left)
            continue
        if left[0] == "OUT" or right[0] == "OUT":
            if output is not None:
                raise ValueError("the source graph has multiple outputs")
            output = _source_endpoint(
                cells, left if right == ("OUT", 0) else right)
            continue
        macro_connect(net, _source_endpoint(cells, left),
                      _source_endpoint(cells, right))
    if cutB is None or output is None:
        raise ValueError("feedback input lacks the INIT cut or output wire")
    return cutA, cutB, output


def suspend_feedback(compiler, number):
    if not isinstance(compiler, CoherentICCompiler):
        raise TypeError("compiler must be a CoherentICCompiler")
    if type(number) is not int or number < 0:
        raise ValueError("feedback input must be a natural number")

    source_types, adjacency = make_sim(number)
    init_names = [name for name, kind in source_types.items() if kind == "INIT"]
    if len(init_names) != 1:
        raise ValueError("the feedback input must contain exactly one INIT cell")
    init_name = init_names[0]

    net = Net()
    cells = {name: compiler._extension(net, kind)
             for name, kind in source_types.items()}
    cutA, cutB, output = _wire_source_edges(net, cells, adjacency, init_name)

    slots = [cutA, cutB, output]
    slots.extend(cell.code_port for cell in cells.values())
    frame = build_M(net, len(slots))
    for slot, leaf in zip(slots, frame.auxiliaries):
        macro_connect(net, slot, leaf)
    root = net.boundary("ROOT")
    macro_connect(net, frame.principal, root)
    net.check()
    validate_package(net)

    return Suspension(number=number, source_cells=len(source_types),
                      width=len(slots), package=GraphSpec.from_net(net),
                      code=GraphSpec.from_net(encode_package(net, label="ROOT")))


def _take_boundary(net, boundary):
    neighbor = net.adj.pop(boundary)
    net.free.remove(boundary)
    if neighbor is None:
        raise ValueError("activation slot has no native connection")
    net.adj[neighbor] = None
    return neighbor


def build_activation(net, width, code_endpoint, program_endpoint,
                     output_endpoint):
    if not isinstance(net, Net):
        raise TypeError("activation must be appended to a primitive IC Net")
    if type(width) is not int or width < 5:
        raise ValueError("invalid suspension width")
    code_count = width - 3
    if code_count and program_endpoint is None:
        raise ValueError("a suspension with code slots needs program code")

    frame = build_M_star(net, width)
    decoder = build_decoder(net)
    macro_connect(net, code_endpoint, decoder.principal)
    macro_connect(net, decoder.auxiliaries[0], frame.principal)

    macro_connect(net, frame.auxiliaries[0], frame.auxiliaries[1])
    macro_connect(net, frame.auxiliaries[2], output_endpoint)

    code_ports = [_take_boundary(net, leaf) for leaf in frame.auxiliaries[3:]]
    if code_ports:
        fan = build_C_n(net, code_ports)
        macro_connect(net, fan.principal, program_endpoint)
    # The enclosing sequence may still have continuation ports to connect.
    # Its final whole-net audit runs after every stage has been prewired.
    return None
