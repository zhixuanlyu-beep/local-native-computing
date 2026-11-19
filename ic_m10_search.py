"""Execute the ordered exhaustive and certificate searches for M10."""

from functools import lru_cache
import os
from time import perf_counter

from ic_coherent_feedback import spec_digest
from ic_coherent_output_decoder import port_graph_isomorphic
from ic_m9_accel import run_native
from ic_m9_core import run_network
from ic_research_artifacts import GraphSpec

import ic_m10_core as core


TERMINAL = {"passed", "wrong-normal-form"}


@lru_cache(maxsize=2)
def _expected(reference):
    return core.expected_value(reference)


def _engine():
    return "native-c" if os.environ.get("IC_M9_NATIVE_LIBRARY") else "python"


def _endpoint_key(endpoint):
    if endpoint[0] == "F":
        return (-1, endpoint[1])
    return (endpoint[0], endpoint[1])


def _final_digest(graph):
    # The result does not seed another FIFO run. Normalize edge order, since
    # Python and C can enumerate the same output edges in different orders.
    graph = graph.to_dict()
    for wire in graph["wires"]:
        wire.sort(key=_endpoint_key)
    graph["wires"].sort(key=lambda wire: tuple(map(_endpoint_key, wire)))
    return spec_digest(graph)


def _evaluate(graph, graph_sha256, reference, expected, bits, index, budget, step_limit, engine):
    limits = dict(budget)
    if step_limit is not None:
        limits["max_steps"] = min(step_limit, limits["max_steps"])
    if engine == "auto":
        engine = _engine()
    if engine == "native-c":
        result = run_native(graph, budget=limits)
        if result is None:
            raise ValueError("C FIFO requested without IC_M9_NATIVE_LIBRARY")
        status = result["status"]
        final = result["graph"]
        matches = status == "passed" and port_graph_isomorphic(final.instantiate(), expected.instantiate())
        if status == "passed" and not matches:
            status = "wrong-normal-form"
        steps, peak, census = result["steps"], result["peak"], result["rule_census"]
    elif engine == "python":
        result = run_network(graph, expected, budget=limits)
        status = result["status"]
        final = GraphSpec.from_dict(result["final_graph"])
        matches = status == "passed"
        resources = result["resources"]
        steps, peak, census = resources["primitive_interactions"], resources["peak_live_cells"], resources["rule_census"]
    else:
        raise ValueError("unknown M10 FIFO engine")
    return {
        "input_index": index, "bits": list(bits), "reference": reference,
        "status": status, "steps": steps, "step_limit": step_limit,
        "peak_live_cells": peak, "initial_live_cells": len(graph.kinds),
        "reference_live_cells": len(expected.kinds), "initial_graph_sha256": graph_sha256,
        "final_graph_sha256": _final_digest(final), "whole_graph_matches_reference": matches,
        "rule_census": census,
    }


def _build(candidate, prepared, bits):
    topology = prepared["problem"].topology
    return core.build_network(candidate["transform"], tuple(bits), topology=topology,
                              compiled=prepared["compiled"])


def evaluate_input(candidate, prepared, bits, index, budget, *, step_limit=None, engine="auto"):
    """Build and execute one explicitly supplied case for a prepared candidate."""
    reference = core.reference(tuple(bits), prepared["problem"].topology)
    initial = _build(candidate, prepared, bits)
    return _evaluate(initial, core.graph_digest(initial), reference, _expected(reference), bits, index,
                     budget, step_limit, engine)


def _exclusion(reason, index, bits, upper, lower, limit, graph_sha256, initial, expected, prefix):
    return {
        "reason": reason, "witness_input_index": index, "witness_bits": list(bits),
        "upper_bound": upper, "lower_bound": lower, "step_limit": limit,
    }, {
        "initial_graph_sha256": graph_sha256, "initial_live_cells": len(initial.kinds),
        "reference_live_cells": len(expected.kinds), "reference_graph_sha256": core.graph_digest(expected),
        "prefix": prefix,
    }


def _candidate(topology, candidate, inputs, budget, engine, times, *, certificate=False, incumbent=None):
    started = perf_counter()
    prepared = core.prepare_candidate(candidate["transform"], topology)
    times["compile"] += perf_counter() - started
    upper = incumbent["cost"] if incumbent else None
    limit = None if upper is None else upper + 1
    decision, evidence = None, None
    records = []
    for index, bits in enumerate(inputs):
        started = perf_counter()
        reference = core.reference(tuple(bits), topology)
        expected = _expected(reference)
        initial = _build(candidate, prepared, bits)
        graph_sha256 = core.graph_digest(initial)
        times["construction"] += perf_counter() - started
        lower = (max(len(initial.kinds) - len(expected.kinds), 0) + 1) // 2
        if upper is not None and lower > upper:
            decision, evidence = _exclusion("static-live-bound", index, bits, upper, lower, None,
                                            graph_sha256, initial, expected, None)
            break
        started = perf_counter()
        record = _evaluate(initial, graph_sha256, reference, expected, bits, index, budget, limit, engine)
        times["execution"] += perf_counter() - started
        records.append(record)
        if limit is not None and record["steps"] == limit and record["status"] != "resource-exhausted":
            decision, evidence = _exclusion("prefix-above-upper", index, bits, upper, limit, limit,
                                            graph_sha256, initial, expected, record)
            break
        if certificate and record["status"] != "passed":
            break
    statuses = {record["status"] for record in records}
    if decision is not None:
        status = "excluded"
    elif "wrong-normal-form" in statuses:
        status = "incorrect"
    elif statuses == {"passed"} and len(records) == len(inputs):
        status = "complete"
    else:
        status = "unresolved"
    cost = max(record["steps"] for record in records) if status == "complete" else None
    row = {"candidate": candidate["id"], "status": status, "cost": cost, "records": records,
           "compiled_ir_sha256": prepared["compiled_ir_sha256"]}
    if certificate:
        row.update(upper=incumbent, decision=decision, evidence=evidence)
    return row


