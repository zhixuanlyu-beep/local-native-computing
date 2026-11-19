"""Freeze, run, and verify the M10 star and cycle FIFO search experiment."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from ic_coherent_feedback import read_json, spec_digest
from ic_localization.report import same_evidence
from ic_m9 import FREEZE as M9_FREEZE, PROTECTED as M9_PROTECTED, REPORT as M9_REPORT, _atomic_json
from ic_m9_core import BUDGET

import ic_m10_core as core


ROOT = Path(__file__).resolve().parent
VERSION = core.VERSION
FREEZE = ROOT / "docs/M10_FREEZE.json"
REPORT = ROOT / "results/m10_topology.json.gz"
MATRIX_CHECKS = core.SMALL_CHECKS
SOURCE_FILES = (
    "ic_m10.py", "ic_m10_core.py", "ic_m10_search.py", "ic_m10_verify.py",
    "ic_m9.py", "ic_m9_core.py", "ic_m9_accel.py", "ic_m9_native.c",
    "ic_localization/model.py", "ic_localization/backend.py", "ic_localization/report.py",
    "ic_coherent_feedback.py", "ic_coherent_output_decoder.py", "ic_evidence_json.py",
    "ic_fast_reducer.py", "ic_observation_contracts.py", "ic_primitive_port_verifier.py",
    "ic_research_artifacts.py", "ic_schedule_audit.py", "lafont_ic_macro_builder.py",
)


def frozen_bindings():
    """Bind the experiment to its definitions before any candidate execution."""
    return {
        **core.frozen_bindings(),
        "contract": VERSION,
        "schedule": "fifo",
        "budget": dict(BUDGET),
        "candidate_input_checks": MATRIX_CHECKS,
        "objective": "minimize the maximum complete FIFO interaction count over 64 search inputs",
        "search_order": {
            "candidates": "M9 raw order: direct S/P, then representation, permutation, materialization bits",
            "inputs": "lexicographic Boolean assignments to the listed free slots, false before true",
            "upper_bound": "minimum from earlier candidates verified on every search input in this group",
            "exclusion": "strict lower bound greater than the current upper bound",
        },
        "holdout_order": "first 256 out-of-domain vectors sorted by SHA-256 of M10-v1:<topology ID>:<bit string>, then bit string",
        "holdout_selection": "lexicographically smallest canonical description among optimal candidates",
        "sources": {
            name: sha256((ROOT / name).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
            for name in SOURCE_FILES
        },
    }


def _output_path(path, *, protect):
    path = Path(path)
    if path.resolve() in {p.resolve() for p in (*M9_PROTECTED, M9_FREEZE, M9_REPORT, *protect)}:
        raise ValueError(f"output path collides with frozen inputs or prior evidence: {path}")
    return path


def freeze(path=FREEZE):
    path = _output_path(path, protect=(REPORT,))
    bindings = frozen_bindings()
    _atomic_json(path, bindings)
    return bindings


def require_frozen(path=FREEZE):
    actual = frozen_bindings()
    if not same_evidence(read_json(path), actual):
        raise ValueError("M10 freeze differs from experiment definitions or source digests")
    return actual


def _jobs(bindings):
    for definition, domain, holdout in zip(bindings["topologies"], bindings["domains"],
                                           bindings["holdouts"], strict=True):
        yield definition["id"], bindings["candidates"], domain["inputs"], holdout["inputs"], bindings["budget"]


def _map(function, jobs, workers):
    if type(workers) is not int or not 1 <= workers <= len(core.TOPOLOGY_IDS):
        raise ValueError("workers must be between one and the number of frozen topologies")
    if workers == 1:
        return list(map(function, jobs))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(function, jobs))


def _measure(function, jobs, workers):
    started = perf_counter()
    result = _map(function, jobs, workers)
    return result, perf_counter() - started


def _print_verification(measurements):
    for item in measurements:
        times = item["host_seconds"]
        print(f"{item['id']} independent verification {times['total']:.3f} s", flush=True)


def generate(path=REPORT, *, freeze_path=FREEZE, workers=1):
    import ic_m10_search as search
    import ic_m10_verify as verifier

    path = _output_path(path, protect=(FREEZE, Path(freeze_path)))
    bindings = require_frozen(freeze_path)
    topologies, duration = _measure(search.run_topology, _jobs(bindings), workers)
    claimed = {
        "contract": VERSION,
        "freeze_sha256": spec_digest(bindings),
        "candidate_input_checks": MATRIX_CHECKS,
        "topologies": topologies,
        "implementation_status": verifier.acceptance(topologies),
        "host_seconds": {"experiment": duration},
    }
    verification_jobs = ((job, topology, False) for job, topology in zip(_jobs(bindings), topologies, strict=True))
    measurements, duration = _measure(verifier.verify_topology, verification_jobs, workers)
    claimed["verification"] = {"topologies": measurements, "host_seconds": {"total": duration}}
    verifier.validate_report(claimed, bindings, VERSION, MATRIX_CHECKS)
    _atomic_json(path, claimed)
    _print_verification(measurements)
    return claimed


def verify(path=REPORT, *, freeze_path=FREEZE, workers=1):
    import ic_m10_verify as verifier

    bindings = require_frozen(freeze_path)
    claimed = read_json(path)
    verifier.validate_report(claimed, bindings, VERSION, MATRIX_CHECKS)
    verification_jobs = ((job, topology, True) for job, topology in
                         zip(_jobs(bindings), claimed["topologies"], strict=True))
    measurements, duration = _measure(verifier.verify_topology, verification_jobs, workers)
    verifier.same(claimed["implementation_status"], verifier.acceptance(claimed["topologies"]),
                  "invalid M10 acceptance claim")
    _print_verification(measurements)
    print(f"Independent verification wall time {duration:.3f} s", flush=True)
    return claimed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", nargs="?", const=FREEZE, metavar="PATH")
    mode.add_argument("--report", nargs="?", const=REPORT, metavar="PATH")
    mode.add_argument("--verify-report", nargs="?", const=REPORT, metavar="PATH")
    parser.add_argument("--freeze-path", default=FREEZE, metavar="PATH")
    parser.add_argument("--workers", default=len(core.TOPOLOGY_IDS), type=int,
                        help="number of topologies to run concurrently")
    args = parser.parse_args()
    try:
        if args.freeze:
            bindings = freeze(args.freeze)
            print(f"Frozen {len(bindings['candidates'])} candidates for each of {len(bindings['topologies'])} topologies")
            return 0
        action, path = (verify, args.verify_report) if args.verify_report else (generate, args.report)
        claimed = action(path, freeze_path=args.freeze_path, workers=args.workers)
    except (OSError, ValueError) as error:
        parser.exit(1, f"M10 evidence rejected: {error}\n")
    for item in claimed["topologies"]:
        summary = item["certificate"]["summary"]
        print(item["id"], summary["status"], summary["best_known_worst_fifo_interactions"])
    print(claimed["implementation_status"], claimed["candidate_input_checks"], "full-enumeration checks")
    return 0 if claimed["implementation_status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
