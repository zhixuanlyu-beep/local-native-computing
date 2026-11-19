"""Independently check the coverage, incumbent history, and FIFO witnesses."""

import math
from time import perf_counter

from ic_coherent_feedback import spec_digest
from ic_localization.report import same_evidence

import ic_m10_core as core
import ic_m10_search as search


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(claimed, actual, message):
    require(same_evidence(claimed, actual), message)


def fields(value, expected, message):
    require(isinstance(value, dict) and value.keys() == set(expected), message)


def times(value, expected):
    fields(value, expected, "missing host timing measurement")
    require(all(type(t) in (int, float) and 0 <= t < math.inf for t in value.values()),
            "invalid host timing measurement")


def ordered_rows(rows, candidates):
    require(isinstance(rows, list) and len(rows) == len(candidates), "candidate coverage differs from freeze")
    for row, candidate in zip(rows, candidates, strict=True):
        require(isinstance(row, dict), "candidate row must be an object")
        same(row.get("candidate"), candidate["id"], "candidate omitted, substituted, or reordered")
        yield row, candidate


def ordered_records(records, inputs):
    require(isinstance(records, list) and len(records) <= len(inputs), "input coverage exceeds freeze")
    for index, record in enumerate(records):
        require(isinstance(record, dict), "input evidence must be an object")
        same(record.get("input_index"), index, "input evidence omitted, repeated, or reordered")
        same(record.get("bits"), inputs[index], "input evidence differs from frozen search or holdout slots")
        yield index, record


def _summary(costs, unresolved):
    best = min(costs.values(), default=None)
    return {
        "status": "incomplete" if not costs else "best-known" if unresolved else "exact",
        "best_known_worst_fifo_interactions": best,
        "winners": [candidate for candidate, cost in costs.items() if cost == best],
        "unresolved_candidates": unresolved,
    }


def _holdout_winner(summary, candidates):
    winners = set(summary["winners"])
    return min((candidate for candidate in candidates if candidate["id"] in winners),
               key=lambda candidate: candidate["canonical"], default=None)


def _checked_upper(certificate, current):
    require(current is not None, "exclusion has no earlier fully verified upper bound")
    same(certificate["upper"], current,
         "exclusion upper bound differs from the earlier fully verified incumbent")
    return current["cost"]


def _strict_static(initial_live, reference_live, upper):
    return (max(initial_live - reference_live, 0) + 1) // 2 > upper


