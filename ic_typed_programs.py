"""Finite typed source syntax and independent verification-only references.

Builders wire literal source graphs without evaluating answers. The source
normalizer and mathematical constructor diagrams belong to verification;
runtime experiments execute only primitive IC interactions.
"""
from collections import Counter
from dataclasses import dataclass
from math import isqrt
from types import MappingProxyType
from typing import Any, Mapping, Sequence
from contextlib import redirect_stdout
from io import StringIO

from source_feedback_audit import AR, RULES
from source_feedback_audit import active_pairs as source_active_pairs
from source_feedback_audit import apply as source_apply
from source_feedback_audit import decode as source_decode
# The original audit exports this authoritative table and prints its audit on
# import. Keep that static validation (including its assertions) without
# repeating its console report in every composition command.
with redirect_stdout(StringIO()):
    from source_rule_audit_v3 import PORTS

MAX_NAT_DEPTH = 2
MAX_PARALLEL_TASKS = 2
MAX_AST_NODES = 12
MAX_AST_DEPTH = 6
MAX_SERIALIZATION_DEPTH = 64
MAX_SERIALIZATION_NODES = 256
FANOUT_CONSUMERS = ("check", "erase")

@dataclass(frozen=True, slots=True)
class Nat:
    kind: str
    pred: "Nat | None" = None

class Zero(Nat):
    def __init__(self):
        super(Zero, self).__init__("zero")

class Succ(Nat):
    def __init__(self, pred):
        super(Succ, self).__init__("succ", pred if isinstance(pred, Nat) else nat(pred))

def nat(value):
    if isinstance(value, Nat):
        return value
    if type(value) is not int:
        raise TypeError("natural sugar must be an int or Nat")
    if not 0 <= value <= MAX_NAT_DEPTH:
        raise ValueError("natural sugar must be in 0..MAX_NAT_DEPTH")
    result = Zero()
    for _ in range(value):
        result = Succ(result)
    return result

def nat_depth(value):
    if not isinstance(value, Nat):
        raise TypeError("expected Nat")
    depth = 0
    while isinstance(value, Succ):
        depth += 1
        if depth > MAX_NAT_DEPTH:
            raise ValueError("Nat depth exceeds MAX_NAT_DEPTH")
        value = value.pred
    if not isinstance(value, Zero):
        raise TypeError("malformed Nat")
    if depth > MAX_NAT_DEPTH:
        raise ValueError("Nat depth exceeds MAX_NAT_DEPTH")
    return depth

def nat_value(value):
    return nat_depth(value)

@dataclass(frozen=True, slots=True)
class Task:
    kind: str

@dataclass(frozen=True, slots=True, init=False)
class Check(Task):
    n: Nat
    def __init__(self, n):
        super(Check, self).__init__("check")
        object.__setattr__(self, "n", nat(n))

@dataclass(frozen=True, slots=True, init=False)
class Copy(Task):
    n: Nat
    def __init__(self, n):
        super(Copy, self).__init__("copy")
        object.__setattr__(self, "n", nat(n))

@dataclass(frozen=True, slots=True, init=False)
class Erase(Task):
    n: Nat
    def __init__(self, n):
        super(Erase, self).__init__("erase")
        object.__setattr__(self, "n", nat(n))

@dataclass(frozen=True, slots=True, init=False)
class Compare(Task):
    n: Nat
    m: Nat
    def __init__(self, n, m):
        super(Compare, self).__init__("compare")
        object.__setattr__(self, "n", nat(n))
        object.__setattr__(self, "m", nat(m))

@dataclass(frozen=True, slots=True, init=False)
class Fanout(Task):
    n: Nat
    left: str
    right: str
    def __init__(self, n, left, right):
        super(Fanout, self).__init__("fanout")
        object.__setattr__(self, "n", nat(n))
        if left not in FANOUT_CONSUMERS or right not in FANOUT_CONSUMERS:
            raise ValueError("Fanout consumers must be check or erase")
        object.__setattr__(self, "left", left)
        object.__setattr__(self, "right", right)

