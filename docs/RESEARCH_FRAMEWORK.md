# Research framework for local native computing

The research question is how a problem's observable meaning can guide the choice of local constraints, so that constrained materials evolve through local interactions into a readable result and useful retained structure. The top-level route is:

**Observation semantics -> local constraints -> constrained materials -> local evolution -> readout and retained structure.**

Here, *materials* means computational building blocks: primitive Interaction Combinator (IC) cells, wires, representations, and component interfaces. A constrained material is a building block together with its admissible states, connections, and interactions. This terminology makes no claim about a finite physical inventory or a material implementation.

This document defines a research agenda and relates it to existing mechanisms. The [claim ledger](CLAIM_LEDGER.md) is the authority for concrete results, test ranges, costs, and source-rule coverage. Definitions below are proposed obligations; linked experiments establish only their recorded scope.

## 1. Two connected lines of work

**Discovering local constraints from problem semantics** starts with information objects and required observations. It asks which representations, interfaces, and local transitions can realize them. Choosing the representation is part of the research. A [bounded IC instance](BOUNDED_IC_INSTANCE.md) now searches a declared finite graph family against a retain/erase observation contract and uses context counterexamples to refine its candidates. Discovery for arbitrary task semantics, general synthesis, and cross-problem cost benefit remain research goals.

