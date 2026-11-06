# Result-controlled native whole-program execution

M6 connects complete compiled feedback tasks using their actual results. The
first task is enabled. An enabled SQ result enables the next task; BR disables
it. A skipped task produces epsilon and its native continuation restores the
next task to enabled. Numerical inputs and every continuation are prewired.
Result numerals do not yet become subsequent task inputs.

The implementation is [ic_result_controlled_execution.py](../ic_result_controlled_execution.py).
Measured acceptance results and archive fingerprints belong exclusively to
[the claim ledger](CLAIM_LEDGER.md#w-result-controlled-complete-programs-e_result_controlled).
The frozen finite matrix and budgets are in
[M6_ACCEPTANCE_MATRIX.json](M6_ACCEPTANCE_MATRIX.json). The public constructor
accepts `build_result_sequence(numbers, *, library, compiler=None, reader_depth=5)`;
it has no per-task flag argument and does not evaluate expected results.

A control packet is a principal M3 frame containing an A Boolean, a native
two-choice selector principal and its output. The result reader's SQ and BR
handlers contain both possible controls. Its bounded unary reader recognizes
all original unary constructors, including both BR arguments, before releasing
an M2 progress packet containing readiness and the next control. Selecting the
skip progress packet restores true without evaluating the suspended program.
Incoming GO guards program delivery and continuation. Program code, readiness
and control pass through the single prewired primitive graph.

The component source is the actual retained M5 `copy_A` storage packet, with
its original typed contract, representation, producer interval and evidence
tier preserved. The network produces a fresh native packet copy, erases the
other product, distributes encoded component copies, decodes each and uses the
actual component to copy the incoming A Boolean into STATUS and enable control.
The final code reserve is retained at CONTROL_LIBRARY. A separate initial
compiler `code_spec` supplies the complete programs and is carried natively to
LIBRARY. The M5 Gamma erasure artifact is data and cannot supply this program
code interface.

Capsule extraction READY and recognition of the original source result are
distinct events. The former establishes that the component frame has been
unpacked. Only the latter authorizes an enabled task's handoff. Reconstruction
and erasure may overlap later work; neither event asserts whole-net quiescence.
Final acceptance compares every labeled output, status, NEXT_ENABLE, retained
program and component code, DONE, all cells, components and cyclic wires against
an independently constructed source reference.

Large archives use a gzip JSON manifest at the supplied trace path and gzip
sibling shards containing the original pair records. The report binds the
manifest digest; each part binds its metadata, record count, raw digest and
compressed-file digest. This is lossless storage of the same primitive stream,
not trace sampling.

Local contracts are independently executed with each admitted test number and
either incoming Boolean. The composition certificate maps their actual stage
cells and ports into the complete prewired graph, checks the supplied graphs,
and lifts every primitive pair with fresh-node renaming. Context interactions
are deferred during that certificate. Separate FIFO, LIFO and fixed seeded
runs select their own primitive interactions and do not use the staged witness.
All future tasks, readers, inputs, native suppliers, reserves and cleanup are
included in whole-network resource accounting. Exact rule censuses and primitive
kind balances are checked; costs are evidence, not a profitability criterion.

Generate and independently reconstruct/replay the entire archive:

```sh
python ic_result_controlled_execution.py --report results/result_controlled_execution.json.gz --library results/structure_library.json.gz --trace results/result_controlled_execution.ictrace.gz
python ic_result_controlled_execution.py --verify-report results/result_controlled_execution.json.gz --library results/structure_library.json.gz --trace results/result_controlled_execution.ictrace.gz
```

The report binds the contract, matrix, compiler code, library provenance,
schedule, initial graph, raw trace intervals, resource balances, events and
whole-terminal graph digest. Passing terminals are reconstructed in full at
verification; counterexamples retain complete initial/reference/actual graphs.
Verification rebuilds the networks, replays every pair,
compares every report field and rejects unconsumed trailing records. Exhausted
budgets remain incomplete; incorrect terminal graphs remain counterexamples.
The enabled-input-1 readiness fault deliberately keeps the correct final graph
while violating the handoff protocol.

Independent case groups may run in local worker processes. Their complete raw
pair streams are assembled in the fixed case order, with every nested interval
translated to its global offset. Verification splits those intervals, replays
each primitive interaction and checks both per-group and whole-stream EOF.
Host worker ordering never selects interactions inside an IC network and is
not a native resource saving.

This is finite implementation evidence and a local interface composition
certificate, conditional on the existing abstract IC model. It does not prove
arbitrary contextual equivalence, physical finite stock or universal reuse
benefit. The next connection is result numerals as subsequent inputs, followed
by broader representation adaptation/discovery and a renewed cost comparison
under that complete computation contract.