@dataclass(frozen=True, slots=True, init=False)
class Parallel(Task):
    tasks: tuple
    def __init__(self, tasks):
        super(Parallel, self).__init__("parallel")
        if isinstance(tasks, (str, bytes)) or not isinstance(tasks, Sequence):
            raise TypeError("Parallel tasks must be a sequence")
        if not 1 <= len(tasks) <= MAX_PARALLEL_TASKS:
            raise ValueError("Parallel must contain 1..MAX_PARALLEL_TASKS tasks")
        object.__setattr__(self, "tasks", tuple(tasks))

def _task_children(task):
    if isinstance(task, Check):
        return (("n", task.n),)
    if isinstance(task, Copy):
        return (("n", task.n),)
    if isinstance(task, Erase):
        return (("n", task.n),)
    if isinstance(task, Compare):
        return (("n", task.n), ("m", task.m))
    if isinstance(task, Fanout):
        return (("n", task.n),)
    if isinstance(task, Parallel):
        return tuple(("task", child) for child in task.tasks)
    raise TypeError("unknown task")

def validate_ast(value):
    if not isinstance(value, Nat) and not isinstance(value, Task):
        raise TypeError("the AST root must be a Nat or Task")
    nodes = 0
    stack = [(value, 1)]
    while stack:
        node, depth = stack.pop()
        nodes += 1
        if nodes > MAX_AST_NODES:
            raise ValueError("AST node bound exceeded")
        if depth > MAX_AST_DEPTH:
            raise ValueError("AST depth bound exceeded")
        if isinstance(node, Nat):
            nat_depth(node)
        elif isinstance(node, Task):
            stack.extend((child, depth + 1) for _, child in _task_children(node))
        else:
            raise TypeError("unknown AST node")



@dataclass(frozen=True, slots=True)
class TypedProgram:
    types: Mapping[str, str]
    adjacency: Mapping[tuple, tuple]
    boundary_types: Mapping[str, tuple]
    def to_dict(self):
        return graph_to_dict(self)

@dataclass(frozen=True, slots=True)
class SourceReference(TypedProgram):
    outputs: tuple
    source_steps: int
    final_active_pairs: int
    rule_trace: list
    def rule_census(self):
        return dict(Counter(record["rule"] for record in self.rule_trace))

class _Builder:
    def __init__(self):
        self.types = {}
        self.adjacency = {}
        self.boundary_types = {}
        self.owners = {}

    def cell(self, kind, name, owner):
        if kind not in AR:
            raise ValueError("unknown source symbol")
        if not isinstance(name, str) or not name or name == "F":
            raise ValueError("invalid source cell name")
        if name in self.types:
            raise ValueError("duplicate source cell name")
        self.types[name] = kind
        for port in range(AR[kind] + 1):
            self.adjacency[(name, port)] = None
        self.owners[name] = owner
        return name

    def link(self, left, right):
        if left not in self.adjacency or right not in self.adjacency:
            raise ValueError("link endpoint is absent")
        if self.adjacency[left] is not None or self.adjacency[right] is not None:
            raise ValueError("source wire endpoint is already used")
        if left == right:
            raise ValueError("source wire cannot connect an endpoint to itself")
        self.adjacency[left] = right
        self.adjacency[right] = left

    def boundary(self, label, direction, semantic):
        if not isinstance(label, str) or not label:
            raise ValueError("boundary label must be a nonempty string")
        if label in self.boundary_types:
            raise ValueError("duplicate boundary")
        endpoint = ("F", label)
        self.adjacency[endpoint] = None
        self.boundary_types[label] = (direction, semantic)
        return endpoint

    def unary(self, value, prefix, owner):
        count = nat_value(value)
        if count == 0:
            name = self.cell("Z", prefix + "Z", owner)
            return (name, 0)
        names = [self.cell("S", prefix + "S" + str(index), owner) for index in range(count)]
        terminal = self.cell("Z", prefix + "Z", owner)
        for index, name in enumerate(names):
            child = (names[index + 1], 0) if index + 1 < len(names) else (terminal, 0)
            self.link((name, 1), child)
        return (names[0], 0)

    def finish(self):
        validate_source_graph(self.types, self.adjacency, self.boundary_types)
        return TypedProgram(
            MappingProxyType(dict(self.types)),
            MappingProxyType(dict(self.adjacency)),
            MappingProxyType(dict(self.boundary_types)),
        )

