"""M8 automatic concept induction from the frozen M7 localization evidence.

The input is the validated M7 candidate matrix.  This module derives only
bounded, local relations between raw transform descriptions.  It does not run a
network, load an archive, or claim that a relation is a general rewrite law.
"""
from collections import Counter
import hashlib
import json

from ic_localization.model import ChainProblem, Transform, compile_transform


LIBRARY_VERSION = "m8-concept-library-v1"
FEATURES = ("step_position", "input_factor_count", "scope_width", "downstream_refs")
EDIT_KINDS = ("materialize", "elimination-swap", "representation")
EXPECTED_CANDIDATES = {2: 18, 3: 98}


def canonical_transform(transform):
    """Canonical description used for stable keys and archive joins."""
    if isinstance(transform, dict):
        transform = Transform.from_dict(transform)
    if not isinstance(transform, Transform):
        raise TypeError("expected a Transform or transform description")
    return json.dumps(transform.to_dict(), sort_keys=True, separators=(",", ":"))


def _factor_simulation(problem, transform):
    """Replay the M7 source-factor elimination without compiling values."""
    factors = [{"id": 0, "scope": (0,)}]
    factors.extend({"id": index+1, "scope": (index, index+1)}
                   for index in range(problem.n-1))
    steps = []
    consumers = {}
    for step, variable in enumerate(transform.order):
        incident = sorted((factor for factor in factors if variable in factor["scope"]),
                          key=lambda factor: factor["id"])
        joined = set().union(*(set(factor["scope"]) for factor in incident))
        result_scope = tuple(sorted(joined - {variable}))
        produced_id = problem.n + step
        steps.append({"step": step, "variable": variable,
                      "incident_count": len(incident),
                      "result_scope": result_scope, "produced_id": produced_id})
        for factor in incident:
            consumers.setdefault(factor["id"], []).append(step)
        factors = [factor for factor in factors if variable not in factor["scope"]]
        factors.append({"id": produced_id, "scope": result_scope})
    return steps, consumers


def _feature_values(problem, transform, step):
    """Compute the four declared features at one elimination step.

    downstream_refs counts consumer table term references per produced table
    entry.  A final scalar result has one output use.  The consumer is the
    first later step that includes the produced factor, which may skip a
    non-adjacent variable in the permutation.
    """
    if transform.kind == "direct":
        return {name: None for name in FEATURES}
    if type(step) is not int or not 0 <= step < problem.n:
        raise ValueError("feature step is outside the elimination")
    steps, consumers = _factor_simulation(problem, transform)
    record = steps[step]
    later = [index for index in consumers.get(record["produced_id"], []) if index > step]
    if not later:
        downstream = 1 if step == problem.n-1 else 0
    else:
        consumer_step = steps[later[0]]
        if later[0] == problem.n-1:
            downstream = 1
        else:
            joined_width = len(consumer_step["result_scope"]) + 1
            difference = joined_width - len(record["result_scope"])
            downstream = 2 ** difference
    return {
        "step_position": step,
        "input_factor_count": record["incident_count"],
        "scope_width": len(record["result_scope"]),
        "downstream_refs": downstream,
    }


def _validate_rows(rows):
    if not isinstance(rows, dict) or set(rows) != {2, 3}:
        raise ValueError("rows must contain exactly the sizes 2 and 3")
    checked = {}
    for n in (2, 3):
        candidates = rows[n]
        if not isinstance(candidates, list) or len(candidates) != EXPECTED_CANDIDATES[n]:
            raise ValueError(f"size {n} does not contain the frozen candidate count")
        by_key = {}
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("candidate records must be objects")
            transform = Transform.from_dict(candidate.get("transform"))
            if transform.kind == "ve" and len(transform.order) != n:
                raise ValueError("candidate transform has the wrong size")
            records = candidate.get("records")
            if not isinstance(records, list) or len(records) != 2 ** (2+4*(n-1)):
                raise ValueError("candidate does not contain the complete input domain")
            if [record.get("input_index") for record in records] != list(range(len(records))):
                raise ValueError("candidate records are not in input order")
            if any(not isinstance(record, dict) for record in records):
                raise ValueError("input records must be objects")
            status = candidate.get("status")
            if status != "complete" or any(record.get("status") != "passed" for record in records):
                raise ValueError("concept induction requires complete validated M7 candidates")
            cost = candidate.get("worst_fifo_interactions")
            if type(cost) is not int or cost < 0:
                raise ValueError("candidate is missing its exact FIFO cost")
            key = canonical_transform(transform)
            if key in by_key:
                raise ValueError("candidate descriptions are not unique")
            by_key[key] = candidate
        if len(by_key) != EXPECTED_CANDIDATES[n]:
            raise ValueError(f"size {n} does not contain the frozen candidate descriptions")
        checked[n] = by_key
    return checked


