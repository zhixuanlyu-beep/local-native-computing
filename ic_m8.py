"""Generate and independently verify the M8 counting and concept evidence."""
import argparse
import gzip
from hashlib import sha256
from pathlib import Path

from ic_coherent_feedback import read_json, spec_digest, write_json
from ic_evidence_json import loads
from ic_localization.evidence import ROOT, VERSION as M7_VERSION, frozen_bindings
from ic_localization.report import FREEZE as M7_FREEZE, same_evidence
from ic_m8_concepts import induce_concepts
from ic_m8_concept_verifier import verify_concept_library
from ic_m8_counting import verify_m8_counts


FREEZE = ROOT / "docs/M8_FREEZE.json"
M7_REPORT = ROOT / "results/localization.json.gz"


def load_frozen_m7_rows(report_path, contract):
    """Check the source freeze and load the exact accepted M7 FIFO archive."""
    baseline = contract["m7_baseline"]
    bindings = frozen_bindings()
    digest = spec_digest(bindings)
    if (baseline["contract"] != M7_VERSION or baseline["bindings_sha256"] != digest
            or not same_evidence(read_json(M7_FREEZE), bindings)):
        raise ValueError("M7 sources or manifest differ from the frozen M8 baseline")

    encoded = Path(report_path).read_bytes()
    if sha256(encoded).hexdigest() != baseline["fifo_report_sha256"]:
        raise ValueError("M7 FIFO report digest differs from the frozen M8 baseline")
    report = loads(gzip.decompress(encoded))
    if (report["contract"] != M7_VERSION or report["bindings_sha256"] != digest
            or not same_evidence(report["bindings"], bindings)
            or report["implementation_status"] != "accepted"
            or report["fifo_candidate_input_checks"] != contract["candidate_input_checks"]):
        raise ValueError("M7 report does not match the accepted contract")

    problems = report["problems"]
    rows = {problem["n"]: problem["candidates"] for problem in problems}
    if list(rows) != [domain["n"] for domain in contract["domains"]] or len(rows) != len(problems):
        raise ValueError("M7 report problem domains differ from the frozen M8 baseline")
    for domain, m7_domain in zip(contract["domains"], bindings["domains"], strict=True):
        candidates = rows[domain["n"]]
        if (len(candidates) != domain["candidates"]
                or not same_evidence([row["transform"] for row in candidates], m7_domain["candidates"])
                or any(len(row["records"]) != domain["inputs"] for row in candidates)):
            raise ValueError("M7 archive candidate/input coverage differs from the frozen M8 baseline")
    return rows


def _reconstruct(m7_report):
    contract = read_json(FREEZE)
    rows = load_frozen_m7_rows(m7_report, contract)
    counting = verify_m8_counts(rows)
    unfinished = [
        {"n": n, "transform": row["transform"], "status": row["status"],
         "records": [case for case in row["records"] if case["status"] != "passed"]}
        for n, candidates in rows.items() for row in candidates if row["status"] != "complete"
    ]
    accepted = not unfinished and counting["status"] == "accepted" and (
        counting["candidate_input_checks"] == contract["candidate_input_checks"])
    evidence = {"contract": contract["contract"], "freeze_sha256": spec_digest(contract),
                "m7_baseline": contract["m7_baseline"], "counting": counting,
                "unfinished": unfinished, "implementation_status": "accepted" if accepted else "not-accepted"}
    return rows, evidence


def generate(report_path, m7_report=M7_REPORT):
    """Build the evidence and cross-check the independently reconstructed library."""
    path = Path(report_path)
    protected_paths = (M7_REPORT, M7_FREEZE, FREEZE, Path(m7_report), ROOT / "results/localization.ictrace.gz")
    if path.resolve() in {protected.resolve() for protected in protected_paths}:
        raise ValueError("M8 output must be separate from the frozen M7 and M8 inputs")
    rows, evidence = _reconstruct(m7_report)
    semantics = evidence["counting"]["semantic_evidence"]
    library = induce_concepts(rows, semantic_evidence=semantics)
    verify_concept_library(rows, library, semantic_evidence=semantics)
    evidence["library"] = library
    write_json(path, evidence)
    return evidence


def verify(report_path, m7_report=M7_REPORT):
    """Verify archived counts and concepts without invoking the induction producer."""
    claimed = read_json(report_path)
    rows, evidence = _reconstruct(m7_report)
    if not isinstance(claimed, dict) or claimed.keys() != evidence.keys() | {"library"}:
        raise ValueError("M8 report fields differ from the frozen evidence schema")
    if not same_evidence({key: claimed[key] for key in evidence}, evidence):
        raise ValueError("M8 count or baseline evidence differs from reconstruction")
    verify_concept_library(rows, claimed["library"], semantic_evidence=evidence["counting"]["semantic_evidence"])
    return claimed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--report", metavar="PATH")
    mode.add_argument("--verify-report", metavar="PATH")
    parser.add_argument("--m7-report", default=M7_REPORT, metavar="PATH")
    args = parser.parse_args()
    action, path = (verify, args.verify_report) if args.verify_report else (generate, args.report)
    try:
        report = action(path, args.m7_report)
    except (OSError, ValueError) as error:
        parser.exit(1, f"M8 evidence rejected: {error}\n")
    print(report["implementation_status"], report["counting"]["candidate_input_checks"],
          "candidate/input count checks")
    return 0 if report["implementation_status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
