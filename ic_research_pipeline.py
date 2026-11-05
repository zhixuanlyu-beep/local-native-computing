"""A bounded observation-to-IC-to-retained-artifact research instance.

Synthesize a conditional retain/erase component; produce data using native IC
copying; archive an actual result component and its replayable construction;
reinstantiate the specimen using fresh symbolic allocation and a new input;
verify its subsequent behavior in the declared finite consumer family.

Archiving/import are research tooling, outside runtime evolution.  They do
not reset physical material or constitute a new IC rule.  The unified source
compiler is evaluated separately; general semantic synthesis remains open.
"""
from dataclasses import asdict, replace
import argparse
import gzip
import json
from pathlib import Path

from ic_primitive_port_verifier import AR, Net, isomorphic
from ic_bounded_execution import explore
from ic_research_artifacts import GraphSpec, RetainedArtifact, capture_root
from ic_bounded_synthesis import (
    CONSUMERS, HOLDOUT, TRAINING, SearchBudget, attach_consumer, build,
    expected, false_carrier, spec_id, synthesize, validate_survivors,
    verify_saved_witnesses, verify_case,
)


def certify_all_schedules(initial, target, budget):
    result = explore(initial, max_states=budget.reachable_states,
                     max_transitions=budget.transitions, max_cells=budget.live_cells)
    assert result.complete, ("incomplete exploration is not a certificate", result.summary())
    assert not result.cycle, ("a reachable cycle admits noncompletion", result.summary())
    assert result.terminal_ids
    for state_id in result.terminal_ids:
        assert isomorphic(result.states[state_id], target), result.trace_to(state_id)
    return result


def replay_artifact(artifact, expected_producer):
    """Verify provenance before treating a serialized artifact as evidence."""
    provenance = artifact.provenance
    net = GraphSpec.from_dict(provenance["initial_graph"]).instantiate()
    for raw_pair in provenance["primitive_trace"]:
        pair = tuple(raw_pair)
        assert pair in net.active() or tuple(reversed(pair)) in net.active()
        net.reduce(*pair)
    assert not net.active()
    assert isomorphic(net, expected_producer)
    recaptured, _ = capture_root(
        net, tuple(provenance["source_boundary"]), provenance, artifact.contract)
    assert recaptured.source_fingerprint == artifact.source_fingerprint
    assert isomorphic(recaptured.instantiate(), artifact.instantiate())
    return net


def build_reuse(gate, carrier, artifact, new_bit, consumer):
    """Use only the archived graph and a separately supplied new input object."""
    net = Net()
    token = (carrier if new_bit else false_carrier()).open_root(net)
    payload = artifact.open_root(net)
    output = net.boundary("GATE_OUTPUT")
    gate.instantiate(net, {"CTRL": token, "DATA": payload, "OUT": output})
    neighbor = net.adj.pop(output)
    net.free.remove(output)
    net.adj[neighbor] = None
    attach_consumer(net, neighbor, consumer)
    net.check()
    return net