def _build_task(task, builder, namespace, owner):
    if isinstance(task, Check):
        init = builder.cell("INIT", namespace + "check.INIT", owner)
        value = builder.unary(task.n, namespace + "check.n.", owner)
        builder.link(value, (init, 0))
        output = builder.boundary(namespace + "O", *PORTS["INIT"][1])
        builder.link((init, 1), output)
        return
    if isinstance(task, Copy):
        dup = builder.cell("DUP", namespace + "copy.DUP", owner)
        value = builder.unary(task.n, namespace + "copy.n.", owner)
        builder.link(value, (dup, 0))
        for index, port in enumerate((1, 2)):
            boundary = builder.boundary(namespace + "N" + str(index), *PORTS["DUP"][port])
            builder.link((dup, port), boundary)
        return
    if isinstance(task, Erase):
        era = builder.cell("ERA", namespace + "erase.ERA", owner)
        value = builder.unary(task.n, namespace + "erase.n.", owner)
        builder.link(value, (era, 0))
        return
    if isinstance(task, Compare):
        cmp_cell = builder.cell("CMP", namespace + "compare.CMP", owner)
        left = builder.unary(task.n, namespace + "compare.n.", owner)
        right = builder.unary(task.m, namespace + "compare.m.", owner)
        builder.link(left, (cmp_cell, 0))
        builder.link(right, (cmp_cell, 1))
        for label, port in (("T", 2), ("N", 3)):
            boundary = builder.boundary(namespace + label, *PORTS["CMP"][port])
            builder.link((cmp_cell, port), boundary)
        return
    if isinstance(task, Fanout):
        dup = builder.cell("DUP", namespace + "fanout.DUP", owner)
        value = builder.unary(task.n, namespace + "fanout.n.", owner)
        builder.link(value, (dup, 0))
        for side, choice in (("left", task.left), ("right", task.right)):
            port = 1 if side == "left" else 2
            if choice == "check":
                init = builder.cell("INIT", namespace + "fanout." + side + ".INIT", owner)
                builder.link((dup, port), (init, 0))
                boundary = builder.boundary(namespace + side + ".O", *PORTS["INIT"][1])
                builder.link((init, 1), boundary)
            else:
                era = builder.cell("ERA", namespace + "fanout." + side + ".ERA", owner)
                builder.link((dup, port), (era, 0))
        return
    if isinstance(task, Parallel):
        for index, child in enumerate(task.tasks):
            child_owner = "part-" + str(index) if owner == "root" else owner
            _build_task(child, builder, namespace + str(index) + ".", child_owner)
        return
    raise TypeError("unknown task")

def _build_with_owners(task):
    validate_ast(task)
    builder = _Builder()
    _build_task(task, builder, "", "root")
    program = builder.finish()
    if set(builder.owners) != set(program.types):
        raise AssertionError("owner index does not cover every source cell")
    return program, builder.owners

def build_program(task):
    """Build a complete typed source matching without consulting semantics."""
    return _build_with_owners(task)[0]

def cell_owners(task):
    """Return an owner for every cell name in build_program(task).types."""
    return dict(_build_with_owners(task)[1])

