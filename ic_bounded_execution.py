"""Exhaust all active-pair choices in a bounded literal IC execution graph.

States are quotiented by exact port-labeled graph isomorphism, preserving
boundary labels and cyclic wires.  A graph hash is only a lookup prefilter.
Any budget cutoff leaves the result incomplete.  A completely explored
acyclic graph proves termination for all schedules of that concrete instance;
no fairness assumption or arbitrary-context theorem is supplied.
"""
from collections import deque
from dataclasses import asdict, dataclass, field
import copy

import networkx as nx

from ic_primitive_port_verifier import Net, isomorphic, pair


@dataclass(frozen=True)
class Step:
    source: int
    target: int
    pair: tuple[str, str]


@dataclass
class Exploration:
    states: list[Net] = field(default_factory=list)
    edges: list[Step] = field(default_factory=list)
    parents: list[tuple[int, tuple[str, str]] | None] = field(default_factory=list)
    terminal_ids: list[int] = field(default_factory=list)
    cutoffs: list[dict] = field(default_factory=list)
    cycle: list[Step] = field(default_factory=list)
    peak_cells: int = 0
    attempted_transitions: int = 0

    @property
    def complete(self):
        return not self.cutoffs

    def trace_to(self, state_id):
        """An actual replayable redex sequence to this representative state."""
        if not 0 <= state_id < len(self.states):
            raise IndexError(state_id)
        trace = []
        while self.parents[state_id] is not None:
            state_id, redex = self.parents[state_id]
            trace.append(redex)
        trace.reverse()
        return trace

    def summary(self):
        graph = nx.DiGraph()
        graph.add_nodes_from(range(len(self.states)))
        graph.add_edges_from((e.source, e.target) for e in self.edges)
        longest = None
        if self.complete and not self.cycle:
            longest = nx.dag_longest_path_length(graph) if self.states else 0
        return {
            "complete": self.complete,
            "states": len(self.states),
            "transitions": len(self.edges),
            "attempted_transitions": self.attempted_transitions,
            "terminal_states": len(self.terminal_ids),
            "peak_live_cells": self.peak_cells,
            "cutoffs": copy.deepcopy(self.cutoffs),
            "cycle": [asdict(e) for e in self.cycle],
            "all_executions_terminate": self.complete and not self.cycle,
            "max_interactions": longest,
            "state_equivalence": "exact labeled-port isomorphism including cyclic wires",
        }


def _prefilter(net):
    return (len(net.nodes), len(net.free), net.cycles,
            nx.weisfeiler_lehman_graph_hash(net.signature(), node_attr="kind"))


def explore(initial, *, max_states=256, max_transitions=2048, max_cells=64):
    """Explore every enabled primitive interaction, subject to explicit bounds.

    max_cells is a material bound.  Exceeding it records a concrete violation
    and its prefix, never an in-bound success.  State/transition limits are
    search budgets.  Cycle witnesses are in the isomorphism quotient; their
    finite prefix is replayable with trace_to, and each cycle edge can be
    lifted to concrete cell names using lift_cycle below.
    """
    for name, value, minimum in (("max_states", max_states, 1),
                                 ("max_transitions", max_transitions, 0),
                                 ("max_cells", max_cells, 0)):
        if type(value) is not int or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    if not isinstance(initial, Net):
        raise TypeError("initial must be a literal IC Net")
    initial.check()
    result = Exploration(states=[copy.deepcopy(initial)], parents=[None],
                         peak_cells=len(initial.nodes))
    if len(initial.nodes) > max_cells:
        result.cutoffs.append({"reason": "material-bound", "source": 0,
                               "pair": None, "observed_cells": len(initial.nodes),
                               "bound": max_cells})
        return result
    buckets = {_prefilter(initial): [0]}
    pending = deque([0])
    attempted = 0
    exhausted_transition_budget = False
    while pending and not exhausted_transition_budget:
        source = pending.popleft()
        net = result.states[source]
        active = net.active()
        if not active:
            result.terminal_ids.append(source)
        for redex in active:
            if attempted >= max_transitions:
                result.cutoffs.append({"reason": "transition-budget", "source": source,
                                       "pair": list(redex), "bound": max_transitions})
                exhausted_transition_budget = True
                break
            attempted += 1
            result.attempted_transitions = attempted
            child = copy.deepcopy(net)
            child.reduce(*redex)
            result.peak_cells = max(result.peak_cells, len(child.nodes))
            if len(child.nodes) > max_cells:
                result.cutoffs.append({"reason": "material-bound", "source": source,
                                       "pair": list(redex), "observed_cells": len(child.nodes),
                                       "bound": max_cells})
                continue
            key = _prefilter(child)
            target = next((i for i in buckets.get(key, ())
                           if isomorphic(child, result.states[i])), None)
            if target is None:
                if len(result.states) >= max_states:
                    result.cutoffs.append({"reason": "state-budget", "source": source,
                                           "pair": list(redex), "bound": max_states})
                    continue
                target = len(result.states)
                result.states.append(child)
                result.parents.append((source, tuple(redex)))
                buckets.setdefault(key, []).append(target)
                pending.append(target)
            result.edges.append(Step(source, target, tuple(redex)))
    graph = nx.DiGraph()
    graph.add_nodes_from(range(len(result.states)))
    graph.add_edges_from((edge.source, edge.target) for edge in result.edges)
    try:
        found = nx.find_cycle(graph)
    except nx.NetworkXNoCycle:
        found = []
    result.cycle = [next(edge for edge in result.edges
                         if (edge.source, edge.target) == (source, target))
                    for source, target in found]
    return result


