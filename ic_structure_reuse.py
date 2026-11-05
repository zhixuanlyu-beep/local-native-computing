"""M5 evidence-scoped storage and common-cost native reuse experiments.

All future tasks are prewired. Literal capsules, eager native distribution,
and retained-code continuation have identical results and reserve policy.
Frame readiness orders activations; it is not task completion or quiescence.
"""
from collections import Counter, defaultdict
from itertools import product
import argparse
import hashlib
from pathlib import Path

from ic_coherent_feedback import read_json, write_json, spec_digest
from ic_composition_certificates import full_match
from ic_observation_contracts import TaskContract, value_spec
from ic_primitive_port_verifier import Net, AR, RULES
from ic_program_code_bridge import load_discovery
from ic_research_artifacts import GraphSpec, capture_root
from ic_schedule_audit import Schedule, ScheduledNet, ScheduleTrace
from ic_structure_library import Catalog, build_catalog, verify_catalog


ROOT = Path(__file__).parent
POLICIES = (Schedule("fifo"), Schedule("lifo"), Schedule("seeded", 17))
COUNTS = (1, 2, 4)
STRATEGIES = ("literal", "native_fanout", "retained_chain")
DISPOSITIONS = ("retain1", "dispose_all")
BUDGET = {"max_steps": 200000, "max_cells": 50000}
STORAGE_REPRESENTATION = "native-code-grant-packet-v1"
FROZEN = {
    "program_code_bridge.json.gz": "624976b188e7659a52a32e92fcd1c46db95a18f639c41909ddaf17eaac29ecf7",
    "composition_certificates.json.gz": "dab2c7cac04220b8d2719e8e2eb812d41a6d4ebf2fb0c98350736aa100e35a33",
    "multitask_discovery.json.gz": "10b65298e08c366e4a5da7ba00a14caf03e7fd6115fc2e818d77c8e42b64b08e",
}
CONTRACT = {
    "environment": "E_structure_library-v1",
    "source_library": "all verified frozen M4 graph/contract/evidence assignments; exact representation and interface queries",
    "native_eligibility": "unchanged original graph in ordered gamma frame; READY Loop is first/deepest slot; full principal-package validator before encoding",
    "storage": STORAGE_REPRESENTATION,
    "stored_value": "gamma(encoded interface capsule, GO Loop); produced by native copying and erasing one branch",
    "workloads": "frozen selected M4 AND/copy/erase/adapter roles plus erasure of the original real Gamma data",
    "counts": list(COUNTS), "strategies": list(STRATEGIES), "dispositions": list(DISPOSITIONS),
    "policies": [p.to_dict() for p in POLICIES], "per_case_budget": BUDGET,
    "inputs": "fixed truth-table tuples in order, cycling only for the declared task count",
    "literal": "common native source production; independent literal raw capsules for tasks; produced code retained or disposed",
    "native_fanout": "common native source production; balanced delta distribution to tasks and one reserve",
    "retained_chain": "common native source production; reservoir passes each native grant before copying to task and next stage",
    "activation_control": "common native grant chain; decoded/raw frame slot zero emits READY, copied to STATUS and next grant",
    "readiness_boundary": "frame extraction only; remaining decoding, component execution and cleanup may overlap",
    "target": "all independent task outputs and STATUS Loops; exactly one code reserve for retain1, none for dispose_all; no other cells/cycles",
    "accounting": "whole initial network, primitive RHS allocations by kind, interactions/census, peak, retained/product cells, explicit eraser lineage",
    "host_work": "separate deterministic acquisition, index/query, packaging and verification counts; not native savings or wall-clock prices",
    "comparison": "same workload, input tuples, count, disposition and policy; Pareto comparison of declared native resource vectors only",
    "scope": "finite measured tradeoffs; no universal gain, optimality, physical stock or reused workspace claim",
}
ROLE_NAMES = ("and_A", "copy_A", "box_AB", "copy_B", "erase_B", "unbox_BA")
IN_LABELS = {"binary": ("LEFT", "RIGHT"), "unary": ("IN",), "copy": ("IN",), "erase": ("IN",)}
OUT_LABELS = {"binary": ("OUT",), "unary": ("OUT",), "copy": ("OUT1", "OUT2"), "erase": ()}
RULE_LABELS = tuple("".join(pair) for pair in RULES)


def empty_census():
    return Counter({label: 0 for label in RULE_LABELS})


