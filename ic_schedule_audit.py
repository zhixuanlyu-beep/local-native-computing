"""Deterministic active-pair policies and exact primitive resource accounting.

Only pair selection is new: every rewrite remains FastNet/Net.reduce.
SplitMix64 and rejection sampling are specified here for portable replay.
Cell ownership is optional instrumentation for a projected disjoint trace.
"""
from collections import Counter, deque
from collections.abc import Mapping
from dataclasses import dataclass
import gzip
import hashlib
import json
from ic_evidence_json import loads as json_loads
import struct

from ic_coherent_feedback import PrimitiveTrace
from ic_fast_reducer import FastNet
from ic_primitive_port_verifier import RULES


MASK = (1 << 64) - 1
RULE_LABELS = tuple("".join(pair) for pair in RULES)


@dataclass(frozen=True)
class Schedule:
    policy: str = "fifo"
    seed: int | None = None

    def __post_init__(self):
        if self.policy not in ("fifo", "lifo", "seeded", "witness"):
            raise ValueError("unknown active-pair policy")
        if self.policy == "seeded":
            if type(self.seed) is not int or not 0 <= self.seed <= MASK:
                raise ValueError("seeded selection requires an unsigned 64-bit seed")
        elif self.seed is not None:
            raise ValueError("only the seeded policy accepts a seed")

    def to_dict(self):
        return {"policy": self.policy, "seed": self.seed,
                "sampler": "splitmix64-rejection-v1" if self.policy == "seeded" else None,
                "ordering": ("validated frozen witness with explicit fresh-cell renaming" if self.policy == "witness"
                             else "link insertion order; random index uses swap-with-last deletion")}