def _edited(transform, kind, index):
    if kind == "materialize":
        flags = list(transform.materialize)
        flags[index] = True
        return Transform(transform.kind, transform.order, tuple(flags), transform.representation)
    if kind == "elimination-swap":
        order = list(transform.order)
        order[index], order[index+1] = order[index+1], order[index]
        return Transform(transform.kind, tuple(order), transform.materialize, transform.representation)
    if kind == "representation":
        return Transform(transform.kind, transform.order, transform.materialize,
                         "P" if transform.representation == "S" else "S")
    raise ValueError("unknown edit kind")


def _candidate_pairs(rows):
    """Enumerate each unordered single-edit pair once."""
    pairs = []
    for n in (2, 3):
        by_key = rows[n]
        for key, candidate in by_key.items():
            transform = Transform.from_dict(candidate["transform"])
            edits = []
            if transform.kind == "ve":
                edits.extend(("materialize", index) for index, flag in enumerate(transform.materialize) if not flag)
                edits.extend(("elimination-swap", index) for index in range(n-1))
            edits.append(("representation", None))
            for kind, index in edits:
                after = _edited(transform, kind, index)
                after_key = canonical_transform(after)
                if after_key not in by_key or key > after_key:
                    continue
                after_candidate = by_key[after_key]
                before_cost = candidate["worst_fifo_interactions"]
                after_cost = after_candidate["worst_fifo_interactions"]
                delta = after_cost - before_cost
                outcome = "improved" if delta < 0 else "degraded" if delta > 0 else "tied"
                step = (index if kind in ("materialize", "elimination-swap") else
                        next((position for position, variable in enumerate(transform.order)
                              if variable != position), 0))
                if transform.kind == "direct":
                    step = None
                pairs.append({
                    "n": n,
                    "before": transform.to_dict(),
                    "after": after.to_dict(),
                    "edit": {"kind": kind, "index": index},
                    "worst_before": before_cost,
                    "worst_after": after_cost,
                    "delta": delta,
                    "outcome": outcome,
                    "support": 1,
                    "semantic_support": 1,
                    "counterexamples": [],
                    "features_before": _feature_values(ChainProblem(n), transform, step),
                    "features_after": _feature_values(ChainProblem(n), after, step),
                })
    pairs.sort(key=lambda pair: (pair["n"], EDIT_KINDS.index(pair["edit"]["kind"]),
                                 -1 if pair["edit"]["index"] is None else pair["edit"]["index"],
                                 canonical_transform(pair["before"]),
                                 canonical_transform(pair["after"])))
    return pairs


def concept_features(transform):
    """Public structural-feature entry point for one M7 transform."""
    if not isinstance(transform, Transform):
        raise TypeError("expected Transform")
    problem = ChainProblem(len(transform.order) if transform.kind == "ve" else 2)
    if transform.kind == "direct":
        return _feature_values(problem, transform, None)
    step = next((position for position, variable in enumerate(transform.order)
                 if variable != position), 0)
    return _feature_values(problem, transform, step)


def _evidence_ok(evidence, n, transform):
    by_size = evidence.get(str(n))
    if not isinstance(by_size, dict):
        return False
    item = by_size.get(canonical_transform(transform))
    return (isinstance(item, dict) and item.get("status") == "passed"
            and item.get("count_equal") is True
            and item.get("count_positive_matches_reference") is True)