def retain_and_reuse(gate, carrier, budget=None):
    budget = budget or SearchBudget(reachable_states=4096, transitions=32768)
    records = []
    for payload_name, description in TRAINING + HOLDOUT:
        for first_bit in (False, True):
            producer, original_payload_ids = build(gate, carrier, first_bit,
                                                   description, "copy")
            initial_spec = GraphSpec.from_net(producer)
            # Use the recorded syntax for both exploration and provenance.
            producer = initial_spec.instantiate()
            result = certify_all_schedules(producer, expected(first_bit, description, "copy"), budget)
            terminal_id = result.terminal_ids[0]
            terminal = result.states[terminal_id]
            terminal_before = GraphSpec.from_net(terminal).to_dict()
            trace = result.trace_to(terminal_id)
            provenance = {
                "initial_graph": initial_spec.to_dict(),
                "primitive_trace": [list(pair) for pair in trace],
                "source_boundary": ["F", "OUT1"],
                "gate": spec_id(gate), "carrier": spec_id(carrier),
                "input": first_bit, "payload": payload_name,
                "producer_certificate": result.summary(),
            }
            contract = {
                "representation": "reduced one-principal-root gamma/epsilon port graph",
                "interface": ["ROOT"],
                "storage": "passive root, no internal active pair; exact structural decoding",
                "invariants": ["fully paired ports", "one exposed principal root",
                               "gamma/epsilon cells only", "no cyclic-wire garbage"],
                "allowed_consumers": list(CONSUMERS),
                "validated_inputs": [False, True],
                "payload_scope": "this archived rooted topology only",
                "replacement_conditions": [
                    "same chosen rooted topology and boundary protocol",
                    "producer provenance independently replayed",
                    "fresh allocation and subsequent consumers included in resource accounting",
                    "only the separately checked finite input/context cases are certified",
                ],
                "construction": "actual post-reduction native delta-copy output",
                "import": "offline specimen construction from the retained exact graph; fresh symbolic cells",
            }
            artifact, archive_ids = capture_root(terminal, ("F", "OUT1"), provenance, contract)
            other_provenance = {**provenance, "source_boundary": ["F", "OUT2"]}
            other, other_ids = capture_root(terminal, ("F", "OUT2"), other_provenance, contract)
            assert archive_ids.isdisjoint(other_ids)
            assert archive_ids | other_ids == set(terminal.nodes)
            assert isomorphic(artifact.instantiate(), other.instantiate())
            # Native copying consumes every original payload cell; captured
            # cells are products of the evolution, not aliases to the input.
            # initial_spec preserves insertion order, so the initial IDs agree
            # with the builder used above.
            assert not (original_payload_ids & set(terminal.nodes))
            artifact.contract["cost"] = {
                "archived_component_cells": len(artifact.spec.kinds),
                "producer_terminal_cells": len(terminal.nodes),
                "producer_initial_cells": len(producer.nodes),
                "producer_peak_live_cells": result.peak_cells,
                "producer_interactions_on_recorded_trace": len(trace),
                "readout_cells": len(artifact.spec.kinds),
                "readout_ports": sum(AR[k] + 1 for k in artifact.spec.kinds) + 1,
            }
            serialized = json.loads(artifact.export_json())
            restored = RetainedArtifact.from_dict(serialized)
            replay_artifact(restored, expected(first_bit, description, "copy"))
            reuse_cases = []
            for new_bit in (False, True):
                for consumer in CONSUMERS:
                    reused = build_reuse(gate, carrier, restored, new_bit, consumer)
                    # The independent reference uses task inputs; the reuse
                    # constructor never reads the old input or its answer.
                    target = expected(first_bit and new_bit, description, consumer)
                    reused_result = certify_all_schedules(reused, target, budget)
                    reuse_peak = reused_result.peak_cells
                    combined_peak = len(terminal.nodes) + reuse_peak
                    assert combined_peak <= budget.live_cells
                    reuse_cases.append({
                        "new_input": new_bit, "consumer": consumer,
                        "initial_cells": len(reused.nodes),
                        "reuse_peak_live_cells": reuse_peak,
                        "derived_peak_including_retained_source": combined_peak,
                        "execution": reused_result.summary(),
                    })
                    assert GraphSpec.from_net(terminal).to_dict() == terminal_before
            records.append({
                "payload": payload_name, "first_input": first_bit,
                "artifact": serialized, "reuse": reuse_cases,
                "source_specimen_unchanged": True,
                "native_copies_disjoint": True,
                "cost_scope": "producer and fresh reuse allocations are separate, both counted; no physical reset claim",
            })
    return {"budget": asdict(budget), "artifacts": records}


def run_research():
    discovery_budget = SearchBudget()
    full_budget = replace(discovery_budget, reachable_states=4096, transitions=32768)
    survivors, synthesis = synthesize(discovery_budget)
    survivors, synthesis["context_refinement"] = validate_survivors(survivors, synthesis, full_budget)
    synthesis["replayed_counterexamples"] = verify_saved_witnesses(synthesis)
    # Choose the smallest verified carrier, then deterministic syntax order.
    # This selection uses search evidence offline, never a runtime task answer.
    gate, carrier = min(survivors, key=lambda pair: (
        len(pair[1].kinds), len(pair[0].kinds), spec_id(pair[0]), spec_id(pair[1])))
    retained = retain_and_reuse(gate, carrier, full_budget)
    return {
        "description": "bounded IC observation contract, graph synthesis, native evolution, archived output, independent reuse",
        "synthesis": synthesis,
        "chosen_component": {"gate": gate.to_dict(), "carrier": carrier.to_dict()},
        "retained_structure": retained,
        "limitations": [
            "finite candidate family and explicit search budgets",
            "finite declared payload/consumer environments",
            "quiescent graph readout rather than a local completion token",
            "artifact export/import is research tooling and fresh allocation",
            "no new coherent source-rule certificates or complete feedback compiler",
        ],
    }


