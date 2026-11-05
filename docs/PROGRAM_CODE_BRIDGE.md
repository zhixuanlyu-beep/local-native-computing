# Program-code bridge and the E_code environment

This guide describes the first bridge between two previously separate results: the retained/erased gates found by bounded semantic synthesis, and the literal program code produced by the unified source-to-IC compiler. The detailed counts and measured resources are recorded only in [claim ledger §R](CLAIM_LEDGER.md#r-program-code-bridge-e_code); this page states the contract, construction and verification procedure without repeating those totals.

The bridge answers a narrow question: can the discovered gates control a real compiler artifact, specifically the delta-free !Gamma program package, so that native IC consumers copy, retain, erase, or decode it? It does not activate a complete feedback program, represent a disabled program, or implement continuous reuse in one network.

## Frozen inputs and the E_code contract

[ic_program_code_bridge.py](../ic_program_code_bridge.py) imports every gate/carrier pair marked verified in the frozen bounded-discovery report. It checks the file digest, report graph fingerprints, candidate accounting, and survivor list before constructing anything. The frozen report itself is not edited or widened; the bridge reads its saved syntax.

The new environment is named E_code-v1. It extends the earlier Boolean/payload contract with four delta-free principal package codes:

- epsilon;
- gamma(epsilon,epsilon);
- delta(epsilon,epsilon);
- the compiler-generated real Gamma program code.

Each payload has two independently recorded forms: the original rooted object and its literal delta-cut code. The compiler supplies both forms for Gamma; the other objects use the same package encoder.

Four consumers are prewired at construction time. Their expected result is defined independently from the actual run:

| Consumer | True input | False input | Boundaries |
|---|---|---|---|
| retain_code | the original code | one epsilon | OUT |
| copy_code | two copies of the code | two epsilons | OUT1, OUT2 |
| decode | the original object | one epsilon | OUT |
| copy_decode | two original objects | two epsilons | OUT1, OUT2 |

The reference graph is built from the original object before execution. Verification compares the complete labeled port graph, including every component, boundary label, and cyclic-wire count. Matching only a decoded value or a node count is not accepted.

## Construction and execution boundary

build_bridge(gate, carrier, bit, code_spec, consumer) returns the initial network and the IDs of the payload cells allocated by the code. The builder prewires the imported gate syntax, control token, payload, and consumer; it never consults an expected output or task result. Malformed interfaces, non-package data, active payloads, or an unknown consumer are rejected before execution.

At runtime, the bridge uses only the existing primitive IC reducer. Large networks use deterministic FIFO scheduling under the declared per-case interaction and live-cell bounds. A budget exhaustion is recorded as incomplete evidence, not as termination, divergence, or a successful case.

Small networks built from the epsilon and delta-object codes are additionally explored over every enabled active-pair choice. A passing exploration requires a complete acyclic reachable quotient and the independently built reference graph at every terminal state. This contract checks the real !Gamma network only under FIFO; it does not attempt exhaustive schedule exploration. For that network, the archived evidence is the recorded FIFO run and replay.

## Trace binding and verification

Generation and verification use the repository's existing gzip trace format: a JSON header followed by little-endian 32-bit cell-ID pairs. The header binds the exact bridge, discovery, payload, and consumer syntax by digest. The report records each case's trace interval, initial size, interaction count, peak live-cell count, final size, cyclic-wire count, and full final graph.

Full verification reconstructs every initial graph from the frozen report and code. It then replays every pair in trace order, requiring each recorded pair to be the next actual FIFO redex. It independently reproduces archived products, rebuilds all-schedule summaries, and compares every report field with the reconstructed result. Any mismatch, trailing trace record, or tampered binding rejects the report.

Generate and verify the archived evidence with:

```sh
python ic_program_code_bridge.py --report results/program_code_bridge.json.gz --trace results/program_code_bridge.ictrace.gz
python ic_program_code_bridge.py --verify-report results/program_code_bridge.json.gz --trace results/program_code_bridge.ictrace.gz
```

The generation command exits nonzero if a case fails, exhausts its budget, or leaves an unexpected terminal state; the report still preserves the concrete failure graph and trace.

## Offline artifact reuse

For each verified gate/carrier pair and each first Boolean input, a native copy_code run archives the program-code product at OUT1. The archive records the literal graph, producer trace interval, input bindings, interface, cost, and evidence scope.

Each archive is then reconstructed as a fresh specimen and used with a new Boolean input and a decode or copy_decode consumer. The combined resource account includes both the retained producer network and the fresh instance. Verification checks that the two native copy products are disjoint, that the original payload cells were consumed by the copy, and that the retained producer graph is unchanged by later reconstruction.

Export and reconstruction are offline research tools. This is not continuous native reuse inside one network, a physical reset, or a new IC rewrite rule.

## Deliberate negative probes

The report retains four boundary checks. An epsilon supplied directly to the package decoder still decodes to epsilon. A wrong control token and a CTRL/DATA-swapped gate wiring each produce a concrete wrong normal form. Finally, epsilon supplied to the code input of an INIT source-symbol extension leaves a substantial residual graph rather than erasing the entire extension. This last witness preserves the required semantic boundary: D(epsilon)=epsilon does not imply that epsilon at a source-symbol code port clears the extension.

## From M1 to later milestones

M1 establishes this program-code bridge and its replayable evidence. Later milestones remain open:

- M2, safe activation and continuous tasks: activate a complete program, represent disabled state explicitly, and define full terminal state conventions.
- M3, compositional correctness and resources: prove macro, decode, source-rule replacement, and readout composition lemmas for larger programs, supported by finite typed programs and explicit resource arguments.
- M4, multi-task constraint discovery: discover composable components from distinct observation contracts, including Boolean combinations, copying/erasing, and representation adapters.
- M5, structure library and benefit evaluation: index retained structures by representation, interface, and evidence scope, then compare rebuilding, native copying, and reuse under one cost model.

The bridge does not claim arbitrary-context equivalence, all-schedule behavior for the full !Gamma network, physical inventory, or general semantic synthesis.