def _predicate_atoms(pairs):
    observed = {feature: sorted({value for pair in pairs for side in ("features_before", "features_after")
                                 for value in (pair[side][feature],) if type(value) is int})
                for feature in FEATURES}
    atoms = []
    for feature in FEATURES:
        for value in observed[feature]:
            atoms.append({"feature": feature, "op": "==", "value": value})
            atoms.append({"feature": feature, "op": "<=", "value": value})
            atoms.append({"feature": feature, "op": ">=", "value": value})
    atoms.sort(key=lambda atom: (FEATURES.index(atom["feature"]), atom["value"],
                                 ("==", "<=", ">=").index(atom["op"])))
    predicates = [{"atoms": (atom,), "text": _atom_text(atom)} for atom in atoms]
    for left_index, left in enumerate(atoms):
        for right in atoms[left_index+1:]:
            if left["feature"] == right["feature"]:
                continue
            if (left["op"] != "==" or right["op"] != "=="):
                continue
            predicates.append({"atoms": (left, right), "text": _atom_text(left)+" AND "+_atom_text(right)})
    predicates.sort(key=lambda predicate: (len(predicate["atoms"]), predicate["text"]))
    return predicates


def _weakened_predicates(predicate):
    """Single-atom conditions subsumed by a discovered conjunction."""
    if len(predicate) != 2:
        return []
    return [{"atoms": (atom,), "text": _atom_text(atom)} for atom in predicate]


def _atom_text(atom):
    return f"{atom['feature']}{atom['op']}{atom['value']}"


def _matches(pair, predicate):
    return all(_atom_matches(pair[side][atom["feature"]], atom["op"], atom["value"])
               for side in ("features_before", "features_after") for atom in predicate["atoms"])


def _atom_matches(value, op, expected):
    if type(value) is not int:
        return False
    if op == "==":
        return value == expected
    if op == "<=":
        return value <= expected
    if op == ">=":
        return value >= expected
    raise ValueError("unknown predicate operator")


def _compiled_signature(problem, transform, cache):
    """Hash the complete ordered IR, output mapping and representation."""
    key = (problem.n, canonical_transform(transform))
    if key not in cache:
        compiled = compile_transform(problem, transform)
        ir = [[operation.kind, list(operation.arguments)] for operation in compiled.ir]
        encoded = json.dumps({"ir": ir, "output": compiled.output,
                              "representation": transform.representation},
                             sort_keys=True, separators=(",", ":"))
        cache[key] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return cache[key]


def _identification_overhead(predicate, kind_pairs):
    """Deterministic host work needed to apply one predicate to a pair set."""
    atom_checks = len(predicate["atoms"]) * 2
    return {
        "candidate_pairs_scanned": len(kind_pairs),
        "feature_sides_per_pair": 2,
        "atom_comparisons": len(kind_pairs) * atom_checks,
        "host_operations": len(kind_pairs) * atom_checks,
    }


def _make_rule(rule_id, kind, predicate, matching, evidence, cache, kind_pairs):
    outcomes = Counter(pair["outcome"] for pair in matching)
    deltas = [pair["delta"] for pair in matching]
    semantic = sum(_evidence_ok(evidence, pair["n"], Transform.from_dict(pair["before"]))
                   and _evidence_ok(evidence, pair["n"], Transform.from_dict(pair["after"]))
                   for pair in matching)
    verified_pairs = [pair for pair in matching
                      if _evidence_ok(evidence, pair["n"], Transform.from_dict(pair["before"]))
                      and _evidence_ok(evidence, pair["n"], Transform.from_dict(pair["after"]))]
    support_pairs = []
    seen_pairs = set()
    for pair in verified_pairs:
        before = Transform.from_dict(pair["before"])
        after = Transform.from_dict(pair["after"])
        before_ir = _compiled_signature(ChainProblem(pair["n"]), before, cache)
        after_ir = _compiled_signature(ChainProblem(pair["n"]), after, cache)
        pair_key = (pair["n"], before_ir, after_ir)
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        ir_pair = json.dumps([pair["n"], before_ir, after_ir], separators=(",", ":"))
        support_pairs.append({"n": pair["n"], "before": before_ir, "after": after_ir,
                              "ir_pair_sha256": hashlib.sha256(ir_pair.encode("utf-8")).hexdigest()})
    counterexamples = [{"n": pair["n"], "before": pair["before"], "after": pair["after"],
                        "delta": pair["delta"], "outcome": pair["outcome"]}
                       for pair in matching if pair["delta"] >= 0]
    return {
        "id": rule_id,
        "predicate": [dict(atom) for atom in predicate["atoms"]],
        "parameters": list(dict.fromkeys(atom["feature"] for atom in predicate["atoms"])),
        "transformation": {"edit_kind": kind, "direction": "before-to-after"},
        "identification_overhead": _identification_overhead(predicate, kind_pairs),
        "source": {"candidate_matrix": "M7 localization archive",
                   "pair_scope": "single materialize, adjacent elimination swap, or representation toggle"},
        "edit_kind": kind,
        "support": len(support_pairs),
        "matching_pairs": len(matching),
        "semantic_support": semantic,
        "outcomes": {name: outcomes[name] for name in ("improved", "tied", "degraded")},
        "cost": {"min_delta": min(deltas), "max_delta": max(deltas),
                 "conservative_saving": max(0, -max(deltas))},
        "counterexamples": counterexamples,
        "support_pairs": support_pairs,
        "origin": "automatic-discovery",
        "status": "accepted" if len(support_pairs) >= 2 else "rejected",
        "rejection": None,
        "semantic_scope": {"requirement": "both endpoint transforms passed independent M8 count checks",
                           "sizes": [2, 3],
                           "inputs": "complete frozen Boolean domains",
                           "verified_endpoint_pairs": semantic},
    }


