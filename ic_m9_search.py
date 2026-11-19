"""M9 concept transfer and frozen candidate visiting orders.

This module consumes candidate descriptions and the accepted M8 library.  It
does not execute a candidate, read an evaluator target, or inspect candidate
records.  The four orders are therefore available before the held-out search
starts and can be rebuilt independently from the frozen M9 inputs.
"""

from collections import defaultdict
import hashlib
import heapq
import json
from time import perf_counter

from ic_m8_concepts import _feature_values
from ic_m9_core import M9Problem, M9Transform


RANKING_VERSION = "m9-strict-m8-ranking-v1"
ORDER_GROUPS = (
    "no-concepts",
    "abstraction-only",
    "ranking-only",
    "abstraction-and-ranking",
)
EDIT_ORDER = ("representation", "materialize", "elimination-swap")


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canonical(transform):
    if isinstance(transform, dict):
        transform = M9Transform.from_dict(transform)
    return json.dumps(transform.to_dict(), sort_keys=True, separators=(",", ":"))


def _rule_is_strict(rule):
    outcomes = rule.get("outcomes")
    matched = rule.get("matching_pairs")
    return (isinstance(outcomes, dict) and type(matched) is int and matched > 0
            and outcomes.get("improved") == matched
            and outcomes.get("tied") == 0 and outcomes.get("degraded") == 0)


def freeze_ranking(m8_library):
    """Select exactly the M8 rules whose complete matched support improved."""
    if not isinstance(m8_library, dict):
        raise TypeError("the M8 library must be an object")
    rules = m8_library.get("rules")
    if not isinstance(rules, list):
        raise ValueError("the M8 library has no rule list")
    strict = []
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("status") != "accepted":
            continue
        if not _rule_is_strict(rule):
            continue
        predicate = rule.get("predicate")
        saving = rule.get("cost", {}).get("conservative_saving")
        kind = rule.get("edit_kind")
        overhead = rule.get("identification_overhead", {}).get("host_operations")
        if (not isinstance(predicate, list) or not predicate
                or any(set(atom) != {"feature", "op", "value"} for atom in predicate)
                or type(saving) is not int or saving < 0
                or kind not in EDIT_ORDER or type(overhead) is not int or overhead < 0):
            raise ValueError("an accepted M8 rule has an unsupported ranking shape")
        strict.append({
            "id": rule.get("id"),
            "predicate": [dict(atom) for atom in predicate],
            "edit_kind": kind,
            "direction": rule.get("transformation", {}).get("direction"),
            "conservative_saving": saving,
            "identification_overhead": {
                key: rule["identification_overhead"][key]
                for key in sorted(rule["identification_overhead"])
            },
        })
    strict.sort(key=lambda rule: rule["id"])
    if len(strict) != 21:
        raise ValueError(f"M9 requires 21 strict M8 rules, found {len(strict)}")
    if any(rule["direction"] != "before-to-after" for rule in strict):
        raise ValueError("M9 supports only the frozen before-to-after rule direction")
    recognition_work = sum(rule["identification_overhead"]["host_operations"]
                           for rule in strict)
    result = {
        "version": RANKING_VERSION,
        "selection": "accepted M8 rules with improved == matching_pairs and no tie or degradation",
        "terminal_edge_base": 117,
        "rules": strict,
        "counts": {"rules": len(strict), "recognition_host_operations": recognition_work},
    }
    result["sha256"] = _digest(result)
    return result


def _atom_matches(value, operator, expected):
    if type(value) is not int:
        return False
    if operator == "==":
        return value == expected
    if operator == "<=":
        return value <= expected
    if operator == ">=":
        return value >= expected
    raise ValueError("unknown M8 predicate operator")


def _predicate_matches(record, predicate):
    return all(_atom_matches(record.get(atom["feature"]), atom["op"], atom["value"])
               for atom in predicate)


def _step_features(transform):
    """Return the complete per-step feature record for one size-4 transform."""
    if transform.kind == "direct":
        return ()
    problem = M9Problem(4)
    return tuple(_feature_values(problem, transform, step)
                 for step in range(problem.n))


