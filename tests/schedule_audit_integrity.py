"""Integrity tests for deterministic scheduled primitive-IC execution.

All checks use the production Schedule, ScheduledNet, and ScheduleTrace
classes.  Every initial graph is rebuilt through GraphSpec.from_net, so cell
identifiers and wiring match without hand-copying mutable Net state.
"""

from __future__ import annotations

from copy import deepcopy
import gzip
from itertools import product
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ic_fast_reducer import FastNet
from ic_primitive_port_verifier import AR, Net, RULES, isomorphic, pair
from ic_research_artifacts import GraphSpec
from ic_schedule_audit import Schedule, ScheduledNet, ScheduleTrace


POLICIES = (Schedule("fifo"), Schedule("lifo"), Schedule("seeded", 0))


def instantiate(source, schedule):
    return GraphSpec.from_net(source).instantiate(ScheduledNet(schedule))


def reduce_scheduled(net, limit=10_000):
    steps, peak = 0, len(net.nodes)
    while (redex := net.next_active()) is not None:
        if steps >= limit:
            raise RuntimeError("test normalization budget exhausted")
        net.reduce(*redex)
        steps += 1
        peak = max(peak, len(net.nodes))
    net.final_check()
    return steps, peak


def two_redex_context(first_kinds, second_kinds, wiring):
    """Build a complete four-cell, two-active-pair context."""
    net = Net()
    a, b, c, d = (net.cell(kind)
                  for kind in (first_kinds[0], first_kinds[1],
                               second_kinds[0], second_kinds[1]))
    net.link((a, 0), (b, 0))
    net.link((c, 0), (d, 0))
    auxiliary = [
        (cell, port)
        for cell, kind in ((a, first_kinds[0]), (b, first_kinds[1]),
                           (c, second_kinds[0]), (d, second_kinds[1]))
        for port in range(1, AR[kind] + 1)
    ]
    for index, endpoint in enumerate(auxiliary):
        if index not in {edge for wire in wiring for edge in wire}:
            net.link(endpoint, net.boundary(f"X{index}"))
    for left, right in wiring:
        net.link(auxiliary[left], auxiliary[right])
    net.check()
    return net, (a, b), (c, d)


def two_independent_pairs():
    """Two complete active pairs with all auxiliary ports wired to boundaries."""
    net = Net()
    cells = [net.cell("g"), net.cell("e"), net.cell("g"), net.cell("e")]
    net.link((cells[0], 0), (cells[1], 0))
    net.link((cells[2], 0), (cells[3], 0))
    for cell in cells[:2]:
        for port in range(1, AR["g" if cell is cells[0] else "e"] + 1):
            if port:
                net.link((cell, port), net.boundary(f"L{cell}-{port}"))
    for cell in cells[2:]:
        for port in range(1, AR["g" if cell is cells[2] else "e"] + 1):
            if port:
                net.link((cell, port), net.boundary(f"R{cell}-{port}"))
    net.check()
    return net, (cells[0], cells[1]), (cells[2], cells[3]), cells


class SixPrimitiveRules(unittest.TestCase):
    def runTest(self):
        for schedule in POLICIES:
            for left, right in sorted(RULES):
                with self.subTest(policy=schedule.policy, rule=(left, right)):
                    source, a, b, _ = pair(left, right)
                    scheduled = instantiate(source, schedule)
                    selected = scheduled.next_active()
                    self.assertEqual(tuple(sorted(selected)), tuple(sorted((a, b))))
                    scheduled.reduce(*selected)
                    reference = deepcopy(source)
                    reference.reduce(a, b)
                    scheduled.final_check()
                    self.assertFalse(scheduled.active())
                    self.assertTrue(isomorphic(scheduled, reference))
                    self.assertEqual(
                        scheduled.statistics()["rule_census"]["".join((left, right))], 1
                    )


class RepresentativeDiamonds(unittest.TestCase):
    def runTest(self):
        cases = (
            (("g", "g"), ("d", "d"), ((0, 2), (1, 3))),
            (("g", "d"), ("g", "d"), ((0, 1), (2, 3))),
            (("g", "g"), ("e", "e"), ()),
            (("d", "e"), ("d", "e"), ()),
        )
        for case, schedule in product(cases, POLICIES):
            first, second, wiring = case
            with self.subTest(first=first, second=second, wiring=wiring,
                              policy=schedule.policy):
                source, left, right = two_redex_context(first, second, wiring)
                one = instantiate(source, schedule)
                two = instantiate(source, schedule)
                self.assertEqual(set(one.active()), {left, right})
                one.reduce(*left)
                self.assertTrue(right in one.active()
                                or tuple(reversed(right)) in one.active())
                one.reduce(*right)
                two.reduce(*right)
                self.assertTrue(left in two.active()
                                or tuple(reversed(left)) in two.active())
                two.reduce(*left)
                one.final_check()
                two.final_check()
                self.assertTrue(isomorphic(one, two))
                self.assertEqual(sum(one.statistics()["rule_census"].values()), 2)
                self.assertEqual(sum(two.statistics()["rule_census"].values()), 2)


