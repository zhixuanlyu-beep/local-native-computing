"""Control packet agreement, full terminals and fixed all-schedule bounds."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ic_native_control_packets import control_packet, validate_control_packet, protocol_evidence
from ic_observation_contracts import value_spec


class Sink:
    count = 0
    def record(self, pair):
        self.count += 1


class NativeControlIntegrity(unittest.TestCase):
    def test_exact_boolean_and_root_interface(self):
        for bit in (False, True):
            packet = control_packet(bit)
            self.assertEqual(packet.boundaries, ("ROOT",))
            self.assertEqual(validate_control_packet(packet), packet)
        for value in (0, 1, None, "true"):
            with self.assertRaises(ValueError):
                control_packet(value)

    def test_wrong_representation_rejected(self):
        for representation in ("A", "B"):
            for bit in (False, True):
                with self.assertRaises(ValueError):
                    validate_control_packet(value_spec(representation, bit))

    def test_all_fixed_payloads_all_schedules_complete_graphs(self):
        cases = protocol_evidence(Sink())
        self.assertEqual(len(cases), 8)
        for record in cases:
            self.assertEqual(record["status"], "passed")
            self.assertTrue(record["all_terminal_graphs_match"])
            self.assertTrue(record["exploration"]["complete"])
            self.assertTrue(record["exploration"]["all_executions_terminate"])
            self.assertLessEqual(record["exploration"]["states"], 4096)
            self.assertLessEqual(record["exploration"]["attempted_transitions"], 32768)
            self.assertLessEqual(record["exploration"]["peak_live_cells"], 128)


if __name__ == "__main__":
    unittest.main()