def _endpoint_features(before, after):
    """Identify a single declared edit and expose both endpoint conditions.

    The M8 relation is local to the edited step.  M9 uses each of the two
    endpoint feature records independently when applying its predicate.
    """
    if before.kind != after.kind:
        return []
    if before.order == after.order and before.representation != after.representation:
        step = next((position for position, variable in enumerate(before.order)
                     if variable != position), 0)
        return [("representation", step, before, after)]
    if before.representation != after.representation:
        return []
    if before.order == after.order:
        changes = [index for index, (left, right)
                   in enumerate(zip(before.materialize, after.materialize)) if left != right]
        if len(changes) == 1:
            index = changes[0]
            if not before.materialize[index] and after.materialize[index]:
                return [("materialize", index, before, after)]
            if before.materialize[index] and not after.materialize[index]:
                return [("materialize", index, after, before)]
        return []
    if before.materialize == after.materialize:
        for index in range(len(before.order)-1):
            order = list(before.order)
            order[index], order[index+1] = order[index+1], order[index]
            if tuple(order) == after.order:
                return [("elimination-swap", index, before, after)]
            if tuple(reversed(order)) == before.order:
                return [("elimination-swap", index, after, before)]
    return []


def _matching_rules(rules, before, after):
    features_before = _step_features(before)
    features_after = _step_features(after)
    matches = []
    for edit_kind, step, original_before, original_after in _endpoint_features(before, after):
        before_record = features_before[step] if features_before else {}
        after_record = features_after[step] if features_after else {}
        for rule in rules:
            if rule["edit_kind"] != edit_kind:
                continue
            before_match = _predicate_matches(before_record, rule["predicate"])
            after_match = _predicate_matches(after_record, rule["predicate"])
            if before_match or after_match:
                matches.append({"rule": rule["id"], "saving": rule["conservative_saving"],
                                "edit_kind": edit_kind, "step": step,
                                "endpoint": ("both" if before_match and after_match else
                                             "before" if before_match else "after")})
    return matches


def _max_predicted_saving(rules, before, after):
    """Conservative saving of all rules matched at either edit endpoint."""
    best = 0
    features_before = _step_features(before)
    features_after = _step_features(after)
    for edit_kind, step, _original_before, _original_after in _endpoint_features(before, after):
        before_record = features_before[step] if features_before else {}
        after_record = features_after[step] if features_after else {}
        for rule in rules:
            if rule["edit_kind"] == edit_kind and (
                    _predicate_matches(before_record, rule["predicate"])
                    or _predicate_matches(after_record, rule["predicate"])):
                best = max(best, rule["conservative_saving"])
    return best


def _single_edits(transform, n=4):
    """Yield each directed declared edit from the frozen M8 edit family."""
    if transform.kind == "direct":
        yield "representation", M9Transform("direct", representation=(
            "P" if transform.representation == "S" else "S"))
        return
    for step in range(n):
        flags = list(transform.materialize)
        if not flags[step]:
            flags[step] = True
            yield "materialize", M9Transform(transform.kind, transform.order, tuple(flags),
                                            transform.representation)
    for index in range(n-1):
        order = list(transform.order)
        order[index], order[index+1] = order[index+1], order[index]
        yield "elimination-swap", M9Transform(transform.kind, tuple(order), transform.materialize,
                                             transform.representation)
    yield "representation", M9Transform(transform.kind, transform.order, transform.materialize,
                                       "P" if transform.representation == "S" else "S")


def _candidate_index(candidates):
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidates must be a nonempty list")
    result = {}
    for item in candidates:
        if not isinstance(item, dict):
            raise TypeError("candidate records must be objects")
        identifier = item.get("id")
        transform = M9Transform.from_dict(item.get("transform"))
        if transform.kind != "direct" and len(transform.order) != 4:
            raise ValueError("M9 candidates must be size-4 transforms")
        canonical = _canonical(transform)
        if canonical in result:
            raise ValueError("candidate descriptions are not unique")
        result[canonical] = {"id": identifier, "transform": transform, "canonical": canonical,
                             "raw": {**item, "canonical": canonical}}
    if len(result) != 770:
        raise ValueError(f"M9 requires 770 raw candidates, found {len(result)}")
    return result


def _predicted_savings(candidates, rules):
    by_canonical = {item["canonical"]: item for item in candidates}
    result = {}
    recognition_checks = 0
    for item in candidates:
        transform = item["transform"]
        best = 0
        evidence = []
        for kind, after in _single_edits(transform):
            neighbor = by_canonical.get(_canonical(after))
            if neighbor is None:
                continue
            recognition_checks += 2 * len(rules)
            matches = _matching_rules(rules, transform, after)
            for match in matches:
                best = max(best, match["saving"])
                evidence.append({"to": neighbor["id"], **match})
        result[item["canonical"]] = (best, evidence)
    return result, recognition_checks


