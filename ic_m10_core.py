"""Frozen M10 four-variable topologies, inputs, candidates, and IC graphs.

M10 extends the M9 transform syntax to two graph topologies without changing
the M7/M9 interaction-combinator semantics.  A factor table is passed to the
compiler explicitly, so this module does not duplicate the Boolean backend.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from heapq import nsmallest
from itertools import product

from ic_localization.model import ChainProblem, CompiledTransform, IROp, Transform
from ic_m9_core import (M9Transform, _build_network, canonical_transform, compiled_signature,
                        enumerate_candidates, expected_value, spec_digest)


VERSION = "M10-v1"
N = 4
SMALL_INPUTS = 64
HOLDOUT_INPUTS = 256
CANDIDATES = 770
SMALL_CHECKS = 2 * CANDIDATES * SMALL_INPUTS

TOPOLOGY_DEFINITIONS = (
    {
        "id": "star4",
        "edges": ((0, 1), (0, 2), (0, 3)),
        "free_entries": (((0, 1), (0, 0)), ((0, 1), (1, 1)),
                         ((0, 2), (0, 1)), ((0, 3), (1, 0))),
    },
    {
        "id": "cycle4",
        "edges": ((0, 1), (0, 3), (1, 2), (2, 3)),
        "free_entries": (((0, 1), (0, 0)), ((0, 3), (1, 1)),
                         ((1, 2), (0, 1)), ((2, 3), (1, 0))),
    },
)
TOPOLOGY_IDS = tuple(item["id"] for item in TOPOLOGY_DEFINITIONS)


def frozen_topologies():
    """Return topology definitions in the frozen star-then-cycle order."""
    return [topology_definition(topology) for topology in TOPOLOGY_IDS]


@dataclass(frozen=True)
class M10Problem(ChainProblem):
    """A four-variable problem with one of the frozen undirected topologies."""

    topology: str = "star4"

    def __post_init__(self):
        if type(self.n) is not int or self.n != N:
            raise ValueError("M10 freezes four variables")
        if self.topology not in TOPOLOGY_IDS:
            raise ValueError("unknown M10 topology")

    @property
    def edges(self):
        return topology_definition(self.topology)["edges"]

    @property
    def input_bits(self):
        return 2 + 4 * len(self.edges)


def topology_definition(topology):
    """Return the canonical, JSON-safe definition for a frozen topology."""
    for definition in TOPOLOGY_DEFINITIONS:
        if definition["id"] == topology:
            return {
                "id": definition["id"],
                "edges": [list(edge) for edge in definition["edges"]],
                "free_entries": [{"edge": list(edge), "assignment": list(values)}
                                 for edge, values in definition["free_entries"]],
            }
    raise ValueError("unknown M10 topology")


def reference(bits, topology="star4"):
    """Directly enumerate all 16 assignments for one frozen topology."""
    definition = topology_definition(topology)
    edges = [tuple(edge) for edge in definition["edges"]]
    expected_bits = 2 + 4 * len(edges)
    if (type(bits) is not tuple or len(bits) != expected_bits
            or any(type(bit) is not bool for bit in bits)):
        raise ValueError("bits do not match the frozen topology input width")
    for assignment in product((0, 1), repeat=N):
        if bits[assignment[0]] and all(
                bits[2 + 4 * index + 2 * assignment[left] + assignment[right]]
                for index, (left, right) in enumerate(edges)):
            return True
    return False


def input_slots(topology):
    """The input positions: two unary entries, then four per declared edge."""
    definition = topology_definition(topology)
    slots = {"alpha": [0, 1], "factors": {}}
    position = 2
    for edge in definition["edges"]:
        key = "".join(str(variable) for variable in edge)
        slots["factors"][key] = {"edge": edge, "offset": position,
                                 "table_slots": list(range(position, position + 4))}
        position += 4
    if len(slots["factors"]) != len(definition["edges"]) or position != 2 + 4 * len(definition["edges"]):
        raise AssertionError("topology input layout does not match its edge count")
    return slots


def _slot_index(topology, edge, assignment):
    slots = input_slots(topology)["factors"]["".join(map(str, edge))]["offset"]
    return slots + 2 * assignment[0] + assignment[1]


def frozen_domains():
    """Return the exact 64-input small domain for each topology."""
    domains = []
    for topology in TOPOLOGY_IDS:
        definition = topology_definition(topology)
        slots = [0, 1] + [_slot_index(topology, tuple(item["edge"]), tuple(item["assignment"]))
                          for item in definition["free_entries"]]
        input_bits = 2 + 4 * len(definition["edges"])
        fixed = [False, False] + [True, False, False, True] * len(definition["edges"])
        inputs = []
        for values in product((False, True), repeat=len(slots)):
            bits = list(fixed)
            for slot, value in zip(slots, values):
                bits[slot] = value
            inputs.append(bits)
        if len(inputs) != SMALL_INPUTS:
            raise AssertionError("small domain does not contain 64 inputs")
        domains.append({"id": topology, "free_slots": slots,
                        "fixed_slots": [index for index in range(input_bits) if index not in slots],
                        "fixed_relation": "all unselected factor entries use f_i(a,b) = (a == b)",
                        "ordering": "Boolean dictionary order of free-slot values, false before true",
                        "inputs": inputs})
    return domains


def _hash_key(topology, bits):
    bits_text = "".join("1" if bit else "0" for bit in bits)
    message = f"M10-v1:{topology}:{bits_text}".encode("utf-8")
    return sha256(message).hexdigest(), bits_text


def holdout_domains():
    """Select 256 out-of-domain inputs by the frozen SHA-256 ordering."""
    domains = []
    small = {domain["id"]: {tuple(bits) for bits in domain["inputs"]} for domain in frozen_domains()}
    for topology in TOPOLOGY_IDS:
        input_bits = 2 + 4 * len(topology_definition(topology)["edges"])
        vectors = (bits for bits in product((False, True), repeat=input_bits)
                   if bits not in small[topology])
        selected = nsmallest(HOLDOUT_INPUTS, vectors, key=lambda bits: _hash_key(topology, bits))
        if len(selected) != HOLDOUT_INPUTS or any(bits in small[topology] for bits in selected):
            raise AssertionError("holdout inputs overlap or are incomplete")
        domains.append({"id": topology, "inputs": [list(bits) for bits in selected],
                        "ordering": "ascending SHA-256(\"M10-v1:<topology>:<bits>\"), bits as tie break",
                        "excluded_small_inputs": True})
    return domains


def candidate_catalog():
    """Return the same 770 topology-independent descriptions in M9 raw order."""
    candidates = []
    for raw_index, transform in enumerate(enumerate_candidates()):
        key = canonical_transform(transform)
        candidate = {"id": f"Q{raw_index:03d}", "canonical": key,
                     "transform": transform.to_dict(), "raw_index": raw_index}
        candidates.append(candidate)
    if len(candidates) != CANDIDATES:
        raise AssertionError("M10 candidate enumeration is incomplete")
    return candidates


def frozen_bindings():
    """Return the topology, input, and candidate definitions for the freeze."""
    return {
        "variable_count": N,
        "input_widths": {topology: 2 + 4 * len(topology_definition(topology)["edges"])
                         for topology in TOPOLOGY_IDS},
        "candidate_count": CANDIDATES,
        "small_input_count": SMALL_INPUTS,
        "holdout_input_count": HOLDOUT_INPUTS,
        "candidates": candidate_catalog(),
        "topologies": frozen_topologies(),
        "domains": frozen_domains(),
        "holdouts": holdout_domains(),
        "reference": "direct exhaustive assignment enumeration over four Boolean labels",
        "factor_numbering": "unary factor 0, then edge factors in topology edge order, then generated factors",
    }


def compile_transform(problem, transform):
    """Compile an M9 transform using the declared M10 factor tables.

    The implementation follows the M7 compiler's traversal and CSE behavior,
    with the factor graph supplied by the topology rather than hard-coded.
    """
    if not isinstance(problem, M10Problem):
        raise TypeError("expected an M10Problem")
    if not isinstance(transform, Transform):
        raise TypeError("expected a transform")
    if transform.kind == "ve" and len(transform.order) != N:
        raise ValueError("elimination permutation does not match problem size")
    edges = [tuple(edge) for edge in problem.edges]
    source = [IROp("input", (i,)) for i in range(problem.input_bits)]

    def node(kind, arguments):
        index = len(source)
        source.append(IROp(kind, tuple(arguments)))
        return index

    def fold(kind, arguments):
        arguments = list(arguments)
        if not arguments:
            raise ValueError("empty product or sum is outside the frozen grammar")
        root = arguments[0]
        for argument in arguments[1:]:
            root = node(kind, (root, argument))
        return root

    forced = []
    if transform.kind == "direct":
        terms = []
        for assignment in product((0, 1), repeat=N):
            terms.append(fold("and", [assignment[0]] + [
                2 + 4 * index + 2 * assignment[left] + assignment[right]
                for index, (left, right) in enumerate(edges)]))
        output = fold("or", terms)
    else:
        factors = [(0, (0,), {(v,): v for v in (0, 1)})]
        factors.extend((index + 1, edge,
                        {(a, b): 2 + 4 * index + 2 * a + b
                         for a, b in product((0, 1), repeat=2)})
                       for index, edge in enumerate(edges))
        for step, variable in enumerate(transform.order):
            incident = sorted((factor for factor in factors if variable in factor[1]),
                              key=lambda factor: factor[0])
            scope = tuple(sorted(set().union(*(set(factor[1]) for factor in incident)) - {variable}))
            table = {}
            for values in product((0, 1), repeat=len(scope)):
                assignment = dict(zip(scope, values))
                terms = []
                for value in (0, 1):
                    assignment[variable] = value
                    terms.append(fold("and", [factor[2][tuple(assignment[v] for v in factor[1])]
                                               for factor in incident]))
                table[values] = fold("or", terms)
                if transform.materialize[step]:
                    forced.append(table[values])
            factors = [factor for factor in factors if variable not in factor[1]]
            factors.append((len(edges) + 1 + step, scope, table))
        if len(factors) != 1 or factors[0][1]:
            raise AssertionError("topology elimination must leave one scalar")
        output = factors[0][2][()]

    ir = list(source[:problem.input_bits])
    shared = set(forced)
    memo = {index: index for index in range(problem.input_bits)}

    def expand(index):
        if index in memo:
            return memo[index]
        operation = source[index]
        arguments = tuple(expand(child) for child in operation.arguments)
        fresh = len(ir)
        ir.append(IROp(operation.kind, arguments))
        if index in shared:
            memo[index] = fresh
        return fresh

    for root in forced:
        expand(root)
    result = expand(output)
    return CompiledTransform(problem, transform, tuple(ir), result, len(forced))


def build_network(description, bits, *, topology="star4", compiled=None):
    """Build the literal IC graph for one candidate and one topology input."""
    if isinstance(description, dict) and "transform" in description:
        description = description["transform"]
    transform = M9Transform.from_dict(description)
    problem = M10Problem(N, topology)
    if (type(bits) is not tuple or len(bits) != problem.input_bits
            or any(type(bit) is not bool for bit in bits)):
        raise ValueError("bits do not match the topology input width")
    compiled = compile_transform(problem, transform) if compiled is None else compiled
    if not isinstance(compiled, CompiledTransform) or compiled.problem != problem or compiled.transform != transform:
        raise ValueError("compiled transform belongs to a different M10 problem or transform")
    return _build_network(problem, compiled, bits)


def prepare_candidate(description, topology="star4"):
    """Compile one candidate and return its reusable preparation record."""
    if isinstance(description, dict) and "transform" in description:
        description = description["transform"]
    transform = M9Transform.from_dict(description)
    problem = M10Problem(N, topology)
    compiled = compile_transform(problem, transform)
    return {"problem": problem, "compiled": compiled,
            "compiled_ir_sha256": compiled_signature(compiled)}


def graph_digest(graph):
    """Digest exact graph syntax, matching the graph hashes in execution evidence."""
    from ic_research_artifacts import GraphSpec
    if isinstance(graph, GraphSpec):
        graph = graph.to_dict()
    return spec_digest(graph)
