"""Schedule, resource and composition evidence for result-controlled IC runs.

The builders in the M6 milestone remain oracle-free: this module executes only
primitive IC rewrites, records every selected pair, and validates the native
protocol from explicit stage metadata.  Reference graphs are supplied by the
caller and are used only after a run reaches its normal form.
"""
from collections import Counter, defaultdict

from ic_coherent_output_decoder import port_graph_isomorphic
from ic_research_artifacts import GraphSpec
from ic_schedule_audit import Schedule, ScheduledNet
from ic_primitive_port_verifier import RULES


POLICIES = (Schedule("fifo"), Schedule("lifo"), Schedule("seeded", 17))
EXECUTION_BUDGET = {"max_steps": 2_000_000, "max_cells": 250_000}
SMALL_BUDGET = {"max_steps": 32_768, "max_cells": 128}
SMALL_STATE_BUDGET = {"max_states": 4_096, "max_transitions": 32_768,
                      "max_cells": 128}


def _budget(budget, default):
    supplied = dict(EXECUTION_BUDGET if default == "execution" else SMALL_BUDGET)
    if budget:
        supplied.update(dict(budget))
    if set(supplied) != {"max_steps", "max_cells"}:
        raise ValueError("run budget accepts only max_steps and max_cells")
    if any(type(value) is not int or value < 0 for value in supplied.values()):
        raise ValueError("run bounds must be non-negative integers")
    return supplied


def trace_frame(net, head, *, stop_kind="e"):
    """Return a principal frame spine, stopping before its first body cell."""
    if head not in net.nodes or net.nodes[head] != "g":
        raise ValueError("a frame head must be a gamma principal")
    cells = []
    while head in net.nodes and net.nodes[head] == "g":
        if head in cells:
            raise ValueError("principal frame contains a cycle")
        cells.append(head)
        endpoint = net.adj[(head, 2)]
        if endpoint is None or endpoint[1] != 0:
            break
        head = endpoint[0]
    if not cells or any(net.nodes[cell] != "g" for cell in cells):
        raise ValueError("invalid principal frame spine")
    if stop_kind is not None and cells[-1] in net.nodes and net.nodes[cells[-1]] != stop_kind:
        # The caller may deliberately pass a boundary leaf.  In that case the
        # last graph cell still identifies the end of the principal spine.
        if net.adj[(cells[-1], 2)] is None or net.adj[(cells[-1], 2)][1] != 0:
            raise ValueError("frame spine did not reach its declared body")
    return tuple(cells)


def _one(events, kind, stage=None, *, expected_kinds="gg"):
    matches = [event for event in events
               if event["kind"] == kind and event.get("stage") == stage]
    if len(matches) != 1 or "".join(sorted(matches[0]["kinds"])) != "".join(sorted(expected_kinds)):
        return None, {"kind": kind, "stage": stage,
                      "reason": "missing, repeated or wrong primitive event"}
    return matches[0], None


def _ensure_list(value):
    if isinstance(value, (tuple, list)):
        return list(value)
    return list(value or ())


