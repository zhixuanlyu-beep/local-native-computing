"""A deterministic finite grammar of literal IC component candidates.

The grammar enumerates every complete port matching for each requested cell
count and each ordered cell-kind tuple. It is intentionally syntactic: it
keeps disconnected graphs, active pairs, and wire cycles among cell/boundary
ports, while detached pure wire cycles are not represented (GraphSpec's
``cycles`` remains zero). No candidate is filtered for expected reduction
success and no runtime, oracle, or reducer is invoked.
"""
from dataclasses import dataclass
from itertools import product
from typing import Iterator

from ic_coherent_feedback import spec_digest
from ic_primitive_port_verifier import AR, pairings
from ic_research_artifacts import GraphSpec


MAX_ENUMERABLE_CELLS = 3
GRAMMAR_FORMAT = "IC-COMPONENT-CANDIDATES-1"


@dataclass(frozen=True)
class Candidate:
    """One literal graph and its deterministic serialization identity.

    ``index`` is the zero-based position in the grammar's deterministic
    enumeration. ``fingerprint`` is the full SHA-256 of the exact GraphSpec
    serialization (the existing ``spec_digest`` format); isomorphic but
    differently serialized graphs remain distinct candidates.
    """

    index: int
    spec: GraphSpec
    fingerprint: str
    cells: int


def _validated_interface(interface):
    if not isinstance(interface, tuple):
        raise TypeError("interface must be a tuple of boundary labels")
    for label in interface:
        if not isinstance(label, str):
            raise TypeError(f"boundary labels must be strings: {label!r}")
        if not label:
            raise ValueError("boundary labels must be non-empty")
    if len(set(interface)) != len(interface):
        raise ValueError(f"duplicate boundary labels: {interface!r}")
    return interface


def _validated_kinds(kinds):
    if not isinstance(kinds, tuple):
        raise TypeError("kinds must be a tuple of cell kinds")
    if not kinds:
        raise ValueError("kinds must not be empty")
    for kind in kinds:
        if not isinstance(kind, str):
            raise TypeError(f"cell kinds must be strings: {kind!r}")
        if kind not in AR:
            raise ValueError(f"unknown cell kind: {kind!r}")
    if len(set(kinds)) != len(kinds):
        raise ValueError(f"duplicate cell kinds: {kinds!r}")
    return kinds


def _validated_count(name, value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    if name == "max_cells" and value > MAX_ENUMERABLE_CELLS:
        raise ValueError(
            f"max_cells is limited to {MAX_ENUMERABLE_CELLS} to keep the grammar finite"
        )
    return value


def _validated_parameters(interface, max_cells, min_cells, kinds):
    interface = _validated_interface(interface)
    kinds = _validated_kinds(kinds)
    max_cells = _validated_count("max_cells", max_cells)
    min_cells = _validated_count("min_cells", min_cells)
    if min_cells > max_cells:
        raise ValueError("min_cells must not exceed max_cells")
    return interface, max_cells, min_cells, kinds


def _normalized_wire(left, right):
    """Use a stable endpoint orientation without changing the matching."""
    left_boundary = left[0] == "F"
    right_boundary = right[0] == "F"
    if left_boundary and not right_boundary:
        return left, right
    if right_boundary and not left_boundary:
        return right, left
    if left_boundary and right_boundary:
        return (left, right) if left[1] <= right[1] else (right, left)
    return (left, right) if left <= right else (right, left)


def candidate_specs(interface, max_cells, min_cells=0, kinds=("e", "g", "d")):
    """Yield every literal complete GraphSpec in a deterministic order.

    For each cell count from ``min_cells`` through ``max_cells`` inclusive,
    every ordered tuple of the supplied cell kinds is considered. All exact
    pairings of cell ports plus fixed interface ports are emitted; a kind
    tuple whose total port count is odd yields no matching. The interface
    order and labels are preserved, detached wire cycles are not added, and
    candidates are not deduplicated isomorphically.
    """
    interface, max_cells, min_cells, kinds = _validated_parameters(
        interface, max_cells, min_cells, kinds
    )
    return _enumerate_candidates(interface, max_cells, min_cells, kinds)


def _enumerate_candidates(interface, max_cells, min_cells, kinds):
    """Lazily generate the already validated candidate stream."""
    index = 0
    for cell_count in range(min_cells, max_cells + 1):
        for kind_tuple in product(kinds, repeat=cell_count):
            endpoints = [
                (cell_index, port)
                for cell_index, kind in enumerate(kind_tuple)
                for port in range(AR[kind] + 1)
            ]
            endpoints.extend(("F", label) for label in interface)
            if len(endpoints) % 2:
                continue
            for matching in pairings(endpoints):
                wires = tuple(
                    _normalized_wire(left, right) for left, right in matching
                )
                spec = GraphSpec(kind_tuple, interface, wires, 0)
                yield Candidate(
                    index=index,
                    spec=spec,
                    fingerprint=spec_digest(spec.to_dict()),
                    cells=cell_count,
                )
                index += 1


def grammar_descriptor(interface, max_cells, min_cells=0, kinds=("e", "g", "d")):
    """Return a serializable description of the exact enumeration contract."""
    interface, max_cells, min_cells, kinds = _validated_parameters(
        interface, max_cells, min_cells, kinds
    )
    return {
        "format": GRAMMAR_FORMAT,
        "interface": list(interface),
        "min_cells": min_cells,
        "max_cells": max_cells,
        "kinds": list(kinds),
        "cell_kind_tuples": "ordered_with_repetition",
        "matching": "all_exact_port_pairings",
        "wire_cycles": 0,
        "deduplication": "none",
        "fingerprint": "sha256_of_sorted_json_serialization",
        "max_enumerable_cells": MAX_ENUMERABLE_CELLS,
    }


def grammar_digest(interface, max_cells, min_cells=0, kinds=("e", "g", "d")):
    """Return the full SHA-256 digest of the grammar descriptor."""
    return spec_digest(grammar_descriptor(interface, max_cells, min_cells, kinds))
