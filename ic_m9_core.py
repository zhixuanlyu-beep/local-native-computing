"""Frozen M9 size-four syntax, Boolean holdout domains, and native FIFO runs.

The M7 compiler and literal Interaction Combinator backend are reused with one
declared extension: elimination permutations have four entries.  Candidate
descriptions remain the M7 four-field records, so archives can be validated
without a second syntax dialect.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import permutations, product
import json
from time import perf_counter

from ic_localization.model import ChainProblem, CompiledTransform, Transform, compile_transform


VERSION = "m9-holdout-v1"
N = 4
INPUT_BITS = 2 + 4 * (N - 1)
EXPECTED_CANDIDATES = 770
EXPECTED_CLASSES = 290
EXPECTED_SMALL_INPUTS = 64
EXPECTED_FULL_INPUTS = 16384
EXPECTED_SMALL_CHECKS = EXPECTED_CANDIDATES * EXPECTED_SMALL_INPUTS * N
EXPECTED_FULL_CHECKS = EXPECTED_FULL_INPUTS * N
BUDGET = {"max_steps": 2_000_000, "max_cells": 250_000}


@dataclass(frozen=True)
class M9Problem(ChainProblem):
    """The frozen chain size-four problem without changing M7's size check."""

    def __post_init__(self):
        if type(self.n) is not int or self.n != N:
            raise ValueError("M9 freezes chain size 4")


@dataclass(frozen=True)
class M9Transform(Transform):
    """M7 transform syntax with a four-entry elimination permutation."""

    def __post_init__(self):
        if self.kind not in ("direct", "ve") or self.representation not in ("S", "P"):
            raise ValueError("unknown transform kind or representation")
        if type(self.order) is not tuple or type(self.materialize) is not tuple:
            raise TypeError("order and materialize must be immutable tuples")
        if self.kind == "direct":
            if self.order or self.materialize:
                raise ValueError("direct enumeration has no elimination flags")
            return
        if (len(self.order) != N
                or any(type(variable) is not int for variable in self.order)
                or sorted(self.order) != list(range(N))
                or len(self.materialize) != N
                or any(type(flag) is not bool for flag in self.materialize)):
            raise ValueError("VE requires a size-four permutation and four Boolean flags")


def canonical_transform(transform):
    """Stable raw-description key shared by all M9 tables."""
    if isinstance(transform, dict):
        transform = M9Transform.from_dict(transform)
    if not isinstance(transform, Transform):
        raise TypeError("expected a transform or transform description")
    return json.dumps(transform.to_dict(), sort_keys=True, separators=(",", ":"))


def spec_digest(data):
    """Canonical JSON digest used by the existing evidence archives."""
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def enumerate_candidates():
    """Return the complete 770-description M9 raw candidate space."""
    for representation in ("S", "P"):
        yield M9Transform("direct", representation=representation)
    for representation in ("S", "P"):
        for order in permutations(range(N)):
            for flags in product((False, True), repeat=N):
                yield M9Transform("ve", order, flags, representation)


def candidate_catalog():
    """Return JSON-safe candidate descriptions and their full-IR classes."""
    candidates = []
    by_signature = {}
    for raw_index, transform in enumerate(enumerate_candidates()):
        compiled = compile_transform(M9Problem(N), transform)
        key = canonical_transform(transform)
        signature = compiled_signature(compiled)
        candidate_id = f"Q{raw_index:03d}"
        class_id = f"K{signature[:16]}"
        candidates.append({"id": candidate_id, "canonical": key,
                           "transform": transform.to_dict(),
                           "class_id": class_id, "class_signature": signature,
                           "raw_index": raw_index})
        by_signature.setdefault(signature, []).append(key)
    if len(candidates) != EXPECTED_CANDIDATES:
        raise AssertionError("M9 candidate enumeration is incomplete")

    representatives = {}
    members = {}
    for signature, keys in by_signature.items():
        ordered = sorted(keys)
        class_id = f"K{signature[:16]}"
        representatives[class_id] = {"signature": signature, "canonical": ordered[0]}
        for key in ordered:
            members[key] = class_id
    abstraction = {
        "definition": "complete ordered IR, representation and output mapping",
        "classes": len(by_signature),
        "representatives": representatives,
        "members": members,
        "signature_sha256": spec_digest(
            {signature: sorted(keys) for signature, keys in sorted(by_signature.items())}
        ),
    }
    return candidates, abstraction