def _concept_key(item):
    """Description supplied by core when available, otherwise raw fallback."""
    for key in ("concept_key", "abstraction_key", "class_key"):
        value = item.get("raw", {}).get(key)
        if isinstance(value, str):
            return value
    return item["canonical"]


def _class_maps(candidates, abstraction):
    candidate_keys = {_canonical(item["transform"]) for item in candidates}
    if isinstance(abstraction, dict) and isinstance(abstraction.get("members"), dict):
        members = abstraction["members"]
        representatives = abstraction.get("representatives")
        if not isinstance(representatives, dict):
            raise ValueError("abstraction requires class representatives")
        if set(members) != candidate_keys:
            raise ValueError("abstraction does not cover the candidate set exactly")
        representative_keys = {value["canonical"] if isinstance(value, dict) else value
                               for value in representatives.values()}
        if not representative_keys.issubset(candidate_keys):
            raise ValueError("abstraction representative is not a candidate")
        declared = {item["canonical"]: item.get("class_id") for item in candidates}
        if any(declared[key] != members[key] for key in members):
            raise ValueError("candidate class ids differ from the abstraction")
        return (
            dict(members),
            {key: (representatives[members[key]]["canonical"]
                   if isinstance(representatives[members[key]], dict)
                   else representatives[members[key]])
             for key in members},
        )
    if isinstance(abstraction, dict) and isinstance(abstraction.get("classes"), list):
        class_id = {}
        representatives = {}
        for record in abstraction["classes"]:
            if not isinstance(record, dict) or not isinstance(record.get("members"), list):
                raise ValueError("abstraction class records require member lists")
            members = record["members"]
            representative = min(members)
            for canonical in members:
                if canonical in class_id:
                    raise ValueError("candidate occurs in more than one abstraction class")
                class_id[canonical] = record.get("id", _digest(record))
                representatives[canonical] = representative
        if set(class_id) != candidate_keys:
            raise ValueError("abstraction does not cover the candidate set exactly")
        return class_id, representatives
    groups = defaultdict(list)
    for item in candidates:
        groups[_concept_key(item)].append(_canonical(item["transform"]))
    class_id = {}
    representatives = {}
    for key in sorted(groups):
        representative = min(groups[key])
        identifier = "class-" + _digest(key)[:16]
        for canonical in groups[key]:
            class_id[canonical] = identifier
            representatives[canonical] = representative
    return class_id, representatives


def _neighbors(canonical, candidates, class_id, representatives):
    """Layered representation, elimination and materialization edges."""
    item = candidates[canonical]
    result = []
    for kind, after in _single_edits(item["transform"]):
        neighbor_key = _canonical(after)
        if neighbor_key in candidates:
            neighbor = neighbor_key
        else:
            # The conceptual graph keeps same-class paths available even when
            # the corresponding raw size-4 description is absent.
            continue
        result.append((kind, neighbor))
    return result