**Compiling known source rules into IC** starts with an already specified source interaction system. It asks for a consistent representation of source nodes and ports and primitive IC simulation of their rules in the admitted contexts. The existing source feedback audits, structural encoding, typed operational fragment, and isolated entry certificates support this line; see [ledger A-G](CLAIM_LEDGER.md#a-source-interaction-system) and [ledger N](CLAIM_LEDGER.md#n-typed-isolated-source-entry-rule-certificates-not-coherent-compiler-coverage). They provide mechanisms and validation instances for the broader agenda, without establishing automatic constraint discovery.

The two lines can inform each other. A compiler fragment can supply a candidate building block, and a context counterexample can expose a missing interface constraint. Success in one line does not discharge the other's proof obligations. The [remaining compiler gaps](CLAIM_LEDGER.md#e-not-yet-established) remain open.

## 2. Declare the problem before choosing materials

Every investigation should record these five inputs, plus a separate search budget:

| Input | Required declaration | IC example or current boundary |
| --- | --- | --- |
| Information objects `I` | What distinctions must be represented, including syntax or ordering that matters. | Ordered source snapshots in [ledger F](CLAIM_LEDGER.md#f-lossless-source-net-storage-in-primitive-ic-structural-bridge); unary values or opaque candidate packages in the comparison components. |
| Observable requirements `O` | Permitted observations, successful results, readiness or stability criteria, and failure outcomes. | A signed residual path, rooted truncated differences, and a tagged sum are different output contracts even when they describe the same comparison. See [ledger H-M](CLAIM_LEDGER.md#h-pure-ic-signed-unary-cancellation-observable-before-global-quiescence). |
| Visible and hidden information `V,H` | Which ports, paths, cells, or events an observer may inspect; which details it hides; and the cost of inspection. | A read-only graph traversal can inspect a residual path while ignoring disconnected cleanup. It is not a constant-time local completion marker. |
| Allowed environments `E` | Admissible connections, consumers, source typing, input assumptions, and scheduling or fairness assumptions. | Passive control ports in pruning and prewired copy/erase/unpack consumers in selectors. Source types are extra contract information, not additional primitive IC cell kinds. |
| Resource bounds `B` | Input size, cells, ports, wires, peak live allocation, and any explicit runtime limit, with the stage to which each bound applies. | A finite initial graph does not imply bounded peak allocation for arbitrary IC evolution. Static macro accounting and operational measurements have different scopes. See [ledger D](CLAIM_LEDGER.md#d-conditional-macro-budget). |

The separate **search budget `A`** records the candidate family, generation method, attempted candidates, reduction cutoffs, scheduler policies, seeds, and verification effort. An execution cutoff is not a physical resource bound or a proof of divergence. A search with no solution establishes only failure within that declared search space and budget. The repository does not yet implement a general search from these inputs to IC materials.

Resource bounds must include consumers and adapters when making a composition claim. If a run exceeds a promised bound, record the violation; do not discard it and then claim correctness within the original contract. Any fairness restriction belongs explicitly in `E`. Random scheduler trials alone do not establish all fair executions, and fairness alone supplies no uniform time bound.

## 3. Observation semantics and information closure

### Separate four interfaces

1. **Structural storage and diagnostic decoding.** The ordered source snapshot encoding preserves symbols, port order, boundaries, and wire matching as data. Its structural decoder recovers that snapshot; it does not execute the source program. See [the encoder and decoder](../source_ic_structure_encoding.py) and [ledger F](CLAIM_LEDGER.md#f-lossless-source-net-storage-in-primitive-ic-structural-bridge).
2. **Task observation.** An observer extracts the task result under a declared readout protocol. The [signed comparator](../ic_signed_unary_comparator.py) traverses a stable oriented path. Readability before disconnected cleanup ends is evidence for that protocol, not for a locally emitted sign signal. See [ledger H](CLAIM_LEDGER.md#h-pure-ic-signed-unary-cancellation-observable-before-global-quiescence).
3. **Runtime control signals.** A control token must have the required effect on its actual IC consumer. The [tagged case](../ic_tagged_unary_case.py), [branch pruning](../ic_signed_branch_pruning.py), and [sum selectors](../ic_signed_sum_selector.py) create interactions through fixed wiring. Their execution does not ask a host observer to choose a branch. Token meaning still depends on the consumer contract; see [ledger J-L](CLAIM_LEDGER.md#j-tagged-unary-local-zerosuccessor-discrimination).
4. **Source-program output decoding.** Showing that an entire compiled source program yields its specified result requires an operational simulation and an output representation/decoder. Recovering a stored source snapshot or decoding a component's unary value does not provide that theorem. See [ledger E](CLAIM_LEDGER.md#e-not-yet-established).

The host reducer enumerates active pairs to schedule primitive interactions, and test code may traverse graphs to check results. Those host operations are not extra abilities of IC cells. The [primitive reducer](../ic_primitive_port_verifier.py) implements local active-pair rewrites and interface splicing; performance of its Python implementation is distinct from the modeled interaction count.

### Information closure is a storage-stage obligation

For a declared storage stage, let `Reach_store(i)` contain the complete carrier states reachable from a representation of information object `i` under the allowed storage-only evolution. Require that distinct objects have disjoint reachable sets and that a diagnostic decoder satisfies `d(x)=i` for every `x` in `Reach_store(i)`. Compare states up to irrelevant cell renaming while retaining the declared boundary identities and representation ordering.

The decoder acts on the complete carrier or an explicitly sufficient information interface. A projection onto hidden state alone need not retain the information. Diagnostic decodability also does not require the task observer to expose the object before the task is ready.

For the stored source snapshots, the delta-free reduced package has no internal active pair while its root remains passive. Isolation therefore supports a storage claim; exact round-trip and native copying/erasure evidence are recorded in [ledger F](CLAIM_LEDGER.md#f-lossless-source-net-storage-in-primitive-ic-structural-bridge). This is not a closure theorem under arbitrary attached IC contexts.

Information preservation ends where the declared task permits transformation. Native delta copying intentionally produces copies, and epsilon erasure intentionally destroys a representation. Comparison consumes input structure, and selection erases losing candidates. Each needs its own task correctness contract; none should be rejected by imposing a global conservation law intended only for storage.

## 4. From local constraints to IC evolution

An IC candidate uses gamma, delta, and epsilon cells (abbreviated `g`, `d`, and `e` below), designated principal/auxiliary ports, and well-formed port pairings. An active pair joins principal ports; evolution applies the original primitive rules. Symbol labels, ordered wiring, and valid splicing are mechanical constraints implemented by [the port-graph reducer](../ic_primitive_port_verifier.py); evidence is in [ledger B](CLAIM_LEDGER.md#b-actual-primitive-lafont-ic-experiments).

Additional representation constraints are component contracts: constructor shapes, orientation, sentinel/tag protocols, designated roots, source types, and passive ports. These are distinct from the universal primitive IC rules. A type precondition in a builder or audit is not a runtime type checker in the target graph. A condition such as a reduced opaque package with only its root exposed may require global construction or validation even though later reductions are local.

For each candidate, separate three obligations:

- **Construction legality:** build a well-formed graph satisfying its representation and interface assumptions, with all initial costs declared. Component builders can encode input lengths and allocate candidates; they must not select a result by evaluating the task in the host.
- **Constraint preservation:** show which invariants survive each permitted interaction and which change at a declared phase boundary. Valid port pairing alone does not establish the intended information or control semantics.
- **Task correctness:** relate the local evolution to the required observations, with explicit termination/readiness assumptions and allowed consumers. Independently built expected normal forms and labeled-boundary isomorphism are existing validation methods, not a general contextual-equivalence theorem.

The comparison builders allocate chains from each input independently; selector builders include every candidate before reduction. Their native evolution supplies useful instances of this route, as documented in [ledger H-M](CLAIM_LEDGER.md#h-pure-ic-signed-unary-cancellation-observable-before-global-quiescence). These comparison constraints and wiring are human designed. The newer bounded carrier/gate search supplies a finite automatic instance ([ledger O](CLAIM_LEDGER.md#o-bounded-semantic-synthesis-of-ic-carriers-and-gates)); general derivation from `O` remains open.

## 5. Context and composition contracts

A reusable component record must state its construction method, representation, boundary ports, allowed consumers, preconditions, observer/decoder, maintained invariants, costs, evidence scope, and replacement conditions. The following is an index of existing contracts, not a declaration that all components compose with each other. Detailed evidence and coverage remain in the linked ledger entries.

| Component and representation | Boundary and permitted use | Preconditions, observation, and evidence boundary |
| --- | --- | --- |
| [Structural source storage](../source_ic_structure_encoding.py): ordered gamma/epsilon package | One principal root, attached to a passive boundary or native delta/epsilon consumer. | Valid finite ordered snapshot; reduced package with paired internal wires. Decode the stored source topology, or validate copied data. Storage is not source execution. [F](CLAIM_LEDGER.md#f-lossless-source-net-storage-in-primitive-ic-structural-bridge). |
| [Operational unary fragment](../ic_unary_operational_fragment.py): `Z=e`, `S(x)=g(x,e)`, `DUP=d`, `ERA=e` | Source-rule auxiliary interfaces and rooted unary data in the declared typed fragment; native copy/erase programs. | Source typing distinguishes coincident target encodings. Boundary-labeled target isomorphism and typed-context checks support the restricted refinement. [G](CLAIM_LEDGER.md#g-four-source-rules-operationally-refined-to-primitive-ic). |
| [Signed comparator](../ic_signed_unary_comparator.py): complementary oriented chains with sentinels | Two observation boundaries; the recorded read-only path observer. | Valid chain construction and passive observation. Orientation and residual length encode sign/magnitude; no native consumer contract follows solely from this readout. [H](CLAIM_LEDGER.md#h-pure-ic-signed-unary-cancellation-observable-before-global-quiescence). |
| [Composable differences](../ic_composable_signed_difference.py): paired comparison channels | Two fixed rooted canonical unary outputs, with prewired delta/epsilon consumers. | Independently allocated input chains; verify both truncated differences or copied selected output by topology. Consumer choice is fixed before execution. [I](CLAIM_LEDGER.md#i-composable-signed-difference-with-native-ic-consumers). |
| [Tagged unary case](../ic_tagged_unary_case.py): `Z=e`, `S(x)=g(x,T)`, `T=g(e,e)` | Case emits token and predecessor; separately checked native copying/erasure and unary rule simulations. | Tagged input required. Topological token recognition and copyability do not imply control behavior for an arbitrary gamma probe. [J](CLAIM_LEDGER.md#j-tagged-unary-local-zerosuccessor-discrimination). |
| [Branch pruning](../ic_signed_branch_pruning.py): probes with guarded fanouts | Exposed control ports stay passive/free; candidate package roots attach to guarded fanouts. | Packages are reduced, fully paired except at the root. Check winning package cells/wires and losing erasure. The surviving package remains guarded; hostile control contexts can erase it. [K](CLAIM_LEDGER.md#k-signed-comparison-controls-native-ic-branch-pruning-restricted-interface). |
| [Signed sum](../ic_signed_sum_selector.py) and [three-way selector](../ic_three_way_selector.py): Loop-tagged options | One fixed sum root; prewired native copy, erase, unpack, and, for the three-way component, unpacked-payload copying. | Opaque reduced rooted gamma/epsilon packages; explicitly ordered wrappers distinguish presence from an epsilon payload. Check independent normal forms and supported consumers. These are tagged sums, not bare-root switches or source `GATE`. [L](CLAIM_LEDGER.md#l-single-port-tagged-sum-and-downstream-ic-consumers-compositional-improvement), [M](CLAIM_LEDGER.md#m-a-three-way-single-port-tagged-sum-selector-with-an-equality-payload). |
| [Isolated entry projections](../ic_typed_entry_rules.py): transparent `SQ(Z)` and typed epsilon outputs | Labeled outputs of isolated `INIT-Z` and `CMP0-Z`; passive, epsilon, or delta target contexts. | Interface types supply meanings lost in the raw graph. Check local projected RHS isomorphism. No general `SQ` representation, discriminating `EQ` signal, or coherent compiler extension follows. [N](CLAIM_LEDGER.md#n-typed-isolated-source-entry-rule-certificates-not-coherent-compiler-coverage). |
| [Bounded carrier/gate synthesis](../ic_bounded_synthesis.py) and [retained artifacts](../ic_research_artifacts.py) | A synthesized `CTRL,DATA,OUT` gate and one-root carrier; fixed retain/copy/erase/unpack consumers; a saved artifact exposes `ROOT`. | Finite graph grammar and declared payload/context family. Complete bounded execution graphs validate accepted cases; serialized producer traces are replayed before reuse. Fresh reconstruction is charged. [O](CLAIM_LEDGER.md#o-bounded-semantic-synthesis-of-ic-carriers-and-gates), [P](CLAIM_LEDGER.md#p-runtime-produced-structure-archive-and-independent-reuse). |

Equal numeric meanings do not establish wire compatibility. In particular, canonical `g(x,e)`, visibly tagged `g(x,g(e,e))`, Loop-tagged unary, and an oriented residual path are separate protocols. No general adapter among them is implemented. A matching constructor spelling is also insufficient: a composition still needs agreement on port orientation, boundary labels, lifecycle, and allowed context. A correct adapter would need a native IC construction, a semantic relation between its input/output representations, cost bounds, and consumer-compatible simulation evidence.

### Replacement is relative to an environment

As a research definition, fix `I,O,V,H,E,B` and a scheduling policy or explicitly stated fairness assumption. For each input and allowed environment, compare the sets of observable maximal executions: their visible event order, stable successful results, finite failure/stuck outcomes, and admitted infinite noncompletion. Hidden steps may be collapsed only when doing so preserves the declared observations and outcomes. A finite quiescent state is successful only if it meets the output contract.

Call two components contextually equivalent within that contract only when these observation sets agree for every allowed input and environment. Replacement additionally requires compatible interfaces and resource bounds. Finite consumer tests establish their listed cases; one real distinguishing context can refute a broader replacement claim. The repository does not provide this general equivalence or replacement proof for the component collection. Random schedules and normal-form checks must retain their narrower descriptions.

## 6. Counterexample-driven refinement

The existing evidence suggests three ways to correct an overly coarse component description:

- **Control-port counterexample.** `adversarial_context()` in [branch pruning](../ic_signed_branch_pruning.py) attaches epsilon to an exposed control port and erases the nominal winner. Record the passive-control precondition and withdraw arbitrary-context retention. Restricting `E` to passive controls changes the theorem's scope; it does not repair the broader claim by internal refinement. See [ledger K](CLAIM_LEDGER.md#k-signed-comparison-controls-native-ic-branch-pruning-restricted-interface).
- **True/false token probe.** `probe_token()` in [the signed sum selector](../ic_signed_sum_selector.py) shows that its gamma probe produces the same two epsilon outputs from epsilon and the older `g(e,e)` token. A self-paired gamma Loop instead connects the two outputs. This motivates a different control representation. The probe establishes one consumer distinction, without a theorem equating the older token with epsilon in every context. See [ledger L](CLAIM_LEDGER.md#l-single-port-tagged-sum-and-downstream-ic-consumers-compositional-improvement).
- **Type-dependent meaning.** `Z` and `ERA` share a raw epsilon encoding in the unary fragment; `EQ` and `Z` share it in isolated entry projections. Source interface types carry the distinction. A transparent `SQ(Z)` projection cannot silently stand for a reactive arbitrary `SQ` node. See [ledger G](CLAIM_LEDGER.md#g-four-source-rules-operationally-refined-to-primitive-ic) and [N](CLAIM_LEDGER.md#n-typed-isolated-source-entry-rule-certificates-not-coherent-compiler-coverage).
- **Probe-partition refinement.** The bounded search initially groups candidates by their behavior on a subset of the fixed environment. Additional permitted payloads expose overfit gates, which are rejected with replayable traces. Projection onto the original probe coordinates recovers the initial signature; the environment does not change. See [ledger O](CLAIM_LEDGER.md#o-bounded-semantic-synthesis-of-ic-carriers-and-gates).

A future refinement record should preserve the original counterexample and say exactly what changed. Adding an internal distinction to an abstract description can refine its candidate classes while keeping `E` fixed; provide a forgetting map back to the old observation vocabulary and check that required input/output meanings are preserved. Such a distinction does not change the true contextual relation for a fixed concrete system and fixed contract. Replacing a token changes the implementation and needs a new simulation check. Changing consumers, inputs, scheduling assumptions, or result meanings changes the contract and must be recorded separately. No general refinement algorithm or completeness theorem is established here.

## 7. Readout and retained research artifacts

Readout is part of the task and its cost. The comparator gives a concrete example of a stable result path before disconnected cleanup finishes, while the selectors produce consumable data at fixed boundaries. Neither establishes a constant-time local marker for every component. A stability argument must name the admitted future interactions: prewired consumers can intentionally copy, erase, or unpack the result.

The existing components can be retained as **research artifacts**: construction code, representation definitions, interfaces, invariants, cost arguments, normal-form checks, and explicit evidence limits. An artifact is ready for a particular reuse only when that reuse satisfies its contract. Replacement evidence must be recorded rather than inferred from matching decoded values.

Distinguish these human-designed reusable artifacts from **structures formed during evolution**. Residual comparison paths, guarded survivors, tagged results, and erased losers are actual outcomes of the linked IC mechanisms. The [bounded pipeline](BOUNDED_IC_INSTANCE.md#native-production-archive-and-reuse) additionally archives native copy products, records construction traces and contracts, and reconstructs fresh specimens for independent-input use in declared consumers. This finite workflow does not constitute a general learned auxiliary-structure library or a cross-task replacement theorem. Those remain research goals.

Cost records should separate representation/constraint discovery, candidate validation, instance construction or compilation, native reduction, readout, and subsequent reuse. Include duplicated inputs, preallocated candidates, wrappers, adapters, consumers, peak live cells, and cleanup when relevant. Keep conditional macro budgets distinct from generated graphs and measured runs. Neither improved yield nor net savings follows from adding constraints; comparing such benefits requires a shared candidate universe and declared budgets. The [ledger](CLAIM_LEDGER.md) retains the concrete accounting already established.

## 8. Next obligations and reporting discipline

The agenda leaves the following concrete work open:

- Native adapters between the relevant unary, path, tag, and control protocols, with interface and resource certificates.
- Composition/replacement proofs for specified consumers, and stronger environment claims only with new evidence.
- A coherent full source-rule compilation, concrete compiled feedback execution, and source-program output decoding, as tracked in [ledger E](CLAIM_LEDGER.md#e-not-yet-established).
- A synthesis/refinement procedure from the declared problem inputs to local constraints, including candidate accounting and independent verification.
- Extraction and reuse of runtime-formed auxiliary structure beyond the current finite archive/reconstruction workflow, with construction history, boundaries, invariants, costs, and replacement conditions.
- Explicit finite-inventory or physical models if such claims are pursued. IC node creation in the reducer is symbolic allocation, not an implemented supply of physical parts.

Reports should label definitions, observed results, scoped arguments, and research goals separately. Cite the ledger for established coverage and test sizes; do not accumulate isolated certificates into coherent compiler coverage. Keep structural storage, primitive mechanisms, typed operational simulation, restricted consumer composition, and full program execution distinct. This preserves all current IC work as the foundation for the broader route while making each remaining obligation reviewable.
