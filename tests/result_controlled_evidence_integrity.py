"""Reduced integrity checks for M6 result-controlled execution evidence."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ic_result_controlled_evidence as evidence


class Event:
    def __init__(self, kind, stage, step, pair, kinds, frame_cells_remaining=None):
        self.update({"kind": kind, "stage": stage, "step": step,
                     "pair": pair, "kinds": kinds})
        if frame_cells_remaining is not None:
            self["frame_cells_remaining"] = frame_cells_remaining

    def update(self, value):
        self.__dict__.update(value)

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def get(self, key, default=None):
        return self.__dict__.get(key, default)


class ProtocolIntegrity(unittest.TestCase):
    def test_late_skip_token_cannot_impersonate_result_readiness(self):
        stages = [{"index": 0, "enabled": True,
                   "reader": {"ready_emitters": ["original-terminal"], "join_gates": [],
                              "result_completion_by_symbol": {"SQ": "completion"},
                              "progress_ready_tokens": {"SQ": "result-progress"}}}]
        events = [Event("grant", 0, 0, ["a", "b"], ["g", "g"]),
                  Event("delivery", 0, 1, ["c", "d"], ["g", "g"]),
                  Event("result-recognition", 0, 2, ["original-terminal", "completion"], ["g", "g"]),
                  Event("progress-unpack", 0, 3, ["e", "f"], ["g", "g"]),
                  Event("advance", 0, 4, ["skip", "advance"], ["g", "g"])]
        errors = evidence.validate_protocol(stages, events)
        self.assertTrue(any("selected result progress token" in e["reason"] for e in errors))
        events[-1].pair = ["result-progress", "advance"]
        self.assertEqual(evidence.validate_protocol(stages, events), [])

    def test_enabled_result_must_be_recognized_before_progress_and_advance(self):
        stages = [{"index": 0, "enabled": True, "skip_ready": "s",
                   "reader": {"ready_emitters": ["ready"], "join_gates": []}}]
        events = [
            Event("grant", 0, 0, ["a", "b"], ["g", "g"]),
            Event("delivery", 0, 1, ["c", "d"], ["g", "g"]),
            Event("result-recognition", 0, 2, ["ready", "gate"], ["g", "g"]),
            Event("progress-unpack", 0, 3, ["e", "f"], ["g", "g"]),
            Event("advance", 0, 4, ["g", "h"], ["g", "g"]),
        ]
        self.assertEqual(evidence.validate_protocol(stages, events), [])

        reordered = [Event("advance", 0, 4, ["g", "h"], ["g", "g"])]
        self.assertNotEqual(evidence.validate_protocol(stages, reordered), [])

    def test_skip_recovery_token_must_reach_advance(self):
        stages = [{"index": 0, "enabled": False, "skip_ready": "skip",
                   "_skip_ready": "skip",
                   "reader": {"ready_emitters": [], "join_gates": []}}]
        events = [
            Event("grant", 0, 0, ["a", "b"], ["g", "g"]),
            Event("delivery", 0, 1, ["c", "d"], ["g", "g"]),
            Event("result-recognition", 0, 2, ["x", "y"], ["g", "g"]),
            Event("progress-unpack", 0, 3, ["e", "f"], ["g", "g"]),
            Event("advance", 0, 4, ["skip", "h"], ["g", "g"]),
        ]
        self.assertEqual(evidence.validate_protocol(stages, events), [])
        events[-1].pair = ["other", "h"]
        self.assertNotEqual(evidence.validate_protocol(stages, events), [])

    def test_component_readiness_requires_complete_unpack_frame(self):
        stages = [{"index": 0, "enabled": True, "skip_ready": "s",
                   "reader": {"ready_emitters": ["ready"], "join_gates": []}}]
        events = [Event("component-ready", 0, 0, ["ready", "consumer"],
                        ["g", "e"], frame_cells_remaining=["frame-cell"])]
        self.assertNotEqual(evidence.validate_protocol(stages, events), [])


if __name__ == "__main__":
    unittest.main()