def frozen_domains():
    """Return the four fixed 64-input domains in Boolean dictionary order."""
    definitions = [
        ("D1", (0, 1, 2, 3, 4, 5), "alpha0,alpha1 plus complete f1 table"),
        ("D2", (0, 1, 6, 7, 8, 9), "alpha0,alpha1 plus complete f2 table"),
        ("D3", (0, 1, 10, 11, 12, 13), "alpha0,alpha1 plus complete f3 table"),
        ("D4", (0, 1, 2, 5, 7, 12),
         "alpha0,alpha1 plus f1(0,0),f1(1,1),f2(0,1),f3(1,0)"),
    ]
    domains = []
    for domain_id, free_slots, description in definitions:
        slots = tuple(free_slots)
        inputs = []
        for values in product((False, True), repeat=len(slots)):
            bits = [False, False] + [True, False, False, True] * (N - 1)
            for slot, value in zip(slots, values):
                bits[slot] = value
            inputs.append(bits)
        if len(inputs) != EXPECTED_SMALL_INPUTS:
            raise AssertionError("small domain does not contain 64 inputs")
        domains.append({
            "id": domain_id,
            "free_slots": list(slots),
            "fixed_slots": sorted(set(range(INPUT_BITS)) - set(slots)),
            "fixed_relation": "factor table identity f_i(a,b) = (a == b)",
            "fixed_values": [{"slot": index, "value": bits}
                             for index, bits in enumerate([False, False] +
                                                          [True, False, False, True] * (N - 1))
                             if index not in slots],
            "description": description,
            "ordering": "Boolean dictionary order of free-slot values, false before true",
            "inputs": inputs,
        })
    return domains


def full_domain():
    """The complete 16,384-slot Boolean domain used for holdout verification."""
    return [list(bits) for bits in product((False, True), repeat=INPUT_BITS)]


def assignment_reference(bits):
    """Independent exhaustive assignment oracle over all four chain labels."""
    if type(bits) is not tuple or len(bits) != INPUT_BITS or any(type(bit) is not bool for bit in bits):
        raise ValueError("bits must be an exact tuple of 14 Booleans")
    for assignment in product((0, 1), repeat=N):
        if bits[assignment[0]] and all(
                bits[2 + 4 * i + 2 * assignment[i] + assignment[i + 1]]
                for i in range(N - 1)):
            return True
    return False


