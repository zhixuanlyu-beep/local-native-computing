"""M8 host counting for the frozen M7 Boolean-chain transforms.

The two count paths share only the frozen transform and input slots. One path
enumerates assignments of the eliminated chain variables. The other evaluates
the compiled IR with integer multiplication for AND and integer addition for OR.
Neither path reads the M7 Boolean reference while computing a count.
"""
from itertools import permutations, product
import json

from ic_coherent_feedback import spec_digest
from ic_localization.evidence import expected_value
from ic_localization.model import ChainProblem, CompiledTransform, Transform, compile_transform


CONTRACT = "M8-counting-v1"
EXPECTED_TRANSFORMS = {2: 18, 3: 98}
EXPECTED_CHECKS = 101_504


def _terminal_digests():
    """Classify both output graphs over every wire-order/loop-orientation spelling.

    GraphSpec serializes adjacency in insertion order. The true output has one
    loop, whose two endpoint orientations and whose position relative to the
    canonical boundary-first OUT wire both preserve the complete graph.
    """
    classified = {False: set(), True: set()}
    for bit in (False, True):
        base = expected_value(bit).to_dict()
        wires = base["wires"]
        for ordered in permutations(wires):
            forms = [list(ordered)]
            loop = next((wire for wire in ordered if wire[0][0] != "F"), None)
            if loop is not None:
                forms.append([list(reversed(wire)) if wire is loop else list(wire)
                              for wire in ordered])
            for form in forms:
                classified[bit].add(spec_digest({**base, "wires": form}))
    if classified[False] & classified[True]:
        raise ValueError("terminal graph spellings are ambiguous")
    return classified


def _validate_rows(rows):
    if not isinstance(rows, dict) or set(rows) != {2, 3}:
        raise ValueError("rows must contain exactly sizes 2 and 3")
    checked = {}
    for n in (2, 3):
        candidates = rows[n]
        if not isinstance(candidates, list) or len(candidates) != EXPECTED_TRANSFORMS[n]:
            raise ValueError(f"size {n} does not contain the frozen candidate count")
        transforms = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("candidate records must be objects")
            transform = Transform.from_dict(candidate.get("transform"))
            if transform.kind == "ve" and len(transform.order) != n:
                raise ValueError("candidate transform has the wrong size")
            records = candidate.get("records")
            if not isinstance(records, list) or len(records) != 2 ** (2+4*(n-1)):
                raise ValueError("candidate does not contain the complete input domain")
            if any(not isinstance(record, dict) for record in records):
                raise ValueError("input records must be objects")
            if [record.get("input_index") for record in records] != list(range(len(records))):
                raise ValueError("candidate records are not in input order")
            transforms.append(transform)
        if len(set(transforms)) != EXPECTED_TRANSFORMS[n]:
            raise ValueError("candidate descriptions are not unique")
        checked[n] = list(zip(transforms, candidates))
    return checked


def _assignment_count(n, bits):
    """Count satisfying hidden assignments without compiling the transform."""
    count = 0
    for assignment in product((0, 1), repeat=n):
        if bits[assignment[0]] and all(
                bits[2+4*i+2*assignment[i]+assignment[i+1]]
                for i in range(n-1)):
            count += 1
    return count


def _integer_ir_count(compiled, bits):
    """Interpret the frozen IR's two Boolean operations as + and *."""
    values = []
    for operation in compiled.ir:
        if operation.kind == "input":
            value = int(bits[operation.arguments[0]])
        elif operation.kind == "and":
            left, right = operation.arguments
            value = values[left] * values[right]
        elif operation.kind == "or":
            left, right = operation.arguments
            value = values[left] + values[right]
        else:
            raise ValueError("unknown frozen IR operation")
        values.append(value)
    return values[compiled.output]


def _boolean_counterexample():
    """Execute duplicate operands through the IR and reject Boolean OR semantics."""
    from ic_localization.model import IROp

    problem = ChainProblem(2)
    # The same input port feeds both OR operands. Its integer value is one, so
    # the host count is 1+1=2. A Boolean OR evaluator would return one.
    compiled = CompiledTransform(problem, Transform("direct", (), (), "S"),
                                 (IROp("input", (0,)), IROp("or", (0, 0))), 1, 0)
    bits = [True] * problem.input_bits
    integer_or = _integer_ir_count(compiled, bits)
    boolean_or = int(bits[0] or bits[0])
    return {
        "name": "duplicate-input OR 1+1=2",
        "integer_or": integer_or,
        "boolean_or": boolean_or,
        "status": "rejected" if integer_or == 2 and boolean_or == 1 else "unexpected-acceptance",
        "scope": "duplicate satisfying assignments contribute twice under integer addition",
    }