def validate_source_graph(types, adjacency, boundary_types):
    if not isinstance(types, Mapping) or not isinstance(adjacency, Mapping) or not isinstance(boundary_types, Mapping):
        raise TypeError("source graph components must be mappings")
    expected_cell_ports = set()
    for name, kind in types.items():
        if not isinstance(name, str) or not name or name == "F":
            raise ValueError("source cell names must be nonempty and must not reserve F")
        if kind not in AR:
            raise ValueError("unknown source symbol")
        for port in range(AR[kind] + 1):
            endpoint = (name, port)
            if endpoint in expected_cell_ports:
                raise ValueError("duplicate cell port")
            expected_cell_ports.add(endpoint)
    external = {endpoint for endpoint in adjacency if endpoint[0] not in types}
    for endpoint in external:
        if len(endpoint) != 2 or endpoint[0] != "F" or not isinstance(endpoint[1], str) or not endpoint[1]:
            raise ValueError("malformed external endpoint")
    if set(adjacency) != expected_cell_ports | external:
        raise ValueError("source graph has missing or extra cell ports")
    if set(boundary_types) != {endpoint[1] for endpoint in external}:
        raise ValueError("boundary type labels do not match external endpoints")
    for label, boundary_type in boundary_types.items():
        if not isinstance(boundary_type, tuple) or len(boundary_type) != 2:
            raise ValueError("boundary type must be a 2-tuple")
        if boundary_type[0] not in ("in", "out") or boundary_type[1] not in ("N", "O", "T"):
            raise ValueError("malformed boundary type")
    for endpoint, other in adjacency.items():
        if not isinstance(endpoint, tuple) or len(endpoint) != 2:
            raise ValueError("malformed source endpoint")
        if not isinstance(other, tuple) or len(other) != 2:
            raise ValueError("malformed source wire endpoint")
        if endpoint == other:
            raise ValueError("source endpoint cannot be wired to itself")
        if other not in adjacency or adjacency[other] != endpoint:
            raise ValueError("source wire is not a reciprocal matching")
        if endpoint[0] in types:
            name, port = endpoint
            if type(port) is not int or not 0 <= port <= AR[types[name]]:
                raise ValueError("cell port out of range")
        else:
            if other[0] in types:
                expected = boundary_types[endpoint[1]]
                actual = PORTS[types[other[0]]][other[1]]
                if expected != actual:
                    raise ValueError("boundary type mismatch")
            else:
                raise ValueError("boundary-to-boundary wires are not admitted")
        if endpoint[0] in types and other[0] in types:
            local_type = PORTS[types[endpoint[0]]][endpoint[1]]
            remote_type = PORTS[types[other[0]]][other[1]]
            same_direction = local_type[0] == remote_type[0]
            principal_pair = endpoint[1] == 0 and other[1] == 0
            if local_type[1] != remote_type[1] or (same_direction and not principal_pair):
                raise ValueError("internal source wire has incompatible polarity or type")
            if principal_pair and same_direction:
                raise ValueError("principal pair must connect opposite polarities")



def clone_source_graph(program):
    return dict(program.types), dict(program.adjacency), dict(program.boundary_types)

def _canonical_rule_name(kinds):
    spec = RULES[frozenset(kinds)]
    return spec[0] + "-" + spec[1]

def source_reference(task):
    """Normalize a fresh source clone using only the existing source evaluator."""
    types, adjacency, boundary_types = clone_source_graph(build_program(task))
    steps = 0
    rule_trace = []
    while True:
        pairs = source_active_pairs(types, adjacency)
        if not pairs:
            break
        u, v = pairs[0]
        rule_trace.append({
            "rule": _canonical_rule_name((types[u], types[v])),
            "before_symbols": dict(sorted(Counter(types.values()).items())),
        })
        source_apply(types, adjacency, u, v)
        validate_source_graph(types, adjacency, boundary_types)
        steps += 1
    final_active = len(source_active_pairs(types, adjacency))
    if final_active:
        raise AssertionError("source normalization ended with active pairs")
    outputs = decode_outputs(types, adjacency, boundary_types)
    return SourceReference(
        MappingProxyType(types),
        MappingProxyType(adjacency),
        MappingProxyType(boundary_types),
        tuple(outputs),
        steps,
        final_active,
        rule_trace,
    )

def decode_outputs(types, adjacency, boundary_types):
    validate_source_graph(types, adjacency, boundary_types)
    result = []
    for label, (_, semantic) in boundary_types.items():
        endpoint = ("F", label)
        neighbor = adjacency[endpoint]
        if neighbor[0] not in types:
            raise ValueError("output boundary is not attached to a source cell")
        name, port = neighbor
        kind = types[name]
        if semantic == "O":
            if port != 0 or kind not in ("SQ", "BR"):
                raise ValueError("bad O output")
            if kind == "SQ":
                result.append(("SQ", source_decode(types, adjacency, (name, 1))))
            else:
                result.append(("BR", source_decode(types, adjacency, (name, 1)),
                               source_decode(types, adjacency, (name, 2))))
        elif semantic == "T":
            if port != 0 or kind not in ("EQ", "GT", "LT"):
                raise ValueError("bad T output")
            result.append((kind,))
        elif semantic == "N":
            result.append(source_decode(types, adjacency, endpoint))
        else:
            raise ValueError("unknown semantic output type")
    return tuple(result)

def _check_output(n):
    root = isqrt(n)
    if root * root == n:
        return (("SQ", root),)
    return (("BR", root, root + 1),)