def verify_report(report):
    """Validate saved rejection evidence and artifact behavior from disk."""
    synthesis = report["synthesis"]
    candidate_keys = [(r["gate"], r["material"]) for r in synthesis["candidates"]]
    gates = {entry["id"]: GraphSpec.from_dict(entry["graph"]) for entry in synthesis["gates"]}
    materials = {entry["id"]: GraphSpec.from_dict(entry["graph"]) for entry in synthesis["materials"]}
    assert len(candidate_keys) == len(set(candidate_keys))
    assert set(candidate_keys) == {(g, m) for g in gates for m in materials}
    assert all(spec_id(graph) == key for key, graph in list(gates.items()) + list(materials.items()))
    verified_keys = {(s["gate"], s["material"]) for s in synthesis["survivors"]}
    for record in synthesis["candidates"]:
        key = (record["gate"], record["material"])
        if record["status"] == "rejected-storage":
            assert isomorphic(materials[record["material"]].instantiate(), false_carrier().instantiate())
        elif record["status"] == "rejected":
            assert any(case.get("witness") for case in record["cases"])
        elif record["status"] == "verified":
            assert key in verified_keys and all(c["status"] == "verified" for c in record["cases"])
        elif record["status"] == "inconclusive":
            assert any(c["status"] == "inconclusive" for c in record["cases"])
        else:
            raise AssertionError("unrecognized candidate outcome")
    assert verified_keys == {key for key, r in zip(candidate_keys, synthesis["candidates"])
                              if r["status"] == "verified"}
    assert verify_saved_witnesses(synthesis) == synthesis["replayed_counterexamples"]
    gate = GraphSpec.from_dict(report["chosen_component"]["gate"])
    carrier = GraphSpec.from_dict(report["chosen_component"]["carrier"])
    payloads = dict(TRAINING + HOLDOUT)
    budget = SearchBudget(**report["retained_structure"]["budget"])
    for survivor in synthesis["survivors"]:
        for description in payloads.values():
            for bit in (False, True):
                for consumer in CONSUMERS:
                    result = verify_case(gates[survivor["gate"]], materials[survivor["material"]],
                                         bit, description, consumer, budget)
                    assert result["status"] == "verified"
    records = report["retained_structure"]["artifacts"]
    artifact_keys = [(r["payload"], r["first_input"]) for r in records]
    assert len(artifact_keys) == len(set(artifact_keys))
    assert set(artifact_keys) == {(name, bit) for name in payloads for bit in (False, True)}
    checked = 0
    for record in records:
        artifact = RetainedArtifact.from_dict(record["artifact"])
        description = payloads[record["payload"]]
        bit = record["first_input"]
        produced = replay_artifact(artifact, expected(bit, description, "copy"))
        producer_initial = GraphSpec.from_dict(artifact.provenance["initial_graph"]).instantiate()
        producer_result = certify_all_schedules(producer_initial, expected(bit, description, "copy"), budget)
        assert producer_result.summary() == artifact.provenance["producer_certificate"]
        costs = artifact.contract["cost"]
        assert costs["archived_component_cells"] == len(artifact.spec.kinds)
        assert costs["readout_cells"] == len(artifact.spec.kinds)
        assert costs["readout_ports"] == sum(AR[k] + 1 for k in artifact.spec.kinds) + 1
        assert costs["producer_peak_live_cells"] == producer_result.peak_cells
        cases = {(case["new_input"], case["consumer"]) for case in record["reuse"]}
        assert cases == {(b, c) for b in (False, True) for c in CONSUMERS}
        for new_bit, consumer in sorted(cases):
            net = build_reuse(gate, carrier, artifact, new_bit, consumer)
            result = certify_all_schedules(net, expected(bit and new_bit, description, consumer), budget)
            assert len(produced.nodes) + result.peak_cells <= budget.live_cells
            checked += 1
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verify-report", type=Path)
    args = parser.parse_args()
    if args.verify_report:
        encoded = args.verify_report.read_bytes()
        if args.verify_report.suffix == ".gz":
            encoded = gzip.decompress(encoded)
        checked = verify_report(json.loads(encoded))
        print("PASS: saved report counterexamples, provenance and native reuse cases", checked)
        return
    report = run_research()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        args.report.write_bytes(gzip.compress(encoded, mtime=0) if args.report.suffix == ".gz" else encoded)
    synthesis = report["synthesis"]
    artifacts = report["retained_structure"]["artifacts"]
    print("PASS: literal IC joint candidates", synthesis["candidate_accounting"]["joint_candidates"],
          "initial survivors", len(synthesis["initial_survivors"]),
          "refined survivors", len(synthesis["survivors"]))
    print("PASS: counterexample replays", synthesis["replayed_counterexamples"],
          "context refinement cases", len(synthesis["context_refinement"]))
    print("PASS: runtime-created archived specimens", len(artifacts), "reuse cases",
          sum(len(a["reuse"]) for a in artifacts))
    print("LIMIT: finite synthesis and reuse contracts; separate compiler and bridge evidence is in docs/CLAIM_LEDGER.md")


if __name__ == "__main__":
    main()
