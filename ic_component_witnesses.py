"""Exact local embedding and trace lifting for finite IC witnesses.

The matcher proves only that a reference net occurs as a labeled local
embedding in an actual net. It deliberately does not claim equality of the
whole actual graph and does not capture unrelated outside components.
"""
from collections import deque
from ic_package_codec import validate_package
from ic_primitive_port_verifier import AR, Net
from ic_research_artifacts import GraphSpec
from ic_rule_trace_lifting import translated_witness_pair
from ic_schedule_audit import Schedule, ScheduledNet


def _actual_endpoint(actual, endpoint):
    if endpoint not in actual.adj:
        raise ValueError("binding endpoint is absent from actual: %r" % (endpoint,))
    neighbor = actual.adj[endpoint]
    if neighbor is None:
        raise ValueError("binding endpoint is unpaired in actual: %r" % (endpoint,))
    return neighbor


def _validated_bindings(reference, actual, bindings):
    if not isinstance(bindings, dict):
        raise TypeError("bindings must be a mapping from reference boundary labels")
    expected = {label for _, label in reference.free}
    if set(bindings) != expected:
        raise ValueError(
            "binding labels differ from reference free labels; expected=%r, got=%r"
            % (sorted(expected), sorted(bindings))
        )
    for label, endpoint in bindings.items():
        if endpoint not in actual.adj:
            raise ValueError("actual binding endpoint is absent: %r -> %r" % (label, endpoint))
        _actual_endpoint(actual, endpoint)
    if len(set(bindings.values())) != len(bindings):
        raise ValueError("reference boundaries must bind distinct actual endpoints")
    return dict(bindings)


def _validated_fixed_cells(reference, actual, fixed_cells):
    if fixed_cells is None:
        return {}
    if not isinstance(fixed_cells, dict):
        raise TypeError("fixed_cells must be a mapping from reference to actual cells")
    if len(set(fixed_cells.values())) != len(fixed_cells):
        raise ValueError("fixed actual cells must be distinct")
    for reference_cell, actual_cell in fixed_cells.items():
        if reference_cell not in reference.nodes:
            raise ValueError("fixed reference cell is absent: %r" % (reference_cell,))
        if actual_cell not in actual.nodes:
            raise ValueError("fixed actual cell is absent: %r" % (actual_cell,))
        if reference.nodes[reference_cell] != actual.nodes[actual_cell]:
            raise ValueError("fixed cell kinds differ: %r -> %r" % (reference_cell, actual_cell))
    return dict(fixed_cells)