def _layered_graph(index, class_id, representatives, savings, ranking):
    """Build the declared root-to-representation-to-edit DAG.

    Direct candidates branch from their representation nodes.  VE candidates
    pass through representation, elimination-order, and materialization
    layers.  All internal edges are zero cost.  Each raw candidate has a
    terminal edge whose cost is exactly 117 minus its maximum matched
    conservative saving.
    """
    nodes = {"ROOT": {"layer": "root", "label": "root"},
             "GOAL": {"layer": "goal", "label": "goal"}}
    edges = []
    for kind in ("direct", "ve"):
        for representation in ("S", "P"):
            node_id = f"R-{kind}-{representation}"
            nodes[node_id] = {"layer": "representation", "kind": kind,
                              "representation": representation}
            edges.append({"from": "ROOT", "to": node_id,
                          "kind": "root-to-representation", "cost": 0})

    order_nodes = set()
    for canonical in index:
        transform = index[canonical]["transform"]
        if transform.kind == "direct":
            parent = f"R-direct-{transform.representation}"
            edge_kind = "representation-to-direct-terminal"
        else:
            order_id = f"O-{transform.representation}-{''.join(map(str, transform.order))}"
            if order_id not in order_nodes:
                order_nodes.add(order_id)
                nodes[order_id] = {"layer": "elimination-order",
                                   "representation": transform.representation,
                                   "order": list(transform.order)}
                edges.append({"from": f"R-ve-{transform.representation}", "to": order_id,
                              "kind": "representation-to-order", "cost": 0})
            parent = order_id
            edge_kind = "order-to-materialization"

        candidate_id = index[canonical]["id"]
        materialization_id = "M-" + candidate_id
        nodes[materialization_id] = {
            "layer": "materialization",
            "candidate": candidate_id,
            "canonical": canonical,
            "materialize": list(transform.materialize),
        }
        edges.append({"from": parent, "to": materialization_id,
                      "kind": edge_kind, "cost": 0})
        terminal_cost = ranking["terminal_edge_base"] - savings[canonical][0]
        if type(terminal_cost) is not int or terminal_cost < 0:
            raise ValueError("predicted terminal cost is negative")
        edges.append({"from": materialization_id, "to": "GOAL", "kind": "terminal",
                      "candidate": candidate_id,
                      "predicted_saving": savings[canonical][0], "cost": terminal_cost})

    # Add the declared single-edit relations between materialization nodes.
    # They remain zero-cost organization links and never replace the terminal
    # edge used to score a path.
    for canonical in index:
        node_id = "M-" + index[canonical]["id"]
        for edit_kind, neighbor in _neighbors(canonical, index, class_id, representatives):
            edges.append({"from": node_id, "to": "M-" + index[neighbor]["id"],
                          "kind": "internal-" + edit_kind, "cost": 0})
    edges.sort(key=lambda edge: (edge["from"], edge["to"], edge["kind"],
                                 edge.get("candidate", "")))
    return {"nodes": dict(sorted(nodes.items())), "edges": edges,
            "root": "ROOT", "goal": "GOAL", "internal_edge_cost": 0,
            "terminal_cost_formula": "117 - maximum matched conservative saving"}


def _conceptual_distances(index, class_id, representatives):
    """Shortest distance to each representative in the layered edit graph.

    Layer edges represent representation, elimination, and materialization
    edits. Internal edges cost zero. A terminal edge costs 117 minus the
    conservative saving of the rules matched at that candidate.
    """
    distances = {}
    queue = []
    for representative in sorted(set(representatives.values())):
        distances[representative] = 0
        heapq.heappush(queue, (0, representatives[representative], representative))
    while queue:
        distance, _, canonical = heapq.heappop(queue)
        if distance != distances[canonical]:
            continue
        for _, neighbor in _neighbors(canonical, index, class_id, representatives):
            if neighbor in distances and distances[neighbor] <= distance:
                continue
            distances[neighbor] = distance
            heapq.heappush(queue, (distance, representatives[neighbor], neighbor))
    return distances