def validate_protocol(stages, events, *, retained_ids=()):
    """Validate result recognition and handoff without consulting references."""
    errors = []
    by_key = defaultdict(list)
    for event in events:
        by_key[(event["kind"], event.get("stage"))].append(event)
        if event["kind"] == "reader-ready" and event.get("frame_cells_remaining"):
            errors.append({"stage": event.get("stage"),
                           "reason": "reader readiness preceded complete unpack extraction"})
        if event["kind"] == "component-ready" and event.get("frame_cells_remaining"):
            errors.append({"stage": event.get("stage"),
                           "reason": "component readiness preceded complete capsule extraction"})

    previous_advance = None
    for expected_stage in stages:
        index = expected_stage["index"]
        grant, grant_error = _one(events, "grant", index)
        delivery, delivery_error = _one(events, "delivery", index)
        advance, advance_error = _one(events, "advance", index)
        for error in (grant_error, delivery_error, advance_error):
            if error is not None:
                errors.append({**error, "stage": index})
        if any(value is None for value in (grant, delivery, advance)):
            continue
        if expected_stage.get("incoming_packet") is not None and expected_stage["incoming_packet"] not in grant["pair"]:
            errors.append({"stage": index, "reason": "grant did not consume its predecessor's actual packet"})
        if expected_stage.get("component"):
            _, component_error = _one(events, "component-ready", index, expected_kinds="ge")
            if component_error is not None:
                errors.append({"stage": index, "reason": "capsule extraction lacks its actual READY Loop"})
        if previous_advance is not None and previous_advance >= grant["step"]:
            errors.append({"stage": index, "reason": "grant preceded previous advancement"})
        if grant["step"] >= delivery["step"] or grant["step"] >= advance["step"]:
            errors.append({"stage": index, "reason": "stage progressed before grant"})
        if expected_stage.get("enabled") and delivery["step"] >= advance["step"]:
            errors.append({"stage": index, "reason": "enabled stage advanced before delivery"})

        reader = expected_stage.get("reader") or {}
        emitters = set(_ensure_list(reader.get("ready_emitters")))
        joins = set(_ensure_list(reader.get("join_gates")))
        completion_by_symbol = {
            symbol: cell for symbol, cell in
            (reader.get("result_completion_by_symbol") or {}).items()
        }
        completion_events = [event for event in events
                             if event["kind"] == "result-recognition" and event.get("stage") == index
                             and "".join(sorted(event["kinds"])) == "gg"]
        completion = completion_events[0] if len(completion_events) == 1 else None
        expected_joins = 1 if completion is not None and completion_by_symbol.get("BR") in completion["pair"] else 0
        if expected_stage.get("enabled") and len(completion_events) != 1:
            errors.append({"stage": index,
                           "reason": "original result recognition did not complete"})
        progress_unpack, unpack_error = _one(events, "progress-unpack", index, expected_kinds="gg")
        if unpack_error is not None:
            errors.append({**unpack_error, "stage": index,
                           "reason": "progress packet extraction did not complete"})
        if expected_stage.get("enabled"):
            selected = [symbol for symbol, gate in completion_by_symbol.items()
                        if completion is not None and gate in completion["pair"]]
            tokens = reader.get("progress_ready_tokens") or {}
            if tokens and (len(selected) != 1 or tokens.get(selected[0]) not in advance["pair"]):
                errors.append({"stage": index, "reason": "handoff did not consume the selected result progress token"})
            if completion is not None and not emitters.intersection(completion["pair"]):
                errors.append({"stage": index,
                               "reason": "result recognition lacked a native unary readiness token"})
            if None not in (completion, progress_unpack, advance) and not (
                    completion["step"] < progress_unpack["step"] < advance["step"]):
                errors.append({"stage": index,
                               "reason": "advance did not follow original result recognition and progress extraction"})
            stage_joins = [event for event in events
                           if event["kind"] == "argument-join" and event.get("stage") == index]
            stage_joins = [event for event in stage_joins
                           if "".join(sorted(event["kinds"])) == "gg"]
            if len(stage_joins) != expected_joins or any(
                    event["step"] >= advance["step"] for event in stage_joins):
                errors.append({"stage": index,
                               "reason": "original unary arguments were not joined before advance"})
        elif expected_stage["_skip_ready"] not in advance["pair"]:
            errors.append({"stage": index,
                               "reason": "skip did not consume its native recovery token"})
        previous_advance = advance["step"]

    for retained in retained_ids:
        consumed = [event for event in events if retained in event["pair"]]
        if len(consumed) != 1:
            errors.append({"reason": "retained control component was not consumed exactly once"})
    return errors


def _allocation_profile(census):
    result = Counter({kind: 0 for kind in ("d", "e", "g")})
    for kinds, (rhs, _) in RULES.items():
        result.update({kind: census["".join(kinds)] * amount
                       for kind, amount in Counter(rhs.values()).items()})
    return dict(result)