def match_bound_graph(reference, actual, bindings, fixed_cells=None):
    if not isinstance(reference, Net) or not isinstance(actual, Net):
        raise TypeError("reference and actual must both be Net instances")
    reference.check()
    actual.check()
    if actual.cycles < reference.cycles:
        raise ValueError(
            "actual cycles cannot be fewer than reference cycles: %r < %r"
            % (actual.cycles, reference.cycles)
        )
    bindings = _validated_bindings(reference, actual, bindings)
    cell_map = _validated_fixed_cells(reference, actual, fixed_cells)
    binding_context_cells = {
        endpoint[0] for endpoint in bindings.values() if endpoint[0] != "F"
    }
    claimed_actual_cells = set(cell_map.values())
    for actual_cell in claimed_actual_cells:
        if actual_cell in binding_context_cells:
            raise ValueError(
                "fixed seed overlaps a binding context cell: %r" % (actual_cell,)
            )

    def force_cell(reference_cell, actual_cell):
        previous = cell_map.get(reference_cell)
        if previous is not None:
            if previous != actual_cell:
                raise ValueError(
                    "reference cell maps to two actual cells: %r" % (reference_cell,)
                )
            return False
        if actual_cell in claimed_actual_cells:
            raise ValueError("actual cell already claimed: %r" % (actual_cell,))
        if actual_cell in binding_context_cells:
            raise ValueError(
                "local mapping claims a binding context cell: %r" % (actual_cell,)
            )
        if reference.nodes[reference_cell] != actual.nodes[actual_cell]:
            raise ValueError(
                "cell kinds differ: %r -> %r" % (reference_cell, actual_cell)
            )
        cell_map[reference_cell] = actual_cell
        claimed_actual_cells.add(actual_cell)
        return True

    queue = deque(cell_map)
    for reference_cell in queue:
        force_cell(reference_cell, cell_map[reference_cell])

    for label, binding_endpoint in bindings.items():
        reference_root = reference.adj[("F", label)]
        if reference_root[0] == "F":
            actual_root = _actual_endpoint(actual, binding_endpoint)
            if actual_root != bindings[reference_root[1]]:
                raise ValueError(
                    "reference boundary wire is not represented by a binding: %r" % (label,)
                )
            continue
        actual_root = _actual_endpoint(actual, binding_endpoint)
        if actual_root[0] == "F":
            raise ValueError(
                "reference boundary root is a cell but actual root is a boundary: %r"
                % (label,)
            )
        if reference_root[1] != actual_root[1]:
            raise ValueError(
                "boundary root port order differs: %r -> %r" % (reference_root, actual_root)
            )
        if force_cell(reference_root[0], actual_root[0]):
            queue.append(reference_root[0])

    while queue:
        reference_cell = queue.popleft()
        actual_cell = cell_map[reference_cell]
        for port in range(AR[reference.nodes[reference_cell]] + 1):
            reference_neighbor = reference.adj[(reference_cell, port)]
            actual_neighbor = _actual_endpoint(actual, (actual_cell, port))
            if reference_neighbor[0] == "F":
                label = reference_neighbor[1]
                if bindings[label] != actual_neighbor:
                    raise ValueError(
                        "boundary wire mismatch at %r: expected %r, got %r"
                        % ((reference_cell, port), bindings[label], actual_neighbor)
                    )
                continue
            if actual_neighbor[0] == "F":
                raise ValueError(
                    "reference cell wire maps to an actual boundary: %r"
                    % ((reference_cell, port),)
                )
            if reference_neighbor[1] != actual_neighbor[1]:
                raise ValueError(
                    "wire port order differs: %r -> %r"
                    % ((reference_cell, port), actual_neighbor)
                )
            if force_cell(reference_neighbor[0], actual_neighbor[0]):
                queue.append(reference_neighbor[0])

    if len(cell_map) != len(reference.nodes):
        missing = sorted(set(reference.nodes) - set(cell_map))
        raise ValueError("reference cells missing from local embedding: %r" % (missing,))
    if len(set(cell_map.values())) != len(cell_map):
        raise ValueError("reference cell mapping is not injective")
    return dict(cell_map)


def boundary_cell_map(reference, actual):
    if not isinstance(reference, Net) or not isinstance(actual, Net):
        raise TypeError("reference and actual must both be Net instances")
    if not reference.nodes:
        raise ValueError("boundary matching requires a nonempty reference net")
    if actual.cycles != reference.cycles:
        raise ValueError(
            "cycle counts differ: reference=%r, actual=%r" % (reference.cycles, actual.cycles)
        )
    if len(actual.nodes) != len(reference.nodes):
        raise ValueError(
            "cell counts differ: reference=%r, actual=%r"
            % (len(reference.nodes), len(actual.nodes))
        )
    reference_labels = {label for _, label in reference.free}
    actual_labels = {label for _, label in actual.free}
    if reference_labels != actual_labels:
        raise ValueError(
            "free boundary labels differ; expected=%r, got=%r"
            % (sorted(reference_labels), sorted(actual_labels))
        )
    bindings = {label: ("F", label) for _, label in reference.free}
    cell_map = match_bound_graph(reference, actual, bindings)
    if len(cell_map) != len(actual.nodes):
        raise ValueError("boundary matching must cover every actual cell")
    return cell_map


def match_value(spec, actual, context_endpoint):
    if not isinstance(spec, GraphSpec):
        raise TypeError("spec must be a GraphSpec")
    if tuple(spec.boundaries) != ("ROOT",):
        raise ValueError("match_value requires exactly a ROOT boundary")
    validate_package(spec.instantiate())
    if not isinstance(actual, Net):
        raise TypeError("actual must be a Net")
    actual.check()
    reference = spec.instantiate()
    return match_bound_graph(reference, actual, {"ROOT": context_endpoint})


def _outside_resource_snapshot(net, outside_cells):
    """Snapshot only outside cell identities and kinds."""
    return {cell: net.nodes[cell] for cell in outside_cells}


def _outside_adjacency(net, outside_cells, binding_ports):
    result = {}
    for port, neighbor in net.adj.items():
        if port[0] == "F":
            include = True
        else:
            include = port[0] in outside_cells
        if include and port not in binding_ports:
            result[port] = neighbor
    return result


