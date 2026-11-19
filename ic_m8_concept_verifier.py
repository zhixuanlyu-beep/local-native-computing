"""Independent reconstruction of the M8 concept library.

This verifier deliberately does not import the induction producer.  It derives
the expected pairs, features, compiled-IR digests and predicates directly from
the frozen M7 rows.  Native costs are reconstructed from the archived per-input
records before any concept is considered.
"""
from collections import Counter
from itertools import combinations
import hashlib
import json

from ic_localization.model import ChainProblem, Transform, compile_transform


LIBRARY_VERSION = "m8-concept-library-v1"
FEATURES = ("step_position", "input_factor_count", "scope_width", "downstream_refs")
EDIT_KINDS = ("materialize", "elimination-swap", "representation")
EXPECTED_CANDIDATES = {2: 18, 3: 98}


def _canonical(transform):
    return json.dumps(transform.to_dict(), sort_keys=True, separators=(",", ":"))


def _validate_rows(rows):
    if not isinstance(rows, dict) or set(rows) != {2, 3}:
        raise ValueError("rows must contain exactly sizes 2 and 3")
    checked = {}
    for n in (2, 3):
        candidates = rows[n]
        if not isinstance(candidates, list) or len(candidates) != EXPECTED_CANDIDATES[n]:
            raise ValueError(f"size {n} does not contain the frozen candidate count")
        by_key = {}
        for row in candidates:
            if not isinstance(row, dict):
                raise ValueError("candidate records must be objects")
            transform = Transform.from_dict(row.get("transform"))
            if transform.kind == "ve" and len(transform.order) != n:
                raise ValueError("candidate transform has the wrong problem size")
            records = row.get("records")
            if (not isinstance(records, list) or len(records) != 2 ** (2 + 4 * (n - 1))
                    or [record.get("input_index") for record in records] != list(range(len(records)))
                    or any(not isinstance(record, dict) for record in records)):
                raise ValueError("candidate does not contain the ordered complete input domain")
            if (row.get("status") != "complete"
                    or any(record.get("status") != "passed"
                           or record.get("whole_graph_matches_reference") is not True
                           or type(record.get("reference")) is not bool
                           for record in records)):
                raise ValueError("concept verification requires complete passed M7 rows")
            costs = [record.get("resources", {}).get("primitive_interactions") for record in records]
            if any(type(cost) is not int or cost < 0 for cost in costs):
                raise ValueError("candidate records have invalid native costs")
            worst = max(costs)
            if row.get("worst_fifo_interactions") != worst:
                raise ValueError("candidate aggregate cost differs from its native records")
            if row.get("observed_work_lower_bound") != worst:
                raise ValueError("candidate observed lower bound differs from its native records")
            key = _canonical(transform)
            if key in by_key:
                raise ValueError("candidate descriptions are not unique")
            by_key[key] = row
        if len(by_key) != EXPECTED_CANDIDATES[n]:
            raise ValueError(f"size {n} does not contain the frozen descriptions")
        checked[n] = by_key
    return checked


def _steps(problem, transform):
    """Simulate the frozen source factors, including all table-entry scopes."""
    factors = [{"id": 0, "scope": (0,)}]
    factors.extend({"id": index + 1, "scope": (index, index + 1)}
                   for index in range(problem.n - 1))
    steps = []
    consumers = {}
    for position, variable in enumerate(transform.order):
        incident = sorted((factor for factor in factors if variable in factor["scope"]),
                          key=lambda factor: factor["id"])
        result_scope = tuple(sorted(set().union(*(set(factor["scope"]) for factor in incident))
                                    - {variable}))
        produced = problem.n + position
        steps.append({"incident": len(incident), "scope": result_scope, "produced": produced})
        for factor in incident:
            consumers.setdefault(factor["id"], []).append(position)
        factors = [factor for factor in factors if variable not in factor["scope"]]
        factors.append({"id": produced, "scope": result_scope})
    return steps, consumers


def _features(problem, transform, position):
    if transform.kind == "direct":
        return {feature: None for feature in FEATURES}
    if type(position) is not int or not 0 <= position < problem.n:
        raise ValueError("feature position lies outside the elimination")
    steps, consumers = _steps(problem, transform)
    record = steps[position]
    later = [index for index in consumers.get(record["produced"], []) if index > position]
    if not later:
        downstream = 1
    else:
        consumer = steps[later[0]]
        if later[0] == problem.n - 1:
            downstream = 1
        else:
            # A consumer table has one term per assignment of its result scope
            # plus the eliminated variable.  Its term reads the produced table.
            downstream = 2 ** ((len(consumer["scope"]) + 1) - len(record["scope"]))
    return {"step_position": position, "input_factor_count": record["incident"],
            "scope_width": len(record["scope"]), "downstream_refs": downstream}


