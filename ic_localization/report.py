"""Exact finite minimax search and independent reconstruction of M7 archives."""
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
import math
from pathlib import Path
from time import perf_counter

from ic_coherent_feedback import read_json, spec_digest
from ic_schedule_audit import ScheduleTrace
from .evidence import (ROOT, VERSION, POLICIES, frozen_bindings, foundation_evidence,
                       negative_evidence, expected_value, run_network)
from .model import ChainProblem, Transform, enumerate_transforms, compile_transform, build_network, reference

FREEZE = ROOT / "docs/M7_FREEZE.json"


def canonical_transform(transform):
    return json.dumps(transform.to_dict(), sort_keys=True, separators=(",", ":"))


def _candidate(job):
    n, description = job
    problem, transform = ChainProblem(n), Transform.from_dict(description)
    start = perf_counter()
    compiled = compile_transform(problem, transform)
    host = {"compile": perf_counter()-start, "construction": 0.0, "reference": 0.0,
            "native_execution": 0.0, "validation": 0.0}
    records = []
    for index, bits in enumerate(problem.inputs()):
        start = perf_counter()
        initial = build_network(problem, transform, bits, compiled=compiled)
        host["construction"] += perf_counter()-start
        start = perf_counter()
        truth = reference(problem, bits)
        target = expected_value(truth)
        host["reference"] += perf_counter()-start
        record = run_network(initial, target)
        for key, elapsed in record.pop("host_seconds").items():
            host[key] += elapsed
        record.update(input_index=index, reference=truth)
        records.append(record)
    complete = all(r["status"] == "passed" for r in records)
    return {"transform": description, "status": "complete" if complete else "incomplete",
            "worst_fifo_interactions": max(r["resources"]["primitive_interactions"] for r in records) if complete else None,
            "observed_work_lower_bound": max(r["resources"]["primitive_interactions"] for r in records),
            "host_seconds": host, "algebra_operations": compiled.operation_counts,
            "records": records}


def summarize(candidates):
    complete = [c for c in candidates if c["status"] == "complete"]
    best = min((c["worst_fifo_interactions"] for c in complete), default=None)
    winners = sorted((c["transform"] for c in complete if c["worst_fifo_interactions"] == best),
                     key=lambda d: canonical_transform(Transform.from_dict(d)))
    return {"status": "class-optimal" if len(complete) == len(candidates) else "best-known",
            "minimum_worst_fifo_interactions": best, "optimal_transforms": winners,
            "representative": winners[0] if winners else None,
            "completed_candidates": len(complete), "total_candidates": len(candidates),
            "unfinished": [c["transform"] for c in candidates if c["status"] != "complete"]}


def semantic(value):
    """Wall time is observed host work, never a replay equality obligation."""
    if isinstance(value, dict):
        return {k: semantic(v) for k, v in value.items() if k != "host_seconds"}
    if isinstance(value, (list, tuple)):
        return [semantic(v) for v in value]
    return value


def same_evidence(claimed, actual):
    """Compare typed JSON fields and validate the shape of measured timings."""
    if isinstance(actual, dict):
        if not isinstance(claimed, dict) or claimed.keys() != actual.keys():
            return False
        for key, value in actual.items():
            if key == "host_seconds":
                times = claimed[key]
                if (not isinstance(times, dict) or times.keys() != value.keys()
                        or not all(type(t) in (int, float) and 0 <= t < math.inf for t in times.values())):
                    return False
            elif not same_evidence(claimed[key], value):
                return False
        return True
    if isinstance(actual, (list, tuple)):
        return isinstance(claimed, (list, tuple)) and len(claimed) == len(actual) and all(
            same_evidence(a, b) for a, b in zip(claimed, actual))
    return type(claimed) is type(actual) and claimed == actual