def _kind_balance(syntax, census, running):
    predicted = Counter(syntax.kinds)
    for kinds, (rhs, _) in RULES.items():
        count = census["".join(kinds)]
        predicted.update({kind: count * value for kind, value in Counter(rhs.values()).items()})
        predicted.subtract({kind: count * value for kind, value in Counter(kinds).items()})
    allocated = _allocation_profile(census)
    if predicted != Counter(running.nodes.values()):
        raise AssertionError("kind-wise primitive allocation balance failed")
    if sum(allocated.values()) != running._allocated:
        raise AssertionError("runtime allocation accounting failed")


def run_case(built, target, trace, schedule, *, budget=None, budget_kind="execution",
             expected_states=None, return_pairs=False):
    """Execute one prewired network under an explicit primitive schedule."""
    if not isinstance(schedule, Schedule):
        raise TypeError("schedule must be a Schedule")
    if schedule.policy == "witness":
        raise ValueError("normal execution requires fifo, lifo or seeded policy")
    limits = _budget(budget, budget_kind)
    if expected_states is not None and (
            not isinstance(expected_states, (list, tuple))
            or len(expected_states) != len(built.stages)
            or any(type(state) is not bool for state in expected_states)):
        raise ValueError("expected_states must be one Boolean per stage")
    syntax = GraphSpec.from_net(built.net)
    running = syntax.instantiate(ScheduledNet(schedule))
    renamed = dict(zip(built.net.nodes, running.nodes))
    if set(renamed.values()) != set(running.nodes):
        raise ValueError("initial graph renaming is not bijective")

    watched = defaultdict(list)
    for stage in built.stages:
        index = stage["index"]
        for field, kind in (("grant_receiver", "grant"), ("delivery_gate", "delivery"),
                            ("advance_gate", "advance")):
            if stage.get(field) is None:
                raise ValueError(f"stage {index} lacks {field}")
            watched[renamed[stage[field]]].append((kind, index))
        reader = stage.get("reader") or {}
        for cell in _ensure_list(reader.get("result_completion_gates")):
            watched[renamed[cell]].append(("result-recognition", index))
        for field, kind in (("result_completion_gate", "result-recognition"),
                            ("progress_unpack", "progress-unpack")):
            if stage.get(field) is not None:
                watched[renamed[stage[field]]].append((kind, index))
        for cell in reader.get("join_gates", ()):
            watched[renamed[cell]].append(("argument-join", index))

    frames = {}
    for stage in built.stages:
        index = stage["index"]
        head = stage.get("reader_unpack_head")
        if head is not None:
            frames[index] = tuple(renamed[cell] for cell in trace_frame(built.net, head))
        ready = stage.get("reader_ready_gate")
        if ready is not None:
            watched[renamed[ready]].append(("reader-ready", index))
        component = stage.get("component") or {}
        component_ready = component.get("ready_consumer")
        if component_ready is not None:
            watched[renamed[component_ready]].append(("component-ready", index))
        unpack_cells = component.get("unpack_cells")
        if unpack_cells:
            frames[("component", index)] = tuple(renamed[cell] for cell in unpack_cells)

    categories = {}
    for cell, label in getattr(built, "initial_categories", {}).items():
        categories[renamed[cell]] = label
    if categories and set(categories) != set(running.nodes):
        raise ValueError("initial resource categories do not cover the whole network")
    if categories:
        running.begin_audit(categories)

    start, steps, events, pairs = trace.count, 0, [], []
    while True:
        if len(running.nodes) > limits["max_cells"]:
            status = "resource-violation"
            break
        pair = running.next_active()
        if pair is None:
            status = "passed" if port_graph_isomorphic(running, target) else "wrong-normal-form"
            break
        if steps >= limits["max_steps"]:
            status = "incomplete"
            break
        for cell in pair:
            for kind, index in watched.get(cell, ()):
                event = {"kind": kind, "stage": index, "step": steps,
                         "pair": list(pair), "kinds": [running.nodes[c] for c in pair]}
                if kind == "reader-ready" and index in frames:
                    event["frame_cells_remaining"] = [cell_id for cell_id in frames[index]
                                                      if cell_id in running.nodes]
                if kind == "component-ready" and ("component", index) in frames:
                    event["frame_cells_remaining"] = [cell_id for cell_id
                                                      in frames[("component", index)]
                                                      if cell_id in running.nodes]
                events.append(event)
        if return_pairs:
            pairs.append(pair)
        trace.record(pair)
        running.reduce(*pair)
        steps += 1

    resources = running.statistics()
    if status == "passed":
        _kind_balance(syntax, resources["rule_census"], running)
    if status == "passed":
        stages = []
        for stage_index, stage in enumerate(built.stages):
            renamed_stage = dict(stage)
            if stage.get("incoming_packet") is not None:
                renamed_stage["incoming_packet"] = renamed[stage["incoming_packet"]]
            if expected_states is not None:
                renamed_stage["enabled"] = bool(expected_states[stage_index])
            else:
                renamed_stage["enabled"] = any(
                    e["stage"] == stage["index"] and e["kind"] == "result-recognition"
                    and sorted(e["kinds"]) == ["g", "g"] for e in events)
            reader = dict(stage.get("reader") or {})
            for field in ("ready_emitters", "join_gates"):
                reader[field] = [renamed[cell] for cell in reader.get(field, ())]
            if reader.get("result_completion_by_symbol") is not None:
                reader["result_completion_by_symbol"] = {
                    symbol: renamed[cell] for symbol, cell in
                    reader["result_completion_by_symbol"].items()
                }
            if reader.get("progress_ready_tokens") is not None:
                reader["progress_ready_tokens"] = {
                    symbol: renamed[cell] for symbol, cell in reader["progress_ready_tokens"].items()}
            renamed_stage["reader"] = reader
            renamed_stage["_skip_ready"] = renamed[stage["skip_ready"]]
            stages.append(renamed_stage)
        protocol = validate_protocol(stages, events,
                                     retained_ids=[renamed[cell] for cell in
                                                   _ensure_list(getattr(built, "retained_ids", ()))])
    else:
        protocol = []
    if status == "passed" and protocol:
        status = "protocol-violation"
    tracked_ids = set(_ensure_list(getattr(built, "source_ids", ())))
    tracked_ids.update(_ensure_list(getattr(built, "program_ids", ())))
    source_ids = {renamed[cell] for cell in tracked_ids}
    source_consumed = not bool(source_ids & set(running.nodes))
    if status == "passed" and not source_consumed:
        status = "source-cells-survived"
    final = GraphSpec.from_net(running).to_dict()
    record = {"status": status, "schedule": schedule.to_dict(),
              "trace_offset_records": start, "primitive_interactions": steps,
              "initial_cells": len(built.net.nodes),
              "initial_graph_sha256": _spec_digest(syntax),
              "resources": {**resources,
                            "rhs_allocations_by_kind": _allocation_profile(resources["rule_census"]),
                            "initial_categories": dict(Counter(categories.values()))},
              "events": events, "protocol_violations": protocol,
              "terminal": not bool(running.active()),
              "whole_graph_matches_reference": port_graph_isomorphic(running, target),
              "final_graph_sha256": _spec_digest(final),
              "expected_graph_sha256": _spec_digest(GraphSpec.from_net(target)),
              "source_cells_consumed": source_consumed}
    if status != "passed":
        record["final_graph"] = final
        record["counterexample"] = {"initial": syntax.to_dict(),
                                    "expected": GraphSpec.from_net(target).to_dict(),
                                    "actual": final, "reason": status}
    return (record, pairs) if return_pairs else record


def _spec_digest(spec):
    from ic_coherent_feedback import spec_digest
    return spec_digest(spec.to_dict() if isinstance(spec, GraphSpec) else spec)