def _check_static(lower, initial_live, reference_live, upper):
    same(lower, (max(initial_live - reference_live, 0) + 1) // 2, "incorrect live-cell lower bound")
    require(_strict_static(initial_live, reference_live, upper), "static exclusion must strictly exceed the upper bound")


def _check_prefix(steps, peak, upper, budget):
    same(steps, upper + 1, "FIFO prefix must strictly exceed the upper bound")
    require(steps <= budget["max_steps"] and peak <= budget["max_cells"],
            "FIFO prefix exceeds the frozen execution budget")


def _execution(record, *, include_limit=False):
    """Compare execution evidence across caps after checking the cap itself."""
    return record if include_limit else {key: value for key, value in record.items() if key != "step_limit"}


def _replay_input(topology, candidate, inputs, index, budget, limit=None):
    prepared = core.prepare_candidate(candidate["transform"], topology)
    return search.evaluate_input(candidate, prepared, inputs[index], index, budget,
                                 step_limit=limit, engine="python")


def _verify_exclusion(topology, row, candidate, inputs, budget, incumbent, index):
    decision = row["decision"]
    evidence = row["evidence"]
    fields(decision, ("reason", "witness_input_index", "witness_bits", "upper_bound", "lower_bound", "step_limit"),
           "invalid exclusion decision fields")
    fields(evidence, ("initial_graph_sha256", "initial_live_cells", "reference_live_cells",
                      "reference_graph_sha256", "prefix"),
           "invalid exclusion proof fields")
    upper = _checked_upper(row, incumbent)
    require(0 <= index < len(inputs), "exclusion witness lies outside the search domain")
    same(decision["witness_input_index"], index, "exclusion witness skipped a preceding input")
    same(decision["witness_bits"], inputs[index], "exclusion witness differs from frozen search input")
    same(decision["upper_bound"], upper, "invalid incumbent cost in exclusion")
    bits = tuple(inputs[index])
    reference = core.expected_value(core.reference(bits, topology))
    graph = core.build_network(candidate["transform"], bits, topology=topology)
    initial_live, reference_live = len(graph.kinds), len(reference.kinds)
    same(evidence["initial_graph_sha256"], core.graph_digest(graph), "exclusion has a changed graph digest")
    same(evidence["reference_graph_sha256"], core.graph_digest(reference), "exclusion has a changed reference graph digest")
    same(evidence["initial_live_cells"], initial_live, "exclusion has a changed initial live-cell count")
    same(evidence["reference_live_cells"], reference_live, "exclusion has a changed reference live-cell count")
    if decision["reason"] == "static-live-bound":
        _check_static(decision["lower_bound"], initial_live, reference_live, upper)
        same(decision["step_limit"], None, "static exclusion unexpectedly has a FIFO cap")
        same(evidence["prefix"], None, "static exclusion unexpectedly has FIFO evidence")
    else:
        same(decision["reason"], "prefix-above-upper", "unknown exclusion reason")
        require(not _strict_static(initial_live, reference_live, upper), "FIFO witness bypassed a static exclusion")
        same(decision["step_limit"], upper + 1, "invalid FIFO witness cap")
        same(decision["lower_bound"], upper + 1, "invalid FIFO lower bound")
        claimed = row["records"][index]
        actual = _replay_input(topology, candidate, inputs, index, budget, upper + 1)
        _check_prefix(actual["steps"], actual["peak_live_cells"], upper, budget)
        same(_execution(claimed, include_limit=True), _execution(actual, include_limit=True),
             "exclusion FIFO prefix disagrees with Python replay")
        same(evidence["prefix"], actual, "exclusion proof differs from its FIFO witness")


def _verify_certificate(topology, group, candidates, inputs, budget, baseline):
    _group_fields(group)
    incumbent = None
    costs = {}
    unresolved = []
    for row, candidate in ordered_rows(group["candidates"], candidates):
        fields(row, ("candidate", "status", "cost", "records", "compiled_ir_sha256", "upper", "decision", "evidence"),
               "invalid certificate candidate fields")
        identifier = candidate["id"]
        baseline_row = baseline[identifier]
        same(row["compiled_ir_sha256"], baseline_row["compiled_ir_sha256"], "candidate changed its compiled IR")
        same(row["upper"], incumbent, "row upper bound differs from the preceding fully verified winner")
        records = row["records"]
        require(isinstance(records, list), "candidate input evidence must be a list")
        decision = row["decision"]
        excluded = row["status"] == "excluded"
        require(not excluded or isinstance(decision, dict), "exclusion has no decision")
        reason = decision.get("reason") if excluded else None
        witness_index = len(records) - (reason == "prefix-above-upper")
        upper = incumbent["cost"] if incumbent is not None else None
        limit = None if upper is None else upper + 1
        for index, record in ordered_records(records, inputs):
            same(record.get("step_limit"), limit, "FIFO replay cap differs from the incumbent")
            if excluded and index == witness_index:
                continue
            full_record = baseline_row["records"][index]
            same(_execution(record), _execution(full_record), "certificate input differs from full FIFO replay")
            if upper is not None:
                require(not _strict_static(record["initial_live_cells"], record["reference_live_cells"], upper),
                        "certificate search skipped an earlier static witness")
                if record["status"] != "resource-exhausted":
                    require(record["steps"] <= upper, "certificate search skipped an earlier FIFO witness")
            if record["status"] != "passed":
                require(not excluded and index == len(records) - 1,
                        "certificate search passed an earlier failure")
                actual = _replay_input(topology, candidate, inputs, index, budget, limit)
                same(_execution(record, include_limit=True), _execution(actual, include_limit=True),
                     "negative witness differs from Python FIFO replay")

        if excluded:
            _verify_exclusion(topology, row, candidate, inputs, budget, incumbent, witness_index)
            status, cost = "excluded", None
        else:
            same(decision, None, "candidate without an exclusion has an unexpected decision")
            same(row["evidence"], None, "candidate without an exclusion has unexpected proof data")
            require(bool(records), "candidate has no verified inputs or exclusion")
            outcome = records[-1]["status"]
            cost = None
            if outcome == "passed":
                require(len(records) == len(inputs), "upper bound requires every frozen input to be correct")
                status, cost = "complete", max(record["steps"] for record in records)
                costs[identifier] = cost
                if incumbent is None or cost < incumbent["cost"]:
                    incumbent = {"candidate": identifier, "cost": cost, "records_sha256": spec_digest(records)}
            elif outcome == "wrong-normal-form":
                status = "incorrect"
            else:
                status = "unresolved"
                unresolved.append(identifier)
        same(row["status"], status, "candidate status disagrees with its input evidence")
        same(row["cost"], cost, "candidate cost disagrees with its complete inputs")
    summary = _summary(costs, unresolved)
    same(group["summary"], summary, "certificate optimum or tie set differs from the ordered proof")
    same(group["metrics"], search.group_metrics(group["candidates"]), "incorrect certificate work accounting")
    return summary


def _group_fields(group):
    fields(group, ("candidates", "summary", "metrics", "engine", "host_seconds"), "invalid group fields")
    require(group["engine"] in ("python", "native-c"), "unknown execution backend")
    times(group["host_seconds"], ("compile", "construction", "execution", "total"))


def _group_evidence(group):
    return {key: value for key, value in group.items() if key != "engine"}


def _verify_full(topology, group, candidates, inputs, budget, *, replay):
    _group_fields(group)
    costs, unresolved, baseline = {}, [], {}
    for row, candidate in ordered_rows(group["candidates"], candidates):
        fields(row, ("candidate", "status", "cost", "records", "compiled_ir_sha256"), "invalid exhaustive candidate fields")
        identifier = candidate["id"]
        records = row["records"]
        require(isinstance(records, list) and len(records) == len(inputs), "exhaustive candidate omitted a frozen case")
        outcomes = set()
        for index, record in ordered_records(records, inputs):
            same(record.get("step_limit"), None, "exhaustive evaluation unexpectedly used a tighter cap")
            outcome = record.get("status")
            require(outcome in ("passed", "wrong-normal-form", "incomplete", "resource-exhausted"),
                    "unknown FIFO execution outcome")
            same(record.get("whole_graph_matches_reference"), outcome == "passed", "terminal match disagrees with status")
            outcomes.add(outcome)
            if outcome != "passed":
                actual = _replay_input(topology, candidate, inputs, index, budget)
                same(record, actual, "exhaustive negative witness differs from Python FIFO replay")
        status = "complete" if outcomes == {"passed"} else "incorrect" if "wrong-normal-form" in outcomes else "unresolved"
        cost = None
        if status == "complete":
            cost = max(record["steps"] for record in records)
            costs[identifier] = cost
        elif status == "unresolved":
            unresolved.append(identifier)
        same(row["status"], status, "exhaustive candidate status disagrees with case evidence")
        same(row["cost"], cost, "exhaustive candidate cost disagrees with the verified inputs")
        baseline[identifier] = row
    same(group["summary"], _summary(costs, unresolved), "exhaustive optimum or tie set changed")
    same(group["metrics"], search.group_metrics(group["candidates"]), "incorrect exhaustive work accounting")
    if replay:
        actual = search.compute_full_enumeration(topology, candidates, inputs, budget, progress=True)
        same(_group_evidence(group), _group_evidence(actual), "exhaustive evidence differs from fresh FIFO replay")
        baseline = {row["candidate"]: row for row in actual["candidates"]}
    return baseline


def verify_topology(job_and_claim):
    job, claim, replay_full = job_and_claim
    topology, candidates, inputs, holdout, budget = job
    times = {}
    started = perf_counter()
    fields(claim, ("id", "full_enumeration", "certificate", "holdout"), "invalid topology evidence fields")
    same(claim["id"], topology, "topology omitted, substituted, or reordered")
    for group in (claim["full_enumeration"], claim["certificate"]):
        _group_fields(group)
        # Reject missing or changed candidate IDs before running the large matrix.
        list(ordered_rows(group["candidates"], candidates))
    require({tuple(bits) for bits in inputs}.isdisjoint(map(tuple, holdout)), "holdout input entered search")

    phase_start = perf_counter()
    baseline = _verify_full(topology, claim["full_enumeration"], candidates, inputs, budget, replay=replay_full)
    times["full_enumeration"] = perf_counter() - phase_start
    phase_start = perf_counter()
    summary = _verify_certificate(topology, claim["certificate"], candidates, inputs, budget, baseline)
    times["certificate"] = perf_counter() - phase_start
    phase_start = perf_counter()
    winner = _holdout_winner(summary, candidates)
    holdout_claim = claim["holdout"]
    fields(holdout_claim, ("candidate", "all_correct", "worst_fifo_interactions", "records", "metrics", "engine", "host_seconds"),
           "invalid holdout evidence fields")
    require(holdout_claim["engine"] in ("python", "native-c"), "unknown holdout execution backend")
    times["holdout"] = perf_counter() - phase_start
    phase_start = perf_counter()
    actual = search.run_holdout(topology, winner, holdout, budget)
    same(_group_evidence(holdout_claim), _group_evidence(actual), "holdout winner or evidence differs from FIFO replay")
    times["holdout"] += perf_counter() - phase_start
    times["total"] = perf_counter() - started
    return {"id": topology, "host_seconds": times}


def acceptance(topologies):
    accepted = all(
        row["full_enumeration"]["summary"]["status"] == "exact"
        and row["certificate"]["summary"]["status"] == "exact"
        and same_evidence(row["full_enumeration"]["summary"], row["certificate"]["summary"])
        and row["holdout"]["all_correct"]
        for row in topologies
    )
    return "accepted" if accepted else "not-accepted"


def validate_report(report, bindings, version, matrix_checks):
    fields(report, ("contract", "freeze_sha256", "candidate_input_checks", "topologies",
                    "implementation_status", "host_seconds", "verification"), "invalid report fields")
    same(report["contract"], version, "wrong report contract")
    same(report["freeze_sha256"], spec_digest(bindings), "report does not bind the M10 freeze")
    same(report["candidate_input_checks"], matrix_checks, "invalid full-enumeration coverage claim")
    times(report["host_seconds"], ("experiment",))
    topologies = report["topologies"]
    require(isinstance(topologies, list) and len(topologies) == len(bindings["topologies"]),
            "topology coverage differs from freeze")
    for row, topology in zip(topologies, bindings["topologies"], strict=True):
        fields(row, ("id", "full_enumeration", "certificate", "holdout"), "invalid topology evidence fields")
        same(row["id"], topology["id"], "topology omitted, substituted, or reordered")
    verification = report["verification"]
    fields(verification, ("topologies", "host_seconds"), "invalid independent verification measurements")
    times(verification["host_seconds"], ("total",))
    measurements = verification["topologies"]
    require(isinstance(measurements, list) and len(measurements) == len(topologies),
            "missing independent verification measurements")
    for measurement, row in zip(measurements, topologies, strict=True):
        fields(measurement, ("id", "host_seconds"), "invalid topology verification measurement")
        same(measurement["id"], row["id"], "independent verification measurement reordered")
        times(measurement["host_seconds"], ("total", "full_enumeration", "certificate", "holdout"))
    require(report["implementation_status"] in ("accepted", "not-accepted"), "invalid M10 acceptance claim")
