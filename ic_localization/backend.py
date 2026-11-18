"""Composable native selector packages; builders never evaluate operations."""
from itertools import product

from ic_coherent_output_decoder import port_graph_isomorphic
from ic_observation_contracts import value_spec
from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec
from lafont_ic_macro_builder import build_M, build_M_star, build_selector, macro_connect

REPRESENTATIONS = ("S", "P")


def _representation(rep):
    if type(rep) is not str or rep not in REPRESENTATIONS:
        raise ValueError("representation must be S or P")


def _a(net, bit):
    cell = net.cell("g" if bit else "e")
    if bit:
        net.link((cell, 1), (cell, 2))
    return cell, 0


def literal(net, rep, bit):
    _representation(rep)
    if type(bit) is not bool:
        raise TypeError("literal input must be an exact Boolean")
    selector = build_selector(net, 2, 1 if bit else 2)
    ports = [selector.principal, selector.auxiliaries[0]]
    if rep == "P":
        ports.insert(0, _a(net, bit))
    frame = build_M(net, len(ports))
    for slot, port in zip(frame.auxiliaries, ports):
        macro_connect(net, slot, port)
    return frame.principal


def erase_value(net, port):
    macro_connect(net, port, (net.cell("e"), 0))


def copy_value(net, port, count):
    if type(count) is not int or count < 0:
        raise ValueError("copy count must be a nonnegative integer")
    if count == 0:
        erase_value(net, port)
        return []
    copies = []
    for _ in range(count-1):
        cell = net.cell("d")
        macro_connect(net, port, (cell, 0))
        copies.append((cell, 1))
        port = (cell, 2)
    copies.append(port)
    return copies


def _select(net, rep, control, first, second):
    _representation(rep)
    unpack = build_M_star(net, 3 if rep == "P" else 2)
    macro_connect(net, control, unpack.principal)
    slots = unpack.auxiliaries
    if rep == "P":
        erase_value(net, slots[0])
        slots = slots[1:]
    menu = build_M(net, 2)
    macro_connect(net, menu.auxiliaries[0], first)
    macro_connect(net, menu.auxiliaries[1], second)
    macro_connect(net, slots[0], menu.principal)
    return slots[1]


def boolean_and(net, rep, left, right):
    return _select(net, rep, left, right, literal(net, rep, False))


def boolean_or(net, rep, left, right):
    return _select(net, rep, left, literal(net, rep, True), right)


def boolean_not(net, rep, operand):
    return _select(net, rep, operand, literal(net, rep, False), literal(net, rep, True))


def decode(net, rep, port, out):
    _representation(rep)
    if rep == "S":
        macro_connect(net, _select(net, rep, port, _a(net, True), _a(net, False)), out)
    else:
        unpack = build_M_star(net, 3)
        macro_connect(net, port, unpack.principal)
        macro_connect(net, unpack.auxiliaries[0], out)
        erase_value(net, unpack.auxiliaries[1])
        erase_value(net, unpack.auxiliaries[2])


def literal_spec(rep, bit):
    net = Net()
    macro_connect(net, literal(net, rep, bit), net.boundary("ROOT"))
    return GraphSpec.from_net(net)


def validate_literal(spec, rep):
    """Offline representation precondition, including P's two views."""
    _representation(rep)
    if not isinstance(spec, GraphSpec) or spec.boundaries != ("ROOT",) or not any(
            port_graph_isomorphic(spec.instantiate(), literal_spec(rep, bit).instantiate())
            for bit in (False, True)):
        raise ValueError("inconsistent or malformed selector package")
    return spec


def _expected(values):
    net = Net()
    for label, bit in values:
        value_spec("A", bit).instantiate(net, {"ROOT": net.boundary(label)})
    return GraphSpec.from_net(net)


def foundation_cases():
    cases = []
    for rep in REPRESENTATIONS:
        for name, builder, reference in (("AND", boolean_and, lambda a, b: a and b),
                                          ("OR", boolean_or, lambda a, b: a or b)):
            for a, b in product((False, True), repeat=2):
                net = Net()
                port = builder(net, rep, literal(net, rep, a), literal(net, rep, b))
                decode(net, rep, port, net.boundary("OUT"))
                cases.append({"name": f"{rep}-{name}-{int(a)}{int(b)}",
                              "initial": GraphSpec.from_net(net),
                              "expected": _expected([("OUT", reference(a, b))])})
        for name in ("NOT", "copy", "erase", "decode"):
            for bit in (False, True):
                net = Net()
                port = literal(net, rep, bit)
                if name == "NOT":
                    decode(net, rep, boolean_not(net, rep, port), net.boundary("OUT"))
                    outputs = [("OUT", not bit)]
                elif name == "copy":
                    for copied, label in zip(copy_value(net, port, 2), ("OUT1", "OUT2")):
                        decode(net, rep, copied, net.boundary(label))
                    outputs = [("OUT1", bit), ("OUT2", bit)]
                elif name == "erase":
                    erase_value(net, port)
                    outputs = []
                else:
                    decode(net, rep, port, net.boundary("OUT"))
                    outputs = [("OUT", bit)]
                cases.append({"name": f"{rep}-{name}-{int(bit)}", "initial": GraphSpec.from_net(net),
                              "expected": _expected(outputs)})
    return cases
