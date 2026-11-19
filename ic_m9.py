"""Freeze, run, and independently replay the M9 size-four holdout."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter

from ic_coherent_feedback import read_json, spec_digest
from ic_localization.evidence import BUDGET, ROOT, frozen_bindings as m7_bindings
from ic_localization.report import same_evidence
import ic_m8
import ic_m9_core as core
import ic_m9_search as search


VERSION = "M9-chain-holdout-v1"
FREEZE = ROOT / "docs/M9_FREEZE.json"
REPORT = ROOT / "results/m9_holdout.json.gz"
M8_REPORT = ROOT / "results/m8_concept_library.json.gz"
M8_REPORT_SHA256 = "457b22ac3fa05084afed9883cfd79612918fed518d8ff64e3a58e6a0b75f5693"
MATRIX_CHECKS = 197_120
FULL_COUNT = 16_384
FULL_BATCH = 256
METHODS = ("no-concepts", "abstraction-only", "ranking-only", "abstraction-and-ranking")
SOURCE_FILES = ("ic_m9.py", "ic_m9_core.py", "ic_m9_search.py", "ic_m9_accel.py", "ic_m9_native.c")
PROTECTED = (ic_m8.FREEZE, ic_m8.M7_FREEZE, ic_m8.M7_REPORT, M8_REPORT,
             ROOT / "results/localization.ictrace.gz")


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            if path.suffix == ".gz":
                with gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as zipped:
                    _write_json(zipped, value)
            else:
                _write_json(stream, value)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write_json(stream, value):
    encoder = json.JSONEncoder(separators=(",", ":"), allow_nan=False)
    buffer = []
    for part in encoder.iterencode(value):
        buffer.append(part)
        if len(buffer) == 8192:
            stream.write("".join(buffer).encode("utf-8"))
            buffer.clear()
    stream.write(("".join(buffer) + "\n").encode("utf-8"))


def frozen_bindings():
    """Build the pre-search manifest using inputs and verified M8 evidence only."""
    if sha256(M8_REPORT.read_bytes()).hexdigest() != M8_REPORT_SHA256:
        raise ValueError("M8 concept archive differs from the verified baseline")
    m8 = read_json(M8_REPORT)
    if m8["implementation_status"] != "accepted":
        raise ValueError("M8 concept archive is unavailable or incomplete")
    if m8["m7_baseline"]["bindings_sha256"] != spec_digest(m7_bindings()):
        raise ValueError("M7 implementation differs from the frozen M8 baseline")
    candidates, abstraction = core.candidate_catalog()
    library = m8["library"]
    counts = library["counts"]
    return {"contract": VERSION, "chain_size": 4, "schedule": "fifo", "budget": dict(BUDGET),
            "candidate_input_checks": MATRIX_CHECKS, "full_input_count": FULL_COUNT,
            "full_input_order": "14 Boolean input slots, lexicographic with false before true",
            "objective": "minimum candidate worst complete FIFO interactions on each declared 64-input domain",
            "methods": list(METHODS), "candidates": candidates, "abstraction": abstraction,
            "domains": core.frozen_domains(), "ranking": search.freeze_ranking(library),
            "visit_order_policy": {"raw_baseline": "frozen candidate enumeration order",
                                   "abstract_baseline": "canonical representative description order",
                                   "ranked_paths": "representation, elimination order, materialization; zero internal cost",
                                   "terminal_distance": "117 minus maximum matching conservative saving, zero saving without a match",
                                   "class_distance": "minimum member terminal distance",
                                   "ranked_ties": "canonical description order"},
            "m8": {"contract": m8["contract"], "freeze_sha256": m8["freeze_sha256"],
                   "archive_sha256": M8_REPORT_SHA256, "library_sha256": spec_digest(library),
                   "archive_bytes": M8_REPORT.stat().st_size,
                   "library_serialized_bytes": counts["library_serialized_bytes"],
                   "induced_rules": counts["rules"], "manual_axioms": len(library["manual_axioms"]),
                   "learning_cost": {"candidate_input_checks": m8["counting"]["candidate_input_checks"],
                                     "single_edit_pairs": counts["pairs"],
                                     "compiled_ir_cache_entries": counts["compiled_ir_cache_entries"],
                                     "rule_recognition_host_operations": counts["rule_recognition_host_operations"]}},
            "m7": m8["m7_baseline"],
            "sources": {name: sha256((ROOT / name).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
                        for name in SOURCE_FILES}}


def freeze(path=FREEZE):
    path = Path(path)
    if path.resolve() in {p.resolve() for p in (*PROTECTED, REPORT)}:
        raise ValueError("freeze path collides with prior evidence")
    bindings = frozen_bindings()
    _atomic_json(path, bindings)
    return bindings


def require_frozen(path=FREEZE):
    bindings = frozen_bindings()
    if not same_evidence(read_json(path), bindings):
        raise ValueError("M9 manifest differs from rebuilt candidates, inputs, rules, or source bindings")
    return bindings


def summarize_domain(rows):
    complete = [row for row in rows if row["status"] == "complete"]
    best = min((row["worst_fifo_interactions"] for row in complete), default=None)
    unfinished = [row["candidate"] for row in rows if row["status"] != "complete"]
    exact = bool(rows) and not unfinished
    return {"status": "exact" if exact else "best-known" if complete else "incomplete",
            "exact_target": best if exact else None, "best_known_worst_fifo_interactions": best,
            "winners": [row["candidate"] for row in complete if row["worst_fifo_interactions"] == best],
            "unresolved_candidates": unfinished}


def query_visits(order, query):
    """Issue sequential queries using only the frozen order and single-row query."""
    for candidate in order:
        yield candidate, query(candidate)


def score_search(order, query, target):
    """Apply a target in the scorer, outside the search generator and query."""
    visited = []
    interactions = 0
    selected = None
    evaluation_seconds = 0.0
    for candidate, row in query_visits(order, query):
        visited.append(candidate)
        interactions += row["verification_interactions"]
        evaluation_seconds += sum(row["host_seconds"].values())
        if target is not None and row["status"] == "complete" and row["worst_fifo_interactions"] == target:
            selected = candidate
            break
    return {"status": "target-reached" if selected is not None else "target-not-reached",
            "visited": visited, "visits": len(visited), "selected": selected,
            "verification_interactions": interactions, "compile_calls": len(visited),
            "additional_compile_calls_with_archive": 0,
            "host_seconds": {"attributed_evaluator": evaluation_seconds}}


def _evaluate(job):
    candidate, description, inputs, budget = job
    return {"candidate": candidate, **core.evaluate_candidate(description, inputs, budget)}


def _jobs(bindings, inputs, indices):
    return ((i, bindings["candidates"][i]["transform"], inputs, bindings["budget"]) for i in indices)


def _map(pool, jobs):
    return pool.map(_evaluate, jobs) if pool else map(_evaluate, jobs)


def _matrix(bindings, pool):
    domains = bindings["domains"]
    indices = range(len(bindings["candidates"]))
    # Compile each raw description once for the complete 256-case small matrix.
    inputs = [bits for domain in domains for bits in domain["inputs"]]
    rows_by_domain = [[] for _ in domains]
    for row in _map(pool, _jobs(bindings, inputs, indices)):
        start = 0
        for domain, rows in zip(domains, rows_by_domain, strict=True):
            end = start + len(domain["inputs"])
            records = row["records"][start:end]
            domain_host = _domain_host(row["host_seconds"], row["records"], start, end)
            rows.append(_row(row["candidate"], records, domain_host))
            start = end
        count = row["candidate"] + 1
        if count % 50 == 0 or count == len(indices):
            print(f"M9 small matrix: {count}/{len(indices)} candidates", flush=True)
    return rows_by_domain


def _domain_host(host, records, start, end):
    window = records[start:end]
    return {"compile": host["compile"],
            **{key: sum(record["host_seconds"][key] for record in window)
               for key in window[0]["host_seconds"]}}


def _row(candidate, records, host):
    costs = [record["fifo_interactions"] for record in records]
    failures = [i for i, record in enumerate(records) if record["status"] != "passed"]
    complete = bool(records) and not failures
    return {"candidate": candidate, "status": "complete" if complete else "incomplete",
            "worst_fifo_interactions": max(costs) if complete else None,
            "observed_max_fifo_interactions": max(costs, default=None),
            "verification_interactions": sum(costs), "host_seconds": host,
            "failed_input_indices": failures,
            "records": [{**{k: v for k, v in record.items() if k != "host_seconds"}, "input_index": i}
                        for i, record in enumerate(records)]}


def _domain_results(bindings, rows_by_domain, orders):
    domains = []
    for domain, rows in zip(bindings["domains"], rows_by_domain, strict=True):
        summary = summarize_domain(rows)
        queries = {row["candidate"]: row for row in rows}
        matches = {}
        for method in METHODS:
            order = orders["orders"][method]
            started = perf_counter()
            matches[method] = score_search(order["raw_order"], queries.__getitem__, summary["exact_target"])
            matches[method]["host_seconds"]["query_and_scoring"] = perf_counter() - started
            matches[method]["recognition"] = order["recognition"]
            matches[method]["host_seconds"]["order_preparation"] = order["host_seconds"]["preparation"]
        domains.append({"id": domain["id"], "candidates": rows, "summary": summary, "methods": matches})
    return domains


def _selections(domains):
    return [{"domain": domain["id"], "method": method, "candidate": result["selected"],
             "full_evidence_id": result["selected"]}
            for domain in domains for method, result in domain["methods"].items()]


def _full_replay(bindings, selections, pool):
    full = []
    inputs = list(core.full_domain())
    for candidate in sorted({s["candidate"] for s in selections if s["candidate"] is not None}):
        jobs = ((candidate, bindings["candidates"][candidate]["transform"], inputs[start:start + FULL_BATCH],
                 bindings["budget"]) for start in range(0, FULL_COUNT, FULL_BATCH))
        records = []
        host = {}
        for row in _map(pool, jobs):
            records.extend(row["records"])
            batch_host = _domain_host(row["host_seconds"], row["records"], 0, len(row["records"]))
            for key, value in batch_host.items():
                host[key] = host.get(key, 0) + value
        evidence = _row(candidate, records, host)
        evidence["compile_calls"] = FULL_COUNT // FULL_BATCH
        full.append(evidence)
        print(f"M9 full domain: candidate {candidate}, {len(records)} cases, {evidence['status']}", flush=True)
    return full


def _report(bindings, pool):
    started = perf_counter()
    orders = search.build_orders(bindings["candidates"], bindings["abstraction"], bindings["ranking"])
    domains = _domain_results(bindings, _matrix(bindings, pool), orders)
    checks = sum(len(row["records"]) for domain in domains for row in domain["candidates"])
    if checks != MATRIX_CHECKS:
        raise ValueError("evaluator did not cover all frozen candidate/input combinations")
    selections = _selections(domains)
    full = _full_replay(bindings, selections, pool)
    return {"contract": VERSION, "freeze_sha256": spec_digest(bindings), "m8": bindings["m8"],
            "candidate_input_checks": checks,
            "matrix_compile_calls": len(bindings["candidates"]),
            "orders": orders, "domains": domains, "selections": selections, "full_evidence": full,
            "implementation_status": _acceptance(domains, selections, full),
            "host_seconds": {"experiment": perf_counter() - started}}


def _acceptance(domains, selections, full):
    return "accepted" if (all(d["summary"]["status"] == "exact" for d in domains)
                          and len(selections) == 16 and all(s["candidate"] is not None for s in selections)
                          and full and all(r["status"] == "complete" for r in full)) else "not-accepted"


def _run(bindings, workers):
    if type(workers) is not int or workers < 1:
        raise ValueError("workers must be a positive integer")
    if workers == 1:
        return _report(bindings, None)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return _report(bindings, pool)


def generate(path=REPORT, *, freeze_path=FREEZE, workers=1):
    path = Path(path)
    if path.resolve() in {p.resolve() for p in (*PROTECTED, Path(freeze_path), FREEZE)}:
        raise ValueError("report path collides with frozen inputs")
    bindings = require_frozen(freeze_path)
    report = _run(bindings, workers)
    validate_report(report, bindings)
    _atomic_json(path, report)
    return report


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _same(claimed, actual, message):
    _require(same_evidence(claimed, actual), message)


def _fields(value, keys, message):
    _require(isinstance(value, dict) and value.keys() == set(keys), message)


def _times(times):
    _require(isinstance(times, dict) and bool(times) and all(
        type(t) in (int, float) and 0 <= t < math.inf for t in times.values()), "invalid host timing evidence")


def _validate_row(row, candidate, inputs, references, *, full=False):
    keys = {"candidate", "status", "worst_fifo_interactions", "observed_max_fifo_interactions",
            "verification_interactions", "failed_input_indices", "records", "host_seconds"}
    _fields(row, keys | ({"compile_calls"} if full else set()), "invalid candidate evidence fields")
    _same(row["candidate"], candidate, "candidate omission, substitution, or reorder")
    _times(row["host_seconds"])
    _same(set(row["host_seconds"]), {"compile", "construction", "native_execution"},
          "invalid candidate host timing fields")
    records = row["records"]
    _require(isinstance(records, list) and len(records) == len(inputs), "candidate has missing input records")
    failures = []
    costs = []
    for i, record in enumerate(records):
        _require(isinstance(record, dict) and type(record.get("input_index")) is int
                 and record["input_index"] == i, "input evidence omitted, repeated, or reordered")
        _same(record.get("bits"), inputs[i], "input evidence differs from frozen slots")
        _same(record.get("reference"), references[i], "reference differs from direct assignment enumeration")
        cost = record.get("fifo_interactions")
        _require(type(cost) is int and cost >= 0, "invalid FIFO interaction count")
        status = record.get("status")
        _require(status in ("passed", "wrong-normal-form", "incomplete", "resource-exhausted", "error"),
                 "invalid native execution status")
        _require(type(record.get("whole_graph_matches_reference")) is bool
                 and (status != "passed" or record["whole_graph_matches_reference"]),
                 "execution marked passed without a verified complete Boolean terminal")
        census = record.get("rule_census")
        _require(isinstance(census, dict) and census.keys() == {"gg", "dd", "ee", "ge", "de", "gd"}
                 and all(type(count) is int and count >= 0 for count in census.values())
                 and sum(census.values()) == cost, "primitive rule census disagrees with FIFO interactions")
        if status != "passed":
            failures.append(i)
        costs.append(cost)
    _same(row["failed_input_indices"], failures, "candidate unresolved inputs differ from case evidence")
    _same(row["status"], "incomplete" if failures else "complete", "unfinished candidate counted as complete")
    _same(row["worst_fifo_interactions"], None if failures else max(costs), "invalid worst FIFO cost")
    _same(row["observed_max_fifo_interactions"], max(costs), "invalid observed maximum FIFO cost")
    _same(row["verification_interactions"], sum(costs), "invalid verification FIFO charge")
    if full:
        _same(row["compile_calls"], FULL_COUNT // FULL_BATCH, "invalid full-domain compile count")


def validate_report(claimed, frozen):
    """Reject inconsistent coverage, targets, orders, and charges before native replay."""
    _fields(claimed, {"contract", "freeze_sha256", "m8", "candidate_input_checks", "matrix_compile_calls",
                      "orders", "domains", "selections", "full_evidence", "implementation_status",
                      "host_seconds"}, "invalid M9 report fields")
    _same(claimed["contract"], VERSION, "wrong M9 contract")
    _same(claimed["freeze_sha256"], spec_digest(frozen), "wrong M9 frozen bindings")
    _same(claimed["m8"], frozen["m8"], "M8 baseline or learning overhead changed")
    _same(claimed["candidate_input_checks"], MATRIX_CHECKS, "wrong small-domain matrix size")
    candidate_count = len(frozen["candidates"])
    _same(claimed["matrix_compile_calls"], candidate_count, "wrong matrix compilation count")
    _times(claimed["host_seconds"])
    orders = search.build_orders(frozen["candidates"], frozen["abstraction"], frozen["ranking"])
    _same(claimed["orders"], orders, "search order or rule evidence differs from frozen inputs")
    domains = claimed["domains"]
    _require(isinstance(domains, list) and len(domains) == len(frozen["domains"]), "domain evidence missing")
    rows_by_domain = []
    for domain, expected in zip(domains, frozen["domains"], strict=True):
        _fields(domain, {"id", "candidates", "summary", "methods"}, "invalid domain evidence fields")
        _same(domain["id"], expected["id"], "domain omitted or reordered")
        rows = domain["candidates"]
        _require(isinstance(rows, list) and len(rows) == candidate_count, "raw candidate omitted")
        inputs = expected["inputs"]
        references = [core.assignment_reference(tuple(bits)) for bits in inputs]
        for candidate, row in enumerate(rows):
            _validate_row(row, candidate, inputs, references)
        rows_by_domain.append(rows)
    reconstructed = _domain_results(frozen, rows_by_domain, orders)
    for domain, expected in zip(domains, reconstructed, strict=True):
        _same(domain["summary"], expected["summary"], "target or ties differ from the complete matrix")
        _same(domain["methods"], expected["methods"], "search prefix or charge differs from independent scoring")
    selections = _selections(reconstructed)
    _same(claimed["selections"], selections, "chosen transforms or full-domain references changed")
    selected = sorted({s["candidate"] for s in selections if s["candidate"] is not None})
    full = claimed["full_evidence"]
    _require(isinstance(full, list) and len(full) == len(selected), "full-domain evidence is missing or repeated")
    inputs = list(core.full_domain())
    references = [core.assignment_reference(tuple(bits)) for bits in inputs]
    for candidate, row in zip(selected, full, strict=True):
        _validate_row(row, candidate, inputs, references, full=True)
    _same(claimed["implementation_status"], _acceptance(reconstructed, selections, full), "invalid M9 acceptance")


def verify(path=REPORT, *, freeze_path=FREEZE, workers=1):
    bindings = require_frozen(freeze_path)
    claimed = read_json(path)
    validate_report(claimed, bindings)
    actual = _run(bindings, workers)
    if not same_evidence(claimed, actual):
        raise ValueError("M9 evidence differs from the independent native reconstruction")
    return claimed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", nargs="?", const=FREEZE, metavar="PATH")
    mode.add_argument("--report", nargs="?", const=REPORT, metavar="PATH")
    mode.add_argument("--verify-report", nargs="?", const=REPORT, metavar="PATH")
    parser.add_argument("--freeze-path", default=FREEZE, metavar="PATH")
    parser.add_argument("--workers", default=min(8, os.cpu_count() or 1), type=int)
    args = parser.parse_args()
    try:
        if args.freeze:
            bindings = freeze(args.freeze)
            print(f"Frozen {len(bindings['candidates'])} candidates and {len(bindings['domains'])} domains")
            return 0
        action, path = (verify, args.verify_report) if args.verify_report else (generate, args.report)
        report = action(path, freeze_path=args.freeze_path, workers=args.workers)
    except (OSError, ValueError) as error:
        parser.exit(1, f"M9 evidence rejected: {error}\n")
    for domain in report["domains"]:
        print(domain["id"], domain["summary"]["status"], domain["summary"]["exact_target"])
    print(report["implementation_status"], report["candidate_input_checks"], "small-domain candidate/input checks")
    return 0 if report["implementation_status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