def expected_outputs(task):
    if isinstance(task, Check):
        return _check_output(nat_value(task.n))
    if isinstance(task, Copy):
        value = nat_value(task.n)
        return (value, value)
    if isinstance(task, Erase):
        return ()
    if isinstance(task, Compare):
        n, m = nat_value(task.n), nat_value(task.m)
        tag = "EQ" if n == m else "GT" if n > m else "LT"
        return ((tag,), abs(n - m))
    if isinstance(task, Fanout):
        result = []
        for side in ("left", "right"):
            if getattr(task, side) == "check":
                result.extend(_check_output(nat_value(task.n)))
        return tuple(result)
    if isinstance(task, Parallel):
        result = []
        for child in task.tasks:
            result.extend(expected_outputs(child))
        return tuple(result)
    raise TypeError("unknown task")

def expected_diagram(task):
    """Independently construct the mathematical normal-form source diagram."""
    program = build_program(task)
    outputs = expected_outputs(task)
    if len(outputs) != len(program.boundary_types):
        raise AssertionError("expected output arity differs from boundary arity")
    builder = _Builder()
    for (label, boundary_type), output in zip(program.boundary_types.items(), outputs):
        semantic = boundary_type[1]
        prefix = "expected." + label.replace(".", "_") + "."
        endpoint = builder.boundary(label, *boundary_type)
        if semantic == "O":
            if output[0] not in ("SQ", "BR"):
                raise ValueError("bad expected O output")
            root = builder.cell(output[0], prefix + output[0], "expected")
            builder.link((root, 0), endpoint)
            for port, value in enumerate(output[1:], 1):
                builder.link(builder.unary(nat(value), prefix + "arg" + str(port) + ".", "expected"), (root, port))
        elif semantic == "T":
            if len(output) != 1 or output[0] not in ("EQ", "GT", "LT"):
                raise ValueError("bad expected T output")
            root = builder.cell(output[0], prefix + output[0], "expected")
            builder.link((root, 0), endpoint)
        elif semantic == "N":
            if type(output) is not int:
                raise ValueError("bad expected N output")
            builder.link(builder.unary(nat(output), prefix + "N.", "expected"), endpoint)
        else:
            raise ValueError("unknown semantic output type")
    return builder.finish()

def compare_source_graph(left, right):
    """Labeled-boundary source port-graph isomorphism for normal forms."""
    if not isinstance(left, TypedProgram) or not isinstance(right, TypedProgram):
        raise TypeError("compare_source_graph expects TypedProgram instances")
    if dict(left.boundary_types) != dict(right.boundary_types):
        return False
    if len(left.types) != len(right.types) or len(left.adjacency) != len(right.adjacency):
        return False
    cell_map = {}
    mapped_right = set()
    queue = []
    for label in left.boundary_types:
        left_endpoint = ("F", label)
        right_endpoint = ("F", label)
        left_neighbor = left.adjacency[left_endpoint]
        right_neighbor = right.adjacency[right_endpoint]
        if left_neighbor[0] == "F" or right_neighbor[0] == "F":
            if left_neighbor != right_neighbor:
                return False
            continue
        left_cell, left_port = left_neighbor
        right_cell, right_port = right_neighbor
        if left_port != right_port or left.types[left_cell] != right.types[right_cell]:
            return False
        if left_cell in cell_map:
            if cell_map[left_cell] != right_cell:
                return False
        else:
            if right_cell in mapped_right:
                return False
            cell_map[left_cell] = right_cell
            mapped_right.add(right_cell)
            queue.append((left_cell, right_cell))
    while queue:
        left_cell, right_cell = queue.pop()
        if left.types[left_cell] != right.types[right_cell]:
            return False
        for port in range(AR[left.types[left_cell]] + 1):
            left_endpoint = (left_cell, port)
            right_endpoint = (right_cell, port)
            left_neighbor = left.adjacency[left_endpoint]
            right_neighbor = right.adjacency[right_endpoint]
            if left_neighbor[0] == "F":
                if right_neighbor[0] != "F" or right_neighbor[1] != left_neighbor[1]:
                    return False
                continue
            if right_neighbor[0] == "F":
                return False
            if left_neighbor[1] != right_neighbor[1]:
                return False
            if left.types[left_neighbor[0]] != right.types[right_neighbor[0]]:
                return False
            if left_neighbor[0] in cell_map:
                if cell_map[left_neighbor[0]] != right_neighbor[0]:
                    return False
            else:
                if right_neighbor[0] in mapped_right:
                    return False
                cell_map[left_neighbor[0]] = right_neighbor[0]
                mapped_right.add(right_neighbor[0])
                queue.append((left_neighbor[0], right_neighbor[0]))
    return set(cell_map) == set(left.types) and set(mapped_right) == set(right.types)

