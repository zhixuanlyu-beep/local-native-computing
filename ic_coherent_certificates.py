"""Generate and replay coherent source-rule to literal IC certificates."""
import argparse
import gzip
import hashlib
import json
from ic_evidence_json import loads as json_loads
from pathlib import Path
import struct

from ic_coherent_feedback import PrimitiveTrace, graph_digest, read_trace_summary, write_json
from ic_coherent_output_decoder import port_graph_isomorphic
from ic_fast_reducer import FastNet
from ic_package_codec import build_decoding
from ic_research_artifacts import GraphSpec
from lafont_ic_macro_builder import macro_connect
from source_feedback_audit import RULES
from source_ic_coherent_compiler import (
    CoherentICCompiler, certify_rule, reduce_compiled, source_rule_lhs, source_rule_rhs,
)


def source_rules_digest():
    return hashlib.sha256(json.dumps(list(RULES.values()), sort_keys=True).encode("utf-8")).hexdigest()


def certify_program_codec(compiler):
    results = []
    original = GraphSpec.from_net(compiler.program)
    for copies in (1, 2):
        source = build_decoding(compiler.code, copies)
        running = GraphSpec.from_net(source).instantiate(FastNet())
        reference = FastNet()
        for label in (("OUT",) if copies == 1 else ("OUT1", "OUT2")):
            original.instantiate(reference, {"ROOT": reference.boundary(label)})
        stats = reduce_compiled(running)
        assert port_graph_isomorphic(running, reference)
        results.append({"decoded_copies": copies, "independent_graph_match": True, **stats})
    assert results[0]["primitive_interactions"] == 3 * sum(k == "d" for k in compiler.program.nodes.values())
    return results


def certify_symbol_extraction(compiler):
    results = []
    templates = {symbol: compiler.symbol_template(symbol) for symbol in compiler.symbols}
    for symbol in compiler.symbols:
        net = FastNet()
        extension = compiler._extension(net, symbol)
        code = compiler.code_spec.open_root(net)
        macro_connect(net, code, extension.code_port)
        macro_connect(net, extension.principal, net.boundary("P0"))
        for port, endpoint in enumerate(extension.auxiliaries, 1):
            macro_connect(net, endpoint, net.boundary("P" + str(port)))
        net.final_check()
        initial = len(net.nodes)
        stats = reduce_compiled(net)
        assert port_graph_isomorphic(net, templates[symbol])
        results.append({"symbol": symbol, "initial_cells": initial,
                        "matches_independent_symbol_template": True, **stats})
    comparisons = 0
    for index, first in enumerate(compiler.symbols):
        for second in compiler.symbols[index + 1:]:
            assert not port_graph_isomorphic(templates[first], templates[second])
            comparisons += 1
    return results, comparisons


def generate(compiler, trace_path=None):
    metadata = {"scope": "all coherent source-rule LHS certificates in table order",
                "program_sha256": graph_digest(compiler.program),
                "source_rules_sha256": source_rules_digest(), "schedule": "FIFO"}
    trace = PrimitiveTrace(trace_path, metadata) if trace_path else None
    records = []
    try:
        for spec in RULES.values():
            offset = trace.count if trace else None
            record = certify_rule(compiler, spec, net_class=FastNet, trace=trace)
            if trace:
                assert trace.count - offset == record["primitive_interactions"]
                record["trace_offset_records"] = offset
            record["independent_rhs_match"] = True
            records.append(record)
            print("CERT", record["rule"], record["primitive_interactions"], "primitive IC interactions", flush=True)
    finally:
        summary = trace.close() if trace else None
    if trace:
        scanned = read_trace_summary(trace_path)
        assert scanned["steps"] == sum(r["primitive_interactions"] for r in records)
        assert scanned["sha256_of_pair_records"] == summary["sha256_of_pair_records"]
    codec = certify_program_codec(compiler)
    extraction, distinct = certify_symbol_extraction(compiler)
    return {"format": "coherent-literal-IC-rule-certificates-v1",
            "compiler": compiler.statistics(), "metadata": metadata,
            "certificates": records, "trace": summary,
            "program_codec": codec, "symbol_extraction": extraction,
            "distinct_symbol_template_pairs": distinct,
            "scope": "one unified representation and exact labeled-interface rule correspondence; contexts checked separately"}


def verify(report, trace_path, compiler):
    if report.get("format") != "coherent-literal-IC-rule-certificates-v1":
        raise ValueError("unknown certificate format")
    assert report["compiler"] == compiler.statistics()
    assert report["metadata"]["source_rules_sha256"] == source_rules_digest()
    assert report["metadata"]["program_sha256"] == graph_digest(compiler.program)
    scanned = read_trace_summary(trace_path)
    assert scanned["sha256_of_pair_records"] == report["trace"]["sha256_of_pair_records"]
    assert scanned["steps"] == report["trace"]["steps"]
    assert len(report["certificates"]) == len(RULES)
    offset = 0
    with gzip.open(trace_path, "rb") as stream:
        header = json_loads(stream.readline())
        assert header["source_rules_sha256"] == source_rules_digest()
        assert header["program_sha256"] == graph_digest(compiler.program)
        for record, spec in zip(report["certificates"], RULES.values()):
            assert record["rule"] == "-".join(spec[:2])
            assert record["trace_offset_records"] == offset
            net = compiler.compile(*source_rule_lhs(spec), net_class=FastNet)
            reference = compiler.compile(*source_rule_rhs(spec))
            assert len(net.nodes) == record["initial_cells"]
            peak = len(net.nodes)
            count = record["primitive_interactions"]
            remaining = count
            while remaining:
                block_count = min(remaining, 65536)
                encoded = stream.read(block_count * 8)
                if len(encoded) != block_count * 8:
                    raise ValueError("certificate trace is truncated")
                for a, b in struct.iter_unpack("<II", encoded):
                    redex = ("c" + str(a), "c" + str(b))
                    assert redex == net.next_active(), "recorded policy differs from FIFO"
                    net.reduce(*redex)
                    peak = max(peak, len(net.nodes))
                remaining -= block_count
            net.final_check()
            assert not net.active()
            assert peak == record["peak_live_cells"]
            assert len(net.nodes) == record["final_cells"] and net.cycles == record["cyclic_wires"]
            assert port_graph_isomorphic(net, reference)
            offset += count
            print("REPLAY", record["rule"], "PASS", flush=True)
        assert stream.read(1) == b"", "unaccounted primitive trace records"
    assert offset == report["trace"]["steps"]
    assert certify_program_codec(compiler) == report["program_codec"]
    extraction, distinct = certify_symbol_extraction(compiler)
    assert extraction == report["symbol_extraction"] and distinct == report["distinct_symbol_template_pairs"]
    return len(report["certificates"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--verify-report", type=Path)
    args = parser.parse_args()
    compiler = CoherentICCompiler()
    if args.verify_report:
        if not args.trace:
            parser.error("--verify-report requires --trace")
        encoded = args.verify_report.read_bytes()
        report = json_loads(gzip.decompress(encoded) if args.verify_report.suffix == ".gz" else encoded)
        print("PASS: coherent primitive rule traces replayed", verify(report, args.trace, compiler))
        return
    report = generate(compiler, args.trace)
    if args.report:
        write_json(args.report, report)
    print("PASS: unified source-rule certificates", len(report["certificates"]),
          "total primitive interactions", sum(c["primitive_interactions"] for c in report["certificates"]))


if __name__ == "__main__":
    main()