def package_counts(spec):
    from ic_package_codec import validate_package
    net = spec.instantiate()
    validate_package(net)
    n = len(net.nodes)
    twice = sum(AR[kind] for kind in net.nodes.values()) - n + 1
    if twice < 0 or twice % 2:
        raise ValueError("invalid principal-package auxiliary-wire equation")
    return Counter(net.nodes.values()), twice // 2


def copy_census(spec):
    kinds, wires = package_counts(spec)
    if kinds["d"]:
        raise ValueError("primitive native copying requires delta-free data")
    result = empty_census()
    result.update({"gd": kinds["g"], "de": kinds["e"], "dd": wires})
    return result


def erase_census(spec):
    kinds, wires = package_counts(spec)
    result = empty_census()
    result.update({"ge": kinds["g"], "de": kinds["d"], "ee": kinds["e"] + wires})
    return result


def decoder_census(capsule):
    count = capsule.package.kinds.count("d")
    result = empty_census()
    result.update({"gg": 2 * (count - 1) + 3, "gd": count - 1} if count else
                  {"gg": 3, "de": 1, "ee": 2})
    return result


def _task(workload):
    if workload["task"] is None:
        return None
    data = workload["task"]
    return TaskContract(data["name"], data["family"], tuple(data["input_reprs"]),
                        tuple(data["output_reprs"]), data["mask"])


def task_inputs(workload, count):
    task = _task(workload)
    domain = task.inputs() if task else ((),)
    return tuple(domain[index % len(domain)] for index in range(count))


def task_census(workload, bits):
    if workload["task"] is None:
        return erase_census(workload["component"])
    for case in workload["source_cases"]:
        if case.bits == bits:
            return Counter(case.resources["rule_census"])
    raise ValueError("task input is outside the exact source evidence domain")


def predicted_census(workload, packet, count, strategy, disposition):
    result = copy_census(packet)
    result.update(erase_census(packet))
    result["gg"] += 1 + count + 1 + count * (workload["capsule"].width - 1)
    result["gd"] += count
    result["dd"] += count
    for bits in task_inputs(workload, count):
        result.update(task_census(workload, bits))
    if strategy != "literal":
        for label, value in (copy_census(workload["capsule"].code) + decoder_census(workload["capsule"])).items():
            result[label] += count * value
    if disposition == "dispose_all":
        result.update(erase_census(workload["capsule"].code))
    return result


def expected(workload, count, disposition):
    net = Net()
    task = _task(workload)
    for index, bits in enumerate(task_inputs(workload, count)):
        if task:
            for label, rep, bit in zip(workload["output_labels"], workload["output_reprs"], task.evaluate(bits)):
                value_spec(rep, bit).instantiate(net, {"ROOT": net.boundary(f"TASK_{index}_{label}")})
        value_spec("A", True).instantiate(net, {"ROOT": net.boundary(f"STATUS_{index}")})
    if disposition == "retain1":
        workload["capsule"].code.instantiate(net, {"ROOT": net.boundary("RESERVE")})
    net.check()
    return net


