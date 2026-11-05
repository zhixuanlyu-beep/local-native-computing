"""Fixed M4 observation contracts and syntax-only observation builders."""

from dataclasses import dataclass
from itertools import product

from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec
from lafont_ic_macro_builder import macro_connect

REPRESENTATIONS = ("A", "B")
FAMILIES = ("binary", "unary", "copy", "erase")
FAMILY_INTERFACES = {
    "binary": ("LEFT", "RIGHT", "OUT"),
    "unary": ("IN", "OUT"),
    "copy": ("IN", "OUT1", "OUT2"),
    "erase": ("IN",),
}


def _strict_bools(bits, length=None):
    if type(bits) is not tuple:
        raise TypeError("bits must be a tuple")
    if length is not None and len(bits) != length:
        raise ValueError(f"expected {length} bits, got {len(bits)}")
    if any(type(bit) is not bool for bit in bits):
        raise TypeError("every bit must be bool")
    return bits


def _strict_reprs(reprs, length=None):
    if type(reprs) is not tuple:
        raise TypeError("representations must be a tuple")
    if length is not None and len(reprs) != length:
        raise ValueError(f"expected {length} representations, got {len(reprs)}")
    if any(type(rep) is not str or rep not in REPRESENTATIONS for rep in reprs):
        raise ValueError(f"unknown representation in {reprs!r}")
    return reprs


def value_spec(rep, bit):
    if type(rep) is not str or rep not in REPRESENTATIONS:
        raise ValueError(f"unknown representation: {rep!r}")
    if type(bit) is not bool:
        raise TypeError("bit must be bool")
    if rep == "A":
        if not bit:
            return GraphSpec(("e",), ("ROOT",), ((("F", "ROOT"), (0, 0)),))
        return GraphSpec(("g",), ("ROOT",), ((("F", "ROOT"), (0, 0)), ((0, 1), (0, 2))))
    if bit:
        return GraphSpec(
            ("g", "e", "g"),
            ("ROOT",),
            (
                (("F", "ROOT"), (0, 0)),
                ((0, 1), (1, 0)),
                ((0, 2), (2, 0)),
                ((2, 1), (2, 2)),
            ),
        )
    return GraphSpec(
        ("g", "e", "e"),
        ("ROOT",),
        (
            (("F", "ROOT"), (0, 0)),
            ((0, 1), (1, 0)),
            ((0, 2), (2, 0)),
        ),
    )


@dataclass(frozen=True)
class TaskContract:
    name: str
    family: str
    input_reprs: tuple[str, ...]
    output_reprs: tuple[str, ...]
    mask: int | None

    def __post_init__(self):
        if type(self.name) is not str or not self.name:
            raise ValueError("name must be a nonempty string")
        if type(self.family) is not str or self.family not in FAMILIES:
            raise ValueError(f"unknown family: {self.family!r}")
        if type(self.input_reprs) is not tuple:
            raise TypeError("input_reprs must be a tuple")
        if type(self.output_reprs) is not tuple:
            raise TypeError("output_reprs must be a tuple")
        _strict_reprs(self.input_reprs)
        _strict_reprs(self.output_reprs)
        if self.family == "binary":
            if self.input_reprs != ("A", "A") or self.output_reprs != ("A",):
                raise ValueError("binary contracts are fixed to A^2 -> A")
            if type(self.mask) is not int or not 0 <= self.mask <= 15:
                raise ValueError("binary mask must be an integer from 0 through 15")
        elif self.family == "unary":
            if len(self.input_reprs) != 1 or len(self.output_reprs) != 1:
                raise ValueError("unary contracts have one input and one output")
            if type(self.mask) is not int or not 0 <= self.mask <= 3:
                raise ValueError("unary mask must be an integer from 0 through 3")
        elif self.family == "copy":
            if len(self.input_reprs) != 1 or self.output_reprs != (self.input_reprs[0], self.input_reprs[0]):
                raise ValueError("copy contracts have one input and two matching outputs")
            if self.mask is not None:
                raise ValueError("copy contracts do not use a mask")
        else:
            if len(self.input_reprs) != 1 or self.output_reprs != ():
                raise ValueError("erase contracts have one input and no outputs")
            if self.mask is not None:
                raise ValueError("erase contracts do not use a mask")

    @property
    def interface(self):
        return FAMILY_INTERFACES[self.family]

    def inputs(self):
        width = len(self.input_reprs)
        return tuple(tuple(bits) for bits in product((False, True), repeat=width))

    def evaluate(self, bits):
        _strict_bools(bits, len(self.input_reprs))
        if self.family in ("binary", "unary"):
            index = sum(int(bit) << (len(bits) - 1 - position) for position, bit in enumerate(bits))
            return (bool((self.mask >> index) & 1),)
        if self.family == "copy":
            return tuple(bits) * 2
        return ()

    def to_dict(self):
        return {
            "name": self.name,
            "family": self.family,
            "input_reprs": list(self.input_reprs),
            "output_reprs": list(self.output_reprs),
            "mask": self.mask,
            "interface": list(self.interface),
        }


