"""Fixed-DAG builders for frozen, independently verified IC components.

The builder is independent of search and source evaluation.  It receives a
role-indexed library of frozen component specs, instantiates all component
syntax before gluing, and appends input values only after those allocations.
Input values are supplied as literal GraphSpec material through the shared
observation-contract API; no TaskContract evaluator is called by construction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ic_package_codec import validate_package
from ic_coherent_feedback import spec_digest
from ic_primitive_port_verifier import Net
from ic_program_code_bridge import attach_consumer
from ic_research_artifacts import GraphSpec
from lafont_ic_macro_builder import macro_connect


ROLE_ORDER = (
    "copy_a", "and_left", "and_right", "and_join", "box_ab", "copy_b",
    "erase_b", "unbox_ba",
)

ROLE_CONTRACTS = {
    "copy_a": ("copy", ("A",), ("A", "A"), None),
    "and_left": ("binary", ("A", "A"), ("A",), 8),
    "and_right": ("binary", ("A", "A"), ("A",), 8),
    "and_join": ("binary", ("A", "A"), ("A",), 8),
    "box_ab": ("unary", ("A",), ("B",), 2),
    "copy_b": ("copy", ("B",), ("B", "B"), None),
    "erase_b": ("erase", ("B",), (), None),
    "unbox_ba": ("unary", ("B",), ("A",), 2),
}
LIBRARY_ROLES = {
    "copy_a": "copy_A",
    "and_left": "and_A",
    "and_right": "and_A",
    "and_join": "and_A",
    "box_ab": "box_AB",
    "copy_b": "copy_B",
    "erase_b": "erase_B",
    "unbox_ba": "unbox_BA",
}

INPUT_REFS = {
    "copy_a": {"IN": ("input", "a")},
    "and_left": {"LEFT": ("stage", "copy_a", "OUT1"),
                 "RIGHT": ("input", "b")},
    "and_right": {"LEFT": ("stage", "copy_a", "OUT2"),
                  "RIGHT": ("input", "c")},
    "and_join": {"LEFT": ("stage", "and_left", "OUT"),
                 "RIGHT": ("stage", "and_right", "OUT")},
    "box_ab": {"IN": ("stage", "and_join", "OUT")},
    "copy_b": {"IN": ("stage", "box_ab", "OUT")},
    "erase_b": {"IN": ("stage", "copy_b", "OUT1")},
    "unbox_ba": {"IN": ("stage", "copy_b", "OUT2")},
}

STAGE_OUTPUTS = {
    "copy_a": ("OUT1", "OUT2"),
    "and_left": ("OUT",),
    "and_right": ("OUT",),
    "and_join": ("OUT",),
    "box_ab": ("OUT",),
    "copy_b": ("OUT1", "OUT2"),
    "erase_b": (),
    "unbox_ba": ("OUT",),
}

INPUT_NAMES = ("a", "b", "c")
INPUT_TYPES = {"a": "A", "b": "A", "c": "A"}
FINAL_OUTPUTS = {"unbox_ba": "OUT"}
REQUIRED_ROLES = ROLE_ORDER


def _observation_contracts():
    """Return the shared ic_observation_contracts module if present."""
    try:
        import ic_observation_contracts
    except ImportError:
        return None
    return ic_observation_contracts


def task_interface(task: Any) -> tuple[str, ...]:
    """Return a TaskContract's fixed ordered interface labels."""
    if isinstance(task, str):
        module = _observation_contracts()
        if module is None or not hasattr(module, "contracts"):
            raise ValueError(
                "a string task cannot be resolved while ic_observation_contracts is absent"
            )
        contracts = module.contracts()
        for candidate in contracts if isinstance(contracts, (list, tuple)) else contracts:
            if getattr(candidate, "name", None) == task:
                task = candidate
                break
        else:
            raise ValueError(f"unknown shared task name: {task}")
    interface = getattr(task, "interface", None)
    if not isinstance(interface, tuple) or not interface or any(
            not isinstance(label, str) or not label for label in interface):
        raise ValueError("TaskContract.interface must be a nonempty tuple of labels")
    if len(set(interface)) != len(interface):
        raise ValueError(f"TaskContract.interface contains duplicates: {interface!r}")
    return interface


