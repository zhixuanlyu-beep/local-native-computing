# Evidence-indexed structure library and native reuse

M5 introduces `E_structure_library-v1`. It freezes the verified M4 structure assignments into an immutable evidence-indexed catalog, assesses which exact graphs can be stored as native capsules, and compares rebuilding, native distribution, and retained-code execution under one declared cost contract. [Claim ledger V](CLAIM_LEDGER.md#v-evidence-indexed-structure-library-and-native-reuse-e_structure_library) records measured counts, costs, Pareto outcomes, archived acceptance, and verification.

## Exact catalog and retrieval

Each M5 library entry binds one exact graph, one task contract, one ordered interface, and one evidence scope. The required input and output representation tuples and interface are matched exactly. A task name can narrow a search, and the minimum evidence tier is `fifo` or `all-schedules-finite` in that declared order. A graph size, task label, or scalar truth-table match never implies applicability, and no missing or wrong interface is silently adapted, including between representations A and B.

The catalog preserves every verified M4 graph/contract/evidence assignment. Separate contracts remain separate entries even when they use the same graph, and an entry is not inferred from arbitrary contexts, all inputs beyond its declared domain, or raw copyability. Each source case records its initial and final graph fingerprints, raw trace interval, pair digest, resource record, and schedule-proof summary references. The catalog binding names the frozen report and trace and their digests; construction rejects a changed report, and verification rebuilds the catalog, compares all canonical fields, and replays the union of referenced local traces under actual FIFO scheduling and resource accounting.

Capsule eligibility is also evidence-scoped and retained in full. A distinct unsupported assessment is a durable result, not a hidden filter. Native eligibility requires the unchanged original graph in an ordered gamma frame and a full principal-package validation before encoding. The READY marker in slot zero is a gamma Loop.

## Native packet storage

The stored representation is `native-code-grant-packet-v1`. Its value is:

```text
gamma(encoded interface capsule, GO Loop)
```

The packet is produced by native copying of the encoded source and erasure of one branch. It stores an interface, not a running continuation and not a guarantee that all future work has completed.

READY is emitted when frame extraction is possible. It marks readiness of that frame only. It does not mark task completion, global quiescence, absence of remaining cleanup, or correctness of later decoding and component execution.

Every future task in a benchmark is prewired before execution. The runtime cannot inspect a partial result and choose a later consumer, reset the network, or reconstruct a graph on the host. It applies only the original primitive IC rules under the declared scheduler.

## Strategies and cost fairness

All strategies share one fresh native source production and the same workload, ordered input tuples, task count, reserve disposition, and scheduler. The strategy set is:

| Strategy | Native arrangement |
|---|---|
| `literal` | Reconstructs the same already-known exact capsule syntax independently for each task; the produced source code is retained or disposed according to the disposition. |
| `native_fanout` | Balanced delta distribution from the produced source to all tasks and the reserve. |
| `retained_chain` | A reservoir passes each native grant onward after copying it to the task and the next stage. |

The source-code reserve dispositions are `retain1`, which leaves exactly one encoded capsule code without the GO wrapper, and `dispose_all`, which applies explicit native erasure so no reserve remains. The target comparison requires all independent task outputs, every STATUS Loop, the declared reserve state, and no other cells or wire cycles.

Cost fairness is explicit. The literal baseline does not rediscover a component and does not rerun the source compiler per task. All strategies share frozen-library acquisition: the earlier M4 discovery and source-validation costs remain frozen provenance rather than rerun charges. Host extraction, verification, index/query, packaging, and replay counts are separate deterministic host work. The offline archive producer is a separately charged native episode; each actual benchmark imports the exact value syntax and then performs its own fresh whole native production and cleanup inside the prewired network. This is not reuse of the original archive network and not same-network reuse of the original producer.

The declared resource vectors include the whole initial network, primitive right-hand-side allocations by cell kind, primitive interaction count and rule census, peak live cells, retained/product cells, and explicit eraser lineage. A run can therefore expose reuse with no net benefit: the comparison reports Pareto fronts and allows a strategy to be dominated or equal on the declared dimensions.

Host-side work is recorded through separate acquisition, query and packaging stage counts and prior-evidence replay resources. These counts do not measure every Python operation or traversal, host byte memory, or wall-clock prices. Retrieval uses linear exact filters; no asymptotic lookup speedup is claimed.

## Conditional native census derivation

The following arithmetic is a conditional derivation from the fixed package shapes; it is not proof by running a test. For a proper principal package with `n` cells and arity sum `A`, the number of auxiliary-to-auxiliary wires is:

```text
w = (A - n + 1) / 2
```

For delta-free data, the native copy census is:

```text
gd = #g
de = #e
dd = w
```

The native erase census is:

```text
ge = #g
de = #d
ee = #e + w
```

For code encoding an original interface capsule with `d` delta cells, the decoder census is conditional:

```text
d = 0: gg = 3, de = 1, ee = 2
d > 0: gg = 2(d - 1) + 3, gd = d - 1
```

The whole source packet is charged once for common copy plus erase. Exact grant/frame/READY/task construction and each subsequent native task execution are charged separately. Each native use of an encoded capsule adds copy of the capsule code plus its conditional decoder census. Reserve disposal adds erase of the capsule code.

Counting principal-parent wires gives the wire equation above. Copying commutes with each gamma, erases each epsilon at a delta, and cancels the remaining paired delta fronts at auxiliary wires; erasure similarly visits each original cell and cancels the epsilon fronts. The decoder counts use the fixed codec frame and its restoration of the removed deltas, under the proper-package hypotheses of the existing composition arguments. These abstract counts require a faithful primitive implementation; each archived execution independently checks them.

These formulas explain why equal interaction and rule censuses do not imply equal peak allocation: eager and retained arrangements can perform the same primitive work while retaining cells for different intervals. They also identify the explicit eraser-ancestry union as a subset of total cleanup, not as all primitive work. Every primitive interaction remains charged within the declared run.

## Evidence boundaries

The common production fixture is part of the declared protocol for every strategy. The literal baseline is not claimed to be an optimal rebuilder among all possible protocols. The FIFO, LIFO, and seeded schedules provide finite, policy-specific evidence. They do not establish all-schedule behavior, a universal reuse benefit, optimality, arbitrary-context replacement, a continuous native workspace, or physical inventory. Source all-schedule proofs are finite and tied to their elementary M4 observations; they do not transfer automatically to capsule production, activation, or composed execution.

Offline archive capture and import precede the benchmarks. An archived packet is not an arbitrary-context continuation. Reuse must satisfy the exact representation, interface, and evidence conditions recorded with it.

## Reproduction

```sh
python tests/structure_library_integrity.py
python tests/structure_capsules_integrity.py
python tests/reuse_benchmarks_integrity.py
python tests/structure_reuse_integrity.py
python ic_structure_reuse.py --report results/structure_reuse.json.gz --library results/structure_library.json.gz --trace results/structure_reuse.ictrace.gz
python ic_structure_reuse.py --verify-report results/structure_reuse.json.gz --library results/structure_library.json.gz --trace results/structure_reuse.ictrace.gz
```

The library test checks strict schemas, fingerprints, nested immutability, source report/trace mutations, exact queries, evidence-tier escalation, and full FIFO replay. The reuse verifier independently reconstructs the library and report and replays the native production and benchmark traces. A generation or verification failure exits nonzero and preserves the concrete failure evidence. Measured dimensions, workloads, and outcomes are recorded only in [claim ledger V](CLAIM_LEDGER.md#v-evidence-indexed-structure-library-and-native-reuse-e_structure_library), together with remaining proof and resource boundaries.

[M6](RESULT_CONTROLLED_EXECUTION.md) loads the actual archived `copy_A` packet
and uses its decoded component in result-controlled whole-program continuations.
The M5 Gamma erasure entry retains its data-only interface and cannot stand in
for the compiler's `!Gamma` program code. Later evidence and cost accounting are
separate in [ledger W](CLAIM_LEDGER.md#w-result-controlled-complete-programs-e_result_controlled).
