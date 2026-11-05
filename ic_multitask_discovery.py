"""M4 finite discovery from distinct Boolean, copying and adapter contracts.

The candidate syntax and observation environments are fixed before search.
Every syntax instance has a ledger entry. Native execution uses only the
original IC rules; reference functions and staged witness selection belong
to verification and never drive the joint native program runs.
"""
from collections import Counter
from itertools import product
import argparse
import hashlib
from pathlib import Path

from ic_coherent_feedback import read_json, write_json, spec_digest
from ic_component_candidates import candidate_specs, grammar_descriptor
from ic_composition_certificates import full_match
from ic_primitive_port_verifier import Net, RULES as PRIMITIVE_RULES
from ic_program_code_bridge import (load_discovery, build_bridge, expected as bridge_expected,
                                    check_schedules)
from ic_research_artifacts import GraphSpec
from ic_schedule_audit import Schedule, ScheduledNet, ScheduleTrace
from source_ic_coherent_compiler import CoherentICCompiler
from ic_observation_contracts import contracts, value_spec, build_observation, expected


ROOT = Path(__file__).parent
POLICIES = (Schedule("fifo"), Schedule("lifo"), Schedule("seeded", 17))
ELEMENT_BUDGET = {"max_steps": 128, "max_cells": 128}
EXPLORATION_BUDGET = {"max_states": 4096, "max_transitions": 32768, "max_cells": 128}
PROGRAM_BUDGET = {"max_steps": 4096, "max_cells": 256}
CODE_BUDGET = {"max_steps": 100000, "max_cells": 20000}
GRAMMARS = {"binary": (("LEFT", "RIGHT", "OUT"), 1),
            "unary": (("IN", "OUT"), 2),
            "copy": (("IN", "OUT1", "OUT2"), 1), "erase": (("IN",), 1)}
FROZEN = {
    "native_ic_research.json.gz": "6a13e33619aabd340e55ac57448e1e6efe3633767654ed2cd407b60941a7f71d",
    "program_code_bridge.json.gz": "624976b188e7659a52a32e92fcd1c46db95a18f639c41909ddaf17eaac29ecf7",
    "safe_program_activation.json.gz": "589c1a3e49411e8304d31ee2790eaab414dcb1ba5da1bb1d51183c1760efcb50",
    "composition_certificates.json.gz": "dab2c7cac04220b8d2719e8e2eb812d41a6d4ebf2fb0c98350736aa100e35a33",
}
CONTRACT = {
    "environment": "E_multitask-v1",
    "candidate_prior": "all complete labeled-port matchings in the declared cell bounds; no semantic wiring or connectivity filter",
    "representations": "A: epsilon/Loop; B: gamma(epsilon,A), with ordered auxiliaries",
    "tasks": "all binary Boolean functions on A; all unary Boolean functions across every ordered A/B pair; copy and erase on each representation",
    "screening": "first all-false input only; remaining fixed truth-table inputs refine the same contract",
    "element_budget": ELEMENT_BUDGET, "all_schedule_budget": EXPLORATION_BUDGET,
    "program_budget": PROGRAM_BUDGET, "code_budget": CODE_BUDGET,
    "policies": [p.to_dict() for p in POLICIES],
    "comparison": "complete independently constructed labeled port graphs, all components and closed wire cycles",
    "selection": "lowest literal candidate fingerprint for each required verified contract; every verified B eraser is a program variant",
    "program": "copy A input a; AND(a,b),AND(a,c); AND both; box A-to-B; copy B; erase first B; unbox second B",
    "compiler_consumer": "computed A output controls first frozen M1 gate and real !Gamma copy_decode consumer",
    "runtime": "one prewired net per case; primitive interactions only; no oracle, reset or host stage transition",
    "staged_verifier": "local discovered traces lifted through the fixed DAG with exact input footprints and fresh-cell renaming; not a runtime controller",
    "unknowns": "budget exhaustion is incomplete, never verified or an impossibility result; absence claims require all syntax rejected",
    "measurement": "symbolic initial and post-atomic-interaction cells, allocations and primitive-rule census; verification host cost is separate",
}