def contracts():
    result = []
    for mask in range(16):
        result.append(TaskContract(f"binary-A-A-{mask:02d}", "binary", ("A", "A"), ("A",), mask))
    for source in REPRESENTATIONS:
        for target in REPRESENTATIONS:
            for mask in range(4):
                result.append(TaskContract(f"unary-{source}-{target}-{mask}", "unary", (source,), (target,), mask))
    for rep in REPRESENTATIONS:
        result.append(TaskContract(f"copy-{rep}", "copy", (rep,), (rep, rep), None))
    for rep in REPRESENTATIONS:
        result.append(TaskContract(f"erase-{rep}", "erase", (rep,), (), None))
    return tuple(result)


@dataclass
class BuiltObservation:
    net: Net
    component_ids: list[str]
    input_ids: list[list[str]]


def build_observation(family, candidate, input_reprs, bits):
    if type(family) is not str or family not in FAMILIES:
        raise ValueError(f"unknown family: {family!r}")
    if not isinstance(candidate, GraphSpec):
        raise TypeError("candidate must be a GraphSpec")
    input_reprs = _strict_reprs(input_reprs)
    expected_count = 2 if family == "binary" else 1
    if len(input_reprs) != expected_count:
        raise ValueError(f"{family} expects {expected_count} input representations")
    if family == "binary" and input_reprs != ("A", "A"):
        raise ValueError("binary observations take two A inputs")
    _strict_bools(bits, expected_count)
    expected_interface = FAMILY_INTERFACES[family]
    if tuple(candidate.boundaries) != expected_interface:
        raise ValueError(f"candidate interface must be {expected_interface}, got {candidate.boundaries}")
    net = candidate.instantiate()
    component_ids = list(net.nodes)
    input_ids = []
    for position, (rep, bit) in enumerate(zip(input_reprs, bits)):
        before = set(net.nodes)
        token_root = value_spec(rep, bit).open_root(net)
        input_proxy = ("F", expected_interface[position])
        if input_proxy not in net.adj:
            raise ValueError(f"candidate input boundary disappeared: {input_proxy}")
        macro_connect(net, input_proxy, token_root)
        input_ids.append([name for name in net.nodes if name not in before])
    net.check()
    return BuiltObservation(net, component_ids, input_ids)


def expected(task, bits):
    if not isinstance(task, TaskContract):
        raise TypeError("task must be a TaskContract")
    _strict_bools(bits, len(task.input_reprs))
    values = task.evaluate(bits)
    if len(values) != len(task.output_reprs):
        raise AssertionError("contract output arity mismatch")
    net = Net()
    output_labels = {
        "binary": ("OUT",),
        "unary": ("OUT",),
        "copy": ("OUT1", "OUT2"),
        "erase": (),
    }[task.family]
    for label, rep, bit in zip(output_labels, task.output_reprs, values):
        root = value_spec(rep, bit).open_root(net)
        net.link(root, net.boundary(label))
    net.check()
    return net


def main():
    records = contracts()
    print("PASS: fixed observation contracts", len(records))
    print("LIMIT: builders are syntax-only; no candidate acceptance is claimed")


if __name__ == "__main__":
    main()