class ScheduledNet(FastNet):
    def __init__(self, schedule=Schedule(), debug_local_invariants=False):
        if not isinstance(schedule, Schedule):
            raise TypeError("schedule must be a Schedule")
        super().__init__(debug_local_invariants)
        self.schedule = schedule
        self._stack, self._items, self._positions = [], [], {}
        self._rng = schedule.seed or 0
        self._selected = None
        self._audit_started = False
        self._current_owner = None
        self._owners = {}
        self._census = Counter({label: 0 for label in RULE_LABELS})
        self._steps = self._allocated = 0

    def link(self, a, b):
        super().link(a, b)
        if a[1] != 0 or b[1] != 0 or a[0] not in self.nodes or b[0] not in self.nodes:
            return
        pair = tuple(sorted((a[0], b[0])))
        self._selected = None
        if self.schedule.policy == "lifo":
            self._stack.append(pair)
        elif self.schedule.policy == "seeded":
            if pair in self._positions:
                raise AssertionError("active pair inserted twice")
            self._positions[pair] = len(self._items)
            self._items.append(pair)

    def _u64(self):
        self._rng = (self._rng + 0x9E3779B97F4A7C15) & MASK
        value = self._rng
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK
        return value ^ (value >> 31)

    def _index(self, count):
        limit = (1 << 64) - (1 << 64) % count
        while True:
            value = self._u64()
            if value < limit:
                return value % count

    def next_active(self):
        if self.schedule.policy == "witness":
            raise ValueError("a witness prefix requires an explicitly validated active pair")
        if self.schedule.policy == "fifo":
            return super().next_active()
        if self._selected is not None and self._pair_is_current(self._selected):
            return self._selected
        if self.schedule.policy == "lifo":
            while self._stack and not self._pair_is_current(self._stack[-1]):
                self._stack.pop()
            pair = self._stack[-1] if self._stack else None
        else:
            pair = self._items[self._index(len(self._items))] if self._items else None
            if pair is not None and not self._pair_is_current(pair):
                raise AssertionError("random live index contains a stale active pair")
        self._selected = pair
        return pair

    def begin_audit(self, owners=None):
        if self._audit_started:
            raise ValueError("resource audit already started")
        if owners is None:
            owners = {cell: "network" for cell in self.nodes}
        if not isinstance(owners, Mapping):
            raise TypeError("ownership must be a mapping from initial cells to component labels")
        if set(owners) != set(self.nodes) or any(not isinstance(v, str) or not v for v in owners.values()):
            raise ValueError("ownership must name every initial cell exactly once")
        self._owners = dict(owners)
        self._initial = len(self.nodes)
        self._peak = self._initial
        self._initial_counts = Counter(owners.values())
        self._live = self._initial_counts.copy()
        self._peaks = self._initial_counts.copy()
        self._component_steps = Counter()
        self._audit_started = True

    def cell(self, kind):
        if self._audit_started and self._current_owner is None:
            raise ValueError("runtime cell allocation must belong to a primitive interaction")
        name = super().cell(kind)
        if self._audit_started:
            self._allocated += 1
            self._owners[name] = self._current_owner
        return name

    def reduce(self, u, v):
        pair = self._validate_reduce_pair(u, v)
        if not self._audit_started:
            self.begin_audit()
        owner = self._owners[u]
        if owner != self._owners[v]:
            raise ValueError("a primitive pair crosses declared independent components")
        kinds = (self.nodes[u], self.nodes[v])
        rule = kinds if kinds in RULES else kinds[::-1]
        rhs_cells = len(RULES[rule][0])
        before, allocated_before = len(self.nodes), self._allocated
        if self.schedule.policy == "seeded":
            index = self._positions.pop(pair)
            last = self._items.pop()
            if index < len(self._items):
                self._items[index] = last
                self._positions[last] = index
        elif self.schedule.policy == "lifo" and self._stack and self._stack[-1] == pair:
            self._stack.pop()
        self._selected = None
        self._current_owner = owner
        try:
            super().reduce(u, v)
        finally:
            self._current_owner = None
        del self._owners[u], self._owners[v]
        if len(self.nodes) != before + rhs_cells - 2 or self._allocated - allocated_before != rhs_cells:
            raise AssertionError("primitive allocation balance differs from the rule syntax")
        self._steps += 1
        self._census["".join(rule)] += 1
        self._live[owner] += rhs_cells - 2
        self._peaks[owner] = max(self._peaks[owner], self._live[owner])
        self._component_steps[owner] += 1
        self._peak = max(self._peak, len(self.nodes))
        # Non-FIFO policies must not retain every erased ID in the inherited
        # FIFO queue. Filtering preserves precisely its remaining birth order.
        if len(self._active_queue) > 4 * len(self._active_pairs) + 1024:
            self._active_queue = deque(self._active_pairs)
        if len(self._stack) > 4 * len(self._active_pairs) + 1024:
            self._stack = [p for p in self._stack if self._pair_is_current(p)]

    def check(self):
        if self._in_reduce:
            return
        super().check()
        if self.schedule.policy == "seeded":
            if set(self._positions) != set(self._active_pairs) or len(self._items) != len(self._positions):
                raise AssertionError("random index and active-pair index disagree")
            if any(self._positions[pair] != i for i, pair in enumerate(self._items)):
                raise AssertionError("random index positions disagree")
        if self._audit_started:
            if set(self._owners) != set(self.nodes) or Counter(self._owners.values()) != self._live:
                raise AssertionError("component live-cell ledger disagrees with the graph")

    def statistics(self):
        if not self._audit_started:
            self.begin_audit()
        self.final_check()
        predicted = self._initial + sum(self._census["".join(k)] * (len(rhs[0]) - 2) for k, rhs in RULES.items())
        positive_bound = self._initial + 2 * self._census["gd"]
        if predicted != len(self.nodes) or self._peak > positive_bound:
            raise AssertionError("rule-census resource equation failed")
        components = {tag: {"initial_cells": count, "final_cells": self._live[tag],
                            "projected_peak": self._peaks[tag], "primitive_interactions": self._component_steps[tag]}
                      for tag, count in sorted(self._initial_counts.items())}
        upper = sum(c["projected_peak"] for c in components.values())
        if self._peak > upper or sum(c["primitive_interactions"] for c in components.values()) != self._steps:
            raise AssertionError("component projection resource equation failed")
        return {"schedule": self.schedule.to_dict(), "initial_cells": self._initial,
                "primitive_interactions": self._steps, "peak_live_cells": self._peak,
                "final_cells": len(self.nodes), "cyclic_wires": self.cycles,
                "rule_census": dict(self._census), "runtime_cells_allocated": self._allocated,
                "total_symbolic_cells_allocated": self._initial + self._allocated,
                "census_predicted_final_cells": predicted, "positive_delta_peak_bound": positive_bound,
                "components": components, "sum_projected_peaks_bound": upper,
                "scope": "measured finite trace and its ownership projections; not host byte memory"}


class ScheduleTrace:
    """Existing pair-record format with policy-neutral strict replay."""
    def __init__(self, path, metadata, replay=False):
        self.replay, self.count = replay, 0
        self.digest = hashlib.sha256()
        if replay:
            self.stream = gzip.open(path, "rb")
            try:
                if json_loads(self.stream.readline()) != {"format": "IC-PAIR-U32LE-1", **metadata}:
                    raise ValueError("composition trace header binding mismatch")
            except BaseException:
                self.stream.close()
                raise
        else:
            self.writer = PrimitiveTrace(path, metadata)

    def record(self, pair):
        if self.replay:
            raw = self.stream.read(8)
            if len(raw) != 8:
                raise ValueError("truncated composition primitive trace")
            if tuple("c" + str(i) for i in struct.unpack("<II", raw)) != pair:
                raise ValueError("trace pair differs from the specified reconstructed schedule")
            self.digest.update(raw)
        else:
            self.writer.record(pair)
        self.count += 1

    def abort(self):
        self.stream.close() if self.replay else self.writer.close()

    def close(self):
        if not self.replay:
            return self.writer.close()
        try:
            if self.stream.read(1):
                raise ValueError("unaccounted composition primitive trace records")
        finally:
            self.stream.close()
        return {"format": "IC-PAIR-U32LE-1", "steps": self.count,
                "sha256_of_pair_records": self.digest.hexdigest()}
