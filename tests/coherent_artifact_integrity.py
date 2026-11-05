"""Reject mismatched reports, damaged traces, and false runtime peak claims."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ic_coherent_feedback import CoherentICCompiler, execute_input, read_json, verify_report, write_json

compiler = CoherentICCompiler()
with TemporaryDirectory() as directory:
    base = Path(directory)
    trace, final, report = (base / name for name in ('pairs.gz', 'final.gz', 'report.gz'))
    original = execute_input(0, compiler, trace_path=trace, final_graph_path=final, progress_interval=0)
    write_json(report, original)
    verify_report(report, trace, final, compiler, replay=True)
    def rejects(action):
        try:
            action()
        except (AssertionError, ValueError):
            return
        raise AssertionError('tampered evidence was accepted')
    for key, value in (('primitive_interactions', 1), ('initial_cells', 1),
                       ('decoded_result', ['SQ', 9]), ('final_graph_spec_sha256', '0' * 64)):
        changed = deepcopy(original)
        changed[key] = value
        write_json(report, changed)
        rejects(lambda: verify_report(report, trace, final, compiler))
    write_json(report, original)
    encoded = gzip.decompress(trace.read_bytes())
    trace.write_bytes(gzip.compress(encoded[:-8], mtime=0))
    rejects(lambda: verify_report(report, trace, final, compiler))
    trace.write_bytes(gzip.compress(encoded, mtime=0))
    changed, snapshot = deepcopy(original), read_json(final)
    changed['peak_live_cells'] += 1
    snapshot['peak_live_cells'] += 1
    write_json(report, changed)
    write_json(final, snapshot)
    rejects(lambda: verify_report(report, trace, final, compiler, replay=True))
    original_snapshot = read_json(final)
    original_snapshot['peak_live_cells'] -= 1
    write_json(report, original)
    write_json(final, original_snapshot)
    header, records = encoded.split(b'\n', 1)
    changed_header = json.loads(header)
    changed_header['input'] = 1
    trace.write_bytes(gzip.compress(json.dumps(changed_header).encode() + b'\n' + records, mtime=0))
    rejects(lambda: verify_report(report, trace, final, compiler))
    damaged = bytearray(records)
    damaged[len(damaged) // 2] ^= 1
    trace.write_bytes(gzip.compress(header + b'\n' + damaged, mtime=0))
    rejects(lambda: verify_report(report, trace, final, compiler))
    trace.write_bytes(gzip.compress(encoded, mtime=0))
    for field, value in (('peak_live_cells', original['peak_live_cells'] + 1), ('input', 1)):
        snapshot = deepcopy(original_snapshot)
        snapshot[field] = value
        write_json(final, snapshot)
        rejects(lambda: verify_report(report, trace, final, compiler))
    snapshot = deepcopy(original_snapshot)
    snapshot['graph']['cycles'] += 1
    write_json(final, snapshot)
    rejects(lambda: verify_report(report, trace, final, compiler))
    write_json(final, original_snapshot)
    for field, value in (('cyclic_wires', 1), ('final_graph_sha256', '0' * 64)):
        changed = deepcopy(original)
        changed[field] = value
        write_json(report, changed)
        rejects(lambda: verify_report(report, trace, final, compiler, replay=field == 'final_graph_sha256'))
print('PASS: valid artifact replay and thirteen evidence-tampering cases')
