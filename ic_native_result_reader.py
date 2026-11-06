"""Bounded native reader for the coherent compiler's SQ/BR unary results.

Selectors dispatch through a literal menu. New source headers are bare
extensions filled with the original header's stored code. Only terminal Z
handlers emit readiness; BR joins readiness of both independently read args.
Construction is finite, typed and offline. Runtime uses primitive IC only.
"""
from dataclasses import dataclass

from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec
from ic_program_suspension import append_spec
from lafont_ic_macro_builder import build_M_star, build_menu, macro_connect
from source_ic_coherent_compiler import CoherentICCompiler


@dataclass
class Reader:
    principal: tuple
    metadata: dict


def _loop(net):
    cell = net.cell("g")
    net.link((cell, 1), (cell, 2))
    return cell, 0


def _take_proxy(net, endpoint):
    if endpoint[0] != "F" or net.adj.get(endpoint) is None:
        raise ValueError("expected a connected private output proxy")
    neighbor = net.adj.pop(endpoint)
    net.free.remove(endpoint)
    net.adj[neighbor] = None
    return neighbor


def build_reader(net, compiler, gate, depth, *, value_out, ready_out, kind="result",
                 result_progress=None):
    if not isinstance(net, Net) or not isinstance(compiler, CoherentICCompiler):
        raise TypeError("native reader requires Net and CoherentICCompiler")
    if not isinstance(gate, GraphSpec) or set(gate.boundaries) != {"CTRL", "DATA", "OUT"} or len(gate.kinds) != 1:
        raise ValueError("invalid one-cell join gate interface")
    if type(depth) is not int or depth < 0 or kind not in ("result", "unary"):
        raise ValueError("invalid bounded reader grammar")
    if value_out == ready_out:
        raise ValueError("value and readiness need distinct output ports")
    if result_progress is not None and (kind != "result" or not callable(result_progress)):
        raise ValueError("result progress adapter requires the result grammar and a callable")

    observer, splitter = net.cell("d"), net.cell("g")
    net.link((observer, 1), (splitter, 0))
    net.link((splitter, 2), (net.cell("e"), 0))
    extraction = build_M_star(net, 2)
    macro_connect(net, (observer, 2), extraction.principal)
    macro_connect(net, extraction.auxiliaries[0], value_out)
    macro_connect(net, extraction.auxiliaries[1], ready_out)
    metadata = {"head_observer": observer, "ready_emitters": [], "join_gates": [],
                "kind": kind, "unary_depth": depth, "embedded_program_copies": 0}

    def collect(child):
        metadata["ready_emitters"].extend(child.metadata["ready_emitters"])
        metadata["join_gates"].extend(child.metadata["join_gates"])

    def unary_child(frame_port, header_port, ready_port, child_depth):
        child = build_reader(net, compiler, gate, child_depth,
                             value_out=header_port, ready_out=ready_port, kind="unary")
        macro_connect(net, frame_port, child.principal)
        collect(child)

    def handler(symbol):
        arity = compiler.arity[symbol]
        frame = build_M_star(net, arity + 2)
        header = compiler._extension(net, symbol)
        # Reuse the original source symbol's stored !Gamma via native D and
        # projection in the new bare header. No literal !Gamma is allocated.
        macro_connect(net, frame.auxiliaries[0], header.code_port)
        packet = net.cell("g")
        net.link((packet, 1), header.principal)
        macro_connect(net, frame.auxiliaries[-1], (packet, 0))
        readiness = (packet, 2)
        if result_progress is not None and symbol in ("SQ", "BR"):
            readiness = result_progress(symbol, readiness)
        if symbol == "Z":
            ready = _loop(net)
            macro_connect(net, readiness, ready)
            metadata["ready_emitters"].append(ready[0])
        elif symbol in ("S", "SQ"):
            unary_child(frame.auxiliaries[1], header.auxiliaries[0], readiness,
                        depth - 1 if symbol == "S" else depth)
        elif symbol == "BR":
            serial = getattr(net, "_reader_join_serial", 0)
            net._reader_join_serial = serial + 1
            left = net.boundary(f"reader-join-{serial}-left")
            right = net.boundary(f"reader-join-{serial}-right")
            unary_child(frame.auxiliaries[1], header.auxiliaries[0], left, depth)
            unary_child(frame.auxiliaries[2], header.auxiliaries[1], right, depth)
            before = set(net.nodes)
            append_spec(gate, net, {"CTRL": _take_proxy(net, left), "DATA": _take_proxy(net, right),
                                    "OUT": _take_proxy(net, readiness) if readiness[0] == "F" else readiness})
            metadata["join_gates"].extend(sorted(set(net.nodes) - before))
        else:
            raise ValueError("unsupported handler")
        return frame.principal

    admitted = ({"SQ", "BR"} if kind == "result" else ({"Z", "S"} if depth else {"Z"}))
    roots = [handler(symbol) if symbol in admitted else (net.cell("e"), 0)
             for symbol in compiler.symbols]
    menu = build_menu(net, roots)
    macro_connect(net, (splitter, 1), menu.principal)
    return Reader((observer, 0), metadata)