def inputs():
    from ic_structure_capsules import build_capsule
    from ic_reuse_benchmarks import make_packet
    if CONTRACT["policies"] != [p.to_dict() for p in POLICIES]:
        raise ValueError("runtime schedules differ from the cost contract")
    reports = {}
    for name, digest in FROZEN.items():
        path = ROOT / "results" / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("frozen evidence changed: " + name)
        reports[name] = read_json(path)
    catalog = build_catalog()
    source_verification = verify_catalog(catalog)
    assessments, eligibility, capsules = {}, [], {}
    for entry in catalog.entries:
        if entry.candidate_id not in assessments:
            component = GraphSpec.from_dict(entry.graph)
            try:
                capsule = build_capsule(component)
            except ValueError as error:
                assessment = {"candidate_id": entry.candidate_id, "status": "unsupported", "reason": str(error)}
            else:
                assessment = {"candidate_id": entry.candidate_id, "status": "eligible",
                              "package_sha256": spec_digest(capsule.package.to_dict()),
                              "code_sha256": spec_digest(capsule.code.to_dict()),
                              "package_cells": len(capsule.package.kinds), "code_cells": len(capsule.code.kinds)}
                capsules[entry.candidate_id] = capsule
            assessments[entry.candidate_id] = assessment
        eligibility.append({"entry_id": entry.id, **assessments[entry.candidate_id]})
    selected = reports["multitask_discovery.json.gz"]["selected_library"]
    workloads, queries, missing = [], [], []
    for role in ROLE_NAMES:
        reference = selected[role]
        task_data = next(task for task in reports["multitask_discovery.json.gz"]["bindings"]["tasks"]
                         if task["name"] == reference["task"])
        matches = catalog.query(tuple(task_data["input_reprs"]), tuple(task_data["output_reprs"]),
                                tuple(task_data["interface"]), task_name=task_data["name"],
                                minimum_evidence="all-schedules-finite")
        entry = next((entry for entry in matches if entry.candidate_id == reference["candidate_id"]), None)
        queries.append({"role": role, "source_task": task_data["name"], "matches": len(matches),
                        "selected_entry": entry.id if entry else None})
        if entry is None or entry.candidate_id not in capsules:
            missing.append(role)
            continue
        task = TaskContract(entry.task_name, task_data["family"], entry.input_reprs, entry.output_reprs, task_data["mask"])
        workloads.append({"name": role, "source_id": entry.id, "component": GraphSpec.from_dict(entry.graph),
                          "capsule": capsules[entry.candidate_id], "task": task.to_dict(),
                          "input_labels": IN_LABELS[task.family], "output_labels": OUT_LABELS[task.family],
                          "input_reprs": entry.input_reprs, "output_reprs": entry.output_reprs, "erase_ports": (),
                          "source_cases": entry.cases, "source_evidence": "all-schedules-finite"})
    gamma = GraphSpec.from_dict(reports["program_code_bridge.json.gz"]["bindings"]["payloads"]["Gamma"]["object"]["graph"])
    gamma_capsule = build_capsule(gamma)
    gamma_id = spec_digest({"kind": "Gamma-data", "graph": gamma.to_dict(),
                            "source": FROZEN["program_code_bridge.json.gz"]})
    gamma_checks = [r for r in reports["composition_certificates.json.gz"]["macro_cases"]
                    if r["name"] == "primitive-erase-program"]
    if not gamma_checks or any(r["status"] != "passed" or r["resources"]["rule_census"] != dict(erase_census(gamma))
                               for r in gamma_checks):
        raise ValueError("Gamma erasure does not agree with its frozen source evidence")
    workloads.append({"name": "Gamma_erase", "source_id": gamma_id, "component": gamma,
                      "capsule": gamma_capsule, "task": None, "input_labels": (), "output_labels": (),
                      "input_reprs": (), "output_reprs": (), "erase_ports": ("ROOT",), "source_cases": (),
                      "source_evidence": "fifo", "source_policy_checks": [r["schedule"] for r in gamma_checks]})
    for workload in workloads:
        workload["packet"] = make_packet(workload["capsule"].code)
    _, gates = load_discovery()
    workload_specs = [{"name": w["name"], "source_id": w["source_id"], "component": w["component"].to_dict(),
                       "interface": list(w["component"].boundaries), "task": w["task"],
                       "input_reprs": list(w["input_reprs"]), "output_reprs": list(w["output_reprs"]),
                       "erase_ports": list(w["erase_ports"]), "source_evidence": w["source_evidence"],
                       "package": w["capsule"].package.to_dict(), "code": w["capsule"].code.to_dict(),
                       "packet": w["packet"].to_dict(), "width": w["capsule"].width,
                       "input_cases": {str(n): [list(bits) for bits in task_inputs(w, n)] for n in COUNTS}}
                      for w in workloads]
    bound = {"contract": CONTRACT, "contract_sha256": spec_digest(CONTRACT), "sources": FROZEN,
             "catalog_sha256": spec_digest(catalog.to_dict()), "eligibility": eligibility,
             "workloads": workload_specs, "gate": gates[0][0].to_dict(),
             "primitive_rules": [{"lhs": list(k), "rhs_cells": v[0], "wires": v[1]} for k, v in RULES.items()]}
    return {"catalog": catalog, "source_verification": source_verification, "eligibility": eligibility,
            "assessments": list(assessments.values()), "queries": queries, "workloads": workloads,
            "gate": gates[0][0], "missing": missing, "bindings": bound}


class CostNet(ScheduledNet):
    """Verification-only epsilon ancestry; rewrites remain the original rules."""
    def __init__(self, schedule):
        super().__init__(schedule)
        self.eraser_tags = {}
        self.erasure_events = Counter()

    def tag_eraser(self, cell, role):
        if cell not in self.nodes or self.nodes[cell] != "e":
            raise ValueError("an explicit erasure origin must be an epsilon cell")
        self.eraser_tags[cell] = frozenset((role,))

    def reduce(self, u, v):
        tags = self.eraser_tags.pop(u, frozenset()) | self.eraser_tags.pop(v, frozenset())
        before = self.next
        super().reduce(u, v)
        if tags:
            self.erasure_events[tuple(sorted(tags))] += 1
            for number in range(before, self.next):
                cell = "c" + str(number)
                if self.nodes[cell] == "e":
                    self.eraser_tags[cell] = tags


