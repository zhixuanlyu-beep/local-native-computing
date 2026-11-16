"""Native IC feedback execution and structural output verification."""
import argparse
import gzip
import hashlib
import json
from ic_evidence_json import loads as json_loads
from math import isqrt
from pathlib import Path
import struct

from ic_fast_reducer import FastNet
from ic_research_artifacts import GraphSpec
from ic_coherent_output_decoder import decode_feedback, port_graph_isomorphic
from source_feedback_audit import make_sim
from source_ic_coherent_compiler import CoherentICCompiler


def graph_digest(net):
    digest = hashlib.sha256()
    for cell, kind in net.nodes.items():
        digest.update((cell + ":" + kind + "\n").encode("ascii"))
    for endpoint, neighbor in net.adj.items():
        digest.update((repr((endpoint, neighbor)) + "\n").encode("utf-8"))
    digest.update(repr((sorted(net.free), net.cycles)).encode("utf-8"))
    return digest.hexdigest()


class PrimitiveTrace:
    """Gzip stream: JSON header followed by little-endian uint32 ID pairs."""
    def __init__(self, path, metadata):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = gzip.open(self.path, "wb", compresslevel=6)
        self.stream.write((json.dumps({"format": "IC-PAIR-U32LE-1", **metadata}, sort_keys=True) + "\n").encode("utf-8"))
        self.digest, self.buffer, self.count = hashlib.sha256(), bytearray(), 0

    def record(self, pair):
        self.buffer.extend(struct.pack("<II", *(int(cell[1:]) for cell in pair)))
        self.count += 1
        if len(self.buffer) >= 1024 * 1024:
            self.flush()

    def flush(self):
        if self.buffer:
            self.digest.update(self.buffer)
            self.stream.write(self.buffer)
            self.buffer.clear()

    def close(self):
        self.flush()
        self.stream.close()
        return {"format": "IC-PAIR-U32LE-1", "steps": self.count,
                "sha256_of_pair_records": self.digest.hexdigest()}


def read_trace_summary(path):
    digest, records = hashlib.sha256(), 0
    with gzip.open(path, "rb") as stream:
        metadata = json_loads(stream.readline())
        if metadata.get("format") != "IC-PAIR-U32LE-1":
            raise ValueError("unknown primitive trace format")
        while block := stream.read(1024 * 1024):
            if len(block) % 8:
                raise ValueError("truncated primitive pair record")
            digest.update(block)
            records += len(block) // 8
    return {"metadata": metadata, "steps": records,
            "sha256_of_pair_records": digest.hexdigest()}


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(data, sort_keys=True, indent=2) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(encoded, mtime=0) if path.suffix == ".gz" else encoded)


def read_json(path):
    path = Path(path)
    encoded = path.read_bytes()
    return json_loads(gzip.decompress(encoded) if path.suffix == ".gz" else encoded)


def spec_digest(spec):
    """Bind a serialized graph independently of runtime cell identifiers."""
    return hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def source_result_graph(value):
    """Independent source output constructor; never used by the runtime."""
    types, adjacency = {}, {}
    def cell(kind):
        name = "out" + str(len(types))
        types[name] = kind
        return name
    def connect(a, b):
        adjacency[a], adjacency[b] = b, a
    def unary(number):
        root = (cell("Z"), 0)
        for _ in range(number):
            successor = cell("S")
            connect((successor, 1), root)
            root = (successor, 0)
        return root
    top = cell(value[0])
    for index, number in enumerate(value[1:], 1):
        connect((top, index), unary(number))
    connect((top, 0), ("OUT", 0))
    return types, adjacency


