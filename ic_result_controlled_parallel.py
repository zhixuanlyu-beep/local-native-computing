"""Standard-library parallel trace chunks for independent M6 case groups."""

import gzip
import hashlib
import json
from ic_evidence_json import loads as json_loads
import multiprocessing
from pathlib import Path
import tempfile

from ic_schedule_audit import ScheduleTrace

_context = None
BLOCK = 1024 * 1024


def _initialize(library, compiler, witnesses, metadata):
    global _context
    _context = library, compiler, witnesses, metadata


def _group(task):
    from ic_result_controlled_evidence import run_case, POLICIES
    from ic_result_controlled_execution import build_result_sequence, expected, reference_states
    from ic_result_controlled_composition import staged_case
    case, path, replay = task
    library, compiler, witnesses, metadata = _context
    trace = ScheduleTrace(path, metadata, replay=replay)
    records = []
    try:
        numbers = case["numbers"]
        states = reference_states(numbers)[0]
        for policy in POLICIES:
            built = build_result_sequence(numbers, library=library, compiler=compiler)
            record = run_case(built, expected(compiler, numbers, library), trace, policy,
                              expected_states=states)
            record.update({"case": case, "reference_states": states})
            records.append(record)
        staged = staged_case(numbers, library, compiler, witnesses, trace)
    except BaseException:
        trace.abort()
        raise
    summary = trace.close()
    print("GROUP", case["name"], [r["status"] for r in records], staged["status"], flush=True)
    return records, staged, summary


def _shift(value, offset):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("trace_offset_records", "end") and type(item) is int:
                value[key] = item + offset
            elif key not in ("initial", "final_graph", "expected", "actual", "wires", "kinds", "boundaries"):
                _shift(item, offset)
        return value
    if isinstance(value, list):
        for item in value:
            _shift(item, offset)
    return value


def _header(metadata):
    return (json.dumps({"format": "IC-PAIR-U32LE-1", **metadata}, sort_keys=True) + "\n").encode()


def _split(parent, path, count, metadata):
    if type(count) is not int or count < 0:
        raise ValueError("parallel replay interval must be a nonnegative integer")
    offset, remaining = parent.count, count * 8
    with gzip.open(path, "wb", compresslevel=6) as output:
        output.write(_header(metadata))
        while remaining:
            raw = parent.stream.read(min(BLOCK, remaining))
            if not raw or len(raw) % 8:
                raise ValueError("truncated parallel replay interval")
            output.write(raw)
            parent.digest.update(raw)
            parent.count += len(raw) // 8
            remaining -= len(raw)
    return offset


def _merge(parent, path, metadata, expected_summary):
    offset, digest, count = parent.count, hashlib.sha256(), 0
    with gzip.open(path, "rb") as stream:
        if json_loads(stream.readline()) != {"format": "IC-PAIR-U32LE-1", **metadata}:
            raise ValueError("parallel chunk header mismatch")
        while raw := stream.read(BLOCK):
            if len(raw) % 8:
                raise ValueError("truncated parallel pair record")
            digest.update(raw)
            count += len(raw) // 8
            parent.writer.buffer.extend(raw)
            parent.writer.count += len(raw) // 8
            parent.count += len(raw) // 8
            parent.writer.flush()
    if count != expected_summary["steps"] or digest.hexdigest() != expected_summary["sha256_of_pair_records"]:
        raise ValueError("parallel chunk differs from validated worker evidence")
    return offset


def run_parallel(case_specs, library, compiler, witnesses, metadata, parent_trace,
                 *, replay_counts=None, max_workers=4):
    """Run independent whole-network experiments locally and order their proofs.

    Parallelism only changes host experiment orchestration. Each individual
    network uses the unchanged primitive reducer and its declared schedule.
    Replay intervals are untrusted hints; each worker validates all pairs and
    exact EOF, and the caller compares every reconstructed report field.
    """
    if type(max_workers) is not int or max_workers < 1:
        raise ValueError("worker count must be a positive integer")
    replay = parent_trace.replay
    if replay and (replay_counts is None or len(replay_counts) != len(case_specs)):
        raise ValueError("one replay interval is required per fixed case")
    with tempfile.TemporaryDirectory(prefix="ic-m6-") as directory:
        paths = [Path(directory) / f"case-{i}.gz" for i in range(len(case_specs))]
        offsets = []
        if replay:
            offsets = [_split(parent_trace, path, count, metadata)
                       for path, count in zip(paths, replay_counts)]
        tasks = [(case, str(path), replay) for case, path in zip(case_specs, paths)]
        context = multiprocessing.get_context("spawn")
        with context.Pool(min(max_workers, len(tasks)), initializer=_initialize,
                          initargs=(library, compiler, witnesses, metadata)) as pool:
            groups = pool.map(_group, tasks, chunksize=1)
        records, staged = [], []
        for index, ((rows, lifted, summary), path) in enumerate(zip(groups, paths)):
            if replay:
                if summary["steps"] != replay_counts[index]:
                    raise ValueError("reconstructed parallel interval length mismatch")
                offset = offsets[index]
            else:
                offset = _merge(parent_trace, path, metadata, summary)
            records.extend(_shift(rows, offset))
            staged.append(_shift(lifted, offset))
        return records, staged