def allocation_profile(census):
    result = Counter({kind: 0 for kind in AR})
    for kinds, (rhs, _) in RULES.items():
        count = census["".join(kinds)]
        result.update({kind: count * amount for kind, amount in Counter(rhs.values()).items()})
    return dict(result)


def _name(cell, rename):
    return rename[cell] if cell is not None else None


def _protocol(built, events, strategy, disposition):
    errors = []
    by_key = defaultdict(list)
    for event in events:
        by_key[(event["kind"], event["stage"])].append(event)
        if event["kind"] == "ready" and event.get("frame_cells_remaining"):
            errors.append({"stage": event["stage"], "reason": "READY escaped before complete frame extraction"})
    def one(kind, stage=None, expected_kind="gg"):
        matches = by_key[(kind, stage)]
        if len(matches) != 1 or "".join(sorted(matches[0]["kinds"])) != "".join(sorted(expected_kind)):
            errors.append({"stage": stage, "event": kind, "reason": "missing, repeated or wrong primitive event"})
            return None
        return matches[0]["step"]
    source, delivered = one("source-copy", expected_kind="gd"), one("source-delivery")
    if source is not None and delivered is not None and source >= delivered:
        errors.append({"reason": "source delivery preceded native production"})
    previous = delivered
    for stage in built.stages:
        index = stage["index"]
        grant, unpack, ready = one("grant", index), one("unpack", index), one("ready", index, "gd")
        positions = [p for p in (previous, grant, unpack, ready) if p is not None]
        if len(positions) == 4 and positions != sorted(set(positions)):
            errors.append({"stage": index, "reason": "native activation order violated"})
        if stage.get("decoder_head") is not None:
            decode = one("decode", index)
            if None not in (grant, decode, unpack) and not grant < decode < unpack:
                errors.append({"stage": index, "reason": "decoder was not granted before frame extraction"})
        if stage.get("copy_head") is not None:
            copy, decode = one("copy", index, "gd"), one("decode", index)
            if None not in (grant, copy, decode) and not grant < copy < decode:
                errors.append({"stage": index, "reason": "carried source was not copied after grant"})
        previous = ready
    reserve = one("reserve")
    if None not in (previous, reserve) and previous >= reserve:
        errors.append({"reason": "reserve released before final frame readiness"})
    if disposition == "dispose_all":
        disposed = one("dispose", expected_kind="ge")
        if None not in (reserve, disposed) and reserve >= disposed:
            errors.append({"reason": "reserve disposal preceded release"})
    return errors