def _manual_axioms():
    identities = [{
        "id": "AX001",
        "name": "integer addition is associative",
        "origin": "manual-axiom",
        "parameters": ["a", "b", "c"],
        "statement": "(a+b)+c = a+(b+c)",
        "scope": "nonnegative integer counting algebra in the frozen IR interpretation",
    }, {
        "id": "AX002",
        "name": "integer addition is commutative",
        "origin": "manual-axiom",
        "parameters": ["a", "b"],
        "statement": "a+b = b+a",
        "scope": "nonnegative integer counting algebra in the frozen IR interpretation",
    }, {
        "id": "AX003",
        "name": "integer multiplication is associative",
        "origin": "manual-axiom",
        "parameters": ["a", "b", "c"],
        "statement": "(a*b)*c = a*(b*c)",
        "scope": "nonnegative integer counting algebra in the frozen IR interpretation",
    }, {
        "id": "AX004",
        "name": "integer multiplication is commutative",
        "origin": "manual-axiom",
        "parameters": ["a", "b"],
        "statement": "a*b = b*a",
        "scope": "nonnegative integer counting algebra in the frozen IR interpretation",
    }, {
        "id": "AX005",
        "name": "integer multiplication distributes over addition",
        "origin": "manual-axiom",
        "parameters": ["a", "b", "c"],
        "statement": "a*(b+c) = a*b+a*c",
        "scope": "nonnegative integer counting algebra in the frozen IR interpretation",
    }]
    for axiom in identities:
        axiom.update({"source": "hand-supplied integer algebra",
                      "cost_model": {"metric": "symbolic identity", "delta": None},
                      "identification_overhead": {"host_operations": 0}})
    return identities