def _record_issues(record, actual):
    """Return typed discrepancies for one archived terminal record."""
    issues = []
    if actual is None:
        issues.append({"field": "final_graph_sha256", "reason": "unknown terminal digest"})
    elif record.get("reference") is not actual:
        issues.append({"field": "reference", "reason": "terminal digest disagrees",
                       "archive_reference": record.get("reference"), "terminal": actual})
    if record.get("status") != "passed":
        issues.append({"field": "status", "archive_status": record.get("status")})
    if record.get("whole_graph_matches_reference") is not True:
        issues.append({"field": "whole_graph_matches_reference"})
    return issues


def _reference_vectors(rows):
    """One compact assignment-count vector per size."""
    vectors = {}
    for n in (2, 3):
        problem = ChainProblem(n)
        candidate = rows[n][0][1]
        values = [_assignment_count(n, bits) for bits in problem.inputs()]
        vectors[str(n)] = {"candidate": candidate["transform"], "counts": values,
                           "sha256": spec_digest(values)}
    return vectors


def verify_m8_counts(rows):
    """Exhaustively compare assignment counts with the frozen IR integer counts.

    rows is {2: [candidate, ...], 3: [candidate, ...]} where each candidate has
    the M7 transform and complete ordered records. Boolean truth is recovered
    from each record's terminal graph digest and is checked separately from the
    count equality and from the archive's recorded reference and status.
    """
    checked_rows = _validate_rows(rows)
    terminals = _terminal_digests()
    evidence = {"2": {}, "3": {}}
    count_mismatches = []
    terminal_mismatches = []
    positivity_mismatches = []
    transform_checks = 0
    total_checks = 0

    for n in (2, 3):
        problem = ChainProblem(n)
        inputs = list(problem.inputs())
        for transform, candidate in checked_rows[n]:
            compiled = compile_transform(problem, transform)
            key = json.dumps(transform.to_dict(), sort_keys=True, separators=(",", ":"))
            records = candidate["records"]
            count_equal = True
            count_positive_equal = True
            archive_truth_equal = candidate.get("status") == "complete"
            for bits, record in zip(inputs, records):
                assignments = _assignment_count(n, bits)
                integer_count = _integer_ir_count(compiled, bits)
                total_checks += 1
                if assignments != integer_count:
                    count_equal = False
                    count_mismatches.append({"size": n, "transform": transform.to_dict(),
                                             "input_index": record["input_index"],
                                             "assignment_count": assignments,
                                             "integer_ir_count": integer_count})
                digest = record.get("final_graph_sha256")
                actual = next((bit for bit, expected in terminals.items() if digest in expected), None)
                if actual is None:
                    count_positive_equal = False
                elif (integer_count > 0) != actual:
                    count_positive_equal = False
                    positivity_mismatches.append({"size": n, "transform": transform.to_dict(),
                                                  "input_index": record["input_index"],
                                                  "integer_ir_count": integer_count,
                                                  "terminal": actual})
                issues = _record_issues(record, actual)
                if issues:
                    archive_truth_equal = False
                    terminal_mismatches.append({"size": n, "transform": transform.to_dict(),
                                                "input_index": record["input_index"],
                                                "issues": issues})
            passed = count_equal and count_positive_equal and archive_truth_equal
            item = {
                "status": "passed" if passed else "failed",
                "count_equal": count_equal,
                "count_positive_matches_reference": count_positive_equal,
            }
            if not passed:
                item["candidate_status"] = candidate.get("status")
                item["archive_reference_matches_terminal"] = archive_truth_equal
            evidence[str(n)][key] = item
            transform_checks += 1

    if total_checks != EXPECTED_CHECKS:
        raise ValueError("counting matrix does not contain exactly 101,504 checks")
    # Direct S and P transforms share a canonical IR shape but remain separate
    # descriptions and therefore receive separate evidence entries.
    if any(len(evidence[str(n)]) != EXPECTED_TRANSFORMS[n] for n in (2, 3)):
        raise ValueError("semantic evidence does not cover every frozen transform")
    counterexample = _boolean_counterexample()
    accepted = (not count_mismatches and not positivity_mismatches and not terminal_mismatches
                and all(item["status"] == "passed"
                        for by_transform in evidence.values() for item in by_transform.values())
                and counterexample["status"] == "rejected")
    return {
        "contract": CONTRACT,
        "candidate_input_checks": total_checks,
        "transform_checks": transform_checks,
        "count_mismatches": count_mismatches,
        "positivity_mismatches": positivity_mismatches,
        "terminal_mismatches": terminal_mismatches,
        "terminal_digests": {str(bit).lower(): sorted(terminals[bit]) for bit in (False, True)},
        "semantic_evidence": evidence,
        "reference_vectors": _reference_vectors(checked_rows),
        "boolean_counterexample": counterexample,
        "status": "accepted" if accepted else "not-accepted",
        "scope": "host counting over all frozen M7 transforms and Boolean inputs",
    }
