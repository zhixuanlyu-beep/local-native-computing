"""Integrity tests for native multiport component capsules.

The fixture uses the actual frozen M4 selected library.  It checks package
encoding, decoded activation, literal unpacking, exact slot order, READY
scope, immutability, and rejection of unsupported package representations.
"""

from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ic_composition_certificates import full_match
from ic_observation_contracts import TaskContract, value_spec
from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec
from ic_structure_capsules import (
    Capsule,
    assess_capsule,
    build_activation,
    build_capsule,
    build_unpack,
)
from lafont_ic_macro_builder import macro_connect


REPORT_PATH = REPO / "results" / "multitask_discovery.json.gz"


def _raw_component(net, component, labels=None):
    """Append the exact component and return its ordered boundary stubs."""
    labels = tuple(component.boundaries) if labels is None else tuple(labels)
    names = [net.cell(kind) for kind in component.kinds]
    stubs = {original: net.boundary("RAW::" + label)
             for original, label in zip(component.boundaries, labels)}

    def port(endpoint):
        if endpoint[0] == "F":
            if endpoint[1] not in stubs:
                raise AssertionError("component boundary disappeared")
            return stubs[endpoint[1]]
        return (names[endpoint[0]], endpoint[1])

    for left, right in component.wires:
        net.link(port(left), port(right))
    net.cycles += component.cycles
    return names, stubs


def _consumers(net, labels):
    """Create one free output per label and return ordered target ports."""
    ports = []
    for label in labels:
        gamma = net.cell("g")
        epsilon = net.cell("e")
        net.link((gamma, 0), net.boundary("OUT::" + label))
        net.link((gamma, 2), (epsilon, 0))
        ports.append((gamma, 1))
    return tuple(ports)


def _original_reference(component, labels):
    net = Net()
    _, stubs = _raw_component(net, component, labels)
    ports = _consumers(net, labels)
    for label, endpoint in zip(component.boundaries, ports):
        macro_connect(net, stubs[label], endpoint)
    net.check()
    return net


def _reduce(net):
    steps = 0
    while net.active():
        net.reduce(*net.active()[0])
        steps += 1
    return steps


class StructureCapsuleIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(REPORT_PATH, "rt", encoding="utf-8") as stream:
            report = json.load(stream)
        assert report["status"] == "passed"
        cls.components = {
            role: GraphSpec.from_dict(entry["graph"])
            for role, entry in report["selected_library"].items()
        }

    def test_frozen_six_roles_round_trip_and_exact_original_order(self):
        for role, component in self.components.items():
            with self.subTest(role=role):
                original = component.to_dict()
                capsule = build_capsule(component)
                self.assertIsInstance(capsule, Capsule)
                self.assertIs(capsule.component, component)
                self.assertEqual(capsule.interface, tuple(component.boundaries))
                self.assertEqual(capsule.width, len(component.boundaries) + 1)
                self.assertEqual(capsule.ready_slot, 0)
                self.assertEqual(capsule.component.to_dict(), original)
                self.assertEqual(capsule.package.boundaries, ("ROOT",))
                self.assertEqual(capsule.code.boundaries, ("ROOT",))
                self.assertTrue(all(kind != "d" for kind in capsule.code.kinds))

                net = Net()
                ports = _consumers(net, capsule.interface)
                ready = net.cell("e")
                code_root = capsule.code.open_root(net)
                metadata = build_activation(
                    net, capsule.width, code_root, ports, (ready, 0)
                )
                self.assertEqual(set(metadata), {"decoder_head", "unpack_head", "width", "ready_slot"})
                self.assertRegex(metadata["decoder_head"], r"^c\d+$")
                self.assertRegex(metadata["unpack_head"], r"^c\d+$")
                self.assertEqual(metadata["width"], capsule.width)
                self.assertEqual(metadata["ready_slot"], 0)
                _reduce(net)
                self.assertTrue(full_match(net, _original_reference(component, capsule.interface)))

                raw = Net()
                package_root = capsule.package.open_root(raw)
                raw_ports = _consumers(raw, capsule.interface)
                raw_ready = raw.cell("e")
                unpack_metadata = build_unpack(
                    raw, capsule.width, package_root, raw_ports, (raw_ready, 0)
                )
                self.assertEqual(set(unpack_metadata), {"decoder_head", "unpack_head", "width", "ready_slot"})
                self.assertIsNone(unpack_metadata["decoder_head"])
                self.assertRegex(unpack_metadata["unpack_head"], r"^c\d+$")
                _reduce(raw)
                self.assertTrue(full_match(raw, _original_reference(component, capsule.interface)))

    def test_ready_slot_is_first_and_frame_readiness_is_local(self):
        component = self.components["copy_A"]
        capsule = build_capsule(component)
        net = Net()
        ports = _consumers(net, capsule.interface)
        ready = net.cell("e")
        package_root = capsule.package.open_root(net)
        build_unpack(net, capsule.width, package_root, ports, (ready, 0))
        _reduce(net)
        self.assertFalse(net.active())
        self.assertEqual(len(net.nodes), len(component.kinds) + 2 * len(capsule.interface))

    def test_empty_wire_component_and_without_ready(self):
        wire = GraphSpec((),
                         ("IN", "OUT"),
                         ((("F", "IN"), ("F", "OUT")),),
                         0)
        capsule = build_capsule(wire)
        self.assertEqual(capsule.interface, ("IN", "OUT"))
        self.assertEqual(capsule.width, 3)
        self.assertEqual(capsule.ready_slot, 0)
        without_ready = build_capsule(wire, with_ready=False)
        self.assertIsNone(without_ready.ready_slot)
        self.assertEqual(without_ready.width, 2)
        self.assertTrue(full_match(without_ready.package.instantiate(), value_spec("A", True).instantiate()))
        net = Net()
        ports = _consumers(net, capsule.interface)
        ready = net.cell("e")
        root = capsule.code.open_root(net)
        build_activation(net, capsule.width, root, ports, (ready, 0))
        _reduce(net)
        self.assertTrue(full_match(net, _original_reference(wire, wire.boundaries)))

    def test_copy_code_activation_is_disjoint_and_original_is_read_only(self):
        component = self.components["copy_A"]
        capsule = build_capsule(component)
        original = capsule.code.to_dict()
        net = Net()
        code_root = capsule.code.open_root(net)
        source_ids = set(net.nodes)
        fork = net.cell("d")
        macro_connect(net, code_root, (fork, 0))
        first_labels = tuple("FIRST::" + label for label in capsule.interface)
        second_labels = tuple("SECOND::" + label for label in capsule.interface)
        first_ports = _consumers(net, first_labels)
        second_ports = _consumers(net, second_labels)
        first_ready = net.boundary("FIRST::READY")
        second_ready = net.boundary("SECOND::READY")
        build_activation(net, capsule.width, (fork, 1), first_ports, first_ready)
        build_activation(net, capsule.width, (fork, 2), second_ports, second_ready)
        _reduce(net)
        net.check()
        expected = Net()
        for prefix in ("FIRST::", "SECOND::"):
            labels = tuple(prefix + label for label in capsule.interface)
            reference = _original_reference(component, labels)
            GraphSpec.from_net(reference).instantiate(expected)
            ready = value_spec("A", True).open_root(expected)
            expected.link(ready, expected.boundary(prefix + "READY"))
        self.assertTrue(full_match(net, expected))
        self.assertFalse(source_ids & set(net.nodes))
        self.assertEqual(capsule.code.to_dict(), original)

    def test_legitimate_disconnected_free_components_are_eligible(self):
        disconnected = GraphSpec(("e", "e"),
                                 ("ROOT", "PRIVATE"),
                                 ((("F", "ROOT"), (0, 0)),
                                  (("F", "PRIVATE"), (1, 0))),
                                 0)
        self.assertEqual(assess_capsule(disconnected)["status"], "eligible")

    def test_gamma_capsule_full_decoded_round_trip(self):
        from ic_program_code_bridge import payloads

        gamma = payloads()["Gamma"]["object"]
        capsule = build_capsule(gamma)
        net = Net()
        out = net.boundary("OUT")
        status = net.boundary("STATUS")
        root = capsule.code.open_root(net)
        build_activation(net, capsule.width, root, (out,), status)
        _reduce(net)

        expected = Net()
        gamma.instantiate(expected, {"ROOT": expected.boundary("OUT")})
        ready = value_spec("A", True).open_root(expected)
        expected.link(ready, expected.boundary("STATUS"))
        expected.check()
        self.assertTrue(full_match(net, expected))

    def test_unsupported_representations_are_reported_without_filtering(self):
        net = Net()
        left = net.cell("g")
        right = net.cell("g")
        net.link((left, 0), (right, 0))
        for cell, suffix in ((left, "L"), (right, "R")):
            net.link((cell, 1), net.boundary(suffix + "-LEFT"))
            net.link((cell, 2), net.boundary(suffix + "-RIGHT"))
        active = GraphSpec.from_net(net)

        private = GraphSpec(("e", "e", "e"),
                            ("ROOT",),
                            ((("F", "ROOT"), (0, 0)),
                             ((1, 0), (2, 0))),
                            0)

        cyclic = GraphSpec(("e", "g", "g"),
                           ("ROOT",),
                           ((("F", "ROOT"), (0, 0)),
                            ((1, 0), (2, 1)),
                            ((2, 0), (1, 1)),
                            ((1, 2), (2, 2))),
                           0)

        for component in (active, private, cyclic):
            result = assess_capsule(component)
            self.assertEqual(result["status"], "unsupported")
            self.assertIsInstance(result["reason"], str)
            self.assertTrue(result["reason"])
            with self.assertRaises(ValueError):
                build_capsule(component)

    def test_strict_preconditions_reject_bad_width_and_bindings(self):
        component = self.components["box_AB"]
        capsule = build_capsule(component)
        net = Net()
        ports = _consumers(net, capsule.interface)
        ready = net.cell("e")
        root = capsule.code.open_root(net)
        with self.assertRaises(ValueError):
            build_activation(net, capsule.width + 1, root, ports, (ready, 0))
        with self.assertRaises(TypeError):
            build_activation(net, capsule.width, root, list(ports), (ready, 0))
        with self.assertRaises(ValueError):
            build_activation(net, capsule.width, root, (ready, *ports), (ready, 0))
        one = Net()
        loop = value_spec("A", True).open_root(one)
        metadata = build_unpack(one, 1, loop, (), one.boundary("STATUS"))
        self.assertIsNone(metadata["unpack_head"])
        reference = Net()
        value_spec("A", True).instantiate(reference, {"ROOT": reference.boundary("STATUS")})
        self.assertTrue(full_match(one, reference))


if __name__ == "__main__":
    unittest.main()