def induce_concepts(candidate_rows_by_n, *, semantic_evidence):
    """Induce the versioned M8 concept library from validated M7 rows.

    The function is deterministic and does not read files.  A rule is accepted
    only with two independent count-verified endpoint pairs and two distinct
    full ordered IR pairs.  Rules are descriptive hypotheses within the
    frozen finite class.
    """
    rows = _validate_rows(candidate_rows_by_n)
    if not isinstance(semantic_evidence, dict):
        raise TypeError("semantic_evidence must be a transform-keyed mapping")
    pairs = _candidate_pairs(rows)
    cache = {}
    for pair in pairs:
        pair["semantic_support"] = int(
            _evidence_ok(semantic_evidence, pair["n"], Transform.from_dict(pair["before"]))
            and _evidence_ok(semantic_evidence, pair["n"], Transform.from_dict(pair["after"])))

    accepted = []
    rejected = []
    rejection_counts = Counter()
    for kind in EDIT_KINDS:
        kind_pairs = [pair for pair in pairs if pair["edit"]["kind"] == kind]
        selected = []
        candidates = []
        for predicate in _predicate_atoms(kind_pairs):
            matching = [pair for pair in kind_pairs if _matches(pair, predicate)]
            if len(matching) < 2:
                continue
            rule = _make_rule("candidate", kind, predicate, matching, semantic_evidence, cache, kind_pairs)
            candidates.append(rule)
        candidates.sort(key=lambda rule: (-rule["support"], -rule["semantic_support"],
                                          rule["cost"]["max_delta"],
                                          len(rule["predicate"]), _predicate_text(rule["predicate"])))
        for rule in candidates:
            if rule["status"] != "accepted":
                if rule["rejection"] is None:
                    reason = "insufficient-verified-ir-pairs"
                    rule["rejection"] = reason
                rejection_counts[rule["rejection"]] += 1
                rejected.append(rule)
                continue
            matching = [pair for pair in kind_pairs if _matches(pair, {"atoms": tuple(rule["predicate"])})]
            covered = {(pair["n"], canonical_transform(pair["before"]),
                        canonical_transform(pair["after"])) for pair in matching}
            if any(previous[1] == covered for previous in selected):
                rule["status"] = "rejected"
                duplicate = next(previous[0] for previous in selected if previous[1] == covered)
                rule["rejection"] = f"redundant-with-{duplicate}"
                rejection_counts[rule["rejection"]] += 1
                rejected.append(rule)
                continue
            rule_id = f"C{len(accepted)+1:03d}"
            rule["id"] = rule_id
            weakened = []
            for narrow in _weakened_predicates(tuple(rule["predicate"])):
                narrowed_pairs = [pair for pair in kind_pairs if _matches(pair, narrow)]
                narrowed_outcomes = Counter(pair["outcome"] for pair in narrowed_pairs)
                narrowed_deltas = [pair["delta"] for pair in narrowed_pairs]
                if not narrowed_deltas:
                    raise AssertionError("a subsumed predicate must match at least one pair")
                weakened.append({
                    "predicate": [dict(atom) for atom in narrow["atoms"]],
                    "support": len(narrowed_pairs),
                    "outcomes": {name: narrowed_outcomes[name]
                                 for name in ("improved", "tied", "degraded")},
                    "cost": {"min_delta": min(narrowed_deltas),
                             "max_delta": max(narrowed_deltas),
                             "conservative_saving": max(0, -max(narrowed_deltas))},
                    "witnesses": [{"n": pair["n"], "before": pair["before"],
                                   "after": pair["after"], "delta": pair["delta"],
                                   "outcome": pair["outcome"]}
                                  for pair in narrowed_pairs if pair["delta"] >= 0],
                })
            rule["weakened_predicate_evidence"] = weakened
            selected.append((rule_id, covered))
            accepted.append(rule)

    counts = Counter(pair["outcome"] for pair in pairs)
    rule_count = len(accepted)
    recognition_work = sum(rule["identification_overhead"]["host_operations"] for rule in accepted)
    library_bytes = len(json.dumps(accepted, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return {
        "version": LIBRARY_VERSION,
        "origin": "automatic-discovery",
        "induction_scope": {
            "sizes": [2, 3],
            "candidate_descriptions": sum(EXPECTED_CANDIDATES.values()),
            "pair_edits": list(EDIT_KINDS),
            "predicate_atoms": 1,
            "max_predicate_atoms": 2,
            "cost_scope": "exact frozen M7 worst-case FIFO primitive interactions",
            "claim_scope": "descriptive relations in the declared finite class",
        },
        "pairs": pairs,
        "rules": accepted,
        "rejected_rules": rejected,
        "manual_axioms": _manual_axioms(),
        "counts": {"pairs": len(pairs), "improved": counts["improved"],
                   "tied": counts["tied"], "degraded": counts["degraded"],
                   "rules": rule_count, "rejected_rules": sum(rejection_counts.values()),
                   "compiled_ir_cache_entries": len(cache),
                   "rule_recognition_host_operations": recognition_work,
                   "library_serialized_bytes": library_bytes,
                   "rejections": dict(sorted(rejection_counts.items()))},
    }


def _predicate_text(predicate):
    return " AND ".join(_atom_text(atom) for atom in predicate)
