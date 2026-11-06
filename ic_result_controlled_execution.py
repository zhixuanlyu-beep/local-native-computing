"""M6: result-driven whole-program continuations in a single primitive IC net.

All numerical inputs and both continuations are wired offline. No constructor
or execution scheduler evaluates a source result or supplies per-task flags.
"""
from dataclasses import dataclass
from itertools import product

from ic_coherent_feedback import source_result_graph
from ic_native_control_packets import control_packet, build_control_reader
from ic_observation_contracts import value_spec
from ic_primitive_port_verifier import Net
from ic_program_suspension import suspend_feedback, build_activation
from ic_research_artifacts import GraphSpec
from ic_safe_program_activation import loop, take, gate_port, reference_result
from ic_structure_capsules import build_activation as activate_component
from lafont_ic_macro_builder import build_M, build_M_star, build_menu, macro_connect
from source_ic_coherent_compiler import CoherentICCompiler


MAX_INPUT, MAX_TASKS, UNARY_DEPTH = 4, 3, 5
BUDGET = {"max_steps": 2_000_000, "max_cells": 250_000}
SMALL_BUDGET = {"max_states": 4096, "max_transitions": 32768, "max_cells": 128}
DOMAIN = (0, 1, 2, 4)
POLICIES = (("fifo", None), ("lifo", None), ("seeded", 17))
CONTRACT = {
    "environment": "E_result_controlled-v1", "max_input": MAX_INPUT,
    "max_tasks": MAX_TASKS, "reader_depth": UNARY_DEPTH,
    "inputs": "first enabled; natural inputs and all connections prewired; no flags",
    "transition": "enabled SQ enables next; enabled BR skips next; skipped task emits epsilon and enables next",
    "control": "M3[Boolean A, S2 principal, S2 output]; progress M2[readiness Loop, control]",
    "program_supply": "compiler code_spec, one initial copy; native copies carried to tasks and retained LIBRARY",
    "component_supply": "actual M5 copy_A archive; native copy/erase producer, distribution, decoding and retention charged",
    "completion": "all original result unary constructors recognized; reconstruction and cleanup may overlap",
    "runtime": "only original primitive IC rules; fifo/lifo/splitmix64 seeded 17; separate staged witness",
    "terminal": "all TASK_i_OUT and STATUS_i, NEXT_ENABLE, exact LIBRARY and CONTROL_LIBRARY, DONE; no extras/cycles",
    "budget": BUDGET, "small_all_schedule_budget": SMALL_BUDGET,
    "scope": "fixed finite cases; no arbitrary-context or syntax-wide claim",
}


def cases():
    numbers = [(n,) for n in DOMAIN] + list(product(DOMAIN, repeat=2))
    numbers += [(0, 1, 4), (1, 2, 4), (2, 1, 0), (2, 4, 2)]
    return [{"name": "sequence-" + "-".join(map(str, ns)), "numbers": list(ns)} for ns in numbers]


def frame(net, endpoints):
    packet = build_M(net, len(endpoints))
    for endpoint, leaf in zip(endpoints, packet.auxiliaries):
        macro_connect(net, endpoint, leaf)
    return packet.principal


@dataclass
class BuiltResultSequence:
    net: Net
    stages: list
    program_ids: set
    source_ids: set
    library: object
    numbers: tuple
    stage_cells: list


def build_result_stage(net, number, incoming, copy_code, *, compiler, library,
                       index=0, reader_depth=UNARY_DEPTH):
    """Open local contract IN -> OUT, plus COPY_CODE and task observations."""
    before = set(net.nodes)
    gate = library.gate
    unpack = build_M_star(net, 3)
    macro_connect(net, incoming, unpack.principal)
    program_fan, go_fan = net.cell("d"), net.cell("d")
    macro_connect(net, unpack.auxiliaries[0], (program_fan, 0))
    macro_connect(net, unpack.auxiliaries[1], (go_fan, 0))
    control = build_M_star(net, 3)
    macro_connect(net, unpack.auxiliaries[2], control.principal)

    # These ports are filled by the *decoded archived* copy_A component.
    holes = {label: net.boundary(f"copy-{index}-{label}") for label in ("IN", "OUT1", "OUT2")}
    component_ready = net.boundary(f"copy-{index}-READY")
    capsule = library.workload["capsule"]
    width = capsule["width"] if isinstance(capsule, dict) else capsule.width
    interface = capsule["interface"] if isinstance(capsule, dict) else capsule.interface
    component_before = set(net.nodes)
    component_meta = activate_component(net, width, copy_code,
                                        tuple(holes[label] for label in interface), component_ready)
    component_meta["unpack_cells"] = [c for c in net.nodes if c not in component_before][:width - 1]
    component_ready_eraser = net.cell("e")
    macro_connect(net, component_ready, (component_ready_eraser, 0))
    component_meta["ready_consumer"] = component_ready_eraser
    macro_connect(net, control.auxiliaries[0], holes["IN"])
    macro_connect(net, holes["OUT1"], net.boundary(f"STATUS_{index}"))
    suspension = suspend_feedback(compiler, number)
    flagged, flag_gate = gate_port(net, gate, holes["OUT2"], suspension.code.open_root(net))
    delivered, delivery_id = gate_port(net, gate, (go_fan, 1), flagged)
    reader_progress = net.boundary(f"reader-progress-{index}")
    reader = build_control_reader(net, compiler, gate, reader_depth,
                                  value_out=net.boundary(f"TASK_{index}_OUT"), ready_out=reader_progress)
    build_activation(net, suspension.width, delivered, (program_fan, 1), reader.principal)
    skip_ready = loop(net)
    skip_progress = frame(net, [skip_ready, control_packet(True).open_root(net)])
    menu = build_menu(net, [take(net, reader_progress), skip_progress])
    macro_connect(net, control.auxiliaries[1], menu.principal)
    selected, progress_gate = gate_port(net, gate, (go_fan, 2), control.auxiliaries[2])
    progress = build_M_star(net, 2)
    macro_connect(net, selected, progress.principal)
    next_packet = frame(net, [(program_fan, 2), loop(net), progress.auxiliaries[1]])
    outgoing, advance_id = gate_port(net, gate, progress.auxiliaries[0], next_packet)
    metadata = {"index": index, "number": number,
                "grant_receiver": unpack.principal[0], "delivery_gate": delivery_id,
                "advance_gate": advance_id, "flag_gate": flag_gate,
                "progress_gate": progress_gate, "program_copy_fan": program_fan,
                "skip_ready": skip_ready[0], "reader": reader.metadata,
                "control_unpack": control.principal[0], "component": component_meta,
                "progress_unpack": progress.principal[0],
                "outgoing_packet": next_packet[0],
                "ready_menu": menu.principal[0]}
    return outgoing, metadata, [c for c in net.nodes if c not in before]


