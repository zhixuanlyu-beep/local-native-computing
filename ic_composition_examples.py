"""Small composition examples for the deterministic schedule audit.

The builders in this module are constructors only.  They never normalize an
example to learn its answer, and every expected graph is assembled
independently.  Runtime examples are intended to be executed by the root-owned
``ic_schedule_audit`` scheduler.  This module records formulas and hypotheses;
empirical counts and replay reports belong to that root-owned audit.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ic_package_codec import build_decoding, encode_package, validate_package
from ic_primitive_port_verifier import AR, Net, isomorphic
from ic_research_artifacts import GraphSpec
from lafont_ic_macro_builder import (
    build_M,
    build_M_star,
    build_menu,
    build_selector,
    macro_connect,
)
from ic_signed_branch_pruning import HOLE, package


@dataclass(frozen=True)
class MacroCase:
    """One positive constructor example and its independent expectation."""

    name: str
    initial: Net
    expected: Net
    expected_interactions: int | None
    hypothesis: str

    def graph_pair(self) -> tuple[GraphSpec, GraphSpec]:
        """Return complete immutable syntax snapshots for both graphs."""
        return GraphSpec.from_net(self.initial), GraphSpec.from_net(self.expected)

    def check_shapes(self) -> None:
        initial, expected = self.initial, self.expected
        initial.check()
        expected.check()
        if self.expected_interactions is not None:
            if type(self.expected_interactions) is not int or self.expected_interactions < 0:
                raise ValueError("expected interaction count must be a non-negative integer")
            if expected.active():
                raise ValueError("the expected graph must already be reduced")
        if self.expected_interactions == 0 and not isomorphic(initial, expected):
            raise ValueError("a zero-interaction example must already match its expectation")


def _case(name, net, expected, interactions, hypothesis):
    case = MacroCase(name, net, expected, interactions, hypothesis)
    case.check_shapes()
    return case


def macro_cases(compiler) -> list[dict]:
    """Build the fixed positive example family without normalizing any case."""
    cases: list[MacroCase] = []
    cases.extend(_m_cases())
    cases.extend(_selector_cases())
    cases.extend(_codec_cases(compiler))
    return [_as_case_dict(case) for case in cases]


def bad_delta_copy() -> dict:
    """Return the negative delta-copy bypass example (never a positive case)."""
    initial = Net()
    payload = _fixed_package(("d", ("e",), ("e",)), ())
    payload_spec = GraphSpec.from_net(payload)
    fanout = initial.cell("d")
    for port, label in ((1, "OUT1"), (2, "OUT2")):
        initial.link((fanout, port), initial.boundary(label))
    payload_spec.instantiate(initial, {"ROOT": (fanout, 0)})

    expected = _expected_copy(payload)

    return {
        "name": "bad-delta-copy",
        "initial": initial,
        "expected": expected,
        "expected_interactions": None,
        "hypothesis": (
            "bypassing the delta-free package precondition yields two epsilon outputs, "
            "rather than the two delta-data trees claimed by unrestricted copying"
        ),
        "negative": True,
    }


def _as_case_dict(case):
    return {
        "name": case.name,
        "initial": case.initial,
        "expected": case.expected,
        "expected_interactions": case.expected_interactions,
        "hypothesis": case.hypothesis,
    }


def _m_cases():
    result = []
    for arity in range(7):
        initial = Net()
        left, right = build_M(initial, arity), build_M_star(initial, arity)
        for index, (a, b) in enumerate(zip(left.auxiliaries, right.auxiliaries)):
            macro_connect(initial, a, initial.boundary(f"LEFT-{index}"))
            macro_connect(initial, b, initial.boundary(f"RIGHT-{index}"))
        macro_connect(initial, left.principal, right.principal)

        expected = Net()
        for index in range(arity):
            expected.link(expected.boundary(f"LEFT-{index}"),
                          expected.boundary(f"RIGHT-{index}"))
        expected_interactions = {0: 1, 1: 0}.get(arity, arity - 1)
        result.append(_case(
            f"M{arity}-Mstar", initial, expected, expected_interactions,
            "M_n and M_n* expose ordered left/right slots; their cut resolves by the primitive rules",
        ))
    return result


def _selector_cases():
    result = []
    for arity in range(1, 4):
        for index in range(1, arity + 1):
            initial = Net()
            package_roots = [_unary_chain(initial, i) for i in range(1, arity + 1)]
            menu = build_menu(initial, package_roots)
            selector = build_selector(initial, arity, index)
            macro_connect(initial, selector.auxiliaries[0], initial.boundary("OUT"))
            macro_connect(initial, menu.principal, selector.principal)

            expected = Net()
            _unary_chain(expected, index, output="OUT")
            erased_cost = sum(2 * i + 1 for i in range(1, arity + 1) if i != index)
            expected_interactions = arity - 1 + erased_cost
            result.append(_case(
                f"selector-{arity}-{index}", initial, expected, expected_interactions,
                "the fixed selector consumes the menu and retains the selected unary payload",
            ))
    return result


def _codec_cases(compiler):
    result = []
    result.extend(_primitive_copy_erase_cases(compiler))
    packages = (
        ("epsilon", _fixed_package(("e",), ())),
        ("gamma-ee", _fixed_package(("g", ("e",), ("e",)), ())),
        ("delta-ee", _fixed_package(("d", ("e",), ("e",)), ())),
        ("loop", _fixed_package(("g", HOLE, HOLE), ((0, 1),))),
        ("program", compiler.program),
    )
    for label, package_net in packages:
        encoded = encode_package(package_net)
        encoded_spec = GraphSpec.from_net(encoded)
        encoded_cells = len(encoded.nodes)
        encoded_wires = _auxiliary_wire_pairs(encoded)
        decode1 = 3 * Counter(package_net.nodes.values())["d"]
        if decode1 == 0:
            decode1 = 6
        package_spec = GraphSpec.from_net(package_net)

        for copies in (1, 2):
            initial = Net()
            encoded_spec.instantiate(initial)
            running = build_decoding(initial, copies)

            expected = Net()
            labels = ("OUT",) if copies == 1 else ("OUT1", "OUT2")
            for output_label in labels:
                package_spec.instantiate(
                    expected, {"ROOT": expected.boundary(output_label)})

            total = decode1 if copies == 1 else encoded_cells + encoded_wires + 2 * decode1
            result.append(_case(
                f"codec-{label}-decode{copies}", running, expected, total,
                ("one native decode yields one independent package copy" if copies == 1 else
                 "a native delta copies the code before two independent decodes"),
            ))
    return result


def _primitive_copy_erase_cases(compiler):
    result = []
    packages = (
        ("epsilon", _fixed_package(("e",), ())),
        ("gamma-ee", _fixed_package(("g", ("e",), ("e",)), ())),
        ("loop", _fixed_package(("g", HOLE, HOLE), ((0, 1),))),
        ("program-code", compiler.code),
    )
    for label, package_net in packages:
        result.append(_case(
            f"primitive-copy-{label}", primitive_copy(package_net), _expected_copy(package_net),
            _copy_cost(package_net), "native delta copying duplicates a delta-free principal package",
        ))
    packages = (packages[0], packages[1],
                ("delta-ee", _fixed_package(("d", ("e",), ("e",)), ())),
                packages[2], ("program", compiler.program))
    for label, package_net in packages:
        result.append(_case(
            f"primitive-erase-{label}", primitive_erase(package_net), _expected_erase(),
            _erase_cost(package_net), "native epsilon erasure removes the complete principal package",
        ))
    return result


def _unary_chain(net, length, output=None):
    root = (net.cell("e"), 0)
    for _ in range(length):
        cell = net.cell("g")
        net.link((cell, 1), root)
        net.link((cell, 2), (net.cell("e"), 0))
        root = (cell, 0)
    if output is not None:
        net.link(root, net.boundary(output))
    return root


def _copy_cost(package_net):
    cells = len(package_net.nodes)
    internal_wires = _auxiliary_wire_pairs(package_net)
    return cells + internal_wires


def _erase_cost(package_net):
    return len(package_net.nodes) + _auxiliary_wire_pairs(package_net)


def _expected_copy(package_net):
    expected = Net()
    spec = GraphSpec.from_net(package_net)
    for label in ("OUT1", "OUT2"):
        spec.instantiate(expected, {"ROOT": expected.boundary(label)})
    expected.check()
    return expected


def _expected_erase():
    expected = Net()
    expected.check()
    return expected


def _fixed_package(shape, matching):
    if shape[0] == "d":
        net = Net()
        root = net.cell("d")
        for port in (1, 2):
            net.link((root, port), (net.cell("e"), 0))
        net.link((root, 0), net.boundary("ROOT"))
        net.check()
        return net
    net = Net()
    root, _, _ = package(net, shape, matching)
    net.link(root, net.boundary("ROOT"))
    validate_package(net)
    return net


def _auxiliary_wire_pairs(net):
    cell_ports = {
        (cell, port)
        for cell, kind in net.nodes.items()
        for port in range(AR[kind] + 1)
    }
    seen, count = set(), 0
    for endpoint, other in net.adj.items():
        if endpoint in seen:
            continue
        if endpoint in cell_ports and other in cell_ports and endpoint[1] != 0 and other[1] != 0:
            count += 1
            seen.update((endpoint, other))
    return count


def primitive_copy(package_net):
    """Native delta copy for a validated principal package.

    Delta copying is a theorem about delta-free reduced packages.  Supplying
    arbitrary delta data bypasses that precondition and is rejected here so
    callers cannot silently obtain the misleading two-copy interface.
    """
    if any(kind == "d" for kind in package_net.nodes.values()):
        raise ValueError("primitive delta copy requires a delta-free package")
    validate_package(package_net)
    net = Net()
    source = GraphSpec.from_net(package_net)
    fanout = net.cell("d")
    bindings = {"ROOT": (fanout, 0)}
    if "OUT1" in source.boundaries or "OUT2" in source.boundaries:
        raise ValueError("package reserves copy output labels")
    for port, label in ((1, "OUT1"), (2, "OUT2")):
        net.link((fanout, port), net.boundary(label))
    source.instantiate(net, bindings)
    net.check()
    return net


def primitive_erase(package_net):
    """Native epsilon erasure for a validated principal package."""
    validate_package(package_net)
    net = Net()
    source = GraphSpec.from_net(package_net)
    eraser = net.cell("e")
    source.instantiate(net, {"ROOT": (eraser, 0)})
    net.check()
    return net
