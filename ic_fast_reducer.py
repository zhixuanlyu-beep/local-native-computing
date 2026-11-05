"""A fast literal-IC reducer with an incremental active-pair index.

FastNet reuses the original Net.reduce implementation unchanged, so the six
primitive Interaction Combinator rules, interface splicing, and cyclic-wire
metadata remain exactly those of ic_primitive_port_verifier.  The only
optimization is an O(1) active-pair membership index plus a deterministic
FIFO worklist.  No source rule, compiler step, or oracle is introduced.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from typing import Iterator

from ic_primitive_port_verifier import AR, Net, isomorphic, pairings


@dataclass(frozen=True)
class NormalizationResult:
    """Outcome of a bounded literal-IC normalization run."""

    steps: int
    peak_cells_after_step: int
    final_cells: int
    cycles: int
    terminal: bool
    cutoff: bool
    limit: int | None
    policy: str

    def to_dict(self) -> dict[str, int | bool | str | None]:
        return asdict(self)


class ActiveView:
    """A list-compatible O(1) membership view of active principal pairs."""

    def __init__(self, net: "FastNet"):
        self._net = net

    def __bool__(self) -> bool:
        return bool(self._net._active_pairs)

    def __len__(self) -> int:
        return len(self._net._active_pairs)

    def __contains__(self, pair: object) -> bool:
        if not isinstance(pair, tuple) or len(pair) != 2:
            return False
        left, right = pair
        if not isinstance(left, str) or not isinstance(right, str):
            return False
        canonical = tuple(sorted((left, right)))
        if self._net._in_reduce and self._net._reducing_pair == canonical:
            return True
        return canonical in self._net._active_pairs

    def __iter__(self) -> Iterator[tuple[str, str]]:
        # Compatibility path only: materialize the exact base order for code
        # that still expects a list-like active() result.
        return iter(Net.active(self._net))

    def __getitem__(self, index: int) -> tuple[str, str]:
        return list(self)[index]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ActiveView):
            return list(self) == list(other)
        if isinstance(other, (list, tuple)):
            return list(self) == list(other)
        return NotImplemented


class FastNet(Net):
    """Net with an incremental active-pair index and FIFO scheduling."""

    def __init__(self, debug_local_invariants: bool = False) -> None:
        super().__init__()
        self._active_pairs: dict[tuple[str, str], None] = {}
        self._active_queue: deque[tuple[str, str]] = deque()
        self._in_reduce = False
        self._reducing_pair: tuple[str, str] | None = None
        self.debug_local_invariants = bool(debug_local_invariants)

    def link(self, x, y) -> None:
        """Link and index a new principal-principal pair, if any."""
        super().link(x, y)
        if (
            x[1] == 0
            and y[1] == 0
            and x[0] in self.nodes
            and y[0] in self.nodes
        ):
            pair = tuple(sorted((x[0], y[0])))
            if pair not in self._active_pairs:
                self._active_pairs[pair] = None
                self._active_queue.append(pair)

    def active(self) -> ActiveView:
        return ActiveView(self)

    def _pair_is_current(self, pair: tuple[str, str]) -> bool:
        left, right = pair
        return (
            left in self.nodes
            and right in self.nodes
            and self.adj.get((left, 0)) == (right, 0)
            and self.adj.get((right, 0)) == (left, 0)
        )

    def next_active(self) -> tuple[str, str] | None:
        """Return the FIFO active pair without scanning all active pairs."""
        while self._active_queue:
            pair = self._active_queue[0]
            if self._pair_is_current(pair):
                return pair
            self._active_queue.popleft()
            self._active_pairs.pop(pair, None)
        return None

    @staticmethod
    def _canonical_cells(u: object, v: object) -> tuple[str, str]:
        if not isinstance(u, str) or not isinstance(v, str):
            raise ValueError("reduce expects cell names")
        return tuple(sorted((u, v)))

    def _validate_reduce_pair(self, u: str, v: str) -> tuple[str, str]:
        pair = self._canonical_cells(u, v)
        left, right = pair
        if left not in self.nodes or right not in self.nodes:
            raise ValueError(f"unknown cell in reduce pair: {pair!r}")
        if self.adj.get((left, 0)) != (right, 0):
            raise ValueError(f"reduce pair is not active: {pair!r}")
        if self.adj.get((right, 0)) != (left, 0):
            raise ValueError(f"reduce pair adjacency is malformed: {pair!r}")
        if pair not in self._active_pairs:
            raise ValueError(f"reduce pair is missing from the active index: {pair!r}")
        return pair

    def reduce(self, u: str, v: str):
        """Reduce one active pair using the original primitive rules."""
        pair = self._validate_reduce_pair(u, v)
        self._active_pairs.pop(pair, None)
        self._in_reduce = True
        self._reducing_pair = pair
        other_pairs = set(self._active_pairs) if self.debug_local_invariants else ()
        try:
            result = super().reduce(u, v)
        finally:
            self._in_reduce = False
            self._reducing_pair = None
        if pair in self._active_pairs:
            raise AssertionError("reduced pair remains in the active index")
        if self.debug_local_invariants:
            for other in other_pairs:
                if other not in self._active_pairs or not self._pair_is_current(other):
                    raise AssertionError(
                        f"local redex lost an unrelated active pair: {other!r}"
                    )
        return result

    def check(self) -> None:
        """Audit the graph and active index outside a primitive reduction."""
        if self._in_reduce:
            return
        super().check()
        actual = set(Net.active(self))
        indexed = set(self._active_pairs)
        if actual != indexed:
            raise AssertionError(
                f"active-index mismatch: actual={sorted(actual)}, indexed={sorted(indexed)}"
            )

    def final_check(self) -> None:
        """Explicit whole-graph audit point for constructors and runs."""
        self.check()

    def normalize(
        self,
        limit: int | None = None,
        policy: str = "fifo",
        final_check: bool = True,
    ) -> NormalizationResult:
        """Normalize using next_active, never by scanning all active pairs."""
        if policy not in ("fifo", None):
            raise ValueError("policy must be 'fifo'")
        if limit is not None and (type(limit) is not int or limit < 0):
            raise ValueError("limit must be a non-negative integer or None")

        steps = 0
        peak = len(self.nodes)
        terminal = False
        cutoff = False
        while True:
            pair = self.next_active()
            if pair is None:
                terminal = True
                break
            if limit is not None and steps >= limit:
                cutoff = True
                break
            self.reduce(*pair)
            steps += 1
            peak = max(peak, len(self.nodes))

        if final_check:
            self.final_check()
        return NormalizationResult(
            steps=steps,
            peak_cells_after_step=peak,
            final_cells=len(self.nodes),
            cycles=self.cycles,
            terminal=terminal,
            cutoff=cutoff,
            limit=limit,
            policy="fifo",
        )


def _pair_net(kind_a: str, kind_b: str, cls=Net):
    """Build a two-cell net with labeled auxiliary boundaries."""
    net = cls()
    a = net.cell(kind_a)
    b = net.cell(kind_b)
    net.link((a, 0), (b, 0))
    boundaries = {}
    for cell, kind, tag in ((a, kind_a, "A"), (b, kind_b, "B")):
        for port in range(1, AR[kind] + 1):
            boundary = net.boundary(f"{tag}{port}")
            net.link((cell, port), boundary)
            boundaries[f"{tag}{port}"] = boundary
    net.final_check() if isinstance(net, FastNet) else net.check()
    return net, a, b, boundaries


def _reduce_same_schedule(fast: FastNet, original: Net) -> tuple[FastNet, Net]:
    while True:
        pair = fast.next_active()
        if pair is None:
            break
        fast.reduce(*pair)
        if pair not in original.active() and tuple(reversed(pair)) not in original.active():
            raise AssertionError(f"schedule pair is not active in original net: {pair!r}")
        original.reduce(*pair)
    if isinstance(fast, FastNet):
        fast.final_check()
    original.check()
    return fast, original


def _test_all_rules() -> None:
    from ic_primitive_port_verifier import RULES

    for left_kind, right_kind in sorted(RULES):
        fast, a, b, _ = _pair_net(left_kind, right_kind, FastNet)
        original, oa, ob, _ = _pair_net(left_kind, right_kind, Net)
        view = fast.active()
        assert view and len(view) == 1
        assert (a, b) in view or (b, a) in view
        assert list(view) == [(a, b)] or list(view) == [(b, a)]
        fast.reduce(a, b)
        original.reduce(oa, ob)
        fast.final_check()
        original.check()
        assert isomorphic(fast, original), (left_kind, right_kind)
    print("PASS: all six primitive rules match original Net")


def _test_exhaustive_contexts() -> None:
    from itertools import product
    from ic_primitive_port_verifier import AR, RULES

    tested = 0
    for (s1, t1), (s2, t2) in product(RULES, RULES):
        def construct(cls, pairs):
            net = cls()
            a = net.cell(s1)
            b = net.cell(t1)
            c = net.cell(s2)
            d = net.cell(t2)
            net.link((a, 0), (b, 0))
            net.link((c, 0), (d, 0))
            aux = [
                (cell, port)
                for cell, kind in ((a, s1), (b, t1), (c, s2), (d, t2))
                for port in range(1, AR[kind] + 1)
            ]
            for i, j in pairs:
                net.link(aux[i], aux[j])
            if isinstance(net, FastNet):
                net.final_check()
            else:
                net.check()
            return net

        aux_count = AR[s1] + AR[t1] + AR[s2] + AR[t2]
        for pairing in pairings(list(range(aux_count))):
            fast = construct(FastNet, pairing)
            original = construct(Net, pairing)

            # Test the local reducer update and both fixed initial redexes.
            # Deliberately do not normalize these open contexts: unrestricted
            # IC normalization is not required to terminate.
            for order in ((0, 1), (1, 0)):
                if order == (1, 0):
                    fast = construct(FastNet, pairing)
                    original = construct(Net, pairing)
                fast_pairs = sorted(fast.active())
                original_pairs = sorted(original.active())
                assert fast_pairs == original_pairs
                first, second = fast_pairs[order[0]], fast_pairs[order[1]]
                original_pairs_same_ids = sorted(original.active())
                fast.reduce(*first)
                original.reduce(*first)
                assert fast.nodes == original.nodes
                assert fast.adj == original.adj
                assert fast.cycles == original.cycles
                assert sorted(fast.active()) == sorted(original.active())
                fast.reduce(*second)
                original.reduce(*second)
                assert fast.nodes == original.nodes
                assert fast.adj == original.adj
                assert fast.cycles == original.cycles
                assert sorted(fast.active()) == sorted(original.active())
                fast.final_check()
                original.check()
                assert fast.nodes == original.nodes
                assert fast.adj == original.adj
                assert fast.cycles == original.cycles
                assert sorted(fast.active()) == sorted(original.active())
            tested += 1
    print(f"PASS: exhaustive paired contexts; {tested} cases match original Net")


def _test_random_small_nets() -> None:
    import random
    from ic_primitive_port_verifier import AR, RULES

    rng = random.Random(20261105)
    for _ in range(200):
        (s1, t1), (s2, t2) = rng.sample(sorted(RULES), 2)
        aux_count = AR[s1] + AR[t1] + AR[s2] + AR[t2]
        all_pairings = list(pairings(list(range(aux_count))))
        pairing = rng.choice(all_pairings)
        kinds = (s1, t1, s2, t2)
        fast = _construct_random(FastNet, kinds, pairing)
        original = _construct_random(Net, kinds, pairing)

        # Compare a bounded prefix primitive-by-primitive. Unrestricted IC
        # normalization is not assumed to terminate.
        limit = rng.randrange(1, 65)
        steps = 0
        terminal = False
        cutoff = False
        while True:
            pair = fast.next_active()
            if pair is None:
                terminal = True
                break
            if steps >= limit:
                cutoff = True
                break
            if pair not in original.active() and tuple(reversed(pair)) not in original.active():
                raise AssertionError(("schedule mismatch", kinds, pairing, pair))
            fast.reduce(*pair)
            original.reduce(*pair)
            steps += 1
            assert fast.nodes == original.nodes, (kinds, pairing, steps)
            assert fast.adj == original.adj, (kinds, pairing, steps)
            assert fast.cycles == original.cycles, (kinds, pairing, steps)
            assert sorted(fast.active()) == sorted(original.active()), (kinds, pairing, steps)
        assert (steps, terminal, cutoff) == (
            min(steps, limit) if cutoff else steps, terminal, cutoff
        )
    print("PASS: 200 randomized bounded-prefix nets match original Net")


def _construct_random(cls, kinds, pairing):
    from ic_primitive_port_verifier import AR

    s1, t1, s2, t2 = kinds
    net = cls()
    a, b, c, d = (net.cell(kind) for kind in kinds)
    net.link((a, 0), (b, 0))
    net.link((c, 0), (d, 0))
    aux = [
        (cell, port)
        for cell, kind in ((a, s1), (b, t1), (c, s2), (d, t2))
        for port in range(1, AR[kind] + 1)
    ]
    for i, j in pairing:
        net.link(aux[i], aux[j])
    if isinstance(net, FastNet):
        net.final_check()
    else:
        net.check()
    return net


def _test_normalize_and_limits() -> None:
    net = FastNet()
    a, b = net.cell("g"), net.cell("g")
    net.link((a, 0), (b, 0))
    net.link((a, 1), (b, 2))
    net.link((a, 2), (b, 1))
    net.final_check()

    result = net.normalize()
    assert result.terminal and not result.cutoff
    assert result.steps > 0
    assert result.final_cells == len(net.nodes)
    assert result.cycles == net.cycles

    limited = FastNet()
    a, b = limited.cell("g"), limited.cell("g")
    limited.link((a, 0), (b, 0))
    limited.link((a, 1), (b, 2))
    limited.link((a, 2), (b, 1))
    cut = limited.normalize(limit=0)
    assert cut.cutoff and not cut.terminal and cut.steps == 0
    assert cut.limit == 0
    print("PASS: normalize, terminal result, and explicit cutoff")


def main() -> None:
    _test_all_rules()
    _test_exhaustive_contexts()
    _test_random_small_nets()
    _test_normalize_and_limits()
    print("PASS: FastNet preserves literal IC semantics with O(1) active membership")


if __name__ == "__main__":
    main()