def finish(net, incoming, *, prefix=""):
    unpack = build_M_star(net, 3)
    macro_connect(net, incoming, unpack.principal)
    macro_connect(net, unpack.auxiliaries[0], net.boundary(prefix + "LIBRARY"))
    macro_connect(net, unpack.auxiliaries[1], net.boundary(prefix + "DONE"))
    control = build_M_star(net, 3)
    macro_connect(net, unpack.auxiliaries[2], control.principal)
    macro_connect(net, control.auxiliaries[0], net.boundary(prefix + "NEXT_ENABLE"))
    for endpoint in control.auxiliaries[1:]:
        macro_connect(net, endpoint, (net.cell("e"), 0))


def _library(library):
    from ic_result_controlled_library import load_control_library, ControlLibrary
    return library if isinstance(library, ControlLibrary) else load_control_library(library)


def build_result_sequence(numbers, *, library, compiler=None, reader_depth=UNARY_DEPTH):
    numbers = tuple(numbers)
    if not 1 <= len(numbers) <= MAX_TASKS:
        raise ValueError("task count outside the fixed contract")
    if any(type(n) is not int or not 0 <= n <= MAX_INPUT for n in numbers):
        raise ValueError("input outside the fixed natural-number contract")
    if type(reader_depth) is not int or reader_depth < 0:
        raise ValueError("reader depth must be a nonnegative integer")
    library = _library(library)
    compiler = compiler or CoherentICCompiler()
    net = Net()
    before = set(net.nodes)
    program = library.program_code(compiler).open_root(net)
    program_ids = set(net.nodes) - before
    incoming = frame(net, [program, loop(net), control_packet(True).open_root(net)])
    incoming_packet = incoming[0]
    before = set(net.nodes)
    archive = library.copy_packet.open_root(net)
    source_ids = set(net.nodes) - before
    producer, eraser = net.cell("d"), net.cell("e")
    net.link(archive, (producer, 0))
    net.link((producer, 1), (eraser, 0))
    source_unpack = build_M_star(net, 2)
    macro_connect(net, (producer, 2), source_unpack.principal)
    macro_connect(net, source_unpack.auxiliaries[1], (net.cell("e"), 0))
    reserve = source_unpack.auxiliaries[0]
    stages, stage_cells = [], []
    for index, number in enumerate(numbers):
        router = net.cell("d")
        macro_connect(net, reserve, (router, 0))
        reserve = (router, 2)
        incoming, meta, cells = build_result_stage(net, number, incoming, (router, 1),
                                                   compiler=compiler, library=library,
                                                   index=index, reader_depth=reader_depth)
        stages.append(meta)
        meta["incoming_packet"] = incoming_packet
        incoming_packet = meta["outgoing_packet"]
        stage_cells.append(cells)
    macro_connect(net, reserve, net.boundary("CONTROL_LIBRARY"))
    finish(net, incoming)
    net.check()
    return BuiltResultSequence(net, stages, program_ids, source_ids, library, numbers, stage_cells)


def reference_states(numbers, first=True):
    """Independent source specification. Called only by evidence/targets."""
    enabled, states, results = first, [], []
    for number in numbers:
        states.append(enabled)
        result = reference_result(number) if enabled else None
        results.append(result)
        enabled = result[0] == "SQ" if result is not None else True
    return states, results, enabled


def expected(compiler, numbers, library, *, first=True):
    net = Net()
    states, results, next_enable = reference_states(numbers, first)
    for index, (enabled, result) in enumerate(zip(states, results)):
        if enabled:
            value = GraphSpec.from_net(compiler.compile(*source_result_graph(result)))
        else:
            value = value_spec("A", False)
        value.instantiate(net, {value.boundaries[0]: net.boundary(f"TASK_{index}_OUT")})
        value_spec("A", enabled).instantiate(net, {"ROOT": net.boundary(f"STATUS_{index}")})
    compiler.code_spec.instantiate(net, {"ROOT": net.boundary("LIBRARY")})
    capsule = library.workload["capsule"]
    code = GraphSpec.from_dict(capsule["code"]) if isinstance(capsule, dict) else capsule.code
    code.instantiate(net, {"ROOT": net.boundary("CONTROL_LIBRARY")})
    value_spec("A", next_enable).instantiate(net, {"ROOT": net.boundary("NEXT_ENABLE")})
    net.link(loop(net), net.boundary("DONE"))
    net.check()
    return net


if __name__ == "__main__":
    from ic_result_controlled_report import main
    main()
