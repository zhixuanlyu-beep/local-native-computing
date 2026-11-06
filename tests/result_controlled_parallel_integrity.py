"""Parallel chunks retain deterministic ordering and strict primitive replay."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ic_native_control_packets import protocol_evidence
from ic_result_controlled_composition import build_local, local_expected, PairList
from ic_result_controlled_evidence import run_case, POLICIES
from ic_result_controlled_parallel import run_parallel
from ic_result_controlled_library import load_control_library, ROOT
from ic_research_artifacts import GraphSpec
from ic_schedule_audit import ScheduleTrace
from source_ic_coherent_compiler import CoherentICCompiler


class ParallelIntegrity(unittest.TestCase):
    def test_actual_case_chunks_reconstruct_and_replay_with_prefix_and_suffix(self):
        library = load_control_library(ROOT / "results/structure_library.json.gz")
        compiler = CoherentICCompiler()
        built = build_local(0, True, library, compiler)
        pairs = PairList()
        record = run_case(built, local_expected(0, True, library, compiler), pairs,
                          POLICIES[0], expected_states=[True])
        self.assertEqual(record["status"], "passed")
        witnesses = {(0, True): {"initial": GraphSpec.from_net(built.net),
                                  "core": built.stage_cells[0], "pairs": pairs.pairs}}
        cases = [{"name": f"zero-{i}", "numbers": [0]} for i in range(2)]
        metadata = {"fixture": "actual parallel group replay"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.gz"
            trace = ScheduleTrace(path, metadata)
            protocol_evidence(trace)
            rows, staged = run_parallel(cases, library, compiler, witnesses, metadata,
                                        trace, max_workers=2)
            protocol_evidence(trace)
            summary = trace.close()
            counts = [sum(r["primitive_interactions"] for r in rows[i*3:i*3+3])
                      + staged[i]["primitive_interactions"] for i in range(2)]
            self.assertTrue(all(r["status"] == "passed" for r in rows + staged))
            replay = ScheduleTrace(path, metadata, replay=True)
            protocol_evidence(replay)
            other_rows, other_staged = run_parallel(cases, library, compiler, witnesses, metadata,
                                                    replay, replay_counts=counts, max_workers=2)
            protocol_evidence(replay)
            self.assertEqual(summary, replay.close())
            self.assertEqual(rows, other_rows)
            self.assertEqual(staged, other_staged)


if __name__ == "__main__":
    unittest.main()