def replay(initial, trace):
    net = copy.deepcopy(initial)
    for raw_pair in trace:
        redex = tuple(raw_pair)
        if redex not in net.active() and tuple(reversed(redex)) not in net.active():
            raise ValueError(f"trace redex is not active: {redex!r}")
        net.reduce(*redex)
    return net


def _cell_renaming(source, target):
    if source.cycles != target.cycles:
        raise ValueError("wire cycles differ")
    matcher = nx.algorithms.isomorphism.GraphMatcher(
        source.signature(), target.signature(),
        node_match=lambda a, b: a["kind"] == b["kind"])
    if not matcher.is_isomorphic():
        raise ValueError("quotient edge cannot be lifted to the current graph")
    return {node[1]: image[1] for node, image in matcher.mapping.items()
            if node[0] == "cell"}


def lift_cycle(initial, result, repetitions=2):
    """Replay a quotient cycle, recomputing cell renamings at every edge."""
    if not result.cycle or type(repetitions) is not int or repetitions < 1:
        raise ValueError("a cycle and a positive repetition count are required")
    first = result.cycle[0].source
    prefix = result.trace_to(first)
    net = replay(initial, prefix)
    concrete_trace = list(prefix)
    for _ in range(repetitions):
        for edge in result.cycle:
            names = _cell_renaming(result.states[edge.source], net)
            redex = tuple(names[cell] for cell in edge.pair)
            net.reduce(*redex)
            concrete_trace.append(redex)
            assert isomorphic(net, result.states[edge.target])
    return net, concrete_trace


def main():
    net = Net()
    for _ in range(2):
        a, b = net.cell("e"), net.cell("e")
        net.link((a, 0), (b, 0))
    original = copy.deepcopy(net)
    result = explore(net)
    assert result.complete and not result.cycle
    assert result.summary()["max_interactions"] == 2
    assert len(result.edges) == 3  # The two first choices merge exactly.
    for terminal in result.terminal_ids:
        assert isomorphic(replay(net, result.trace_to(terminal)), result.states[terminal])
        assert not result.states[terminal].nodes
    assert isomorphic(net, original)
    assert not explore(net, max_states=1).complete
    assert not explore(net, max_transitions=0).complete
    assert not explore(net, max_cells=1).complete
    commutation, _, _, _ = pair("g", "d")
    cutoff = explore(commutation, max_cells=2)
    assert not cutoff.complete and cutoff.peak_cells == 4
    assert cutoff.cutoffs[0]["reason"] == "material-bound"
    cyclic, _, _, _ = pair("g", "g")
    for label in list(cyclic.free):
        del cyclic.adj[label]
    cyclic.free.clear()
    # Build the two cross-wires directly on the former auxiliary ports.
    names = list(cyclic.nodes)
    for cell in names:
        for p in (1, 2):
            cyclic.adj[(cell, p)] = None
    cyclic.link((names[0], 1), (names[1], 2))
    cyclic.link((names[0], 2), (names[1], 1))
    cyclic.check()
    cycles = explore(cyclic)
    assert cycles.complete and cycles.states[cycles.terminal_ids[0]].cycles == 2
    assert not isomorphic(cycles.states[cycles.terminal_ids[0]], Net())
    print("PASS: exhaustive active-pair exploration, exact quotient, trace replay, cycles and explicit cutoffs")


if __name__ == "__main__":
    main()