def lift_trace(
    reference_initial, actual, initial_map, bindings, pairs,
    trace, *, max_steps=4096, max_cells=256,
):
    from ic_coherent_feedback import spec_digest
    if not isinstance(reference_initial, GraphSpec):
        raise TypeError("reference_initial must be a GraphSpec")
    if not isinstance(actual, ScheduledNet):
        raise TypeError("actual must be a ScheduledNet")
    if actual.schedule.policy != "witness":
        raise ValueError("lift_trace requires a witness-scheduled actual net")
    if not isinstance(initial_map, dict):
        raise TypeError("initial_map must be a mapping")
    for name, value in (("max_steps", max_steps), ("max_cells", max_cells)):
        if type(value) is not int or value < 0:
            raise ValueError("%s must be a non-negative integer" % name)
    reference = reference_initial.instantiate(ScheduledNet(Schedule("witness")))
    reference.check()
    actual.check()
    initial_map = match_bound_graph(reference, actual, bindings, initial_map)
    outside_initial = set(actual.nodes) - set(initial_map.values())
    context_cells = len(outside_initial)
    binding_ports = set(bindings.values())
    outside_cells = set(outside_initial)
    outside_snapshot = _outside_resource_snapshot(actual, outside_cells)
    outside_adjacency = _outside_adjacency(actual, outside_cells, binding_ports)
    initial_digest = spec_digest(reference_initial.to_dict())
    renaming = dict(initial_map)
    start = trace.count
    steps = 0
    reference_peak = len(reference.nodes)
    segment_peak = len(actual.nodes)
    status = "passed" if len(actual.nodes) <= max_cells else "resource-violation"

    for pair in pairs:
        if status != "passed":
            break
        if steps >= max_steps:
            status = "incomplete"
            break
        if pair not in reference.active():
            raise ValueError("reference witness pair is not active before recording")
        translated = translated_witness_pair(pair, renaming, actual)
        trace.record(translated)
        old_next, actual_next = reference.next, actual.next
        reference.reduce(*pair)
        actual.reduce(*translated)
        steps += 1
        old_new = tuple(
            "c" + str(number) for number in range(old_next, reference.next)
        )
        actual_new = tuple(
            "c" + str(number) for number in range(actual_next, actual.next)
        )
        if len(old_new) != len(actual_new):
            raise AssertionError("fresh allocation counts differ")
        if [reference.nodes[cell] for cell in old_new] != [
            actual.nodes[cell] for cell in actual_new
        ]:
            raise AssertionError("fresh allocation kinds differ")
        for old_cell, actual_cell in zip(old_new, actual_new):
            renaming[old_cell] = actual_cell
        del renaming[pair[0]], renaming[pair[1]]
        if len(actual.nodes) != len(reference.nodes) + context_cells:
            raise AssertionError("outside live-cell equation failed")
        outside_now = set(actual.nodes) - set(renaming.values())
        if outside_now != outside_cells:
            raise AssertionError("outside cell set changed during reduction")
        if _outside_resource_snapshot(actual, outside_cells) != outside_snapshot:
            raise AssertionError("outside cell kinds changed during reduction")
        if actual.cycles < reference.cycles:
            raise AssertionError("actual cycles dropped below the reference cycles")
        reference_peak = max(reference_peak, len(reference.nodes))
        segment_peak = max(segment_peak, len(actual.nodes))
        if len(actual.nodes) > max_cells:
            status = "resource-violation"
            break

    outside_unchanged = (
        _outside_resource_snapshot(actual, outside_cells) == outside_snapshot
        and _outside_adjacency(actual, outside_cells, binding_ports) == outside_adjacency
    )
    if status == "passed" and not outside_unchanged:
        status = "proof-rejected"
    if status == "passed":
        try:
            final_map = match_bound_graph(reference, actual, bindings, renaming)
        except ValueError:
            status = "embedding-mismatch"
        else:
            if set(final_map.values()) != set(renaming.values()):
                status = "embedding-mismatch"

    result = {
        "status": status,
        "initial_graph_sha256": initial_digest,
        "trace_offset_records": start,
        "primitive_interactions": steps,
        "context_cells": context_cells,
        "reference_peak_live_cells": reference_peak,
        "segment_peak_live_cells": segment_peak,
        "renaming": dict(renaming),
        "reference_final_graph": GraphSpec.from_net(reference).to_dict(),
        "reference_resources": reference.statistics(),
        "outside_unchanged": outside_unchanged,
    }
    if status != "passed":
        result["final_graph"] = GraphSpec.from_net(actual).to_dict()
    return result