def execute_input(number, compiler, *, limit=50_000_000, trace_path=None,
                  final_graph_path=None, progress_interval=100_000):
    if type(number) is not int or number < 0:
        raise ValueError("input must be a natural number")
    source_types, source_adjacency = make_sim(number)
    net = compiler.compile(source_types, source_adjacency, net_class=FastNet)
    initial = len(net.nodes)
    initial_digest = graph_digest(net)
    program_digest = graph_digest(compiler.program)
    trace = PrimitiveTrace(trace_path, {"input": number, "initial_graph_sha256": initial_digest,
                                        "program_sha256": program_digest, "schedule": "FIFO"}) if trace_path else None
    print(f"IC input {number}: expanded initial cells={initial}", flush=True)
    steps, peak = 0, initial
    try:
        while net.active():
            if steps >= limit:
                raise RuntimeError(f"native execution cutoff after {steps} primitive steps")
            pair = net.next_active()
            if pair is None:
                raise AssertionError("nonempty active index has no schedulable pair")
            if trace:
                trace.record(pair)
            net.reduce(*pair)
            steps += 1
            peak = max(peak, len(net.nodes))
            if progress_interval and steps % progress_interval == 0:
                print(f"IC input {number}: {steps} primitive reductions, {len(net.nodes)} live cells", flush=True)
    finally:
        trace_summary = trace.close() if trace else None
    net.final_check()
    final_spec = GraphSpec.from_net(net).to_dict()
    if final_graph_path:
        # Preserve actual execution evidence before any subsequent readout
        # check, so an observer defect does not force a runtime restart.
        write_json(final_graph_path, {"input": number, "graph": final_spec,
                                      "native_steps": steps, "initial_cells": initial,
                                      "peak_live_cells": peak, "trace": trace_summary})
    actual = decode_feedback(net, compiler)
    root = isqrt(number)
    oracle = ("SQ", root) if root * root == number else ("BR", root, root + 1)
    if actual != oracle:
        raise AssertionError((number, actual, oracle))
    independent = compiler.compile(*source_result_graph(oracle))
    if not port_graph_isomorphic(net, independent):
        raise AssertionError("the entire terminal IC graph differs from the independent source output encoding")
    if trace_path:
        scanned = read_trace_summary(trace_path)
        assert scanned["steps"] == steps == trace_summary["steps"]
        assert scanned["sha256_of_pair_records"] == trace_summary["sha256_of_pair_records"]
    return {"input": number, "source_initial_cells": len(source_types), "initial_cells": initial,
            "initial_graph_sha256": initial_digest, "program_sha256": program_digest,
            "primitive_interactions": steps, "peak_live_cells": peak,
            "final_cells": len(net.nodes), "final_graph_sha256": graph_digest(net),
            "final_graph_spec_sha256": spec_digest(final_spec),
            "cyclic_wires": net.cycles, "decoded_result": list(actual),
            "whole_graph_matches_independent_output": True,
            "schedule": "FIFO primitive active pairs", "trace": trace_summary}


def verify_final_graph(path, compiler):
    data = read_json(path)
    net = GraphSpec.from_dict(data["graph"]).instantiate()
    if net.active():
        raise ValueError("saved output is not a terminal primitive graph")
    decoded = decode_feedback(net, compiler)
    number = data["input"]
    root = isqrt(number)
    oracle = ("SQ", root) if root * root == number else ("BR", root, root + 1)
    assert decoded == oracle
    independent = compiler.compile(*source_result_graph(decoded))
    assert port_graph_isomorphic(net, independent)
    return {"input": data["input"], "decoded_result": list(decoded),
            "final_cells": len(net.nodes), "native_steps_recorded": data["native_steps"],
            "cyclic_wires": net.cycles, "final_graph_spec_sha256": spec_digest(data["graph"])}


def verify_report(report_path, trace_path, final_path, compiler, *, replay=False, limit=50_000_000):
    """Bind all archived artifacts; optional replay executes every primitive step.

    Without replay this checks integrity and structural output, not the
    intermediate transitions or the reported peak. Full replay checks those.
    """
    report, saved = read_json(report_path), read_json(final_path)
    number = report["input"]
    assert type(number) is int and number >= 0
    source = make_sim(number)
    initial = compiler.compile(*source, net_class=FastNet)
    scanned = read_trace_summary(trace_path)
    header = scanned["metadata"]
    expected_header = {"format": "IC-PAIR-U32LE-1", "input": number,
                       "initial_graph_sha256": graph_digest(initial),
                       "program_sha256": graph_digest(compiler.program), "schedule": "FIFO"}
    assert header == expected_header, "trace header does not match the actual compiled input"
    assert report["initial_graph_sha256"] == header["initial_graph_sha256"]
    assert report["program_sha256"] == header["program_sha256"]
    assert report["source_initial_cells"] == len(source[0])
    assert report["initial_cells"] == saved["initial_cells"] == len(initial.nodes)
    assert saved["input"] == number
    expected_trace = {"format": header["format"], "steps": scanned["steps"],
                      "sha256_of_pair_records": scanned["sha256_of_pair_records"]}
    assert report["trace"] == saved["trace"] == expected_trace
    assert report["primitive_interactions"] == saved["native_steps"] == scanned["steps"]
    assert report["peak_live_cells"] == saved["peak_live_cells"]
    assert report["peak_live_cells"] >= max(report["initial_cells"], report["final_cells"])
    assert report["schedule"] == "FIFO primitive active pairs"
    assert report["whole_graph_matches_independent_output"] is True
    terminal = verify_final_graph(final_path, compiler)
    for key in ("decoded_result", "final_cells", "cyclic_wires", "final_graph_spec_sha256"):
        assert report[key] == terminal[key], (key, "saved report differs from terminal graph")
    if replay:
        actual = replay_input(number, compiler, trace_path, limit=limit)
        assert actual["final_graph_spec_sha256"] == terminal["final_graph_spec_sha256"]
        for key, value in actual.items():
            if key != "execution_mode":
                assert report[key] == value, (key, "saved report differs from primitive replay")
    return {"input": number, "decoded_result": terminal["decoded_result"],
            "primitive_interactions": scanned["steps"],
            "verification": "full primitive replay and artifact binding" if replay else "artifact integrity and structural output"}