class PolicyFidelityAndReplay(unittest.TestCase):
    def test_fifo_matches_fastnet_on_short_gamma_epsilon_packages(self):
        for levels in range(6):
            with self.subTest(levels=levels):
                source = Net()
                root = (source.cell("e"), 0)
                for _ in range(levels):
                    cell = source.cell("g")
                    source.link((cell, 1), root)
                    source.link((cell, 2), (source.cell("e"), 0))
                    root = (cell, 0)
                source.link(root, source.boundary("ROOT"))
                source.check()
                scheduled = instantiate(source, Schedule("fifo"))
                fast = GraphSpec.from_net(source).instantiate(FastNet())
                while True:
                    expected = fast.next_active()
                    actual = scheduled.next_active()
                    self.assertEqual(expected, actual)
                    if actual is None:
                        break
                    fast.reduce(*expected)
                    scheduled.reduce(*actual)
                self.assertTrue(isomorphic(scheduled, fast))

    def test_seeded_selection_is_reproducible_and_validation_is_strict(self):
        seed = 0x123456789ABCDEF0
        schedule = Schedule("seeded", seed)
        source = Net()
        left, right = source.cell("g"), source.cell("g")
        source.link((left, 0), (right, 0))
        source.link((left, 1), (right, 2))
        source.link((left, 2), (right, 1))
        source.check()
        first = instantiate(source, schedule)
        second = instantiate(source, schedule)
        first_pairs, second_pairs = [], []
        while (redex := first.next_active()) is not None:
            first_pairs.append(redex)
            first.reduce(*redex)
        while (redex := second.next_active()) is not None:
            second_pairs.append(redex)
            second.reduce(*redex)
        self.assertEqual(first_pairs, second_pairs)
        self.assertTrue(isomorphic(first, second))
        self.assertEqual(first.statistics()["primitive_interactions"], len(first_pairs))

        invalid = ((-1,), (1 << 64,), (True,))
        for seed_args in invalid:
            with self.subTest(seed_args=seed_args), self.assertRaises(ValueError):
                Schedule("seeded", *seed_args)
        with self.assertRaises(ValueError):
            Schedule("fifo", 1)


class OwnershipAndResources(unittest.TestCase):
    def test_lineage_and_cross_component_rejection(self):
        source, left, right, cells = two_independent_pairs()
        net = instantiate(source, Schedule("fifo"))
        names = list(net.nodes)
        owners = {names[0]: "left", names[1]: "left", names[2]: "right", names[3]: "right"}
        # Pair the two gamma cells across components: this is an active pair,
        # but it violates the declared independent ownership projection.
        pair_ = tuple(sorted((names[0], names[2])))
        net._active_pairs[pair_] = None
        net._active_queue.append(pair_)
        # Do not call reduce via next_active: this projection deliberately
        # requests an active pair that crosses the two declared owners.
        net.begin_audit(owners)
        with self.assertRaises(ValueError):
            net.reduce(names[0], names[2])

    def test_runtime_allocation_outside_interaction_rejected(self):
        net = ScheduledNet(Schedule("fifo"))
        net.cell("g")
        net.begin_audit()
        with self.assertRaises(ValueError):
            net.cell("g")

    def test_rule_census_resource_equation(self):
        source, _, _, _ = pair("g", "e")
        net = instantiate(source, Schedule("lifo"))
        steps, peak = reduce_scheduled(net)
        stats = net.statistics()
        self.assertEqual(steps, 1)
        self.assertEqual(stats["primitive_interactions"], 1)
        self.assertEqual(stats["runtime_cells_allocated"], 2)
        self.assertEqual(stats["rule_census"]["ge"], 1)
        self.assertEqual(stats["census_predicted_final_cells"], len(net.nodes))
        self.assertGreaterEqual(peak, len(net.nodes))


class TinyTraceIntegrity(unittest.TestCase):
    def test_trace_replay_and_corruption_rejection(self):
        schedule = Schedule("seeded", 11)
        metadata = {"scope": "tiny schedule trace", **schedule.to_dict()}
        source, a, b, _ = pair("g", "e")
        spec = GraphSpec.from_net(source)
        with tempfile.TemporaryDirectory(prefix="schedule-trace-") as directory:
            path = Path(directory) / "tiny.ictrace.gz"
            writer = ScheduleTrace(path, metadata)
            net = spec.instantiate(ScheduledNet(schedule))
            while (redex := net.next_active()) is not None:
                writer.record(redex)
                net.reduce(*redex)
            writer.close()
            original = gzip.decompress(path.read_bytes())
            header, records = original.split(b"\n", 1)
            self.assertEqual(json.loads(header), {"format": "IC-PAIR-U32LE-1", **metadata})
            self.assertEqual(len(records), 8)

            def replay():
                reader = ScheduleTrace(path, metadata, replay=True)
                try:
                    replay_net = spec.instantiate(ScheduledNet(schedule))
                    while (redex := replay_net.next_active()) is not None:
                        reader.record(redex)
                        replay_net.reduce(*redex)
                    reader.close()
                except BaseException:
                    reader.abort()
                    raise

            replay()
            changed_header = json.loads(header)
            changed_header["seed"] = 12
            variants = [
                original[:-1], original[:-8], original + b"\0" * 8,
                json.dumps(changed_header).encode() + b"\n" + records,
                header + b"\n" + records[4:8] + records[:4],
            ]
            for variant in variants:
                with self.subTest(size=len(variant)):
                    path.write_bytes(gzip.compress(variant, mtime=0))
                    with self.assertRaises(ValueError):
                        replay()


if __name__ == "__main__":
    unittest.main(verbosity=2)
