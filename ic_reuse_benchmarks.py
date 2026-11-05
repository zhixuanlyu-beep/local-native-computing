"""Finite M5 reuse-benchmark constructions.

All future tasks are prewired.  The three strategies share one literal source
packet, one native producer, the same task outputs, statuses, and source-reserve
disposition.  Constructors never reduce a network or evaluate a task contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ic_observation_contracts import TaskContract, value_spec
from ic_package_codec import validate_package
from ic_program_code_bridge import load_discovery
from ic_program_suspension import append_spec
from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec
from ic_structure_capsules import build_activation, build_capsule, build_unpack
from lafont_ic_macro_builder import build_M_star, macro_connect


STRATEGIES = ("literal", "native_fanout", "retained_chain")
DISPOSITIONS = ("retain1", "dispose_all")
MAX_TASKS = 4
CATEGORIES = (
    "source_value", "source_machinery", "dispatch_control", "task_literals",
    "copy_routers", "activation_machinery", "task_inputs", "task_consumers",
    "reserve_consumer",
)


def _cells(net, kind, count=1):
    if not isinstance(net, Net):
        raise TypeError("a primitive IC Net is required")
    if count < 1 or kind not in ("g", "d", "e"):
        raise ValueError("invalid primitive allocation request")
    return [net.cell(kind) for _ in range(count)]


def _loop(net):
    cell = _cells(net, "g", 1)[0]
    net.link((cell, 1), (cell, 2))
    return cell, 0


def _validate_data(spec):
    if not isinstance(spec, GraphSpec) or spec.boundaries != ("ROOT",):
        raise ValueError("native data must expose exactly ROOT")
    net = spec.instantiate()
    validate_package(net)
    if "d" in spec.kinds:
        raise ValueError("native code data must be delta-free")


def _open_boundary(net, label):
    endpoint = ("F", label)
    if endpoint not in net.adj:
        raise ValueError("unknown construction boundary")
    neighbor = net.adj.pop(endpoint)
    net.free.remove(endpoint)
    if neighbor is None:
        raise ValueError("construction boundary has no native connection")
    net.adj[neighbor] = None
    return neighbor


def _take(net, endpoint):
    if endpoint[0] == "F" and endpoint in net.adj:
        if net.adj.get(endpoint) is not None:
            return _open_boundary(net, endpoint[1])
    if endpoint not in net.adj or net.adj.get(endpoint) is not None:
        raise ValueError("expected a free composition endpoint")
    return endpoint


def _new(net, before):
    return set(net.nodes) - before


def _add(category, cells, label):
    if label not in CATEGORIES:
        raise ValueError("unknown initial-resource category")
    if not set(cells).isdisjoint(category):
        raise ValueError("initial allocation overlap in " + label)
    for cell in cells:
        category[cell] = label


def _bool_tuple(value, name="input vectors"):
    if not isinstance(value, tuple) or any(type(item) is not bool for item in value):
        raise ValueError(name + " must be a tuple of exact booleans")
    return value


def _task(workload):
    data = workload.get("task")
    if data is None:
        return None
    return TaskContract(data["name"], data["family"], tuple(data["input_reprs"]),
                        tuple(data["output_reprs"]), data["mask"])


def _validate_workload(workload, n):
    if not isinstance(workload, dict):
        raise TypeError("workload must be the root M5 workload mapping")
    for key in ("name", "component", "input_labels", "output_labels",
                "input_reprs", "output_reprs", "erase_ports"):
        if key not in workload:
            raise ValueError("workload lacks required field " + key)
    if not isinstance(workload["component"], GraphSpec):
        raise TypeError("workload component must be a GraphSpec")
    for key in ("input_labels", "output_labels", "input_reprs",
                "output_reprs", "erase_ports"):
        if not isinstance(workload[key], tuple):
            raise TypeError("workload " + key + " must be a tuple")
    capsule = workload.get("capsule")
    if not capsule:
        capsule = build_capsule(workload["component"])
    interface = tuple(capsule.interface)
    if tuple(workload["component"].boundaries) != interface:
        raise ValueError("capsule interface differs from the original component")
    if capsule.width != len(interface) + 1 or capsule.ready_slot != 0:
        raise ValueError("capsule does not use the declared READY-slot convention")
    if (len(workload["input_labels"]) != len(workload["input_reprs"]) or
            len(workload["output_labels"]) != len(workload["output_reprs"])):
        raise ValueError("workload labels and representations differ in length")
    if any(port not in interface for port in workload["erase_ports"]):
        raise ValueError("erase port is absent from the component interface")
    _task(workload)


def _fanout(net, targets):
    if not targets or len({repr(p) for p in targets}) != len(targets):
        raise ValueError("fanout needs distinct nonempty leaves")
    leaves = [_take(net, p) for p in targets]
    def tree(items):
        if len(items) == 1:
            return items[0]
        head = net.cell("d")
        middle = len(items) // 2
        net.link((head, 1), tree(items[:middle]))
        net.link((head, 2), tree(items[middle:]))
        return head, 0
    return tree(leaves)


def _gate(net, gate, serial, control, data, output_label):
    if (not isinstance(gate, GraphSpec) or set(gate.boundaries) != {"CTRL", "DATA", "OUT"}
            or gate.kinds != ("g",)):
        raise ValueError("invalid M1 gate interface")
    output = net.boundary(output_label)
    before = set(net.nodes)
    append_spec(gate, net, {"CTRL": _take(net, control), "DATA": _take(net, data), "OUT": output})
    ids = _new(net, before)
    if len(ids) != 1:
        raise ValueError("the protocol requires a one-cell gate")
    return _open_boundary(net, output_label), next(iter(ids))


@dataclass(frozen=True)
class BuiltProducer:
    net: Net
    source_ids: tuple[str, ...]
    producer_fan: str
    producer_eraser: str


@dataclass
class BuiltBenchmark:
    net: Net
    stages: list[dict[str, Any]]
    source_ids: tuple[str, ...]
    source_output: tuple[str, int]
    producer_fan: str
    producer_eraser: str
    common_unpack_head: str
    reserve_gate: str
    reserve_eraser: str | None
    initial_categories: dict[str, str]


def make_packet(code: GraphSpec) -> GraphSpec:
    """Return ROOT = gamma(code, GO Loop), without normalizing it."""
    _validate_data(code)
    net = Net()
    code_root = code.open_root(net)
    packet = _cells(net, "g", 1)[0]
    net.link((packet, 1), code_root)
    net.link((packet, 2), _loop(net))
    net.link((packet, 0), net.boundary("ROOT"))
    net.check()
    return GraphSpec.from_net(net)


def producer(packet: GraphSpec) -> BuiltProducer:
    """Build a native producer of the common encoded package."""
    _validate_data(packet)
    net = Net()
    before = set(net.nodes)
    packet_root = packet.open_root(net)
    source_ids = tuple(sorted(_new(net, before)))
    fan, eraser = _cells(net, "d", 1)[0], _cells(net, "e", 1)[0]
    net.link((fan, 0), packet_root)
    net.link((eraser, 0), (fan, 1))
    net.link((fan, 2), net.boundary("ROOT"))
    net.check()
    return BuiltProducer(net, source_ids, fan, eraser)


def _validate_common(packet, n, strategy, disposition, input_vectors, gate):
    _validate_data(packet)
    if type(n) is not int or not 1 <= n <= MAX_TASKS:
        raise ValueError("n must be an integer in 1..4")
    if strategy not in STRATEGIES:
        raise ValueError("unknown reuse strategy")
    if disposition not in DISPOSITIONS:
        raise ValueError("unknown source-reserve disposition")
    if not isinstance(input_vectors, tuple) or len(input_vectors) != n:
        raise ValueError("input_vectors must be a tuple of n task tuples")
    for bits in input_vectors:
        _bool_tuple(bits, "each task input tuple")
    if not isinstance(gate, GraphSpec):
        raise TypeError("gate must be a GraphSpec")


def build_benchmark(workload, packet, n, strategy, disposition,
                    input_vectors, gate=None) -> BuiltBenchmark:
    """Construct the whole experiment before any native interaction."""
    if gate is None:
        gate = load_discovery()[1][0][0]
    _validate_workload(workload, n)
    _validate_common(packet, n, strategy, disposition, input_vectors, gate)
    if any(len(bits) != len(workload["input_labels"]) for bits in input_vectors):
        raise ValueError("task input width differs from the workload interface")
    capsule = workload.get("capsule") or build_capsule(workload["component"])
    interface = tuple(capsule.interface)
    if capsule.component != workload["component"]:
        raise ValueError("capsule contains a different component")
    labels = workload["input_labels"] + workload["output_labels"] + workload["erase_ports"]
    if len(set(labels)) != len(labels) or set(labels) != set(interface):
        raise ValueError("functional ports must partition the original interface")
    if any(rep not in ("A", "B") for rep in workload["input_reprs"] + workload["output_reprs"]):
        raise ValueError("unsupported workload representation")
    net, category = Net(), {}
    before = set(net.nodes)
    packet_root = packet.open_root(net)
    source_ids = tuple(sorted(_new(net, before)))
    _add(category, source_ids, "source_value")
    fan, eraser = net.cell("d"), net.cell("e")
    net.link((fan, 0), packet_root)
    net.link((eraser, 0), (fan, 1))
    _add(category, (fan, eraser), "source_machinery")
    before = set(net.nodes)
    common_unpack = build_M_star(net, 2)
    net.link((fan, 2), common_unpack.principal)
    _add(category, _new(net, before), "source_machinery")
    code_slot, go_slot = common_unpack.auxiliaries

    reserve_data = net.boundary("RESERVE-DATA")
    reserve_ctrl = net.boundary("RESERVE-CTRL")
    before = set(net.nodes)
    reserve_output, reserve_gate = _gate(net, gate, n, reserve_ctrl, reserve_data, "RESERVE-OUT")
    _add(category, _new(net, before), "reserve_consumer")
    if disposition == "retain1":
        macro_connect(net, reserve_output, net.boundary("RESERVE"))
        reserve_eraser = None
    else:
        reserve_eraser = net.cell("e")
        net.link((reserve_eraser, 0), reserve_output)
        _add(category, (reserve_eraser,), "reserve_consumer")
    task_data = [net.boundary(f"TASK-{i}-DATA") for i in range(n)]
    task_ctrl = [net.boundary(f"TASK-{i}-CTRL") for i in range(n)]
    before = set(net.nodes)
    gates = [_gate(net, gate, i, task_ctrl[i], task_data[i], f"TASK-{i}-GATE-OUT") for i in range(n)]
    _add(category, _new(net, before), "dispatch_control")
    macro_connect(net, go_slot, task_ctrl[0])
    if strategy == "native_fanout":
        before = set(net.nodes)
        root = _fanout(net, [*task_data, reserve_data])
        _add(category, _new(net, before), "copy_routers")
        macro_connect(net, code_slot, root)
    elif strategy == "retained_chain":
        macro_connect(net, code_slot, task_data[0])
    else:
        macro_connect(net, code_slot, reserve_data)

    stages = []
    for index, ((gate_output, gate_id), bits) in enumerate(zip(gates, input_vectors)):
        holes = {label: net.boundary(f"TASK-{index}::{label}") for label in interface}
        ready_hole = net.boundary(f"TASK-{index}-READY")
        copy_head = None
        if strategy == "literal":
            before = set(net.nodes)
            package_root = capsule.package.open_root(net)
            _add(category, _new(net, before), "task_literals")
            macro_connect(net, package_root, task_data[index])
            activation_input = gate_output
        elif strategy == "retained_chain":
            copy_head = net.cell("d")
            _add(category, (copy_head,), "copy_routers")
            net.link(gate_output, (copy_head, 0))
            activation_input = (copy_head, 1)
            next_data = reserve_data if index + 1 == n else task_data[index + 1]
            macro_connect(net, (copy_head, 2), next_data)
        else:
            activation_input = gate_output
        before = set(net.nodes)
        constructor = build_unpack if strategy == "literal" else build_activation
        metadata = constructor(net, capsule.width, activation_input,
                               tuple(holes[label] for label in interface), ready_hole)
        _add(category, _new(net, before), "activation_machinery")
        ready_fork = net.cell("d")
        _add(category, (ready_fork,), "dispatch_control")
        macro_connect(net, ready_hole, (ready_fork, 0))
        net.link((ready_fork, 1), net.boundary(f"STATUS_{index}"))
        next_control = reserve_ctrl if index + 1 == n else task_ctrl[index + 1]
        macro_connect(net, (ready_fork, 2), next_control)
        task_erasers = []
        for label in workload["erase_ports"]:
            task_eraser = net.cell("e")
            _add(category, (task_eraser,), "task_consumers")
            macro_connect(net, (task_eraser, 0), holes[label])
            task_erasers.append(task_eraser)
        for label, representation, bit in zip(workload["input_labels"], workload["input_reprs"], bits):
            before = set(net.nodes)
            root = value_spec(representation, bit).open_root(net)
            _add(category, _new(net, before), "task_inputs")
            macro_connect(net, root, holes[label])
        for label in workload["output_labels"]:
            macro_connect(net, holes[label], net.boundary(f"TASK_{index}_{label}"))
        stages.append({"index": index, "grant_gate": gate_id, "copy_head": copy_head,
                       "decoder_head": metadata["decoder_head"], "unpack_head": metadata["unpack_head"],
                       "ready_fork": ready_fork, "task_erasers": task_erasers, "input_bits": list(bits)})
    net.check()
    if set(category) != set(net.nodes):
        raise AssertionError("initial resource categories must partition all cells")
    return BuiltBenchmark(net, stages, source_ids, common_unpack.principal, fan, eraser,
                          common_unpack.principal[0], reserve_gate, reserve_eraser, category)
