"""Native A/selector control packets and original-result-gated progress."""
from ic_native_result_reader import Reader, build_reader
from ic_primitive_port_verifier import Net
from ic_program_suspension import append_spec
from ic_research_artifacts import GraphSpec
from lafont_ic_macro_builder import build_M, build_selector, build_M_star, build_menu, macro_connect


def _loop(net):
    cell = net.cell("g")
    net.link((cell, 1), (cell, 2))
    return cell, 0


def _frame(net, ports):
    packet = build_M(net, len(ports))
    for leaf, port in zip(packet.auxiliaries, ports):
        macro_connect(net, leaf, port)
    return packet.principal


def control_packet(bit):
    if type(bit) is not bool:
        raise ValueError("control packet requires an exact Boolean")
    net = Net()
    selector = build_selector(net, 2, 1 if bit else 2)
    root = _frame(net, [_loop(net) if bit else (net.cell("e"), 0),
                        selector.principal, selector.auxiliaries[0]])
    macro_connect(net, root, net.boundary("ROOT"))
    net.check()
    return GraphSpec.from_net(net)


def validate_control_packet(spec):
    """Offline representation precondition, never a runtime branch oracle."""
    from ic_coherent_output_decoder import port_graph_isomorphic
    if not isinstance(spec, GraphSpec) or spec.boundaries != ("ROOT",):
        raise ValueError("control requires a rooted A/selector three-slot packet")
    if not any(port_graph_isomorphic(spec.instantiate(), control_packet(bit).instantiate())
               for bit in (False, True)):
        raise ValueError("control packet has an inconsistent A/selector encoding")
    return spec


def build_control_reader(net, compiler, gate, depth, *, value_out, ready_out):
    gates, progress_frames, packets, by_symbol, ready_tokens = [], [], {}, {}, {}

    def progress(symbol, output):
        bit = symbol == "SQ"
        packet = control_packet(bit)
        packets[symbol] = packet.to_dict()
        ready_token = _loop(net)
        ready_tokens[symbol] = ready_token[0]
        root = _frame(net, [ready_token, packet.open_root(net)])
        progress_frames.append(root[0])
        serial = len(gates)
        ready = net.boundary(f"control-reader-{output[0]}-{serial}")
        before = set(net.nodes)
        append_spec(gate, net, {"CTRL": ready, "DATA": root, "OUT": output})
        added = [c for c in net.nodes if c not in before]
        gates.extend(added)
        by_symbol[symbol] = added[0]
        return ready

    reader = build_reader(net, compiler, gate, depth, value_out=value_out,
                          ready_out=ready_out, result_progress=progress)
    metadata = {**reader.metadata, "kind": "control", "control_depth": depth,
                "control_packets": packets, "progress_frames": progress_frames,
                "result_completion_gates": gates,
                "result_completion_by_symbol": by_symbol,
                "progress_ready_tokens": ready_tokens,
                "result_completion_kinds": "gg"}
    return Reader(reader.principal, metadata)


def protocol_network(bit, payload):
    """Test both the A and selector views against independent payloads."""
    net = Net()
    packet = control_packet(bit).open_root(net)
    unpack = build_M_star(net, 3)
    macro_connect(net, packet, unpack.principal)
    macro_connect(net, unpack.auxiliaries[0], net.boundary("A"))
    menu = build_menu(net, [payload.open_root(net), (net.cell("e"), 0)])
    macro_connect(net, unpack.auxiliaries[1], menu.principal)
    macro_connect(net, unpack.auxiliaries[2], net.boundary("OUT"))
    net.check()
    return net


def protocol_evidence(trace):
    from ic_bounded_execution import explore
    from ic_coherent_feedback import spec_digest
    from ic_coherent_output_decoder import port_graph_isomorphic
    from ic_observation_contracts import value_spec
    from ic_schedule_audit import ScheduledNet, Schedule
    payloads = {"epsilon": value_spec("A", False), "Loop": value_spec("A", True),
                "B_false": value_spec("B", False), "B_true": value_spec("B", True)}
    records = []
    for bit in (False, True):
        for name, payload in payloads.items():
            initial = protocol_network(bit, payload)
            target = Net()
            value_spec("A", bit).instantiate(target, {"ROOT": target.boundary("A")})
            (payload if bit else value_spec("A", False)).instantiate(target, {"ROOT": target.boundary("OUT")})
            exploration = explore(initial, max_states=4096, max_transitions=32768, max_cells=128)
            all_match = all(port_graph_isomorphic(exploration.states[i], target) for i in exploration.terminal_ids)
            running = GraphSpec.from_net(initial).instantiate(ScheduledNet(Schedule()))
            offset = trace.count
            while running.active():
                pair = running.next_active()
                trace.record(pair)
                running.reduce(*pair)
            passed = exploration.complete and not exploration.cycle and all_match and bool(exploration.terminal_ids)
            records.append({"bit": bit, "payload": name, "status": "passed" if passed else "not-accepted",
                            "initial": GraphSpec.from_net(initial).to_dict(),
                            "expected": GraphSpec.from_net(target).to_dict(),
                            "initial_graph_sha256": spec_digest(GraphSpec.from_net(initial).to_dict()),
                            "trace_offset_records": offset, "primitive_interactions": trace.count - offset,
                            "exploration": exploration.summary(), "all_terminal_graphs_match": all_match,
                            "resources": running.statistics(), "final": GraphSpec.from_net(running).to_dict()})
    return records