def build_orders(candidates, abstraction, ranking):
    """Build all four frozen visiting orders without evaluator information."""
    started = perf_counter()
    if not isinstance(ranking, dict) or ranking.get("version") != RANKING_VERSION:
        raise ValueError("ranking is not the frozen M9 ranking configuration")
    checked_ranking = dict(ranking)
    claimed_digest = checked_ranking.pop("sha256", None)
    if claimed_digest != _digest(checked_ranking):
        raise ValueError("ranking configuration digest mismatch")
    rules = ranking.get("rules")
    if not isinstance(rules, list) or len(rules) != 21:
        raise ValueError("ranking must contain exactly 21 strict rules")
    for rule in rules:
        if (not isinstance(rule, dict) or not isinstance(rule.get("predicate"), list)
                or rule.get("edit_kind") not in EDIT_ORDER
                or type(rule.get("conservative_saving")) is not int
                or rule["conservative_saving"] < 0
                or not isinstance(rule.get("identification_overhead"), dict)
                or type(rule["identification_overhead"].get("host_operations")) is not int):
            raise ValueError("ranking rule has an unsupported shape")
    for field in ("id", "canonical", "transform", "class_id"):
        if any(field not in item for item in candidates):
            raise ValueError(f"candidate records require the field {field}")
    if [item.get("raw_index") for item in candidates] != list(range(len(candidates))):
        raise ValueError("candidates must follow the frozen raw_index order")
    index = _candidate_index(candidates)
    class_id, representatives = _class_maps(candidates, abstraction)
    indexed_candidates = list(index.values())
    savings, recognition_checks = _predicted_savings(indexed_candidates, rules)
    class_members = defaultdict(list)
    for canonical in index:
        class_members[class_id[canonical]].append(canonical)
    if len(class_members) != 290:
        raise ValueError(f"M9 abstraction requires 290 classes, found {len(class_members)}")
    graph = _layered_graph(index, class_id, representatives, savings, ranking)
    for members in class_members.values():
        members.sort(key=lambda key: index[key]["canonical"])
    order = {}
    for group in ORDER_GROUPS:
        abstract = group in ("abstraction-only", "abstraction-and-ranking")
        ranked = group in ("ranking-only", "abstraction-and-ranking")
        records = []
        if abstract:
            representatives_by_class = sorted(class_members)
            representative_rows = []
            for cid in representatives_by_class:
                representative = min(class_members[cid])
                representative_rows.append({
                    "candidate_id": index[representative]["id"],
                    "canonical": representative,
                    "class_id": cid,
                    "class_size": len(class_members[cid]),
                    "predicted_saving": max(savings[key][0] for key in class_members[cid]),
                    "minimum_path_cost": ranking["terminal_edge_base"] - max(
                        savings[key][0] for key in class_members[cid]),
                })
            representative_rows.sort(key=lambda row: (
                -row["predicted_saving"] if ranked else row["minimum_path_cost"],
                row["canonical"]))
            records.extend(representative_rows)
        else:
            ordered = sorted(index, key=lambda key: (-savings[key][0], key)
                             if ranked else index[key]["raw"]["raw_index"])
            for canonical in ordered:
                records.append({
                    "candidate_id": index[canonical]["id"],
                    "canonical": canonical,
                    "class_id": class_id[canonical],
                    "representative": representatives[canonical],
                    "predicted_saving": savings[canonical][0] if ranked else 0,
                })
        visiting_order = [record["candidate_id"] for record in records]
        expected_count = 290 if abstract else 770
        if len(visiting_order) != len(set(visiting_order)) or len(visiting_order) != expected_count:
            raise AssertionError(f"{group} does not visit its declared candidate set exactly once")
        order[group] = {
            "candidates": records,
            "raw_order": [index[record["canonical"]]["raw"]["raw_index"] for record in records],
            "visiting_order": visiting_order,
            "unique_candidates": len(set(visiting_order)),
            "recognition": {
                "host_operations": recognition_checks if ranked else 0,
                "rule_endpoint_checks": recognition_checks if ranked else 0,
                "candidate_edges": sum(
                    1 for key in index for _kind, _after in _single_edits(
                        index[key]["transform"]) if _canonical(_after) in index) if ranked else 0,
            },
            "host_seconds": {"preparation": 0.0},
        }
    classes = [{"id": cid, "members": sorted(members),
                "representative": min(members), "size": len(members)}
               for cid, members in sorted(class_members.items())]
    evidence = {
        "version": RANKING_VERSION,
        "ranking_sha256": claimed_digest,
        "candidate_count": len(index),
        "class_count": len(classes),
        "classes": classes,
        "predicted_savings": {key: savings[key][0] for key in sorted(index)},
        "rule_matches": {key: savings[key][1] for key in sorted(index) if savings[key][1]},
        "orders": order,
        "graph": {**graph, "edge_count": len(graph["edges"]),
                  "node_count": len(graph["nodes"]),
                  "candidate_terminal_costs": {key: ranking["terminal_edge_base"] - value[0]
                                               for key, value in sorted(savings.items())}},
        "work": {
            "recognition_candidate_edges": sum(
                1 for key in index for _kind, _after in _single_edits(
                    index[key]["transform"]) if _canonical(_after) in index),
            "recognition_rule_endpoint_checks": recognition_checks,
            "host_operations": recognition_checks,
            "rule_identification_host_operations": ranking["counts"]["recognition_host_operations"],
            "library_rule_bytes": len(json.dumps(rules, sort_keys=True,
                                                   separators=(",", ":")).encode("utf-8")),
        },
    }
    elapsed = perf_counter() - started
    for record in evidence["orders"].values():
        record["host_seconds"]["preparation"] = elapsed
    # Timings remain verifier-checked host observations rather than digest inputs.
    semantic = json.loads(json.dumps(evidence))
    for record in semantic["orders"].values():
        record["host_seconds"].pop("preparation", None)
    evidence["sha256"] = _digest(semantic)
    return evidence