def run_case(built, target, schedule, trace, predicted, *, strategy, disposition,
             max_steps=200000, max_cells=50000):
    if any(type(v) is not int or v < 0 for v in (max_steps, max_cells)):
        raise ValueError("native limits must be non-negative integers")
    syntax = GraphSpec.from_net(built.net)
    actual = syntax.instantiate(CostNet(schedule))
    rename = dict(zip(built.net.nodes, actual.nodes))
    categories = {rename[cell]: label for cell, label in built.initial_categories.items()}
    if set(categories) != set(actual.nodes):
        raise ValueError("initial resource categories do not cover the whole network")
    actual.tag_eraser(rename[built.producer_eraser], "source-production-erasure")
    if built.reserve_eraser is not None:
        actual.tag_eraser(rename[built.reserve_eraser], "reserve-disposal")
    watched = defaultdict(list)
    watched[rename[built.producer_fan]].append(("source-copy", None))
    watched[rename[built.common_unpack_head]].append(("source-delivery", None))
    watched[rename[built.reserve_gate]].append(("reserve", None))
    if built.reserve_eraser is not None:
        watched[rename[built.reserve_eraser]].append(("dispose", None))
    for stage in built.stages:
        index = stage["index"]
        for field, kind in (("grant_gate", "grant"), ("copy_head", "copy"), ("decoder_head", "decode"),
                            ("unpack_head", "unpack"), ("ready_fork", "ready")):
            if stage.get(field) is not None:
                watched[rename[stage[field]]].append((kind, index))
        for cell in stage["task_erasers"]:
            actual.tag_eraser(rename[cell], "task-output-erasure:" + str(index))
    frames = {}
    for stage in built.stages:
        cells, head = [], stage["unpack_head"]
        while head in built.net.nodes and built.net.nodes[head] == "g":
            if head in cells:
                raise ValueError("unpack frame contains a principal cycle")
            cells.append(head)
            endpoint = built.net.adj[(head, 2)]
            if endpoint[1] != 0:
                break
            head = endpoint[0]
        frames[stage["index"]] = tuple(rename[c] for c in cells)
    start, steps, events = trace.count, 0, []
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
        for cell in pair:
            for kind, stage in watched[cell]:
                event = {"kind": kind, "stage": stage, "step": steps,
                         "pair": list(pair), "kinds": [actual.nodes[c] for c in pair]}
                if kind == "ready":
                    event["frame_cells_remaining"] = [c for c in frames[stage] if c in actual.nodes]
                events.append(event)
        trace.record(pair)
        actual.reduce(*pair)
        steps += 1
    resources = actual.statistics()
    protocol = _protocol(built, events, strategy, disposition) if status == "passed" else []
    if status == "passed" and protocol:
        status = "protocol-violation"
    if status == "passed" and resources["rule_census"] != dict(predicted):
        status = "cost-prediction-violation"
    source_consumed = not bool({rename[c] for c in built.source_ids} & set(actual.nodes))
    if status == "passed" and not source_consumed:
        status = "source-cells-survived"
    cleanup = sum(actual.erasure_events.values())
    if cleanup > steps:
        raise AssertionError("eraser lineage events were double counted")
    allocated = allocation_profile(resources["rule_census"])
    initial_kinds = Counter(syntax.kinds)
    predicted_kinds = initial_kinds.copy()
    for kinds, (rhs, _) in RULES.items():
        count = resources["rule_census"]["".join(kinds)]
        predicted_kinds.update({kind: count * value for kind, value in Counter(rhs.values()).items()})
        predicted_kinds.subtract({kind: count * value for kind, value in Counter(kinds).items()})
    if predicted_kinds != Counter(actual.nodes.values()) or sum(allocated.values()) != resources["runtime_cells_allocated"]:
        raise AssertionError("kind-wise primitive allocation balance failed")
    final = GraphSpec.from_net(actual).to_dict()
    retained_cells = 0
    retained = None
    if status == "passed" and disposition == "retain1":
        artifact, ids = capture_root(actual, ("F", "RESERVE"),
                                     {"initial_graph_sha256": spec_digest(syntax.to_dict()),
                                      "trace_offset_records": start, "primitive_interactions": steps},
                                     {"representation": "encoded-interface-capsule-v1", "interface": ["ROOT"],
                                      "runtime": "native value carried or retained inside one prewired benchmark"})
        retained, retained_cells = artifact.to_dict(), len(ids)
    record = {"status": status, "schedule": schedule.to_dict(), "trace_offset_records": start,
              "primitive_interactions": steps, "initial_graph_sha256": spec_digest(syntax.to_dict()),
              "resources": {**resources, "initial_categories": dict(Counter(categories.values())),
                            "initial_kind_counts": dict(initial_kinds), "rhs_allocations_by_kind": allocated,
                            "final_kind_counts": dict(Counter(actual.nodes.values())),
                            "retained_cells": retained_cells, "final_nonreserve_cells": len(actual.nodes) - retained_cells,
                            "explicit_eraser_interactions": cleanup,
                            "eraser_lineage_groups": [{"roles": list(roles), "interactions": value}
                                                      for roles, value in sorted(actual.erasure_events.items())],
                            "cleanup_scope": "union of interactions involving epsilon descendants of named erasure consumers; decoder cleanup is also charged in total work"},
              "predicted_rule_census": dict(predicted), "events": events, "protocol_violations": protocol,
              "source_cells_consumed": source_consumed, "terminal": not bool(actual.active()),
              "whole_graph_matches_reference": full_match(actual, target), "final_graph": final,
              "final_graph_sha256": spec_digest(final),
              "expected_graph_sha256": spec_digest(GraphSpec.from_net(target).to_dict()),
              "retained_artifact": retained}
    if status != "passed":
        record["counterexample"] = {"initial": syntax.to_dict(), "actual": final,
                                    "expected": GraphSpec.from_net(target).to_dict(), "reason": status}
    return record