def _suite(trace_path, *, replay=False, workers=1):
    start = perf_counter()
    bound = frozen_bindings()
    if not same_evidence(read_json(FREEZE), bound):
        raise ValueError("implementation, grammar or input manifest differs from M7 pre-search freeze")
    metadata = {"scope": VERSION, "bindings_sha256": spec_digest(bound)}
    trace = ScheduleTrace(trace_path, metadata, replay=replay)
    try:
        foundation = foundation_evidence(trace)
        negative = negative_evidence(trace)
        problems = []
        for n in (2, 3):
            problem = ChainProblem(n)
            transforms = list(enumerate_transforms(problem))
            jobs = [(n, t.to_dict()) for t in transforms]
            if workers > 1:
                with ProcessPoolExecutor(max_workers=workers) as pool:
                    candidates = list(pool.map(_candidate, jobs))
            else:
                candidates = [_candidate(job) for job in jobs]
            summary = summarize(candidates)
            print("SEARCH", n, len(candidates), summary["status"], summary["minimum_worst_fifo_interactions"], flush=True)
            selected = [t for t in transforms if t.kind == "direct"]
            if summary["representative"] is not None:
                winner = Transform.from_dict(summary["representative"])
                if winner not in selected:
                    selected.append(winner)
            archives = []
            for transform in selected:
                compiled = compile_transform(problem, transform)
                searched = next(c for c in candidates if c["transform"] == transform.to_dict())["records"]
                for policy in POLICIES:
                    runs = []
                    for index, bits in enumerate(problem.inputs()):
                        initial = build_network(problem, transform, bits, compiled=compiled)
                        record = run_network(initial, expected_value(reference(problem, bits)), policy, trace=trace)
                        record["input_index"] = index
                        if policy.policy == "fifo":
                            for key in ("status", "initial_graph_sha256", "final_graph_sha256", "resources"):
                                if record[key] != searched[index][key]:
                                    raise ValueError("archived FIFO run differs from the original candidate search")
                        runs.append(record)
                    archives.append({"transform": transform.to_dict(), "schedule": policy.to_dict(),
                                     "worst_interactions": max(r["resources"]["primitive_interactions"] for r in runs),
                                     "records": runs})
                print("ARCHIVE", n, canonical_transform(transform), flush=True)
            counterexamples = []
            for candidate in candidates:
                if candidate["status"] == "complete":
                    continue
                transform = Transform.from_dict(candidate["transform"])
                compiled = compile_transform(problem, transform)
                for record, bits in zip(candidate["records"], problem.inputs()):
                    if record["status"] != "passed":
                        witness = run_network(build_network(problem, transform, bits, compiled=compiled),
                                              expected_value(reference(problem, bits)), trace=trace)
                        counterexamples.append({"transform": transform.to_dict(),
                                                "input_index": record["input_index"], "run": witness})
            problems.append({"n": n, "candidates": candidates, "optimization": summary,
                             "archives": archives, "counterexamples": counterexamples})
    except BaseException:
        trace.abort()
        raise
    trace_summary = trace.close()
    checks = sum(len(c["records"]) for p in problems for c in p["candidates"])
    if checks != 101504:
        raise ValueError("incomplete frozen candidate/input matrix")
    accepted = (all(r["status"] == "passed" for r in foundation)
                and all(p["optimization"]["status"] == "class-optimal" for p in problems)
                and all(r["status"] == "passed" for p in problems for a in p["archives"] for r in a["records"])
                and [negative[k]["status"] for k in negative] ==
                    ["wrong-normal-form", "incomplete", "resource-exhausted", "wrong-normal-form",
                     "precondition-rejected", "precondition-rejected"])
    return {"contract": VERSION, "bindings": bound, "bindings_sha256": spec_digest(bound),
            "implementation_status": "accepted" if accepted else "not-accepted",
            "fifo_candidate_input_checks": checks, "foundation": foundation,
            "negative": negative, "problems": problems, "trace": trace_summary,
            "host_seconds": {"search_and_archive_total": perf_counter()-start},
            "claim_scope": "declared raw candidates, exhaustive Boolean inputs, fixed FIFO only; no universal optimality or automatic savings claim"}


def generate(report_path, trace_path, *, workers=1):
    path = Path(report_path)
    if path.resolve() == Path(trace_path).resolve():
        raise ValueError("report and trace must be separate files")
    report = _suite(trace_path, workers=workers)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(report, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(encoded, compresslevel=6, mtime=0) if path.suffix == ".gz" else encoded)
    return report


def verify(report_path, trace_path, *, workers=1):
    claimed = read_json(report_path)
    # Reconstruct the entire manifest and rerun every candidate, not only winners.
    actual = _suite(trace_path, replay=True, workers=workers)
    if not same_evidence(claimed, actual):
        raise ValueError("M7 report differs from independently rebuilt complete evidence")
    return actual