def _inventory():
    return {family: list(candidate_specs(interface, bound))
            for family, (interface, bound) in GRAMMARS.items()}


def inputs():
    if CONTRACT["policies"] != [p.to_dict() for p in POLICIES]:
        raise ValueError("runtime policies differ from the trace-bound contract")
    for name, digest in FROZEN.items():
        if hashlib.sha256((ROOT / "results" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("frozen prior evidence changed: " + name)
    compiler = CoherentICCompiler()
    discovery, pairs = load_discovery()
    if not full_match(value_spec("A", True).instantiate(), pairs[0][1].instantiate()):
        raise ValueError("M4 A representation differs from the frozen M1 true carrier")
    tasks, inventory = contracts(), _inventory()
    if len({task.name for task in tasks}) != len(tasks):
        raise ValueError("contract identifiers must be unique")
    bound = {"contract": CONTRACT, "contract_sha256": spec_digest(CONTRACT),
             "tasks": [t.to_dict() for t in tasks],
             "representations": {rep: {str(bit): value_spec(rep, bit).to_dict() for bit in (False, True)}
                                 for rep in ("A", "B")},
             "grammars": {family: grammar_descriptor(interface, cap)
                          for family, (interface, cap) in GRAMMARS.items()},
             "candidate_inventories": {family: {"count": len(candidates),
                 "ordered_fingerprints_sha256": spec_digest([c.fingerprint for c in candidates])}
                 for family, candidates in inventory.items()},
             "primitive_rules": [{"lhs": k, "cells": v[0], "wires": v[1]} for k, v in PRIMITIVE_RULES.items()],
             "frozen_reports": FROZEN, "discovery": discovery,
             "program_code_sha256": spec_digest(compiler.code_spec.to_dict()),
             "program_triples": [list(bits) for bits in product((False, True), repeat=3)]}
    return {"compiler": compiler, "pairs": pairs, "tasks": tasks,
            "inventory": inventory, "bindings": bound}


def observe(built, trace, *, max_steps=128, max_cells=128):
    """Observe one candidate without choosing or evaluating an output contract."""
    if any(type(v) is not int or v < 0 for v in (max_steps, max_cells)):
        raise ValueError("native evidence bounds must be non-negative integers")
    syntax = GraphSpec.from_net(built.net)
    running = syntax.instantiate(ScheduledNet(Schedule()))
    start, pairs, steps = trace.count, [], 0
    while True:
        if len(running.nodes) > max_cells:
            status = "resource-violation"
            break
        pair = running.next_active()
        if pair is None:
            status = "normal-form"
            break
        if steps >= max_steps:
            status = "incomplete"
            break
        trace.record(pair)
        pairs.append(pair)
        running.reduce(*pair)
        steps += 1
    final = GraphSpec.from_net(running).to_dict()
    record = {"status": status, "initial_graph": syntax.to_dict(),
              "initial_graph_sha256": spec_digest(syntax.to_dict()),
              "trace_offset_records": start, "primitive_interactions": steps,
              "terminal": not bool(running.active()), "final_graph": final,
              "final_graph_sha256": spec_digest(final), "resources": running.statistics()}
    renamed = dict(zip(built.net.nodes, ("c" + str(i) for i in range(len(built.net.nodes)))))
    witness = {"initial": syntax, "pairs": pairs, "record": record,
               "component_ids": [renamed[c] for c in built.component_ids],
               "input_ids": [[renamed[c] for c in ids] for ids in built.input_ids]}
    return record, witness


def _case_status(observation, target):
    if observation["status"] != "normal-form":
        return observation["status"]
    final = GraphSpec.from_dict(observation["final_graph"]).instantiate()
    return "matched" if full_match(final, target) else "wrong-normal-form"


def _counterexample(observation, observation_id, target, reason):
    return {"observation": observation_id, "reason": reason,
            "initial_graph_sha256": observation["initial_graph_sha256"],
            "expected_graph": GraphSpec.from_net(target).to_dict(),
            "actual_graph_sha256": observation["final_graph_sha256"],
            "trace_range": [observation["trace_offset_records"],
                            observation["trace_offset_records"] + observation["primitive_interactions"]]}


def discover(context, trace):
    """Complete syntax accounting and finite-input contract refinement."""
    observations, ledgers, explorations = [], {}, []
    witnesses, exploration_cache = {}, {}
    tasks = context["tasks"]
    for family, candidates in context["inventory"].items():
        family_tasks = [t for t in tasks if t.family == family]
        if not family_tasks:
            continue
        representations = sorted({t.input_reprs for t in family_tasks})
        rows = []
        for candidate in candidates:
            observation_ids = {}
            for reps in representations:
                for bits in product((False, True), repeat=len(reps)):
                    built = build_observation(family, candidate.spec, reps, bits)
                    observation, witness = observe(built, trace, **ELEMENT_BUDGET)
                    observation_id = len(observations)
                    observation.update({"id": observation_id, "family": family,
                                        "candidate_id": candidate.fingerprint,
                                        "input_reprs": list(reps), "bits": list(bits)})
                    observations.append(observation)
                    witnesses[observation_id] = witness
                    observation_ids[(reps, bits)] = observation_id
            outcomes = []
            for task in family_tasks:
                cases, targets = [], []
                for bits in task.inputs():
                    observation_id = observation_ids[(task.input_reprs, tuple(bits))]
                    target = expected(task, bits)
                    cases.append({"observation": observation_id,
                                  "status": _case_status(observations[observation_id], target),
                                  "expected_graph_sha256": spec_digest(GraphSpec.from_net(target).to_dict())})
                    targets.append(target)
                wrong = next((i for i, case in enumerate(cases) if case["status"] in
                              ("wrong-normal-form", "resource-violation")), None)
                unresolved = any(case["status"] == "incomplete" for case in cases)
                outcome = {"task": task.name, "screening": cases[0]["status"],
                           "cases": cases, "status": "rejected" if wrong is not None else
                           "incomplete" if unresolved else "fifo-compatible"}
                if wrong is not None:
                    case = cases[wrong]
                    oid = case["observation"]
                    outcome["counterexample"] = _counterexample(observations[oid], oid, targets[wrong], case["status"])
                elif not unresolved:
                    checks = []
                    for case, target in zip(cases, targets):
                        oid = case["observation"]
                        key = (oid, case["expected_graph_sha256"])
                        if key not in exploration_cache:
                            initial = GraphSpec.from_dict(observations[oid]["initial_graph"]).instantiate()
                            check = check_schedules(initial, target, **EXPLORATION_BUDGET)
                            check.update({"id": len(explorations), "observation": oid,
                                          "expected_graph_sha256": key[1]})
                            exploration_cache[key] = len(explorations)
                            explorations.append(check)
                        checks.append(exploration_cache[key])
                    outcome["all_schedule_checks"] = checks
                    failed = next((i for i in checks if explorations[i]["status"] not in ("passed", "incomplete")), None)
                    if failed is not None:
                        outcome.update({"status": "rejected", "schedule_counterexample": failed})
                    elif any(explorations[i]["status"] == "incomplete" for i in checks):
                        outcome["status"] = "incomplete"
                    else:
                        outcome["status"] = "verified"
                outcomes.append(outcome)
            rows.append({"index": candidate.index, "candidate_id": candidate.fingerprint,
                         "graph": candidate.spec.to_dict(), "outcomes": outcomes})
        ledgers[family] = rows
        print("SEARCH", family, "accounted", len(rows), flush=True)
    summaries = []
    for task in tasks:
        outcomes = [(row, next(o for o in row["outcomes"] if o["task"] == task.name))
                    for row in ledgers[task.family]]
        counts = Counter(o["status"] for _, o in outcomes)
        summaries.append({"task": task.name, "counts": dict(counts),
                          "screening_compatible": sum(o["screening"] == "matched" for _, o in outcomes),
                          "verified_candidates": [r["candidate_id"] for r, o in outcomes if o["status"] == "verified"],
                          "absence": ("none-verified-in-this-grammar" if not counts["verified"] and not counts["incomplete"]
                                      else "unresolved-candidates-remain" if not counts["verified"] else None)})
    return {"candidate_ledgers": ledgers, "observations": observations,
            "all_schedule_checks": explorations, "task_summaries": summaries}, witnesses


def select_library(context, discovery):
    queries = {"and_A": ("binary", ("A", "A"), ("A",), 8),
               "copy_A": ("copy", ("A",), ("A", "A"), None),
               "box_AB": ("unary", ("A",), ("B",), 2),
               "copy_B": ("copy", ("B",), ("B", "B"), None),
               "erase_B": ("erase", ("B",), (), None),
               "unbox_BA": ("unary", ("B",), ("A",), 2)}
    library, missing = {}, []
    for role, query in queries.items():
        task = next(t for t in context["tasks"] if (t.family, t.input_reprs, t.output_reprs, t.mask) == query)
        choices = []
        for row in discovery["candidate_ledgers"][task.family]:
            outcome = next(o for o in row["outcomes"] if o["task"] == task.name)
            if outcome["status"] == "verified":
                choices.append({"task": task, "candidate_id": row["candidate_id"],
                                "spec": GraphSpec.from_dict(row["graph"]),
                                "cases": {tuple(discovery["observations"][case["observation"]]["bits"]): case["observation"]
                                          for case in outcome["cases"]}})
        choices.sort(key=lambda c: c["candidate_id"])
        if not choices:
            missing.append(role)
        else:
            library[role] = choices[0]
            if role == "erase_B":
                library["erase_variants"] = choices
    return library, missing


class TraceTap:
    """Collect one verified witness while retaining the global raw interval."""
    def __init__(self, trace):
        self.trace, self.pairs = trace, []

    @property
    def count(self):
        return self.trace.count

    def record(self, pair):
        self.trace.record(pair)
        self.pairs.append(tuple(pair))


INPUT_LABELS = {"binary": ("LEFT", "RIGHT"), "unary": ("IN",),
                "copy": ("IN",), "erase": ("IN",)}
OUTPUT_LABELS = {"binary": ("OUT",), "unary": ("OUT",),
                 "copy": ("OUT1", "OUT2"), "erase": ()}


def small_expected(bits):
    if type(bits) is not tuple or len(bits) != 3 or any(type(bit) is not bool for bit in bits):
        raise ValueError("the program expects three Boolean inputs")
    net = Net()
    value_spec("A", all(bits)).instantiate(net, {"ROOT": net.boundary("OUT")})
    return net


def _endpoint(endpoint, rename):
    return (rename[endpoint[0]], endpoint[1]) if endpoint[0] != "F" else endpoint


def staged_program(built, library, bits, witnesses, trace):
    """Construct a literal primitive witness by composing discovered traces."""
    from ic_component_witnesses import match_value, lift_trace
    syntax = GraphSpec.from_net(built.net)
    actual = syntax.instantiate(ScheduledNet(Schedule("witness")))
    actual.begin_audit()
    rename = dict(zip(built.net.nodes, actual.nodes))
    values = {("input", name): bit for name, bit in zip(("a", "b", "c"), bits)}
    entries = [entry for key, entry in library.items() if key != "erase_variants"]
    tap, records, predicted = TraceTap(trace), [], Counter()
    start, status, reason = trace.count, "passed", None
    try:
        for stage in built.stages:
            task = stage["task"]
            entry = next(e for e in entries if e["candidate_id"] == stage["candidate_id"] and
                         e["task"].name == task.name)
            in_labels = INPUT_LABELS[task.family]
            stage_bits = tuple(values[tuple(stage["inputs"][label])] for label in in_labels)
            observation_id = entry["cases"][stage_bits]
            witness = witnesses[observation_id]
            local_map = dict(zip(witness["component_ids"], (rename[c] for c in stage["cells"])))
            for index, (label, rep, bit) in enumerate(zip(in_labels, task.input_reprs, stage_bits)):
                port = _endpoint(stage["ports"][label], rename)
                token_map = match_value(value_spec(rep, bit), actual, port)
                source_ids = witness["input_ids"][index]
                if len(source_ids) != len(token_map):
                    raise ValueError("input footprint differs from its discovered witness")
                for position, source_cell in enumerate(source_ids):
                    local_map[source_cell] = token_map["c" + str(position)]
            if len(set(local_map.values())) != len(local_map):
                raise ValueError("local component and input footprints overlap")
            bindings = {label: actual.adj[_endpoint(stage["ports"][label], rename)]
                        for label in OUTPUT_LABELS[task.family]}
            result = lift_trace(witness["initial"], actual, local_map, bindings,
                                witness["pairs"], tap,
                                max_steps=max(0, PROGRAM_BUDGET["max_steps"] - (trace.count - start)),
                                max_cells=PROGRAM_BUDGET["max_cells"])
            result.update({"stage": stage["name"], "task": task.name,
                           "candidate_id": stage["candidate_id"], "observation": observation_id,
                           "input_bits": list(stage_bits)})
            records.append(result)
            if result["status"] != "passed":
                status = result["status"]
                break
            reference = expected(task, stage_bits)
            if not full_match(GraphSpec.from_dict(result["reference_final_graph"]).instantiate(), reference):
                raise ValueError("lifted local trace differs from the independent contract result")
            resource = witness["record"]["resources"]
            if (result["reference_resources"]["rule_census"] != resource["rule_census"] or
                    result["reference_peak_live_cells"] != resource["peak_live_cells"]):
                raise ValueError("local witness resource ledger differs after lifting")
            predicted.update(resource["rule_census"])
            output_cells = set()
            for label, rep, bit in zip(OUTPUT_LABELS[task.family], task.output_reprs, task.evaluate(stage_bits)):
                token_map = match_value(value_spec(rep, bit), actual, bindings[label])
                if output_cells & set(token_map.values()):
                    raise ValueError("distinct output packages share cells")
                output_cells.update(token_map.values())
                values[("stage", stage["name"], label)] = bit
            if output_cells != set(result["renaming"].values()) or actual.cycles:
                raise ValueError("local completion left an extra cell or wire cycle")
    except (ValueError, AssertionError, KeyError, StopIteration) as error:
        status, reason = "proof-rejected", str(error)
    target = small_expected(bits)
    resources = actual.statistics()
    bound = max((r["context_cells"] + r["reference_peak_live_cells"] for r in records),
                default=len(built.net.nodes))
    if status == "passed" and (actual.active() or not full_match(actual, target)):
        status = "wrong-normal-form"
    if status == "passed" and (resources["rule_census"] != dict(predicted) or
                               resources["peak_live_cells"] != bound):
        status = "staged-resource-violation"
    final = GraphSpec.from_net(actual).to_dict()
    record = {"status": status, "input_bits": list(bits), "trace_offset_records": start,
              "primitive_interactions": trace.count - start, "initial_graph_sha256": spec_digest(syntax.to_dict()),
              "stages": records, "resources": resources, "constructive_staged_peak": bound,
              "final_graph": final, "final_graph_sha256": spec_digest(final),
              "whole_graph_matches_reference": full_match(actual, target), "terminal": not bool(actual.active()),
              "expected_graph_sha256": spec_digest(GraphSpec.from_net(target).to_dict())}
    if status != "passed":
        record["counterexample"] = {"reason": reason or status, "initial": syntax.to_dict(),
                                    "actual": final, "expected": GraphSpec.from_net(target).to_dict()}
    return record, {"initial": syntax, "pairs": tap.pairs, "record": record}


def run_joint(built, target, schedule, trace, *, predicted_census=None,
              max_steps=4096, max_cells=256):
    """Run a single prewired network without a host stage interpreter."""
    if any(type(v) is not int or v < 0 for v in (max_steps, max_cells)):
        raise ValueError("native evidence bounds must be non-negative integers")
    syntax = GraphSpec.from_net(built.net)
    actual = syntax.instantiate(ScheduledNet(schedule))
    rename = dict(zip(built.net.nodes, actual.nodes))
    payload = {rename[c] for c in getattr(built, "program_ids", ())}
    start, steps = trace.count, 0
    while True:
        if len(actual.nodes) > max_cells:
            status = "resource-violation"
            break
        pair = actual.next_active()
        if pair is None:
            status = "passed" if full_match(actual, target) else "wrong-normal-form"
            break
        if steps >= max_steps:
            status = "incomplete"
            break
        trace.record(pair)
        actual.reduce(*pair)
        steps += 1
    resources = actual.statistics()
    if status == "passed" and predicted_census is not None and resources["rule_census"] != predicted_census:
        status = "composed-cost-violation"
    if status == "passed" and payload & set(actual.nodes):
        status = "original-program-cells-survived"
    final = GraphSpec.from_net(actual).to_dict()
    record = {"status": status, "schedule": schedule.to_dict(), "trace_offset_records": start,
              "primitive_interactions": steps, "initial_graph_sha256": spec_digest(syntax.to_dict()),
              "resources": resources, "predicted_rule_census": predicted_census,
              "final_graph": final, "final_graph_sha256": spec_digest(final),
              "expected_graph_sha256": spec_digest(GraphSpec.from_net(target).to_dict()),
              "terminal": not bool(actual.active()), "whole_graph_matches_reference": full_match(actual, target),
              "initial_program_cells_consumed": not bool(payload & set(actual.nodes)) if payload else None}
    if status != "passed":
        record["counterexample"] = {"initial": syntax.to_dict(), "actual": final,
                                    "expected": GraphSpec.from_net(target).to_dict(), "reason": status}
    return record


def staged_code_program(built, small_witness, bridge_witness, bits, trace):
    from ic_component_witnesses import lift_trace, boundary_cell_map
    syntax = GraphSpec.from_net(built.net)
    actual = syntax.instantiate(ScheduledNet(Schedule("witness")))
    actual.begin_audit()
    tap, start, records = TraceTap(trace), trace.count, []
    status, reason = "passed", None
    small_initial = small_witness["initial"].instantiate()
    small_names = list(small_initial.nodes)
    initial_map = dict(zip(small_names, list(actual.nodes)[:len(small_names)]))
    output_port = small_initial.adj[("F", "OUT")]
    actual_port = (initial_map[output_port[0]], output_port[1])
    first_bindings = {"OUT": actual.adj[actual_port]}
    try:
        result = lift_trace(small_witness["initial"], actual, initial_map, first_bindings,
                            small_witness["pairs"], tap, **CODE_BUDGET)
        result["part"] = "discovered Boolean/adapter DAG"
        records.append(result)
        if result["status"] != "passed":
            status = result["status"]
        else:
            reference = bridge_witness["initial"].instantiate()
            initial_map = boundary_cell_map(reference, actual)
            bindings = {label: ("F", label) for _, label in reference.free}
            result = lift_trace(bridge_witness["initial"], actual, initial_map, bindings,
                                bridge_witness["pairs"], tap,
                                max_steps=max(0, CODE_BUDGET["max_steps"] - (trace.count - start)),
                                max_cells=CODE_BUDGET["max_cells"])
            result["part"] = "frozen M1 real-code consumer"
            records.append(result)
            status = result["status"]
    except (ValueError, AssertionError, KeyError) as error:
        status, reason = "proof-rejected", str(error)
    resources = actual.statistics()
    predicted = Counter(small_witness["record"]["resources"]["rule_census"])
    predicted.update(bridge_witness["record"]["resources"]["rule_census"])
    bound = max((r["context_cells"] + r["reference_peak_live_cells"] for r in records), default=len(actual.nodes))
    final = GraphSpec.from_net(actual).to_dict()
    record = {"status": status, "input_bits": list(bits), "trace_offset_records": start,
              "primitive_interactions": trace.count - start, "initial_graph_sha256": spec_digest(syntax.to_dict()),
              "parts": records, "resources": resources, "constructive_staged_peak": bound,
              "predicted_rule_census": dict(predicted), "final_graph": final,
              "final_graph_sha256": spec_digest(final), "terminal": not bool(actual.active())}
    if status == "passed" and (resources["rule_census"] != dict(predicted) or resources["peak_live_cells"] != bound):
        status = record["status"] = "staged-resource-violation"
    if status != "passed":
        record["counterexample"] = {"reason": reason or status, "initial": syntax.to_dict(), "actual": final}
    return record


def _library_record(library):
    return {role: {"task": entry["task"].name, "candidate_id": entry["candidate_id"],
                   "graph": entry["spec"].to_dict(),
                   "witness_cases": [{"bits": list(bits), "observation": oid}
                                     for bits, oid in entry["cases"].items()]}
            for role, entry in library.items() if role != "erase_variants"}


def _negative_boundaries(discovery, tasks):
    erase_a = next(t for t in tasks if t.family == "erase" and t.input_reprs == ("A",))
    erase_b = next(t for t in tasks if t.family == "erase" and t.input_reprs == ("B",))
    specific = []
    for row in discovery["candidate_ledgers"]["erase"]:
        by_task = {o["task"]: o for o in row["outcomes"]}
        if (by_task[erase_b.name]["status"] == "verified" and by_task[erase_a.name]["status"] == "rejected"
                and "counterexample" in by_task[erase_a.name]):
            specific.append((row, by_task[erase_a.name]))
    specific.sort(key=lambda item: item[0]["candidate_id"])
    representation = {"status": "not-refuted"}
    if specific:
        row, outcome = specific[0]
        representation = {"status": "refuted", "candidate_id": row["candidate_id"],
                          "valid_task": erase_b.name, "invalid_task": erase_a.name,
                          "counterexample": outcome.get("counterexample"),
                          "claim": "a component verified for B erasure can erase A without an adapter"}
    refinements = [(row, outcome) for rows in discovery["candidate_ledgers"].values() for row in rows
                   for outcome in row["outcomes"] if outcome["screening"] == "matched" and
                   outcome["status"] == "rejected" and "counterexample" in outcome]
    refinements.sort(key=lambda item: (item[0]["candidate_id"], item[1]["task"]))
    weak = {"status": "not-refuted"}
    if refinements:
        row, outcome = refinements[0]
        weak = {"status": "refuted", "candidate_id": row["candidate_id"], "task": outcome["task"],
                "counterexample": outcome["counterexample"],
                "claim": "compatibility with the first false-input observation establishes the whole contract"}
    return {"representation_scope": representation, "screening_overgeneralization": weak}


def _suite(trace_path, replay=False, context=None):
    from ic_discovered_programs import build_program, build_code_program
    from types import SimpleNamespace
    context = context or inputs()
    metadata = {"scope": "M4 finite multitask discovery and native component composition",
                "bindings_sha256": spec_digest(context["bindings"])}
    trace = ScheduleTrace(trace_path, metadata, replay)
    small_staged, small_runs, code_staged, code_runs, bridges = [], [], [], [], []
    try:
        discovery, witnesses = discover(context, trace)
        library, missing = select_library(context, discovery)
        negative = _negative_boundaries(discovery, context["tasks"])
        library_record = _library_record(library)
        if not missing:
            compiler, pair = context["compiler"], context["pairs"][0]
            program = GraphSpec.from_net(compiler.program)
            bridge_witnesses = {}
            for bit in (False, True):
                net, payload_ids = build_bridge(*pair, bit, compiler.code_spec, "copy_decode")
                built = SimpleNamespace(net=net, component_ids=[], input_ids=[])
                record, witness = observe(built, trace, **CODE_BUDGET)
                target = bridge_expected(bit, program, "copy_decode")
                if record["status"] == "normal-form":
                    record["status"] = ("passed" if full_match(
                        GraphSpec.from_dict(record["final_graph"]).instantiate(), target) else "wrong-normal-form")
                record["bit"] = bit
                if record["status"] != "passed":
                    record["counterexample"] = {"initial": record["initial_graph"], "actual": record["final_graph"],
                                                "expected": GraphSpec.from_net(target).to_dict(), "reason": record["status"]}
                bridges.append(record)
                bridge_witnesses[bit] = witness
            base_library = {role: entry for role, entry in library.items() if role != "erase_variants"}
            for variant, eraser in enumerate(library["erase_variants"]):
                chosen = {**base_library, "erase_B": eraser}
                for bits in product((False, True), repeat=3):
                    built = build_program(chosen, bits)
                    record, witness = staged_program(built, chosen, bits, witnesses, trace)
                    record["variant"] = variant
                    small_staged.append(record)
                    for schedule in POLICIES:
                        joint = run_joint(built, small_expected(bits), schedule, trace,
                                          predicted_census=record["resources"]["rule_census"], **PROGRAM_BUDGET)
                        joint.update({"variant": variant, "input_bits": list(bits)})
                        small_runs.append(joint)
                    if variant == 0:
                        code_built = build_code_program(chosen, bits, pair[0], compiler.code_spec)
                        bridge_witness = bridge_witnesses[all(bits)]
                        proof = staged_code_program(code_built, witness, bridge_witness, bits, trace)
                        target = bridge_expected(all(bits), program, "copy_decode")
                        final_net = GraphSpec.from_dict(proof["final_graph"]).instantiate()
                        proof["whole_graph_matches_reference"] = full_match(final_net, target)
                        if proof["status"] == "passed" and not proof["whole_graph_matches_reference"]:
                            proof["status"] = "wrong-normal-form"
                        if proof["status"] != "passed":
                            proof.setdefault("counterexample", {
                                "reason": proof["status"], "initial": GraphSpec.from_net(code_built.net).to_dict(),
                                "actual": proof["final_graph"]})["expected"] = GraphSpec.from_net(target).to_dict()
                        code_staged.append(proof)
                        for schedule in POLICIES:
                            joint = run_joint(code_built, target, schedule, trace,
                                              predicted_census=proof["predicted_rule_census"], **CODE_BUDGET)
                            joint["input_bits"] = list(bits)
                            code_runs.append(joint)
                    print("COMPOSE", variant, "".join(str(int(bit)) for bit in bits), record["status"], flush=True)
    except BaseException:
        trace.abort()
        raise
    summary = trace.close()
    positives = bridges + small_staged + small_runs + code_staged + code_runs
    decided = all(outcome["status"] in ("verified", "rejected")
                  for rows in discovery["candidate_ledgers"].values() for row in rows for outcome in row["outcomes"])
    accepted = decided and not missing and all(r["status"] == "passed" for r in positives) and all(
        r["status"] == "refuted" for r in negative.values())
    return {"format": "ic-multitask-discovery-v1", "bindings": context["bindings"], "metadata": metadata,
            "status": "passed" if accepted else "not-accepted", "discovery": discovery,
            "selected_library": library_record, "missing_roles": missing,
            "erase_variants": [entry["candidate_id"] for entry in library.get("erase_variants", [])],
            "bridge_baselines": bridges, "staged_programs": small_staged, "program_runs": small_runs,
            "staged_code_programs": code_staged, "code_program_runs": code_runs,
            "negative_probes": negative, "trace": summary,
            "limitations": ["finite syntactic prior and finite representation/input contracts; unsupported tasks do not imply IC impossibility",
                            "incomplete candidate evidence is unresolved and is never a verified component or a finite-absence certificate",
                            "all-schedule exploration is for verified elementary instances; larger compositions use staged witnesses and selected policies",
                            "written composition arguments assume the abstract IC model and faithful implementation",
                            "no general semantic discovery, arbitrary observational equivalence, structure-library benefit or physical inventory claim"]}


def compare_report(report, rebuilt):
    if spec_digest(report) != spec_digest(rebuilt):
        raise ValueError("multitask report differs from rebuilt candidate and primitive evidence")
    if rebuilt["status"] != "passed":
        raise ValueError("reproducible M4 evidence does not meet its fixed acceptance contract")
    return len(rebuilt["discovery"]["observations"])


def verify_report(report, trace_path):
    if report.get("format") != "ic-multitask-discovery-v1":
        raise ValueError("unknown multitask discovery report")
    context = inputs()
    if spec_digest(report.get("bindings")) != spec_digest(context["bindings"]):
        raise ValueError("M4 contract, grammar, task or dependency binding changed")
    return compare_report(report, _suite(trace_path, replay=True, context=context))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verify-report", type=Path)
    parser.add_argument("--trace", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.report) == bool(args.verify_report):
        parser.error("choose --report or --verify-report")
    if args.verify_report:
        verify_report(read_json(args.verify_report), args.trace)
    else:
        report = _suite(args.trace)
        write_json(args.report, report)
        if report["status"] != "passed":
            raise SystemExit("NOT ACCEPTED: fixed search and failure evidence preserved")
    print("PASS: M4 evidence; measured coverage and boundaries in docs/CLAIM_LEDGER.md")


if __name__ == "__main__":
    main()