def run_producer(built, packet, trace, **budget):
    """Validate an offline library specimen; benchmarks produce again natively."""
    syntax = GraphSpec.from_net(built.net)
    actual = syntax.instantiate(CostNet(Schedule()))
    rename = dict(zip(built.net.nodes, actual.nodes))
    actual.tag_eraser(rename[built.producer_eraser], "source-production-erasure")
    start, steps = trace.count, 0
    while True:
        if len(actual.nodes) > budget["max_cells"]:
            status = "resource-violation"
            break
        pair = actual.next_active()
        if pair is None:
            status = "passed" if full_match(actual, packet.instantiate()) else "wrong-normal-form"
            break
        if steps >= budget["max_steps"]:
            status = "incomplete"
            break
        trace.record(pair)
        actual.reduce(*pair)
        steps += 1
    resources = actual.statistics()
    prediction = copy_census(packet)
    prediction.update(erase_census(packet))
    consumed = not bool(set(rename[c] for c in built.source_ids) & set(actual.nodes))
    if status == "passed" and (resources["rule_census"] != dict(prediction) or not consumed):
        status = "producer-invariant-violation"
    artifact = None
    if status == "passed":
        artifact, ids = capture_root(actual, ("F", "ROOT"),
                                     {"initial_graph_sha256": spec_digest(syntax.to_dict()),
                                      "trace_start": start, "trace_steps": steps},
                                     {"scope": "FIFO native copy and erasure; offline capture"})
        if set(ids) != set(actual.nodes):
            raise AssertionError("producer archive omits extra components")
    record = {"status": status, "trace_start": start, "trace_steps": steps,
              "initial_graph_sha256": spec_digest(syntax.to_dict()),
              "expected_packet_sha256": spec_digest(packet.to_dict()),
              "resources": resources, "predicted_rule_census": dict(prediction),
              "source_cells_consumed": consumed,
              "whole_graph_matches_reference": full_match(actual, packet.instantiate()),
              "final_graph": GraphSpec.from_net(actual).to_dict(),
              "retained_artifact": artifact.to_dict() if artifact else None}
    if status != "passed":
        record["counterexample"] = {"initial": syntax.to_dict(), "actual": record["final_graph"],
                                    "expected": packet.to_dict(), "reason": status}
    return record, artifact


def query_artifacts(manifest, *, storage_representation, storage_interface,
                    activation_interface, input_reprs, output_reprs,
                    source_id=None, minimum_evidence="fifo"):
    """No implicit representation adaptation or inherited production theorem."""
    from copy import deepcopy
    if minimum_evidence not in ("fifo", "all-schedules-finite"):
        raise ValueError("unknown production evidence scope")
    for interface in (storage_interface, activation_interface, input_reprs, output_reprs):
        if not isinstance(interface, tuple) or any(type(label) is not str for label in interface):
            raise ValueError("artifact query interfaces must be ordered string tuples")
    if minimum_evidence != "fifo":
        return ()
    return tuple(deepcopy(entry) for entry in manifest["native_artifacts"]
                 if entry["storage_representation"] == storage_representation
                 and tuple(entry["storage_interface"]) == storage_interface
                 and tuple(entry["activation_interface"]) == activation_interface
                 and tuple(entry["input_reprs"]) == input_reprs
                 and tuple(entry["output_reprs"]) == output_reprs
                 and (source_id is None or entry["source_id"] == source_id)
                 and entry["production_evidence"] == "fifo")


def compare_costs(records):
    dimensions = ("initial_cells", "primitive_interactions", "total_symbolic_cells_allocated", "peak_live_cells")
    groups = defaultdict(dict)
    for record in records:
        key = (record["workload"], record["task_count"], record["disposition"],
               record["schedule"]["policy"], record["schedule"]["seed"])
        groups[key][record["strategy"]] = record
    comparisons = []
    for key, strategies in groups.items():
        if set(strategies) != set(STRATEGIES):
            raise ValueError("cost comparison has an incomplete strategy group")
        accepted = all(r["status"] == "passed" for r in strategies.values())
        vectors = {s: [r["resources"][d] for d in dimensions] for s, r in strategies.items()}
        dominates = lambda a, b: all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))
        comparisons.append({"workload": key[0], "task_count": key[1], "disposition": key[2],
                            "policy": key[3], "seed": key[4], "status": "comparable" if accepted else "unresolved",
                            "dimensions": list(dimensions), "vectors": vectors,
                            "pareto_front": [s for s in STRATEGIES if not any(dominates(vectors[t], vectors[s])
                                              for t in STRATEGIES)] if accepted else [],
                            "relative_to_literal": {s: {"savings": dict(zip(dimensions,
                                [x-y for x, y in zip(vectors["literal"], vectors[s])])),
                                "dominates_literal": accepted and dominates(vectors[s], vectors["literal"]),
                                "dominated_by_literal": accepted and dominates(vectors["literal"], vectors[s])}
                                for s in STRATEGIES if s != "literal"}})
    return comparisons