def replay_input(number, compiler, path, *, limit=50_000_000,
                 final_graph_path=None, progress_interval=100_000):
    """Re-execute a stored primitive witness from the expanded initial graph."""
    source_types, source_adjacency = make_sim(number)
    net = compiler.compile(source_types, source_adjacency, net_class=FastNet)
    initial, peak, steps = len(net.nodes), len(net.nodes), 0
    initial_digest, program_digest = graph_digest(net), graph_digest(compiler.program)
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as stream:
        header = json_loads(stream.readline())
        assert header["format"] == "IC-PAIR-U32LE-1" and header["input"] == number
        assert header["initial_graph_sha256"] == initial_digest
        assert header["program_sha256"] == program_digest and header["schedule"] == "FIFO"
        while encoded := stream.read(1024 * 1024):
            if len(encoded) % 8:
                raise ValueError("truncated primitive witness")
            digest.update(encoded)
            for a, b in struct.iter_unpack("<II", encoded):
                if steps >= limit:
                    raise RuntimeError("primitive replay budget exhausted")
                redex = ("c" + str(a), "c" + str(b))
                assert redex == net.next_active(), "recorded action is not the next FIFO active pair"
                net.reduce(*redex)
                steps += 1
                peak = max(peak, len(net.nodes))
                if progress_interval and steps % progress_interval == 0:
                    print(f"IC replay {number}: {steps} primitive reductions", flush=True)
    net.final_check()
    assert not net.active(), "the trace stops before normalization"
    actual = decode_feedback(net, compiler)
    root = isqrt(number)
    oracle = ("SQ", root) if root * root == number else ("BR", root, root + 1)
    assert actual == oracle
    independent = compiler.compile(*source_result_graph(oracle))
    assert port_graph_isomorphic(net, independent)
    trace = {"format": "IC-PAIR-U32LE-1", "steps": steps,
             "sha256_of_pair_records": digest.hexdigest()}
    result = {"input": number, "source_initial_cells": len(source_types),
              "initial_cells": initial, "initial_graph_sha256": initial_digest,
              "program_sha256": program_digest, "primitive_interactions": steps,
              "peak_live_cells": peak, "final_cells": len(net.nodes),
              "final_graph_sha256": graph_digest(net), "cyclic_wires": net.cycles,
              "final_graph_spec_sha256": spec_digest(GraphSpec.from_net(net).to_dict()),
              "decoded_result": list(actual), "whole_graph_matches_independent_output": True,
              "schedule": "FIFO primitive active pairs", "execution_mode": "full primitive trace replay",
              "trace": trace}
    if final_graph_path:
        write_json(final_graph_path, {"input": number, "graph": GraphSpec.from_net(net).to_dict(),
                                      "native_steps": steps, "initial_cells": initial,
                                      "peak_live_cells": peak, "trace": trace})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=int, default=0)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--final-graph", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verify-final", type=Path)
    parser.add_argument("--verify-report", type=Path)
    parser.add_argument("--replay-trace", type=Path)
    parser.add_argument("--limit", type=int, default=50_000_000)
    args = parser.parse_args()
    compiler = CoherentICCompiler()
    if args.verify_report:
        trace_path = args.replay_trace or args.trace
        if not trace_path or not args.verify_final:
            parser.error("--verify-report requires --trace (or --replay-trace) and --verify-final")
        print(json.dumps(verify_report(args.verify_report, trace_path, args.verify_final, compiler,
                                      replay=bool(args.replay_trace), limit=args.limit), sort_keys=True))
        return
    if args.verify_final:
        print(json.dumps(verify_final_graph(args.verify_final, compiler), sort_keys=True))
        return
    if args.replay_trace:
        result = replay_input(args.input, compiler, args.replay_trace,
                              limit=args.limit, final_graph_path=args.final_graph)
    else:
        result = execute_input(args.input, compiler, limit=args.limit,
                               trace_path=args.trace, final_graph_path=args.final_graph)
    if args.report:
        write_json(args.report, result)
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