def _component_fields(entry: Mapping[str, Any]) -> tuple[Any, GraphSpec, str]:
    if not isinstance(entry, Mapping):
        raise TypeError("library entries must be mappings")
    task = entry.get("task")
    spec = entry.get("spec")
    candidate_id = entry.get("candidate_id")
    if task is None or not isinstance(spec, GraphSpec):
        raise ValueError("library entry requires task, spec, and candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id must be a nonempty string")
    if candidate_id != spec_digest(spec.to_dict()):
        raise ValueError("candidate fingerprint does not bind the supplied literal graph")
    interface = task_interface(task)
    if tuple(spec.boundaries) != interface:
        raise ValueError(
            f"component interface mismatch: spec={tuple(spec.boundaries)!r}, task={interface!r}"
        )
    return task, spec, candidate_id


def validate_library(library: Mapping[str, Mapping[str, Any]]) -> None:
    """Validate exactly the required role keys and component interfaces."""
    if not isinstance(library, Mapping):
        raise TypeError("library must be a mapping from role to component record")
    missing = set(LIBRARY_ROLES.values()) - set(library)
    extra = set(library) - set(LIBRARY_ROLES.values())
    if missing or extra:
        raise ValueError(f"library role mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
    for role, library_role in LIBRARY_ROLES.items():
        task, spec, _ = _component_fields(library[library_role])
        family = ROLE_CONTRACTS[role][0]
        input_reprs = ROLE_CONTRACTS[role][1]
        output_reprs = ROLE_CONTRACTS[role][2]
        mask = ROLE_CONTRACTS[role][3]
        actual = (
            getattr(task, "family", None),
            tuple(getattr(task, "input_reprs", ()) or ()),
            tuple(getattr(task, "output_reprs", ()) or ()),
            getattr(task, "mask", None),
        )
        expected = (family, input_reprs, output_reprs, mask)
        if actual != expected:
            raise ValueError(
                f"role {role} requires contract {expected!r}, got {actual!r}"
            )


def _ref_endpoint(ref: tuple[str, ...]) -> Any:
    kind = ref[0]
    if kind == "input":
        return ref[1]
    if kind == "stage":
        return (ref[1], ref[2])
    raise ValueError(f"unknown wiring reference: {ref!r}")


def _resolve_endpoint(
    ref: tuple[str, ...],
    stages: Mapping[str, Any],
    input_types: Mapping[str, str],
) -> Any:
    if not isinstance(ref, tuple) or len(ref) < 2:
        raise ValueError(f"wiring reference must be a tuple: {ref!r}")
    kind, name = ref[0], ref[1]
    if kind == "input":
        if len(ref) != 2 or name not in input_types:
            raise ValueError(f"unknown or malformed input reference: {ref!r}")
        return name
    if kind == "stage":
        if len(ref) != 3 or name not in stages:
            raise ValueError(f"unknown or malformed stage reference: {ref!r}")
        output = ref[2]
        if output not in stages[name]["outputs"]:
            raise ValueError(f"stage {name} has no output {output!r}")
        return (name, output)
    raise ValueError(f"unknown wiring reference kind: {kind!r}")


def _is_input_ref(ref: Any) -> bool:
    return isinstance(ref, tuple) and len(ref) == 2 and ref[0] == "input"


def _is_stage_ref(ref: Any) -> bool:
    return isinstance(ref, tuple) and len(ref) == 3 and ref[0] == "stage"


def validate_wiring(
    stages: Mapping[str, Any],
    input_types: Mapping[str, str],
    outputs: Mapping[str, str],
) -> None:
    """Validate the fixed dataflow DAG's types, linearity, and dependencies.

    Every declared stage must be present exactly once.  Input and output
    references must use the fixed interface labels.  Each input and each
    produced output is consumed at most once; a value needed twice must pass
    through an explicit copy component.  Stage dependencies must be acyclic.
    This is a structural wiring audit, not a semantic evaluation of tasks.
    """
    if not isinstance(stages, Mapping):
        raise TypeError("stages must be a mapping")
    if not isinstance(input_types, Mapping) or not isinstance(outputs, Mapping):
        raise TypeError("input_types and outputs must be mappings")
    if set(stages) != set(ROLE_ORDER):
        raise ValueError("stage names differ from the fixed program DAG")
    if set(input_types) != set(INPUT_NAMES):
        raise ValueError("program inputs must be exactly a, b, c")

    produced: dict[Any, str] = {name: kind for name, kind in input_types.items()}
    consumers: dict[Any, list[str]] = {name: [] for name in input_types}
    graph: dict[str, set[str]] = {}

    for role in ROLE_ORDER:
        stage = stages[role]
        if not isinstance(stage, Mapping):
            raise TypeError(f"stage {role} must be a mapping")
        task = stage.get("task")
        if task is None:
            raise ValueError(f"stage {role} lacks its TaskContract")
        descriptor = (getattr(task, "family", None), tuple(getattr(task, "input_reprs", ())),
                      tuple(getattr(task, "output_reprs", ())), getattr(task, "mask", None))
        if descriptor != ROLE_CONTRACTS[role]:
            raise ValueError(f"stage {role} has the wrong representation or truth contract")
        expected_inputs = tuple(INPUT_REFS[role])
        interface = task_interface(task)
        if interface != expected_inputs + STAGE_OUTPUTS[role]:
            raise ValueError(
                f"stage {role} interface {interface!r} does not match fixed DAG wiring"
            )
        refs = stage.get("inputs")
        if not isinstance(refs, Mapping) or tuple(refs) != expected_inputs:
            raise ValueError(f"stage {role} inputs must be exactly {expected_inputs!r}")
        graph[role] = set()
        for position, label in enumerate(expected_inputs):
            ref = refs[label]
            endpoint = _resolve_endpoint(ref, stages, input_types)
            repr_type = produced.get(endpoint)
            if repr_type is None:
                raise ValueError(f"stage {role}.{label} consumes an unknown source: {ref!r}")
            required = task.input_reprs[position]
            if repr_type != required:
                raise ValueError(
                    f"stage {role}.{label} expects {required}, got {repr_type}"
                )
            if len(consumers[endpoint]) >= 1:
                raise ValueError(f"linear wiring violation at {ref!r}")
            consumers[endpoint].append(f"{role}.{label}")
            if isinstance(endpoint, tuple):
                graph[role].add(endpoint[0])
        for output in STAGE_OUTPUTS[role]:
            endpoint = (role, output)
            if endpoint in produced:
                raise ValueError(f"duplicate produced endpoint: {endpoint!r}")
            produced[endpoint] = task.output_reprs[
                STAGE_OUTPUTS[role].index(output)
            ]
            consumers[endpoint] = []

    # A dependency cycle cannot be acyclic with topological consumption, but
    # reject it directly and with a stable message.
    remaining = set(ROLE_ORDER)
    while remaining:
        ready = {role for role in remaining if not (graph[role] & remaining)}
        if not ready:
            raise ValueError("stage wiring contains a dependency cycle")
        remaining -= ready

    final_refs = {
        (role, output)
        for role, output in outputs.items()
        if role in stages
    }
    if len(final_refs) != len(outputs) or set(outputs) - set(stages):
        raise ValueError("program outputs must name fixed stages")
    allowed_final = {(role, output) for role in ROLE_ORDER for output in STAGE_OUTPUTS[role]}
    if not final_refs <= allowed_final:
        raise ValueError("program outputs must reference fixed stage outputs")
    if any(consumers[endpoint] for endpoint in final_refs):
        raise ValueError("a program output is already consumed internally; use an explicit copier")
    unconsumed = [key for key, users in consumers.items() if not users]
    internal_unconsumed = [key for key in unconsumed if key not in final_refs]
    if internal_unconsumed:
        raise ValueError(f"unconsumed internal value: {internal_unconsumed!r}")
    # A program output is intentionally unconsumed by another stage.


@dataclass
class BuiltProgram:
    """A literal prewired program and its construction-time stage records."""

    net: Net
    stages: list[dict[str, Any]]
    input_ids: list[list[str]]
    program_ids: tuple[str, ...] = ()


def _stub_label(role: str, label: str) -> str:
    return f"{role}::{label}"


def _stage_ports(
    spec: GraphSpec, net: Net, role: str
) -> tuple[dict[str, Any], tuple[str, ...], dict[str, Any]]:
    """Instantiate a component with unique interface stubs and record cells."""
    ports = {}
    before = set(net.nodes)
    stubs = {
        label: net.boundary(_stub_label(role, label)) for label in spec.boundaries
    }
    # Instantiate against unique free target holes, then resolve those holes
    # to physical cell ports. GraphSpec.instantiate expects bindings keyed by
    # its own boundary labels and maps them to the supplied target endpoints.
    spec.instantiate(net, stubs)
    net.check()
    new_cells = tuple(sorted(set(net.nodes) - before, key=lambda name: int(name[1:])))
    if tuple(net.nodes[name] for name in new_cells) != spec.kinds:
        raise AssertionError("component cell allocation accounting mismatch")
    if len(new_cells) != len(spec.kinds):
        raise AssertionError("component cell count accounting mismatch")
    for label, stub in stubs.items():
        neighbor = net.adj.get(stub)
        if neighbor is None or neighbor[0] not in net.nodes:
            raise ValueError(
                f"interface label {label!r} in role {role!r} is not attached to a physical cell"
            )
        ports[label] = neighbor
    # Keep the stub boundary in place for now; it is removed only after all
    # components have been instantiated, preserving a complete matching.
    return ports, new_cells, stubs


def build_program(
    library: Mapping[str, Mapping[str, Any]],
    bits: tuple[bool, bool, bool],
) -> BuiltProgram:
    """Instantiate components, append literal inputs, and glue the fixed DAG."""
    validate_library(library)
    if not isinstance(bits, tuple) or len(bits) != 3 or any(type(bit) is not bool for bit in bits):
        raise ValueError("bits must be a tuple of exactly three Booleans")
    contracts = _observation_contracts()
    if contracts is None or not hasattr(contracts, "value_spec"):
        raise ImportError("ic_observation_contracts.value_spec is required")

    net = Net()
    stages: list[dict[str, Any]] = []
    stage_map: dict[str, dict[str, Any]] = {}
    all_stubs = {}
    for role, library_role in LIBRARY_ROLES.items():
        task, spec, candidate_id = _component_fields(library[library_role])
        ports, cells, stubs = _stage_ports(spec, net, role)
        for label, stub in stubs.items():
            all_stubs[(role, label)] = stub
        stage = {
            "name": role,
            "task": task,
            "spec": spec,
            "candidate_id": candidate_id,
            "cells": cells,
            "ports": ports,
            "inputs": dict(INPUT_REFS[role]),
        }
        stages.append(stage)
        stage_map[role] = stage

    # Enrich stage records with outputs before structural validation.
    for stage in stages:
        stage["outputs"] = STAGE_OUTPUTS[stage["name"]]
    validate_wiring(stage_map, INPUT_TYPES, FINAL_OUTPUTS)

    # All literal component syntax is now allocated.  Remove the interface
    # stubs and expose their physical neighbors for wiring.
    for role in ROLE_ORDER:
        stage = stage_map[role]
        for label, neighbor in stage["ports"].items():
            stub = all_stubs[(role, label)]
            net.adj.pop(stub)
            net.free.remove(stub)
            net.adj[neighbor] = None

    input_ids: list[list[str]] = []
    for name, bit in zip(INPUT_NAMES, bits):
        before = set(net.nodes)
        value = contracts.value_spec(INPUT_TYPES[name], bit).open_root(net)
        input_ids.append(sorted(set(net.nodes) - before, key=lambda n: int(n[1:])))
        for role in ROLE_ORDER:
            for label, ref in INPUT_REFS[role].items():
                if ref == ("input", name):
                    macro_connect(net, value, stage_map[role]["ports"][label])

    for consumer_role in ROLE_ORDER:
        for label, ref in INPUT_REFS[consumer_role].items():
            if not _is_stage_ref(ref):
                continue
            _, producer, output = ref
            macro_connect(
                net,
                stage_map[producer]["ports"][output],
                stage_map[consumer_role]["ports"][label],
            )

    # Program output is left as a physical free boundary for observation.
    final_role, final_label = next(iter(FINAL_OUTPUTS.items()))
    final_endpoint = stage_map[final_role]["ports"][final_label]
    final_boundary = net.boundary("OUT")
    macro_connect(net, final_endpoint, final_boundary)
    net.check()
    return BuiltProgram(
        net=net, stages=stages, input_ids=input_ids, program_ids=()
    )


def build_code_program(
    library: Mapping[str, Mapping[str, Any]],
    bits: tuple[bool, bool, bool],
    gate: GraphSpec,
    code_spec: GraphSpec,
) -> BuiltProgram:
    """Extend a small program with a frozen M1 gate and copy/decode consumer."""
    built = build_program(library, bits)
    if not isinstance(gate, GraphSpec) or set(gate.boundaries) != {"CTRL", "DATA", "OUT"}:
        raise ValueError("gate must expose exactly CTRL, DATA, OUT")
    if not isinstance(code_spec, GraphSpec) or code_spec.boundaries != ("ROOT",):
        raise ValueError("code_spec must expose exactly ROOT")
    validate_package(code_spec.instantiate())
    if any(kind not in ("g", "e") for kind in code_spec.kinds):
        raise ValueError("program code must be a delta-free principal package")

    net = built.net
    program_before = set(net.nodes)
    gate_stubs = {label: net.boundary(f"code_gate::{label}") for label in gate.boundaries}
    gate.instantiate(net, gate_stubs)
    gate_cells = tuple(sorted(set(net.nodes) - program_before, key=lambda n: int(n[1:])))
    if tuple(net.nodes[name] for name in gate_cells) != gate.kinds:
        raise AssertionError("gate cell allocation accounting mismatch")
    if len(gate_cells) != len(gate.kinds):
        raise AssertionError("gate cell count accounting mismatch")

    # The existing small-program output controls the gate.
    output_port = ("F", "OUT")
    output_neighbor = net.adj.pop(output_port)
    net.free.remove(output_port)
    net.adj[output_neighbor] = None
    macro_connect(net, output_neighbor, gate_stubs["CTRL"])

    code_before = set(net.nodes)
    code_root = code_spec.open_root(net)
    payload_ids = tuple(sorted(set(net.nodes) - code_before, key=lambda n: int(n[1:])))
    macro_connect(net, code_root, gate_stubs["DATA"])

    gate_out_stub = gate_stubs["OUT"]
    gate_out_neighbor = net.adj.pop(gate_out_stub)
    net.free.remove(gate_out_stub)
    net.adj[gate_out_neighbor] = None
    attach_consumer(net, gate_out_neighbor, "copy_decode")
    net.check()

    built.program_ids = payload_ids
    return built


__all__ = [
    "ROLE_ORDER", "ROLE_CONTRACTS", "LIBRARY_ROLES", "INPUT_REFS", "STAGE_OUTPUTS",
    "INPUT_NAMES", "FINAL_OUTPUTS", "INPUT_TYPES", "BuiltProgram",
    "build_program", "build_code_program", "validate_library",
    "validate_wiring", "task_interface",
]