def negative_cases(context, trace):
    """Durable failures preserve the full graphs and raw interaction intervals."""
    from ic_reuse_benchmarks import build_benchmark
    workload = context["workloads"][0]
    net = Net()
    code = workload["capsule"].code.open_root(net)
    head, disabled = net.cell("g"), net.cell("e")
    net.link((head, 1), code)
    net.link((head, 2), (disabled, 0))
    net.link((head, 0), net.boundary("ROOT"))
    wrong_packet = GraphSpec.from_net(net)
    gate = context["gate"]
    def swap(endpoint):
        return ("F", {"CTRL": "DATA", "DATA": "CTRL"}.get(endpoint[1], endpoint[1])) if endpoint[0] == "F" else endpoint
    wrong_gate = GraphSpec(gate.kinds, gate.boundaries,
                           tuple((swap(a), swap(b)) for a, b in gate.wires), gate.cycles)
    records = []
    for name, packet, specimen in (("epsilon-is-not-GO", wrong_packet, gate),
                                  ("swapped-control-data", workload["packet"], wrong_gate)):
        built = build_benchmark(workload, packet, 1, "retained_chain", "retain1",
                                task_inputs(workload, 1), specimen)
        record = run_case(built, expected(workload, 1, "retain1"), Schedule(), trace,
                          predicted_census(workload, packet, 1, "retained_chain", "retain1"),
                          strategy="retained_chain", disposition="retain1", **BUDGET)
        record["probe"] = name
        record["conclusion"] = "refuted" if record["status"] == "wrong-normal-form" else "unresolved"
        records.append(record)
    return records