def to_dict(value):
    if isinstance(value, Zero):
        return {"kind": "Nat", "constructor": "zero"}
    if isinstance(value, Succ):
        return {"kind": "Nat", "constructor": "succ", "pred": to_dict(value.pred)}
    if isinstance(value, Check):
        return {"kind": "Check", "n": to_dict(value.n)}
    if isinstance(value, Copy):
        return {"kind": "Copy", "n": to_dict(value.n)}
    if isinstance(value, Erase):
        return {"kind": "Erase", "n": to_dict(value.n)}
    if isinstance(value, Compare):
        return {"kind": "Compare", "n": to_dict(value.n), "m": to_dict(value.m)}
    if isinstance(value, Fanout):
        return {"kind": "Fanout", "n": to_dict(value.n), "left": value.left, "right": value.right}
    if isinstance(value, Parallel):
        return {"kind": "Parallel", "tasks": [to_dict(child) for child in value.tasks]}
    raise TypeError("cannot serialize AST node")

def _exact_keys(data, keys):
    if not isinstance(data, dict) or set(data) != keys:
        raise ValueError("expected object with exact keys " + repr(sorted(keys)))

def _serialization_preflight(data):
    nodes = 0
    stack = [(data, 1)]
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > MAX_SERIALIZATION_NODES:
            raise ValueError("serialized AST is too large")
        if depth > MAX_SERIALIZATION_DEPTH:
            raise ValueError("serialized AST is nested too deeply")
        if isinstance(value, dict):
            stack.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
    return nodes

def from_dict(data):
    _serialization_preflight(data)
    result = _from_dict(data)
    validate_ast(result)
    return result

def _from_dict(data):
    if not isinstance(data, dict):
        raise TypeError("AST node must be an object")
    kind = data.get("kind")
    if kind == "Nat":
        constructor = data.get("constructor")
        if constructor == "zero":
            _exact_keys(data, {"kind", "constructor"})
            return Zero()
        if constructor == "succ":
            _exact_keys(data, {"kind", "constructor", "pred"})
            return Succ(_from_dict(data["pred"]))
        raise ValueError("unknown Nat constructor")
    if kind == "Check":
        _exact_keys(data, {"kind", "n"})
        return Check(_from_nat_dict(data["n"]))
    if kind == "Copy":
        _exact_keys(data, {"kind", "n"})
        return Copy(_from_nat_dict(data["n"]))
    if kind == "Erase":
        _exact_keys(data, {"kind", "n"})
        return Erase(_from_nat_dict(data["n"]))
    if kind == "Compare":
        _exact_keys(data, {"kind", "n", "m"})
        return Compare(_from_nat_dict(data["n"]), _from_nat_dict(data["m"]))
    if kind == "Fanout":
        _exact_keys(data, {"kind", "n", "left", "right"})
        left, right = data["left"], data["right"]
        if not isinstance(left, str) or not isinstance(right, str):
            raise TypeError("Fanout consumers must be strings")
        if left not in FANOUT_CONSUMERS or right not in FANOUT_CONSUMERS:
            raise ValueError("Fanout consumers must be check or erase")
        return Fanout(_from_nat_dict(data["n"]), left, right)
    if kind == "Parallel":
        _exact_keys(data, {"kind", "tasks"})
        tasks = data["tasks"]
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= MAX_PARALLEL_TASKS:
            raise ValueError("Parallel tasks must be a nonempty bounded list")
        result = Parallel([_from_dict(child) for child in tasks])
        return result
    raise ValueError("unknown AST kind")

def _from_nat_dict(data):
    result = _from_dict(data)
    if not isinstance(result, Nat):
        raise TypeError("expected a Nat node")
    return result

def _endpoint_key(endpoint):
    if endpoint[0] == "F":
        return (1, endpoint[1], 0)
    return (0, endpoint[0], endpoint[1])