def summary(rows):
    complete = [row for row in rows if row["status"] == "complete"]
    unresolved = [row["candidate"] for row in rows if row["status"] == "unresolved"]
    best = min((row["cost"] for row in complete), default=None)
    return {
        "status": "incomplete" if best is None else "best-known" if unresolved else "exact",
        "best_known_worst_fifo_interactions": best,
        "winners": [row["candidate"] for row in complete if row["cost"] == best],
        "unresolved_candidates": unresolved,
    }


def group_metrics(rows):
    metrics = dict.fromkeys(("candidate_visits", "compile_calls", "graph_constructions", "execution_calls",
                             "complete_input_checks", "fifo_steps", "static_certificates",
                             "prefix_certificates", "incorrect_candidates", "unresolved_candidates"), 0)
    for row in rows:
        records = row["records"]
        reason = row["decision"]["reason"] if row.get("decision") else None
        static = reason == "static-live-bound"
        prefix = reason == "prefix-above-upper"
        metrics["candidate_visits"] += 1
        metrics["compile_calls"] += 1
        metrics["graph_constructions"] += len(records) + static
        metrics["execution_calls"] += len(records)
        metrics["complete_input_checks"] += sum(record["status"] in TERMINAL for record in records) - (
            prefix and records[-1]["status"] in TERMINAL)
        metrics["fifo_steps"] += sum(record["steps"] for record in records)
        metrics["static_certificates"] += static
        metrics["prefix_certificates"] += prefix
        metrics["incorrect_candidates"] += row["status"] == "incorrect"
        metrics["unresolved_candidates"] += row["status"] == "unresolved"
    return metrics


def _group(topology, candidates, inputs, budget, *, certificate=False, progress=False):
    started = perf_counter()
    times = dict.fromkeys(("compile", "construction", "execution"), 0.0)
    rows = []
    incumbent = None
    engine = _engine()
    for i, candidate in enumerate(candidates, 1):
        row = _candidate(topology, candidate, inputs, budget, engine, times,
                         certificate=certificate, incumbent=incumbent)
        rows.append(row)
        if certificate and row["status"] == "complete" and (incumbent is None or row["cost"] < incumbent["cost"]):
            incumbent = {"candidate": row["candidate"], "cost": row["cost"],
                         "records_sha256": spec_digest(row["records"])}
        if progress and (i % 100 == 0 or i == len(candidates)):
            name = "certificate" if certificate else "exhaustive"
            print(f"M10 {topology} {name}: {i}/{len(candidates)} candidates", flush=True)
    result = {"candidates": rows, "summary": summary(rows), "metrics": group_metrics(rows), "engine": engine}
    result["host_seconds"] = {**times, "total": perf_counter() - started}
    return result


def compute_full_enumeration(topology, candidates, inputs, budget, *, progress=False):
    return _group(topology, candidates, inputs, budget, progress=progress)


def compute_certificates(topology, candidates, inputs, budget, *, progress=False):
    return _group(topology, candidates, inputs, budget, certificate=True, progress=progress)


def run_holdout(topology, winner, inputs, budget):
    group = _group(topology, [winner] if winner is not None else [], inputs, budget)
    row = group["candidates"][0] if winner is not None else None
    return {"candidate": row["candidate"] if row else None,
            "all_correct": bool(row and row["status"] == "complete"),
            "worst_fifo_interactions": max((record["steps"] for record in row["records"]), default=None) if row else None,
            "records": row["records"] if row else [], "metrics": group["metrics"],
            "engine": group["engine"], "host_seconds": group["host_seconds"]}


def run_topology(job):
    topology, candidates, inputs, holdouts, budget = job
    full = compute_full_enumeration(topology, candidates, inputs, budget, progress=True)
    certificates = compute_certificates(topology, candidates, inputs, budget, progress=True)
    winners = set(certificates["summary"]["winners"])
    winner = min((candidate for candidate in candidates if candidate["id"] in winners),
                 key=lambda candidate: candidate["canonical"], default=None)
    holdout = run_holdout(topology, winner, holdouts, budget)
    return {"id": topology, "full_enumeration": full, "certificate": certificates, "holdout": holdout}
