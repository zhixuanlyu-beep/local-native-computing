"""Lift frozen rule witnesses through a literal boundary-frame context.

The context's own interactions are deliberately deferred. The conclusion
is an exact finite C[LHS] ->* C[RHS] prefix, not contextual normalization.
"""
import gzip
import hashlib
from pathlib import Path
import struct
from ic_evidence_json import loads as json_loads

from ic_coherent_feedback import graph_digest, read_json, spec_digest
from ic_coherent_certificates import source_rules_digest
from ic_coherent_output_decoder import port_graph_isomorphic
from ic_fast_reducer import FastNet
from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec
from ic_schedule_audit import Schedule, ScheduledNet
from lafont_ic_macro_builder import macro_connect
from source_feedback_audit import RULES
from source_ic_coherent_compiler import source_rule_lhs, source_rule_rhs


RESULTS = Path(__file__).parent / "results"
CERTIFICATE_HASHES = {
    "coherent_rule_certificates.json.gz": "35417c8cb39893904c79943cf11f16fca7f302948ec9ed692d0b2a819d129d65",
    "coherent_rule_certificates.ictrace.gz": "e29f2ad225d16eef4ad1c6d3560bdc0fcce76435e91071dd4664f031795bc0d4",
}


def frozen_certificates(compiler):
    for name, digest in CERTIFICATE_HASHES.items():
        if hashlib.sha256((RESULTS / name).read_bytes()).hexdigest() != digest:
            raise ValueError("frozen source-rule certificate evidence changed")
    report = read_json(RESULTS / "coherent_rule_certificates.json.gz")
    if report["compiler"] != compiler.statistics() or report["metadata"]["program_sha256"] != graph_digest(compiler.program):
        raise ValueError("rule witnesses do not bind the current compiler program")
    if report["metadata"]["source_rules_sha256"] != source_rules_digest():
        raise ValueError("source rule table differs from the frozen witness table")
    return report


def frame_context(net):
    """Attach one literal gamma frame at each labeled boundary."""
    before = set(net.nodes)
    labels = sorted(endpoint[1] for endpoint in net.free)
    for label in labels:
        cell = net.cell("g")
        macro_connect(net, ("F", label), (cell, 0))
        net.link((cell, 1), net.boundary(label + "::L"))
        net.link((cell, 2), net.boundary(label + "::R"))
    net.check()
    return labels, set(net.nodes) - before


def translated_witness_pair(pair, renaming, contextual, *, proposed=None):
    """Validate the witness-to-context cell map before choosing an interaction."""
    try:
        mapped = tuple(renaming[cell] for cell in pair)
    except KeyError as error:
        raise ValueError("witness refers to an absent or consumed cell") from error
    if proposed is not None and tuple(proposed) != mapped:
        raise ValueError("witness pair does not respect the current fresh-cell renaming")
    if mapped not in contextual.active():
        raise ValueError("renamed witness pair is not active in the declared context")
    return mapped