def _classify_edit(before, after):
    """Classify one unordered pair without assuming either neighbor exists."""
    if before.kind != after.kind:
        return None
    if before.order == after.order and before.representation == after.representation:
        changed = [index for index, (left, right)
                   in enumerate(zip(before.materialize, after.materialize)) if left != right]
        if len(changed) == 1 and before.materialize[changed[0]] is False:
            return "materialize", changed[0]
    if (before.materialize == after.materialize
            and before.representation == after.representation):
        for index in range(len(before.order) - 1):
            swapped = list(before.order)
            swapped[index], swapped[index + 1] = swapped[index + 1], swapped[index]
            if tuple(swapped) == after.order:
                return "elimination-swap", index
    if (before.order == after.order and before.materialize == after.materialize
            and before.representation != after.representation):
        return "representation", None
    return None


def _pairs(rows):
    result = []
    for n in (2, 3):
        problem = ChainProblem(n)
        candidates = sorted(rows[n].items())
        for (left_key, left_row), (right_key, right_row) in combinations(candidates, 2):
            before = Transform.from_dict(left_row["transform"])
            after = Transform.from_dict(right_row["transform"])
            classified = _classify_edit(before, after)
            if classified is None:
                continue
            kind, index = classified
            before_cost = left_row["worst_fifo_interactions"]
            after_cost = right_row["worst_fifo_interactions"]
            delta = after_cost - before_cost
            outcome = "improved" if delta < 0 else "degraded" if delta > 0 else "tied"
            if before.kind == "direct":
                position = None
            elif kind in ("materialize", "elimination-swap"):
                position = index
            else:
                position = next((i for i, variable in enumerate(before.order)
                                 if variable != i), 0)
            result.append({
                "n": n, "before": before.to_dict(), "after": after.to_dict(),
                "edit": {"kind": kind, "index": index},
                "worst_before": before_cost, "worst_after": after_cost,
                "delta": delta, "outcome": outcome, "support": 1,
                "semantic_support": 1, "counterexamples": [],
                "features_before": _features(problem, before, position),
                "features_after": _features(problem, after, position),
            })
    result.sort(key=lambda pair: (pair["n"], EDIT_KINDS.index(pair["edit"]["kind"]),
                                   -1 if pair["edit"]["index"] is None else pair["edit"]["index"],
                                   _canonical(Transform.from_dict(pair["before"])),
                                   _canonical(Transform.from_dict(pair["after"]))))
    return result


def _evidence_item(evidence, n, transform):
    size = evidence.get(str(n))
    item = size.get(_canonical(transform)) if isinstance(size, dict) else None
    return (isinstance(item, dict) and item.get("status") == "passed"
            and item.get("count_equal") is True
            and item.get("count_positive_matches_reference") is True)


def _compiled_digest(problem, transform, cache):
    key = (problem.n, _canonical(transform))
    if key not in cache:
        compiled = compile_transform(problem, transform)
        payload = {"ir": [[operation.kind, list(operation.arguments)] for operation in compiled.ir],
                   "output": compiled.output, "representation": transform.representation}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        cache[key] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return cache[key]


def _predicate_atoms(pairs):
    observed = {feature: sorted({value for pair in pairs for side in ("features_before", "features_after")
                                 for value in (pair[side][feature],) if type(value) is int})
                for feature in FEATURES}
    atoms = []
    for feature in FEATURES:
        for value in observed[feature]:
            atoms.extend(({"feature": feature, "op": op, "value": value}
                          for op in ("==", "<=", ">=")))
    atoms.sort(key=lambda atom: (FEATURES.index(atom["feature"]), atom["value"],
                                 ("==", "<=", ">=").index(atom["op"])))
    predicates = [((atom,), _atom_text(atom)) for atom in atoms]
    for index, left in enumerate(atoms):
        for right in atoms[index + 1:]:
            if left["feature"] != right["feature"] and left["op"] == right["op"] == "==":
                predicates.append(((left, right), _atom_text(left) + " AND " + _atom_text(right)))
    return predicates


def _atom_text(atom):
    return f"{atom['feature']}{atom['op']}{atom['value']}"


def _matches(pair, predicate):
    for side in ("features_before", "features_after"):
        for atom in predicate:
            value = pair[side][atom["feature"]]
            if type(value) is not int:
                return False
            if atom["op"] == "==" and value != atom["value"]:
                return False
            if atom["op"] == "<=" and value > atom["value"]:
                return False
            if atom["op"] == ">=" and value < atom["value"]:
                return False
    return True


