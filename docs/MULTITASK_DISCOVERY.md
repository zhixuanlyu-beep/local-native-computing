# Discovery from multiple observation contracts

M4 introduces `E_multitask-v1`. It searches literal primitive IC graphs against distinct finite observation contracts, then composes selected search products into prewired native programs. [Claim ledger §U](CLAIM_LEDGER.md#u-multiple-observation-contracts-and-discovered-composition-e_multitask) is the sole record of measured coverage, candidate counts, costs, fingerprints, and acceptance results. The [M3 arguments](COMPOSITION_LEMMAS.md) supply the abstract-model composition basis; experiments and implementation assumptions remain separate.

## Fixed prior and contracts

The prior is fixed before acceptance: `ic_component_candidates.py` enumerates every complete port matching for each ordered cell-kind tuple within the declared bounds. It keeps disconnected components, internal active pairs, principal cycles, and boundary wires. It performs no semantic screening, success-dependent rewiring, or isomorphism deduplication. Detached pure wire cycles are absent from the input syntax; runtime wire cycles are fully retained. The complete ordered inventory is fingerprinted.

Representation A uses epsilon for false and the gamma auxiliary self-wire Loop for true. Representation B is the ordered package `gamma(epsilon,A)`: its first auxiliary holds epsilon and its second holds the A value. Both are finite sets of delta-free principal packages. The contracts include every binary Boolean function on A, every unary Boolean function for every ordered A/B representation pair, and copying and erasure on each representation. Truth-table bit order and graph interfaces are explicit in `ic_observation_contracts.py`. A contract is a full graph postcondition, not just a scalar result or node count.

Candidate size bounds depend on the declared interface family. They are recorded in the contract and ledger, and are not increased or narrowed after observing results. Missing solutions are an allowed research outcome. They say only that the frozen syntax and resource contract yielded no verified candidate; they do not establish that an IC function is impossible. General task semantics, arbitrary representations, and unbounded component synthesis remain separate goals.

## Search accounting and verification

The first all-false input is the fixed weak observation. Remaining truth-table inputs refine that same contract. Native observation depends on a candidate, input representation, and supplied values, so a recorded execution can be compared against different output contracts without rerunning the same network. The report explicitly distinguishes shared native observations from candidate/contract assignments.

Every literal candidate has an entry for every relevant contract. A concrete wrong complete normal form or material violation rejects that assignment with a trace interval, independent expected graph, and links to its entire initial and actual graph. A step budget exhaustion is incomplete. A candidate compatible with the whole FIFO input table is explored over every active-pair choice on those elementary instances. Verification requires complete acyclic exploration and the correct entire graph at every terminal state. Exploration limits remain incomplete; they never become verified components or finite-absence certificates.

Reports bind the representation graphs, masks, interface grammar, ordered candidate inventory, primitive rules, policies, budgets, compiler code, and frozen discovery/bridge/activation/composition reports. Every saved raw trace can be reconstructed and replayed. Full verification repeats the search and reference checks, including counterexamples and all-schedule exploration, and compares every report field. The original environments and archives are unchanged.

## Composition of discovered graphs

Library selection is deterministic: the lowest literal fingerprint among verified candidates for each required contract. Every verified B eraser is retained as a separate small-program variant. Selection does not optimize cost or hand-rewrite a candidate into an anticipated successful gate. The builder checks that a candidate fingerprint binds its exact graph and that the role's representation, interface, and truth mask agree with its contract.

The fixed DAG copies input `a`, computes `a AND b` and `a AND c`, combines those results with AND, adapts A to B, copies B, erases one copy, and adapts the other back to A. It must produce `a AND b AND c`. Every connection consumes one produced value; sharing requires an explicit discovered copier and disposal requires an explicit eraser. Representation mismatches, missing ports, repeated consumers, and forward/cyclic dependencies are rejected before native execution.

All component instances and inputs are preallocated. Builders encode the supplied bits and wire the fixed graph; they never call truth-table evaluation to choose an output or wiring. A joint execution repeatedly selects an active pair under its declared policy and calls the original IC reducer. It does not interpret DAG stages, inspect a partial result, reset state, or reconstruct a network.

The compiler-facing extension connects the computed A result to the first frozen M1 gate, the real compiler-generated `!Gamma`, and a native copy/decode consumer. The reference is independently constructed from the original Gamma object. Original code-cell consumption and the entire terminal output graph are checked. This is program-code consumer composition, not a new theorem about feedback-program activation or disabled-source-extension semantics.

## Why the local evidence composes

Each selected component has an actual primitive trace for every finite input tuple, ending in exactly its declared output packages. For the staged verifier, match those input packages at the current DAG edges and map the candidate's literal cells to its original preallocated instance. Validate every kind, ordered port, wire, interface binding, and distinct cell footprint. Then translate the recorded local pairs through that embedding, extending the map to each fresh primitive allocation and deleting consumed names.

Only the mapped interior is reduced. The verifier checks constant exterior cell count, unchanged exterior cells and non-interface wiring, the complete local result, disjoint output packages, and fresh-allocation counts and kinds. This is an actual primitive trace of the one prewired global graph. It concretely instantiates the M3 contextual-lifting argument and supplies an explicit normalizing witness for the declared DAG. It is a verification schedule, not the runtime controller.

For the compiler-facing graph, first lift the whole small-DAG witness through the prewired M1 body. An exact boundary-forced map must then identify the entire resulting graph with an independently built M1 ready-input instance. Lift that instance's native witness to completion. This checks the intermediate gluing boundary rather than inferring composition merely from matching final Boolean values.

Independent FIFO, LIFO, and portable seeded joint runs are compared with those staged witnesses. Their total interaction counts and primitive-rule censuses must equal the sum of the contributing local certificates. The staged peak is obtained from constant exterior size plus each local peak. Other interleavings can have different peaks, so joint runs use their own exact allocation/census ledgers and conservative positive-growth bound. Every future component and the real code consumer is included in the initial and live-cell counts.

The abstract strict-diamond and uniform-normalization arguments remain conditional on faithful implementation, as explained in M3. Elementary all-schedule exploration is concrete finite evidence. Larger composed networks have the recorded staged witnesses and selected-policy runs; no exhaustive large-network schedule search or arbitrary-context observational equivalence is claimed.

## Boundaries and reproduction

The archive preserves refutations of weak-observation generalization and cross-representation reuse. A B eraser can eliminate every cell of an A input while leaving a closed wire cycle, which violates erasure to the empty graph. Representation and interface evidence must therefore accompany an archived component. This is preparation for the structure-library work, not a general library, a physical reset, or a demonstrated reuse benefit.

```sh
python tests/component_candidates_integrity.py
python tests/observation_contracts_integrity.py
python tests/discovered_programs_integrity.py
python tests/component_witnesses_integrity.py
python tests/multitask_discovery_integrity.py
python ic_multitask_discovery.py --report results/multitask_discovery.json.gz --trace results/multitask_discovery.ictrace.gz
python ic_multitask_discovery.py --verify-report results/multitask_discovery.json.gz --trace results/multitask_discovery.ictrace.gz
```

Symbolic native interactions and cells are measured separately from search, construction, exploration, source/reference evaluation, readout, and proof replay on the host. There is no common-cost rebuilding/copying/reuse comparison yet. M5 retains that obligation, along with representation/interface/evidence-indexed retrieval and the possibility that reuse has no net benefit.