def lift_all_rules(compiler, trace, *, max_steps=2_000_000, max_cells=250_000):
    if any(type(v) is not int or v < 0 for v in (max_steps, max_cells)):
        raise ValueError("lifting bounds must be non-negative integers")
    saved = frozen_certificates(compiler)
    if len(saved["certificates"]) != len(RULES):
        raise ValueError("incomplete frozen source-rule table")
    records, old_offset = [], 0
    with gzip.open(RESULTS / "coherent_rule_certificates.ictrace.gz", "rb") as stream:
        header = json_loads(stream.readline())
        if header != {"format": "IC-PAIR-U32LE-1", **saved["metadata"]}:
            raise ValueError("frozen rule trace metadata mismatch")
        for old_record, rule in zip(saved["certificates"], RULES.values()):
            name = "-".join(rule[:2])
            if old_record["rule"] != name or old_record["trace_offset_records"] != old_offset:
                raise ValueError("frozen rule witness order or interval mismatch")
            isolated = compiler.compile(*source_rule_lhs(rule), net_class=FastNet)
            if len(isolated.nodes) != old_record["initial_cells"]:
                raise ValueError("frozen rule initial size mismatch")
            built = compiler.compile(*source_rule_lhs(rule))
            core_ids = list(built.nodes)
            labels, frame_ids = frame_context(built)
            initial_spec = GraphSpec.from_net(built)
            contextual = initial_spec.instantiate(ScheduledNet(Schedule("witness")))
            initial_names = list(contextual.nodes)
            renaming = dict(zip(isolated.nodes, initial_names[:len(core_ids)]))
            contextual.begin_audit({cell: "core" if i < len(core_ids) else "frame"
                                    for i, cell in enumerate(initial_names)})
            target = compiler.compile(*source_rule_rhs(rule))
            frame_context(target)
            start, peak, status = trace.count, len(isolated.nodes), "matched-prefix"
            isolated_steps, read_count = 0, 0
            for _ in range(old_record["primitive_interactions"]):
                raw = stream.read(8)
                if len(raw) != 8:
                    raise ValueError("truncated frozen source-rule witness")
                read_count += 1
                pair = tuple("c" + str(i) for i in struct.unpack("<II", raw))
                if pair != isolated.next_active():
                    raise ValueError("frozen source witness differs from reconstructed FIFO")
                translated = translated_witness_pair(pair, renaming, contextual)
                if trace.count - start >= max_steps:
                    status = "incomplete"
                    break
                if len(contextual.nodes) > max_cells:
                    status = "resource-violation"
                    break
                old_next, new_next = isolated.next, contextual.next
                trace.record(translated)
                contextual.reduce(*translated)
                isolated.reduce(*pair)
                isolated_steps += 1
                peak = max(peak, len(isolated.nodes))
                for old, new in zip(range(old_next, isolated.next), range(new_next, contextual.next)):
                    renaming["c" + str(old)] = "c" + str(new)
                del renaming[pair[0]], renaming[pair[1]]
                if len(contextual.nodes) != len(isolated.nodes) + len(frame_ids):
                    raise AssertionError("constant-context live-cell equation failed")
                if len(contextual.nodes) > max_cells:
                    status = "resource-violation"
                    break
            if status != "matched-prefix":
                # Consume the untouched original interval so following cases
                # still retain their fixed witness accounting on a cutoff.
                remaining = old_record["primitive_interactions"] - read_count
                if remaining > 0 and len(stream.read(remaining * 8)) != remaining * 8:
                    raise ValueError("truncated remaining source-rule interval")
            else:
                isolated.final_check()
                if isolated.active() or peak != old_record["peak_live_cells"]:
                    raise ValueError("isolated witness termination or resource mismatch")
                expected_rhs = compiler.compile(*source_rule_rhs(rule))
                if not port_graph_isomorphic(isolated, expected_rhs):
                    raise ValueError("isolated source-rule RHS mismatch")
                if not port_graph_isomorphic(contextual, target):
                    status = "wrong-contextual-prefix"
            resources = contextual.statistics()
            if status == "matched-prefix" and resources["peak_live_cells"] != peak + len(frame_ids):
                raise AssertionError("constant-context peak equation failed")
            final = GraphSpec.from_net(contextual).to_dict()
            record = {"rule": name, "status": status, "context": "one gamma frame per original boundary",
                      "interface": labels, "context_cells": len(frame_ids),
                      "original_trace_offset_records": old_offset,
                      "trace_offset_records": start, "primitive_interactions": trace.count - start,
                      "initial_graph_sha256": spec_digest(initial_spec.to_dict()),
                      "final_graph": final, "final_graph_sha256": spec_digest(final),
                      "matches_plugged_rhs": status == "matched-prefix",
                      "terminal": not bool(contextual.active()), "resources": resources,
                      "scope": "fixed internal witness lifted; context redexes not executed"}
            if status != "matched-prefix":
                record["counterexample"] = {"initial": initial_spec.to_dict(),
                                            "expected": GraphSpec.from_net(target).to_dict(), "actual": final}
            records.append(record)
            old_offset += old_record["primitive_interactions"]
            print("LIFT", name, status, flush=True)
        if stream.read(1):
            raise ValueError("unaccounted frozen source-rule witness records")
        if old_offset != saved["trace"]["steps"]:
            raise ValueError("frozen source-rule total interval mismatch")
    return records