def _make_rule(kind, predicate, matching, evidence, cache):
    deltas = [pair["delta"] for pair in matching]
    outcomes = Counter(pair["outcome"] for pair in matching)
    verified = [pair for pair in matching
                if _evidence_item(evidence, pair["n"], Transform.from_dict(pair["before"]))
                and _evidence_item(evidence, pair["n"], Transform.from_dict(pair["after"]))]
    support_pairs = []
    seen = set()
    for pair in verified:
        before = Transform.from_dict(pair["before"])
        after = Transform.from_dict(pair["after"])
        problem = ChainProblem(pair["n"])
        before_digest = _compiled_digest(problem, before, cache)
        after_digest = _compiled_digest(problem, after, cache)
        pair_key = (pair["n"], before_digest, after_digest)
        if pair_key in seen:
            continue
        seen.add(pair_key)
        encoded = json.dumps([pair["n"], before_digest, after_digest], separators=(",", ":"))
        support_pairs.append({"n": pair["n"], "before": before_digest, "after": after_digest,
                              "ir_pair_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest()})
    counterexamples = [{"n": pair["n"], "before": pair["before"], "after": pair["after"],
                        "delta": pair["delta"], "outcome": pair["outcome"]}
                       for pair in matching if pair["delta"] >= 0]
    return {
        "id": "candidate", "predicate": [dict(atom) for atom in predicate],
        "parameters": list(dict.fromkeys(atom["feature"] for atom in predicate)),
        "transformation": {"edit_kind": kind, "direction": "before-to-after"},
        "identification_overhead": _identification_overhead(predicate, matching),
        "source": {"candidate_matrix": "M7 localization archive",
                   "pair_scope": "single materialize, adjacent elimination swap, or representation toggle"},
        "edit_kind": kind, "support": len(support_pairs), "matching_pairs": len(matching),
        "semantic_support": len(verified),
        "outcomes": {name: outcomes[name] for name in ("improved", "tied", "degraded")},
        "cost": {"min_delta": min(deltas), "max_delta": max(deltas),
                 "conservative_saving": max(0, -max(deltas))},
        "counterexamples": counterexamples, "support_pairs": support_pairs,
        "origin": "automatic-discovery",
        "status": "accepted" if len(support_pairs) >= 2 else "rejected",
        "rejection": None,
        "semantic_scope": {"requirement": "both endpoint transforms passed independent M8 count checks",
                           "sizes": [2, 3], "inputs": "complete frozen Boolean domains",
                           "verified_endpoint_pairs": len(verified)},
    }


def _identification_overhead(predicate, matching):
    checks = len(predicate) * 2
    return {"candidate_pairs_scanned": len(matching), "feature_sides_per_pair": 2,
            "atom_comparisons": len(matching) * checks, "host_operations": len(matching) * checks}


def _axioms():
    scope = "nonnegative integer counting algebra in the frozen IR interpretation"
    identities = [
        {"id": "AX001", "name": "integer addition is associative", "origin": "manual-axiom",
         "parameters": ["a", "b", "c"], "statement": "(a+b)+c = a+(b+c)", "scope": scope},
        {"id": "AX002", "name": "integer addition is commutative", "origin": "manual-axiom",
         "parameters": ["a", "b"], "statement": "a+b = b+a", "scope": scope},
        {"id": "AX003", "name": "integer multiplication is associative", "origin": "manual-axiom",
         "parameters": ["a", "b", "c"], "statement": "(a*b)*c = a*(b*c)", "scope": scope},
        {"id": "AX004", "name": "integer multiplication is commutative", "origin": "manual-axiom",
         "parameters": ["a", "b"], "statement": "a*b = b*a", "scope": scope},
        {"id": "AX005", "name": "integer multiplication distributes over addition",
         "origin": "manual-axiom", "parameters": ["a", "b", "c"],
         "statement": "a*(b+c) = a*b+a*c", "scope": scope},
    ]
    for axiom in identities:
        axiom.update({"source": "hand-supplied integer algebra",
                      "cost_model": {"metric": "symbolic identity", "delta": None},
                      "identification_overhead": {"host_operations": 0}})
    return identities


def reconstruct(rows, *, semantic_evidence):
    """Return the library implied by the rows and count evidence."""
    checked = _validate_rows(rows)
    if not isinstance(semantic_evidence, dict):
        raise TypeError("semantic_evidence must be a size-keyed mapping")
    pairs = _pairs(checked)
    cache = {}
    for pair in pairs:
        pair["semantic_support"] = int(
            _evidence_item(semantic_evidence, pair["n"], Transform.from_dict(pair["before"]))
            and _evidence_item(semantic_evidence, pair["n"], Transform.from_dict(pair["after"])))
    accepted, rejected = [], []
    rejection_counts = Counter()
    for kind in EDIT_KINDS:
        kind_pairs = [pair for pair in pairs if pair["edit"]["kind"] == kind]
        kind_pair_count = len(kind_pairs)
        candidates = []
        for predicate, text in _predicate_atoms(kind_pairs):
            matching = [pair for pair in kind_pairs if _matches(pair, predicate)]
            if len(matching) >= 2:
                rule = _make_rule(kind, predicate, matching, semantic_evidence, cache)
                rule["identification_overhead"] = _identification_overhead(predicate, [None] * kind_pair_count)
                candidates.append((rule, text))
        candidates.sort(key=lambda item: (-item[0]["support"], -item[0]["semantic_support"],
                                          item[0]["cost"]["max_delta"], len(item[0]["predicate"]),
                                          item[1]))
        selected = []
        for rule, text in candidates:
            if rule["status"] != "accepted":
                if rule["rejection"] is None:
                    rule["rejection"] = "insufficient-verified-ir-pairs"
                rejection_counts[rule["rejection"]] += 1
                rejected.append(rule)
                continue
            matching = [pair for pair in kind_pairs if _matches(pair, tuple(rule["predicate"]))]
            covered = {(pair["n"], _canonical(Transform.from_dict(pair["before"])),
                        _canonical(Transform.from_dict(pair["after"]))) for pair in matching}
            if any(previous[1] == covered for previous in selected):
                rule["status"] = "rejected"
                duplicate = next(previous[0] for previous in selected if previous[1] == covered)
                rule["rejection"] = f"redundant-with-{duplicate}"
                rejection_counts[rule["rejection"]] += 1
                rejected.append(rule)
                continue
            rule["id"] = f"C{len(accepted) + 1:03d}"
            rule["weakened_predicate_evidence"] = _weakened(kind_pairs, rule["predicate"])
            selected.append((rule["id"], covered))
            accepted.append(rule)
    outcomes = Counter(pair["outcome"] for pair in pairs)
    recognition = sum(rule["identification_overhead"]["host_operations"] for rule in accepted)
    serialized = len(json.dumps(accepted, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return {
        "version": LIBRARY_VERSION, "origin": "automatic-discovery",
        "induction_scope": {"sizes": [2, 3], "candidate_descriptions": 116,
                            "pair_edits": list(EDIT_KINDS), "predicate_atoms": 1,
                            "max_predicate_atoms": 2,
                            "cost_scope": "exact frozen M7 worst-case FIFO primitive interactions",
                            "claim_scope": "descriptive relations in the declared finite class"},
        "pairs": pairs, "rules": accepted, "rejected_rules": rejected,
        "manual_axioms": _axioms(),
        "counts": {"pairs": len(pairs), "improved": outcomes["improved"],
                   "tied": outcomes["tied"], "degraded": outcomes["degraded"],
                   "rules": len(accepted), "rejected_rules": sum(rejection_counts.values()),
                   "compiled_ir_cache_entries": len(cache),
                   "rule_recognition_host_operations": recognition,
                   "library_serialized_bytes": serialized,
                   "rejections": dict(sorted(rejection_counts.items()))},
    }


def _weakened(kind_pairs, predicate):
    result = []
    if len(predicate) != 2:
        return result
    for atom in predicate:
        narrow = (atom,)
        matching = [pair for pair in kind_pairs if _matches(pair, narrow)]
        outcomes = Counter(pair["outcome"] for pair in matching)
        deltas = [pair["delta"] for pair in matching]
        result.append({"predicate": [dict(atom)], "support": len(matching),
                       "outcomes": {name: outcomes[name] for name in ("improved", "tied", "degraded")},
                       "cost": {"min_delta": min(deltas), "max_delta": max(deltas),
                                "conservative_saving": max(0, -max(deltas))},
                       "witnesses": [{"n": pair["n"], "before": pair["before"],
                                      "after": pair["after"], "delta": pair["delta"],
                                      "outcome": pair["outcome"]}
                                     for pair in matching if pair["delta"] >= 0]})
    return result


def _same(left, right, path="library"):
    """Strict JSON comparison, including integer versus Boolean types."""
    if type(left) is not type(right):
        raise ValueError(f"{path}: expected {type(right).__name__}, found {type(left).__name__}")
    if isinstance(right, dict):
        if left.keys() != right.keys():
            raise ValueError(f"{path}: keys differ")
        for key in right:
            _same(left[key], right[key], f"{path}.{key}")
    elif isinstance(right, list):
        if len(left) != len(right):
            raise ValueError(f"{path}: list length differs")
        for index, (actual, expected) in enumerate(zip(left, right)):
            _same(actual, expected, f"{path}[{index}]")
    elif left != right:
        raise ValueError(f"{path}: value differs")


def verify_concept_library(rows, library, *, semantic_evidence):
    """Rebuild the library and reject any omitted, changed or malformed field."""
    if not isinstance(library, dict):
        raise ValueError("concept library must be a JSON object")
    expected = reconstruct(rows, semantic_evidence=semantic_evidence)
    _same(library, expected)
    return expected
