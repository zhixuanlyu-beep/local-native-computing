# Safe program activation and prewired task continuations

This guide defines the M2 environment `E_activation-v1`. It composes the compiler's bare source-symbol extensions, the frozen retain/erase gates from M1, the real `!Gamma` package, and the primitive IC reducer. Concrete test counts, interaction totals, peaks, digests, and other measured resources are recorded only in [claim ledger §S](CLAIM_LEDGER.md#s-safe-program-activation-e_activation); this page gives the contract and interface without repeating those totals.

## Contract

The builder constants MAX_INPUT, MAX_TASKS, and UNARY_DEPTH declare representation and grammar bounds. Their values and the exact finite case list are recorded in [claim ledger §S](CLAIM_LEDGER.md#s-safe-program-activation-e_activation).

A task begins as a **suspended bare feedback program**. Each source symbol is instantiated through `compiler._extension`; it does not contain an embedded copy of `!Gamma`. The initial principal cut ends, the program output, and every bare-extension code input are collected as the leaves of one principal package, which is then encoded as a delta-free code package. At activation the decoder restores the package, `M*` reconnects the initial cut and output, and `C_n` distributes native copies of the shared program code to all bare extensions.

Exactly one literal `!Gamma` package is supplied to the complete prewired network. Native delta copying supplies the current stage and carries one copy forward in the continuation packet. No additional literal `!Gamma` is allocated during runtime; the task-specific bare capsules and continuation wiring are preallocated during construction.

Each enable flag is represented twice: by the frozen gate's Loop/epsilon carrier, and by an `S_2` selector that selects between reader readiness and a constant skip token. This is an input representation, not a precomputed task answer.

### Enabled task

The flag gate retains the suspension and the GO gate delivers it only after the incoming continuation packet is unpacked. Activation restores the full feedback program and supplies all code inputs from the shared `!Gamma`. `TASK_i_OUT` must contain the independently compiled source result (`SQ(n)` or `BR(n,n+1)`), and `STATUS_i` must contain a Loop.

A bounded native reader observes the original result. It dispatches on the compiled `SQ`/`BR` constructors, rebuilds the corresponding source header through a bare extension supplied with original stored code, and recursively recognizes unary `Z`/`S` up to the declared depth. `Z` emits a Loop readiness token; `BR` joins readiness of both arguments with the discovered gate. Readiness is therefore **local recognition of all original result constructors**, not global completion of unrelated reconstruction or cleanup.

### Disabled task

The flag gate erases the suspension. `TASK_i_OUT` and `STATUS_i` are each one epsilon. The incoming GO token is still consumed. The readiness selector chooses the constant skip token, and the GO gate forwards the continuation packet to the next task. A disabled stage is a skip-and-continue stage, not a halt of the whole sequence and not an attempt to erase the source extension merely because `D(epsilon)=epsilon`.

### Continuation and final state

Every future task and its capsule is prewired before execution. The next stage can consume its continuation packet only after the current stage's GO gate advances that packet. For an enabled stage this requires the native reader's readiness token; for a disabled stage it requires the constant skip token. Runtime executes one network under the original primitive IC rules with FIFO scheduling. The host does not rebuild the net, inspect a result to choose a transition, reset state, or call a source evaluator.

The terminal graph must match an independently constructed complete labeled port graph: every task output and status, the exact retained `!Gamma` at `LIBRARY`, `DONE` as a Loop, no extra components, and no cyclic wires. `port_graph_isomorphic` performs the whole-graph comparison.

## Bounded reader and overlap boundary

The reader's constructor grammar is deliberately finite: result heads `SQ`/`BR` and unary `Z`/`S` up to `UNARY_DEPTH`. It is a representation bound and a construction precondition.

Local readiness means every original result constructor has been recognized: an enabled `SQ` requires its nested unary terminal, and an enabled `BR` requires both argument terminals plus the gate join. Once readiness permits continuation, later native reconstruction and cleanup may overlap execution of subsequent stages. This is an explicitly weaker boundary than global quiescence; it is not a claim that every detached component has already disappeared.

## Native event checks

Generation watches the actual primitive pairs that consume each stage's incoming packet, delivery gate, and advance gate. It records their FIFO step, pair identities, and cell kinds. For accepted enabled cases it requires:

- the incoming packet is consumed by that stage's unpacker;
- grant precedes delivery and advance;
- delivery precedes advance;
- the reader's terminal-Z readiness emitter participates in the advance;
- every required BR argument join is a separate earlier gamma/gamma event and occurs before advance.

For accepted disabled cases it requires the constant skip token to participate in advance. These are native-event certificates beyond whole-graph output matching.

## Verification and replay

Generation and verification use the existing gzip trace format: a JSON metadata header followed by little-endian 32-bit cell-ID pairs. The header binds the contract, frozen M1 discovery/report, exact program and suspension syntax, and case list by digest. The report records each case's trace interval, initial graph digest and size, primitive interaction count, peak live cells, final graph, protocol events, retained program capture, and any counterexample.

Full verification rebuilds every initial graph from the frozen bindings, replays each recorded pair in FIFO order, and requires it to be the next actual redex. It independently rebuilds references, checks every report field, rejects trailing or truncated trace records, and preserves concrete wrong/cutoff cases rather than treating them as success.

Generate and verify with:

```sh
python ic_safe_program_activation.py --report results/safe_program_activation.json.gz --trace results/safe_program_activation.ictrace.gz
python ic_safe_program_activation.py --verify-report results/safe_program_activation.json.gz --trace results/safe_program_activation.ictrace.gz
```

[tests/safe_program_activation_integrity.py](../tests/safe_program_activation_integrity.py) uses a reduced real-input fixture and mutates fields against an actual replay; it also checks raw trace order and truncation. It is not itself the full frozen matrix. CI replays the complete archived matrix separately.

## Negative probes

Two durable probes mark the phase boundary:

- **Insufficient unary depth:** reader depth 0 on enabled input 1. The run must yield a wrong normal form rather than silently accepting or fabricating readiness.
- **Premature ready selector:** an enabled stage is miswired to choose the immediate skip token. The final output graph can still be correct, so verification additionally checks the native protocol events; the case must be rejected as a protocol violation.

These probes are finite witnesses, not a general impossibility claim.

## Scope

This work establishes finite FIFO evidence for safe activation, explicit disabled state, skip-and-continue behavior, one shared native program supply, and prewired native continuations in the recorded cases. It does not claim arbitrary-context equivalence, all-schedule behavior, exhaustive coverage of the representation bounds, optimality, physical inventory, or a demonstrated cost benefit. The earlier M1 offline archive/reuse boundary remains unchanged.