def _suite(trace_path, *, replay=False, context=None):
    from ic_reuse_benchmarks import producer, build_benchmark
    context = inputs() if context is None else context
    metadata = {"experiment": "ic-structure-reuse-v1", "bindings_sha256": spec_digest(context["bindings"])}
    trace = ScheduleTrace(trace_path, metadata, replay=replay)
    producers, native_artifacts, benchmarks, cache = [], [], [], {}
    try:
        for workload in context["workloads"]:
            packet = workload["packet"]
            fingerprint = spec_digest(packet.to_dict())
            if fingerprint not in cache:
                record, artifact = run_producer(producer(packet), packet, trace, **BUDGET)
                record["id"] = fingerprint
                producers.append(record)
                cache[fingerprint] = record, artifact
            record, artifact = cache[fingerprint]
            if artifact is None:
                continue
            native_artifacts.append({"id": spec_digest({"source": workload["source_id"], "producer": fingerprint}),
                "source_id": workload["source_id"], "workload": workload["name"],
                "storage_representation": STORAGE_REPRESENTATION, "storage_interface": ["ROOT"],
                "activation_interface": list(workload["component"].boundaries),
                "input_reprs": list(workload["input_reprs"]), "output_reprs": list(workload["output_reprs"]),
                "production_evidence": "fifo", "source_component_evidence": workload["source_evidence"],
                "producer_id": fingerprint, "trace_start": record["trace_start"], "trace_steps": record["trace_steps"],
                "original_packet_sha256": fingerprint, "produced_packet_sha256": spec_digest(artifact.spec.to_dict()),
                "full_graph_equal_to_original": record["whole_graph_matches_reference"],
                "artifact": artifact.to_dict()})
        manifest = {"format": "ic-structure-library-v1", "bindings_sha256": metadata["bindings_sha256"],
                    "raw_catalog": context["catalog"].to_dict(), "eligibility": context["eligibility"],
                    "distinct_assessments": context["assessments"], "native_artifacts": native_artifacts}
        for workload in context["workloads"]:
            matches = query_artifacts(manifest, storage_representation=STORAGE_REPRESENTATION,
                 storage_interface=("ROOT",), activation_interface=workload["component"].boundaries,
                 input_reprs=workload["input_reprs"], output_reprs=workload["output_reprs"], source_id=workload["source_id"])
            if len(matches) != 1:
                context["missing"].append(workload["name"] + ":native-artifact")
                continue
            packet = GraphSpec.from_dict(matches[0]["artifact"]["spec"])
            for count, disposition in product(COUNTS, DISPOSITIONS):
                target = expected(workload, count, disposition)
                for strategy in STRATEGIES:
                    built = build_benchmark(workload, packet, count, strategy, disposition,
                                            task_inputs(workload, count), context["gate"])
                    prediction = predicted_census(workload, packet, count, strategy, disposition)
                    for schedule in POLICIES:
                        record = run_case(built, target, schedule, trace, prediction,
                                          strategy=strategy, disposition=disposition, **BUDGET)
                        record.update({"workload": workload["name"], "source_id": workload["source_id"],
                                       "artifact_id": matches[0]["id"], "task_count": count, "strategy": strategy,
                                       "disposition": disposition, "input_vectors": [list(b) for b in task_inputs(workload, count)]})
                        benchmarks.append(record)
                print("REUSE", workload["name"], count, disposition, benchmarks[-1]["status"], flush=True)
        negative = negative_cases(context, trace) if context["workloads"] else []
    except BaseException:
        trace.abort()
        raise
    summary = trace.close()
    manifest["trace"] = summary
    accepted = (not context["missing"] and all(r["status"] == "passed" for r in producers + benchmarks)
                and all(r["conclusion"] == "refuted" for r in negative))
    report = {"format": "ic-structure-reuse-v1", "status": "passed" if accepted else "not-accepted",
              "bindings": context["bindings"], "metadata": metadata,
              "library_sha256": spec_digest(manifest), "source_verification": context["source_verification"],
              "queries": context["queries"], "missing_workloads": context["missing"],
              "host_acquisition": {"scope": "deterministic setup counts, separate from primitive native work",
                  "catalog_entries": len(context["catalog"].entries), "catalog_query_calls": len(context["queries"]),
                  "catalog_entries_examined": len(context["catalog"].entries) * len(context["queries"]),
                  "distinct_capsule_assessments": len(context["assessments"]),
                  "gamma_capsule_builds": 1, "distinct_archive_productions": len(producers),
                  "artifact_query_calls": len(context["workloads"]),
                  "artifact_entries_examined": len(native_artifacts) * len(context["workloads"]),
                  "lookup_algorithm": "linear exact evidence/representation filter; no asymptotic indexing speedup claim"},
              "acquisition_native_work": {"primitive_interactions": sum(r["resources"]["primitive_interactions"] for r in producers),
                    "symbolic_cells_allocated": sum(r["resources"]["total_symbolic_cells_allocated"] for r in producers),
                    "scope": "shared prior archive-production episodes, charged separately for all strategies; not free or simultaneous inventory"},
              "producers": producers, "benchmarks": benchmarks, "negative_probes": negative,
              "comparisons": compare_costs(benchmarks), "trace": summary,
              "limitations": ["offline archive capture/import precedes benchmarks; original producer networks are not native continuations",
                  "within each benchmark all future tasks are prewired and a fresh native source production is included",
                  "READY means frame extraction, not completion; task decoding and cleanup may overlap",
                  "catalog finite exhaustive proofs do not transfer to production, activation or composed execution",
                  "selected schedules and bounded workloads do not prove general savings, contextual equivalence or optimality",
                  "symbolic cells and allocations are not host byte memory or physical finite inventory"]}
    return report, manifest


def verify_report(report, manifest, trace_path):
    if report.get("format") != "ic-structure-reuse-v1" or manifest.get("format") != "ic-structure-library-v1":
        raise ValueError("unknown M5 report or library format")
    context = inputs()
    if spec_digest(report.get("bindings")) != spec_digest(context["bindings"]):
        raise ValueError("M5 fixed contract, source evidence or workload binding changed")
    if report.get("library_sha256") != spec_digest(manifest):
        raise ValueError("M5 library provenance or graph changed")
    rebuilt, library = _suite(trace_path, replay=True, context=context)
    if spec_digest(report) != spec_digest(rebuilt) or spec_digest(manifest) != spec_digest(library):
        raise ValueError("M5 evidence differs from independent primitive replay and reconstruction")
    if rebuilt["status"] != "passed":
        raise ValueError("reproducible evidence did not meet the fixed M5 acceptance contract")
    return len(rebuilt["benchmarks"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verify-report", type=Path)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.report) == bool(args.verify_report):
        parser.error("choose --report or --verify-report")
    if args.verify_report:
        verify_report(read_json(args.verify_report), read_json(args.library), args.trace)
    else:
        report, manifest = _suite(args.trace)
        write_json(args.library, manifest)
        write_json(args.report, report)
        if report["status"] != "passed":
            raise SystemExit("NOT ACCEPTED: fixed contract and failure evidence preserved")
    print("PASS: M5 structure library and resource evidence; see docs/CLAIM_LEDGER.md")


if __name__ == "__main__":
    main()