def compiled_signature(compiled):
    if not isinstance(compiled, CompiledTransform):
        raise TypeError("expected CompiledTransform")
    payload = {
        "ir": [[operation.kind, list(operation.arguments)] for operation in compiled.ir],
        "output": compiled.output,
        "representation": compiled.transform.representation,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def expected_value(bit):
    from ic_observation_contracts import value_spec
    from ic_primitive_port_verifier import Net
    from ic_research_artifacts import GraphSpec

    net = Net()
    value_spec("A", bit).instantiate(net, {"ROOT": net.boundary("OUT")})
    return GraphSpec.from_net(net)


def run_network(initial, expected, *, budget=None):
    """M7 FIFO execution semantics without importing its archived bindings."""
    from ic_coherent_output_decoder import port_graph_isomorphic
    from ic_primitive_port_verifier import RULES
    from ic_research_artifacts import GraphSpec
    from ic_schedule_audit import Schedule, ScheduledNet

    limits = {**BUDGET, **(budget or {})}
    if set(limits) != set(BUDGET) or any(type(value) is not int or value < 0
                                        for value in limits.values()):
        raise ValueError("invalid execution budget")
    net = initial.instantiate(ScheduledNet(Schedule()))
    net.begin_audit()
    steps = 0
    status = None
    if len(net.nodes) > limits["max_cells"]:
        status = "resource-exhausted"
    while status is None and net.active():
        if steps >= limits["max_steps"]:
            status = "incomplete"
            break
        pair = net.next_active()
        net.reduce(*pair)
        steps += 1
        if len(net.nodes) > limits["max_cells"]:
            status = "resource-exhausted"
    resources = net.statistics()
    census = resources["rule_census"]
    allocations = sum(census["".join(rule)] * len(rhs[0]) for rule, rhs in RULES.items())
    if (sum(census.values()) != steps or resources["primitive_interactions"] != steps
            or resources["runtime_cells_allocated"] != allocations
            or resources["initial_cells"] + allocations != resources["final_cells"] + 2 * steps):
        raise ValueError("primitive interaction and allocation accounts disagree")
    matches = not net.active() and port_graph_isomorphic(net, expected.instantiate())
    status = status or ("passed" if matches else "wrong-normal-form")
    initial_data, final_data = initial.to_dict(), GraphSpec.from_net(net).to_dict()
    return {"status": status, "initial_graph_sha256": spec_digest(initial_data),
            "whole_graph_matches_reference": matches, "resources": resources,
            "final_graph_sha256": spec_digest(final_data),
            "initial_graph": initial_data, "final_graph": final_data}


def evaluate_candidate(description, inputs, budget=None):
    """Compile once and execute one raw candidate over the supplied inputs.

    This function never receives the optimization target or another candidate's
    results.  It returns exact native FIFO evidence for each input in order.
    """
    if isinstance(description, dict) and "transform" in description:
        description = description["transform"]
    transform = M9Transform.from_dict(description)
    problem = M9Problem(N)
    started = perf_counter()
    compiled = compile_transform(problem, transform)
    compile_seconds = perf_counter() - started
    if not isinstance(inputs, (list, tuple)) or not inputs:
        raise ValueError("inputs must be a nonempty list or tuple")
    from ic_m9_accel import run_native
    records = []
    run_seconds = 0.0
    engine = "python"
    for index, raw_bits in enumerate(inputs):
        bits = problem.validate_bits(tuple(raw_bits))
        started = perf_counter()
        reference = assignment_reference(bits)
        initial = _build_network(problem, compiled, bits)
        construction_seconds = perf_counter() - started
        started = perf_counter()
        native = run_native(initial, budget=budget)
        if native is not None:
            initial_graph_sha256 = spec_digest(initial.to_dict())
        if native is None:
            result = run_network(initial, expected_value(reference), budget=budget)
            if result["status"] != "passed":
                result["initial_graph"] = initial.to_dict()
                result["final_graph"] = result["final_graph"]
        else:
            from ic_coherent_output_decoder import port_graph_isomorphic

            engine = "native-c"
            expected = expected_value(reference)
            graph_out = native["graph"]
            matches = (native["status"] == "passed" and graph_out is not None
                       and port_graph_isomorphic(graph_out.instantiate(),
                                                 expected.instantiate()))
            result = {
                "status": native["status"] if native["status"] != "passed" else
                          "passed" if matches else "wrong-normal-form",
                "whole_graph_matches_reference": matches,
                "resources": {"primitive_interactions": native["steps"],
                              "rule_census": native["rule_census"],
                              "peak_live_cells": native["peak"]},
                "initial_graph_sha256": initial_graph_sha256,
                "final_graph_sha256": spec_digest(graph_out.to_dict())
                                    if graph_out is not None else None,
            }
            if native["status"] != "passed":
                result["initial_graph"] = initial.to_dict()
                result["final_graph"] = graph_out.to_dict() if graph_out is not None else None
        execution_seconds = perf_counter() - started
        run_seconds += execution_seconds
        records.append({
            "input_index": index,
            "bits": list(bits),
            "reference": reference,
            "status": result["status"],
            "whole_graph_matches_reference": result["whole_graph_matches_reference"],
            "fifo_interactions": result["resources"]["primitive_interactions"],
            "initial_graph_sha256": result["initial_graph_sha256"],
            "final_graph_sha256": result["final_graph_sha256"],
            "rule_census": result["resources"]["rule_census"],
            "host_seconds": {"construction": construction_seconds,
                             "native_execution": execution_seconds},
        })
        if result["status"] != "passed":
            records[-1]["initial_graph"] = result["initial_graph"]
            records[-1]["final_graph"] = result["final_graph"]
    complete = all(record["status"] == "passed" for record in records)
    return {
        "transform": transform.to_dict(),
        "compiled_ir_sha256": compiled_signature(compiled),
        "compiled_ir_length": len(compiled.ir),
        "materialized_entries": compiled.materialized_entries,
        "input_count": len(records),
        "records": records,
        "worst_fifo_interactions": max(record["fifo_interactions"] for record in records)
        if complete else None,
        "status": "complete" if complete else "incomplete",
        "host_seconds": {
            "compile": compile_seconds,
            "native_execution": run_seconds,
        },
        "engine": engine,
    }


def _build_network(problem, compiled, bits):
    """M7 build_network with a compiled size-four transform."""
    from collections import deque

    from ic_localization.backend import (
        boolean_and,
        boolean_or,
        copy_value,
        decode,
        literal,
    )
    from ic_primitive_port_verifier import Net
    from ic_research_artifacts import GraphSpec

    uses = [0] * len(compiled.ir)
    for operation in compiled.ir:
        if operation.kind != "input":
            for child in operation.arguments:
                uses[child] += 1
    uses[compiled.output] += 1
    net = Net()
    representation = compiled.transform.representation
    available = [deque(copy_value(net, literal(net, representation, bit), uses[index]))
                 for index, bit in enumerate(bits)]
    for index, operation in enumerate(compiled.ir[problem.input_bits:], problem.input_bits):
        left, right = (available[child].popleft() for child in operation.arguments)
        builder = boolean_and if operation.kind == "and" else boolean_or
        available.append(deque(copy_value(net, builder(net, representation, left, right),
                                          uses[index])))
    decode(net, representation, available[compiled.output].popleft(), net.boundary("OUT"))
    if any(available):
        raise AssertionError("unconsumed linear IR ports")
    return GraphSpec.from_net(net)


if __name__ == "__main__":
    candidates, abstraction = candidate_catalog()
    print(json.dumps({"candidates": len(candidates), "classes": abstraction["classes"],
                      "domains": len(frozen_domains())}, sort_keys=True))