def graph_to_dict(program):
    if not isinstance(program, TypedProgram):
        raise TypeError("graph_to_dict expects TypedProgram")
    validate_source_graph(program.types, program.adjacency, program.boundary_types)
    wires = []
    seen = set()
    for endpoint, other in program.adjacency.items():
        if endpoint in seen:
            continue
        seen.update((endpoint, other))
        pair = ([list(endpoint), list(other)] if _endpoint_key(endpoint) <= _endpoint_key(other)
                else [list(other), list(endpoint)])
        wires.append(pair)
    wires.sort(key=lambda wire: (_endpoint_key(tuple(wire[0])), _endpoint_key(tuple(wire[1]))))
    return {
        "types": {name: program.types[name] for name in sorted(program.types)},
        "adjacency": wires,
        "boundary_types": {label: list(program.boundary_types[label]) for label in sorted(program.boundary_types)},
    }

def _graph_endpoint(data, types):
    if not isinstance(data, list) or len(data) != 2:
        raise ValueError("graph endpoint must be a two-element list")
    first, second = data
    if first == "F":
        if not isinstance(second, str) or not second:
            raise ValueError("boundary endpoint label must be a nonempty string")
        return ("F", second)
    if first not in types:
        raise ValueError("endpoint names an unknown source cell")
    if type(second) is not int or not 0 <= second <= AR[types[first]]:
        raise ValueError("cell endpoint port is malformed or out of range")
    return (first, second)

def graph_from_dict(data):
    _exact_keys(data, {"types", "adjacency", "boundary_types"})
    raw_types = data["types"]
    if not isinstance(raw_types, dict):
        raise TypeError("graph types must be an object")
    types = {}
    for name, kind in raw_types.items():
        if not isinstance(name, str) or not name or not isinstance(kind, str) or kind not in AR:
            raise ValueError("malformed source cell declaration")
        if name in types:
            raise ValueError("duplicate source cell")
        types[name] = kind
    raw_wires = data["adjacency"]
    if not isinstance(raw_wires, list):
        raise TypeError("graph adjacency must be a list")
    adjacency = {}
    for wire in raw_wires:
        if not isinstance(wire, list) or len(wire) != 2:
            raise ValueError("source wire must contain exactly two endpoints")
        left = _graph_endpoint(wire[0], types)
        right = _graph_endpoint(wire[1], types)
        if left == right:
            raise ValueError("source wire aliases one endpoint")
        for endpoint in (left, right):
            if endpoint in adjacency:
                raise ValueError("source wire endpoint is used more than once")
        adjacency[left] = right
        adjacency[right] = left
    raw_boundaries = data["boundary_types"]
    if not isinstance(raw_boundaries, dict):
        raise TypeError("boundary types must be an object")
    boundary_types = {}
    for label, value in raw_boundaries.items():
        if not isinstance(label, str) or not label or not isinstance(value, list) or len(value) != 2:
            raise ValueError("malformed boundary type")
        if value[0] not in ("in", "out") or value[1] not in ("N", "O", "T"):
            raise ValueError("malformed boundary direction or semantic type")
        boundary_types[label] = (value[0], value[1])
    validate_source_graph(types, adjacency, boundary_types)
    return TypedProgram(MappingProxyType(types), MappingProxyType(adjacency), MappingProxyType(boundary_types))

def root_dataset():
    """Fixed M3 integration dataset; no grammar cross-product is enumerated."""
    cases = [
        ("check-0", Check(0)), ("check-1", Check(1)), ("check-2", Check(2)),
        ("copy-0", Copy(0)), ("copy-2", Copy(2)),
        ("erase-2", Erase(2)),
        ("compare-0-0", Compare(0, 0)), ("compare-0-1", Compare(0, 1)),
        ("compare-1-0", Compare(1, 0)), ("compare-1-2", Compare(1, 2)),
        ("compare-1-1", Compare(1, 1)),
        ("fanout-1-check-erase", Fanout(1, "check", "erase")),
        ("fanout-0-check-check", Fanout(0, "check", "check")),
        ("parallel-check0-copy1", Parallel([Check(0), Copy(1)])),
    ]
    return [{"name": name, "ast": ast, "ast_dict": to_dict(ast)} for name, ast in cases]
