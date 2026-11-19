"""Optional ctypes bridge to the exact M9 C FIFO reducer.

The Python engine remains the reference implementation. A shared library is
used only when selected by IC_M9_NATIVE_LIBRARY. Native results are converted
back into a GraphSpec so callers apply the same whole-graph terminal check.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

from ic_primitive_port_verifier import AR
from ic_research_artifacts import GraphSpec


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY = ROOT / "ic-research-scratch" / "ic_m9_native.dll"
RULE_ORDER = (
    ("g", "g"),
    ("d", "d"),
    ("e", "e"),
    ("g", "e"),
    ("d", "e"),
    ("g", "d"),
)
KIND_CODE = {"g": 0, "d": 1, "e": 2}
CODE_KIND = {code: kind for kind, code in KIND_CODE.items()}


class Result(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int),
        ("steps", ctypes.c_int),
        ("peak", ctypes.c_int),
        ("cycles", ctypes.c_int),
        ("cell_count", ctypes.c_int),
        ("live", ctypes.c_int),
        ("census", ctypes.c_int * 6),
        ("kinds", ctypes.POINTER(ctypes.c_int)),
        ("adj", ctypes.POINTER(ctypes.c_int)),
    ]


_LIBRARY = None
_LOADED_PATH = None
_TABLE = None


def _library():
    global _LIBRARY, _LOADED_PATH
    configured = os.environ.get("IC_M9_NATIVE_LIBRARY")
    if not configured:
        return None
    path = Path(configured)
    if not path.is_file():
        raise ValueError(f"configured M9 native library does not exist: {path}")
    if _LIBRARY is not None and path == _LOADED_PATH:
        return _LIBRARY
    library = ctypes.CDLL(str(path))
    library.m9_run.argtypes = [
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(Result),
    ]
    library.m9_run.restype = ctypes.c_int
    library.m9_free.argtypes = [ctypes.POINTER(Result)]
    library.m9_free.restype = None
    _LIBRARY, _LOADED_PATH = library, path
    return library


def _endpoint_code(endpoint, cell_index):
    if endpoint[0] == "F":
        if endpoint[1] != "OUT":
            raise ValueError("native M9 reducer supports the OUT boundary")
        return 0
    return 1 + 3 * cell_index[endpoint[0]] + endpoint[1]


def _rule_table():
    global _TABLE
    if _TABLE is not None:
        return _TABLE
    from ic_primitive_port_verifier import RULES

    values = []
    for left_kind, right_kind in RULE_ORDER:
        new_types, wires = RULES[(left_kind, right_kind)]
        new_names = list(new_types)
        index = {name: position for position, name in enumerate(new_names)}

        def encode(endpoint):
            if isinstance(endpoint, str):
                return int(endpoint[1:]) - 1 + 2 * (endpoint[0] == "B")
            return 4 + 3 * index[endpoint[0]] + endpoint[1]

        row = [KIND_CODE[left_kind], KIND_CODE[right_kind], len(new_names), len(wires)]
        row.extend(KIND_CODE[new_types[name]] for name in new_names)
        row.extend([-1] * (4 - len(new_names)))
        encoded = [encode(endpoint) for wire in wires for endpoint in wire]
        row.extend(encoded + [-1] * (16 - len(encoded)))
        values.extend(row)
    _TABLE = (ctypes.c_int * len(values))(*values)
    return _TABLE


def run_native(graph, *, budget=None):
    """Run one GraphSpec through the optional C reducer.

    Returns None when no library is configured. The Result is copied into
    Python data and released before return. C status maps to the Python status
    vocabulary, and the current graph is decoded for terminal and partial runs.
    """
    library = _library()
    if library is None:
        return None
    if not isinstance(graph, GraphSpec) or graph.boundaries != ("OUT",) or graph.cycles:
        raise ValueError("native M9 bridge requires one OUT boundary and no cycles")
    limits = {"max_steps": 2_000_000, "max_cells": 250_000, **(budget or {})}
    cell_index = {i: i for i in range(len(graph.kinds))}
    kinds = (ctypes.c_int * len(graph.kinds))(
        *(KIND_CODE[kind] for kind in graph.kinds)
    )
    flat_edges = []
    for left, right in graph.wires:
        flat_edges.extend((_endpoint_code(left, cell_index),
                           _endpoint_code(right, cell_index)))
    edges = (ctypes.c_int * len(flat_edges))(*flat_edges)
    result = Result()
    status = library.m9_run(
        len(graph.kinds),
        kinds,
        len(graph.wires),
        edges,
        _rule_table(),
        graph.cycles,
        limits["max_steps"],
        limits["max_cells"],
        ctypes.byref(result),
    )
    if status != 0:
        raise ValueError(f"native M9 reducer rejected the graph (ABI status {status})")
    try:
        terminal = result.status == 0
        native_status = {0: "passed", 1: "incomplete", 2: "resource-exhausted"}[
            result.status
        ]
        graph_out = _decode_result(result)
        return {
            "status": native_status,
            "terminal": terminal,
            "steps": result.steps,
            "peak": result.peak,
            "cycles": result.cycles,
            "cell_count": result.cell_count,
            "live": result.live,
            "rule_census": dict(zip(
                ("".join(pair) for pair in RULE_ORDER),
                (result.census[i] for i in range(6)),
                strict=True,
            )),
            "graph": graph_out,
        }
    finally:
        library.m9_free(ctypes.byref(result))


def _decode_result(result):
    live_names = []
    live_set = set()
    for index in range(result.cell_count):
        code = result.kinds[index]
        if code in CODE_KIND:
            live_set.add(index)
            live_names.append(CODE_KIND[code])
    name_index = {index: position for position, index in enumerate(sorted(live_set))}
    wires = []
    seen = set()
    for index in sorted(live_set):
        kind = CODE_KIND[result.kinds[index]]
        for port in range(AR[kind] + 1):
            endpoint = 1 + 3 * index + port
            if endpoint in seen:
                continue
            neighbor = result.adj[endpoint]
            if neighbor < 0:
                continue
            if neighbor == 0:
                left = ("F", "OUT")
                right = (name_index[index], port)
                seen.add(endpoint)
            else:
                neighbor_index = (neighbor - 1) // 3
                if neighbor_index not in live_set:
                    raise ValueError("final native graph links to a dead cell")
                left = (name_index[index], port)
                right = (name_index[neighbor_index], (neighbor - 1) % 3)
                seen.update((endpoint, neighbor))
            wires.append((left, right))
    return GraphSpec(tuple(live_names), ("OUT",), tuple(wires), result.cycles)
