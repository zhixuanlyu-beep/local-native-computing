# Claim ledger and proof boundaries

This ledger separates results with executable evidence from conditional accounting, mathematical arguments, and open goals. It is the sole source for detailed test sizes, coverage counts, and proof boundaries. The research route and terminology are defined in [RESEARCH_FRAMEWORK.md](RESEARCH_FRAMEWORK.md); this file records what the current code does and does not establish.

## Evidence classification

The entries below use six evidence classes to distinguish the scope of results. An entry can belong to more than one class; classification does not add coverage.

| Class | Meaning | Current entries |
|---|---|---|
| Structural representation | A source object is stored losslessly as IC data, with an explicit decoder and copying or erasing behavior. | [F](#f-lossless-source-net-storage-in-primitive-ic-structural-bridge), [R](#r-program-code-bridge-e_code) |
| Primitive mechanism | Literal gamma/delta/epsilon cells execute the six Lafont rules; no source-rule meaning is implied by this alone. | [B](#b-actual-primitive-lafont-ic-experiments), [H-M](#h-pure-ic-signed-unary-cancellation-observable-before-global-quiescence) |
| Coherent typed fragment | One typed sublanguage has a consistent operational refinement and contextual checks; alternate encodings of the same rules add no distinct rule coverage. | [G](#g-four-source-rules-operationally-refined-to-primitive-ic), [J](#j-tagged-unary-local-zerosuccessor-discrimination) |
| Isolated projection | A typed source redex has a local IC certificate, without a globally coherent encoding. | [N](#n-typed-isolated-source-entry-rule-certificates-not-coherent-compiler-coverage) |
| Restricted-consumer composition | Components compose with declared consumers under explicit interface preconditions; tests retain their recorded scope. | [I](#i-composable-signed-difference-with-native-ic-consumers), [J-M](#j-tagged-unary-local-zerosuccessor-discrimination), [N](#n-typed-isolated-source-entry-rule-certificates-not-coherent-compiler-coverage), [R](#r-program-code-bridge-e_code), [S](#s-safe-program-activation-e_activation) |
| Full program execution | A complete source program is compiled to IC and executed with a decoded result. | [Q](#q-coherent-14-symbol-compiler-and-81--sq9-feedback-execution), [S](#s-safe-program-activation-e_activation) |

Source-level results in §A and §C and conditional static accounting in §D are not themselves IC execution evidence. In particular, the coherent fragment in §G and the isolated projections in §N use different typing assumptions and cannot be added into the separate unified compiler coverage in §Q. Finite consumer tests do not establish equivalence in arbitrary contexts, and randomized schedules do not establish all executions.

The bounded semantics-driven search in [§O](#o-bounded-semantic-synthesis-of-ic-carriers-and-gates) and the retained-artifact workflow in [§P](#p-runtime-produced-structure-archive-and-independent-reuse) add primitive-mechanism and restricted-consumer evidence. They do not add source-rule coverage and are separate from the unified compiler in [§Q](#q-coherent-14-symbol-compiler-and-81--sq9-feedback-execution). Section [§R](#r-program-code-bridge-e_code) records the finite bridge from those verified gates to the compiler's real !Gamma code; it is restricted-consumer evidence, not new source-rule coverage or full-program activation. Section [§S](#s-safe-program-activation-e_activation) adds finite whole-program activation and native continuation evidence without adding source-rule coverage.

## A. Source interaction system

The source model has 14 node symbols and 15 unordered interaction rules. Its implementation is in `source_feedback_audit.py`.

The audit in `source_rule_audit_v3.py` checks:

- every RHS port is used exactly once;
- the rule interface matches the LHS auxiliary ports;
- source port types are preserved;
- RHS nets contain no internal active pair;
- RHS nets contain no principal-path cycle;
- the source RHS forest decomposition is consistent.

The unary square-checking feedback is tested for inputs 0 through 200. The source-level result for 81 is `SQ(9)` in 279 source interactions. This is not an IC execution count.

## B. Actual primitive Lafont IC experiments

`ic_primitive_port_verifier.py` implements the six original interaction rules over explicit port graphs. It checks the six rules and **1160 two-redex local diamonds** (paired port contexts, with cyclic-wire handling).

The remaining IC demo scripts provide the following primitive-mechanism evidence:

- The gamma-tree copier checks balanced full binary trees to depth six and **200 random ordered irregular trees**. Copying an original delta-free gamma/epsilon constructor tree with `n` cells takes exactly `n` IC interactions and yields two disjoint copies. For full balanced trees, the maximal parallel redex layers have sizes `1,2,4,...,2^depth`; no clock is needed to perform the transitions.
- The reduced-package copier checks a gamma node with a self-wire, a 3-gamma package with two non-tree internal wires, and **200 randomly generated delta-free wired reduced packages**. For these packages, IC copying takes exactly `#gamma + #epsilon + #internal_wiring_pairs` interactions and reproduces two disjoint, structurally identical copies. The deltas at internal wiring pairs annihilate via the original delta-delta rule.
- The tree eraser checks **200 random gamma/delta/epsilon trees**. One epsilon on the principal root erases the tree in exactly `n` interactions for a tree with `n` cells.

These are actual gamma/delta/epsilon reductions. They are not a compilation of the 14-symbol source system.

## C. Source-level Lafont decomposition

`lafont_phi_psi_split.py` constructs 15 noncanonical source-level phi/psi/sigma splits. It reconstructs each original RHS exactly. The sigma widths are 0 in 10 rules, 1 in 4 rules, and 2 in 1 rule, for six crossing strands total.

The JSON output is a source-level split specification, not an IC target graph.

## D. Conditional macro budget

`lafont_macro_budget_v2.py` counts one specified set of Figure-10 macro expansions and epsilon fillers for undefined rule entries. Its current conditional budget is:

- decoded Gamma: 1549 gamma + 147 delta + 1241 epsilon = 2937 cells;
- delta-cut Gamma-prime: 442 free ports;
- encoded delta-free package: 1990 gamma + 1241 epsilon = 3231 cells.

The script checks all 30 single-port subpackage parity conditions. These counts are conditional static accounting, not a generated or reduced complete IC graph. Alternative macro conventions or a different valid decomposition may change the budget.

**Historical correction:** the earlier `ic_feedback_audit_bundle.zip` figures of **197 delta** in decoded Gamma and **592 exposed ports** after the delta cut are obsolete. They used the source interaction interface width `arity(A)+arity(B)` for `T_sigma`. In the supplied noncanonical Figure-6 split, sigma acts only on cross-half wiring strands, whose widths are recorded in §C. This changes the `T_sigma` contribution from 52 delta to **2 delta**. The revised totals above use epsilon fillers for 166 undefined entries and the specified standard macro choices. The cut package has `3*147 + 1 = 442` free ports and no delta; the encoded package is also delta-free. The static script remains conditional accounting. Independently generated graphs in [section Q](#q-coherent-14-symbol-compiler-and-81--sq9-feedback-execution) confirm these same inventories under the explicit port conventions in the [compiler guide](COHERENT_IC_COMPILER.md).

## E. Not yet established

The project does **not** yet contain:

1. an automatic compiler from polynomial-term structure to the source rule package;
2. a derivation of the three-cycle or `J^2 = -I` from the polynomial's initial IC graph;
3. a contextual-equivalence theorem for the unified compiler under arbitrary source contexts and schedules;
4. a physical finite-inventory implementation of symbolic IC allocation.

The former gaps concerning literal macros, genetic-package coding, rule simulation, coherent source lowering, and concrete feedback execution are discharged for this fixed source system by [§Q](#q-coherent-14-symbol-compiler-and-81--sq9-feedback-execution); the remaining items are different research goals.

Sections F-P retain the earlier component evidence and its original representations. Their fragment coverage and missing adapters describe those components; the separate unified compiler is evaluated in section Q. Section R records the M1 bridge between the bounded-discovery survivors and that compiler's program code.

## F. Lossless source-net storage in primitive IC (structural bridge)

`source_ic_structure_encoding.py` provides a concrete, injective **ordered representation** of finite, fully paired source port nets using only primitive `gamma`/`epsilon` nodes and wires. The representation records source symbol tags (not source evaluator functions), ordered ports, boundary positions, and the complete wire matching. It does not consult source rewrite rules or output values to encode a net. A structural decoder recovers the source snapshot exactly.

One primitive IC `delta` attached to the root of that *closed, delta-free reduced package* duplicates the encoding, and one `epsilon` erases it, using **only primitive IC reductions**. Tests exercise the 15 source-rule RHS nets, initial source nets for `N=0..200`, and 60 arbitrary typed port matchings (including cycles and disconnected components). For copying/erasing this particular representation, the observed count is `payload_IC_cells + original_internal_wire_pairs`; this is an encoding/copy resource count, **not** a source square-checker reduction count.

For `N=81`, the initial source structure encodes as **533 gamma/epsilon IC cells**, containing **83 original source wire pairs**. Copying or erasing it takes **616 primitive IC reductions**. These numbers represent the encoded **initial problem data only**; they do not imply an IC computation of `SQ(9)`, a runtime rule compiler, or an output decoder. The representation's node order and boundary order are part of its chosen syntax, not canonical graph-isomorphism invariants. Source symbolic types are represented as unary data tags, not active IC node kinds.

**Historical bridge:** source program graphs can exist *as data* inside literal 3-symbol IC nets and be copied/erased locally. That storage bridge is distinct from executing source rules; the unified compiler and full `81 -> SQ(9)` trace are now established in [§Q](#q-coherent-14-symbol-compiler-and-81--sq9-feedback-execution).

## G. Four SOURCE rules operationally refined to primitive IC

`ic_unary_operational_fragment.py` defines a separately typed, closed-net operational refinement for source symbols `Z,S,DUP,ERA`. The representation is `Z -> epsilon`, `ERA -> epsilon`, `DUP -> delta`, and `S(x) -> gamma(x,epsilon-tag)`. The source type/polarity context distinguishes `Z` and `ERA`; **the raw target graph alone does not injectively distinguish them**, and the translation is restricted to well-typed source nets of this fragment.

All four source rules (`ERA-Z`, `ERA-S`, `DUP-Z`, `DUP-S`) have independently translated IC LHS and RHS structures and primitive reduction certificates of length **1, 2, 1, and 2** respectively. A local certificate checks colored-free-port graph isomorphism. In addition, the test checks **400 randomly wired well-typed closed source contexts**, independently computes their expected source one-step result, and compares it with primitive IC reduction. Complete unary copy and erase programs `S^n(Z)` are tested for `n=0..200`; an entire closed copy-then-erase program also reduces without invoking any source rules at runtime.

This is genuine historical operational-refinement evidence for **4 of 15 source rules under its own representation**. It is not the unified 14-symbol compiler in [§Q](#q-coherent-14-symbol-compiler-and-81--sq9-feedback-execution), and its raw target graphs do not establish arbitrary-context simulation for that compiler. Source-level success and compiled IC success must remain separately distinguished.

## H. Pure IC signed unary cancellation; observable before global quiescence

`ic_signed_unary_comparator.py` constructs two independently specified gamma/epsilon unary chains oriented in opposite directions, each with a gamma/epsilon *zero sentinel*. The two outer principal ports are connected to form one gamma-gamma active pair. The builder uses `m` and `n` **only as independent chain lengths**; it neither compares them nor constructs an answer-specific result. The original six IC rewrite rules are the only runtime operations.

**Inductive mechanism.** While both chains have an unmatched gamma, a gamma-gamma collision splices the two continuation ports (left auxiliary 1 to right auxiliary 2) into the next collision and separately connects their two epsilon tags. Each collision thus creates exactly one independent epsilon-epsilon garbage redex. With `k=min(m,n)+1`, including the two zero sentinels, exactly `k` gamma-gamma collisions take place. The two observation boundaries then connect directly when `m=n`, otherwise via an oriented chain of `|m-n|` surviving gamma/epsilon pairs. Entering from boundary A through gamma auxiliary 1 means `m>n`; entering through gamma principal 0 means `m<n`. The residual chain length is exactly `|m-n|`. The output path contains no active pairs, and epsilon-tag garbage is disconnected from it. All remaining `k` epsilon-epsilon redexes may be reduced in any order without affecting the observation.

Therefore the **complete** IC reduction count is `2*(min(m,n)+1)`; if the causal gamma frontier is reduced first, the result becomes readable after `min(m,n)+1` interactions, *strictly before total quiescence*. This is an observer-extracted fact, not a signal propagated to a source `GATE` or `CMP`. The observer traverses a possibly long output path: it is a read-only macro observation, **not** a constant-time local cell detecting the sign or magnitude.

Tests run all `0<=m,n<25` under three reduction policies (1,875 runs), plus eight larger edge cases with randomized schedules and explicit early-read audits. These are finite tests backed by the elementary inductive wiring argument; they are not exhaustive model checking of arbitrary IC contexts. The comparison encodings are distinct from the typed four-rule embedding in section G; no adapter or `CMP` simulation using these comparison chains is implemented. This component adds no coverage to the historical **4/15** fragment; the separate unified representation is evaluated in section Q.

## I. Composable signed difference with native IC consumers

`ic_composable_signed_difference.py` uses two oppositely ordered copies of the previous gamma/epsilon comparator component, but **does not wait for or branch on any external observation**. The input builder allocates separate chains from the supplied natural numbers. Both channels have a fixed epsilon probe on the left and a fixed delta probe on the right, with the unused delta output connected to epsilon. One channel compares `m,n`, and the other `n,m`.

The independently decoded final output graphs are canonical rooted unary values `P=max(m-n,0)` and `N=max(n-m,0)`, with `S(x)=gamma(x,epsilon)`, `Z=epsilon`, and one fixed boundary per result. They are **real nets rather than an observer-calculated sign or magnitude**. The test also statically connects one output to a primitive `delta` duplicator and the other to an `epsilon` eraser. Then it executes *only primitive IC* active pairs; the final two output boundaries contain two exact copies of the chosen truncated difference. The choice of which output to consume is fixed before evolution and is not an if-statement driven by the answer.

The construction uses two copies of each input and may allocate additional garbage and cleanup work. It does **not** establish an optimal comparator, a runtime three-way branch/GATE selector, or a compiler for any of the remaining 11 source rules. The initial network contains no hard-coded result or comparison. It does not use the source `apply` evaluator during execution. CI tests randomized schedules and subsequent copy/erase interaction in genuine IC. The equivalence for arbitrary natural numbers follows from the complementary-chain cancellation mechanism and native IC duplication/erasure rules; finite tests are not exhaustive proof of arbitrary contexts.

## J. Tagged-unary local zero/successor discrimination

`ic_tagged_unary_case.py` introduces a **different**, visibly tagged unary encoding: `Z=e`, `S(x)=g(x,T)` with `T=g(e,e)`. A fixed, input-independent gamma *case* destructor connected to the input principal port reduces in **one primitive IC interaction** to a Boolean token and a predecessor. For input `Z`, the outputs are `(false=e, predecessor=e)`; for `S(x)`, they are `(true=T, predecessor=x)`. The Boolean token is a genuine, independently copyable/erasable IC constructor, not a result of external graph traversal controlling an interaction. Its meaning is still verified with read-only test observers.

All four original `{ERA,DUP} x {Z,S}` source interactions were independently translated into this new tagged representation, with boundary-labeled target isomorphism certificates of lengths **1, 4, 1, 4** for `ERA-Z`, `ERA-S`, `DUP-Z`, `DUP-S` respectively. These demonstrate the new tag does not destroy the operational unary copy/erase fragment; they do **not** count as four additional distinct source rules. A case can be pre-wired to `delta` to produce two Booleans or to `epsilon` to erase the Boolean while preserving the predecessor; tested on `n=0..200` under three schedulers. End-to-end copying and erasing of tagged unary values uses `4*n+1` primitive IC interactions.

This is **not** an IC implementation of a total Boolean-controlled two-branch selector, the source `CMP` family or the original `GATE`; it does not accept the previous canonical `S(x)=g(x,e)` encoding. A converter between the signed-comparator output and this tagged case protocol remains an independent missing component. This component leaves its historical source fragment at **4/15**; section Q evaluates the separate unified encoding. The new discriminator is a useful local subroutine but does not solve the complete square checker.

## K. Signed comparison controls native IC branch pruning (restricted interface)

`ic_signed_branch_pruning.py` adds gamma probes to opposite ends of the signed unary collision network. These probes each guard a delta fanout connected to two **opaque reduced gamma/epsilon packages**, which may have non-tree internal wiring. The compiler creates both families for all inputs. During primitive IC reduction only, the local wiring is enough to **erase all negative-family packages if m>n, erase all positive-family packages if m<n, and erase both families if m=n**. Every winning package remains cell-for-cell and wire-for-wire unchanged, verified against its original ports. A winning family is **still attached to its passive guarded fanout**, not converted to a canonical output or made automatically executable. This is conditional pruning, not a complete switch or the original source GATE.

For `k=min(m,n)+1` and `W_P,W_N` the per-family sums of `number of package cells + number of paired internal wires`, the verified native IC step count is `2*k + 4 + W_loser` if unequal, and `2*k + 4 + W_P + W_N` if equal. With `d=abs(m-n)`, surviving cell count is `(size_of_winning_family + 3 if unequal else 0) + max(0, 2*d-1)`. The family overhead 3 is gamma guard + delta fanout + epsilon tag. These are bounds for this exact representation and specified closed package inputs, not universal IC runtime results.

Tests cover all `m,n<18` under five schedules (1,620), 480 random multi-package wiring trials, and nine additional large edge cases. A deliberately adversarial test attaches epsilon to the **exposed control port** and erases what would otherwise be the winning family. Consequently, the preservation theorem has an essential interface precondition: control ports must remain passive/free, and the branch packages must be fully reduced, closed except at their designated root. This does NOT prove retention under arbitrary contexts, guarantee unexecuted computation in selected branches, supply an equality payload, or compile new source rules. The historical fragment associated with these components remains **4/15**; section Q evaluates the separate unified encoding.

## L. Single-port tagged sum and downstream IC consumers (compositional improvement)

`ic_signed_sum_selector.py` uses a modified *left-side unary encoding*: each predecessor/sentinel gamma carries the self-paired one-port gamma token `Loop = gamma(aux1--aux2)`, while right-side predecessor tags are epsilon. Matching gamma-gamma collisions connect these complementary tags; `Loop` against epsilon erases in a local IC interaction without producing wire-cycle garbage. The residual positive difference becomes a native tagged unary `S(x)=gamma(x,Loop)`, `Z=epsilon`. The opposite channel produces the negative truncated difference by swapping m and n. Both inputs are built independently, without precomputed order or result.

Each truncated-difference root is consumed by a fixed gamma case destructor and a gamma probe guarding an opaque, reduced, fully paired gamma/epsilon candidate package. Zero sends epsilon to the designated option slot and erases the package; positive sends a self-paired loop token which the probe turns into a connection preserving the package inside an explicit `Tagged(payload)=gamma(payload,Loop)` wrapper, while the remaining predecessor is erased. Two slots form one rooted `gamma(positive_option,negative_option)` at a **single fixed output boundary**. The output normal form is:

- `m>n`: `gamma(Tagged(A),epsilon)`;
- `m=n`: `gamma(epsilon,epsilon)`;
- `m<n`: `gamma(epsilon,Tagged(B))`.

A selected package consisting of one epsilon remains distinguished from an absent branch by its explicit wrapper and Loop tag. The unselected package is completely erased through primitive IC interactions, including internal paired wires. The initial graph always contains both candidate packages; the builder uses `m,n` only to allocate separate unary chains, never to choose the branch.

The new code independently constructs the exact target nets and checks labeled-interface graph isomorphism under five IC redex schedules, with finite wire-graph test cases, 800 randomized opaque packages, larger input pairs including `81:80`, `80:81`, and `81:81`, and real downstream `delta` copying and `epsilon` erasure. A static gamma deconstructor can additionally deliver four **fixed, typed output ports** (`POS_FLAG,POS_DATA,NEG_FLAG,NEG_DATA`), where absent flags and absent data are epsilon and present flags are Loop. These consumer ports are ordinary graph interfaces, not observer-issued rewrite commands.

**Limitations:** the result is a *tagged sum*, not an unwrapped bare payload or an equality payload. The code validates structural normal forms under tested reduction schedules but does not prove full contextual equivalence under arbitrary hostile consumers. The self-paired Loop token is distinguishable from epsilon by a specific gamma probe, whereas the old `gamma(epsilon,epsilon)` token is *not* distinguishable from epsilon by that probe. This corrects any implication that the old token alone was already a usable branch-control signal. This selector adds no source-rule certificates to the historical **4/15** fragment and does not implement source `CMP` or `GATE` in its own protocol. The separate Figure-10 compiler and concrete square-checking execution are established in section Q.

## M. A three-way single-port tagged-sum selector with an equality payload

`ic_three_way_selector.py` independently builds **three** gamma/epsilon cancellation channels: a left-positive difference for `m>n`, a right-positive difference for `m<n`, and a new zero-sentinel equality channel. All three candidate gamma/epsilon packages (including opaque non-tree wired packages) are present before reduction. The equality channel uses two special gamma sentinels: when both zero sentinels meet, their gamma-gamma interaction connects the prebuilt equality package to the equality option; if one unary chain terminates first, a gamma-epsilon interaction erases the equality package and fills that option with epsilon. This construction does not contain a conditional on the relationship between the two input sizes. All runtime computation calls the original six `Net.reduce` primitives only.

The **single fixed output** is an ordered tagged sum `gamma(Option(A), gamma(Option(B), Option(C)))`, where `Option(X)=gamma(X,Loop)` and `Loop` is a gamma whose two auxiliary ports are wired together. Exactly one option contains a candidate, with `A` for greater, `B` for equal, `C` for less; the other two options are epsilon. A chosen epsilon-valued candidate remains distinguishable from an absent option because of the wrapper. The exact final network is compared to an independently constructed normal form by labeled-boundary graph isomorphism.

The component also supports **prewired native IC consumers**: copy the tagged sum with delta, erase it with epsilon, unpack all three typed option flags/data into six output ports via gamma interactions, or immediately delta-copy each unpacked payload into two result ports (including epsilon for inactive branches). On `sum` outputs the test additionally checks that every original node and every port pairing of the winning opaque package survives unaltered and both losing packages are absent. Reduction policies only select which *already active* IC pair to reduce and do not inspect the answer.

The regression test includes separate zero-sentinel equality certificates, all `0<=m,n<8` under five schedules and five modes, 800 randomized three-package inputs, and larger representative cases including `81:80`, `80:81`, `81:81` and `200:200`. Tested normal-form agreement is not exhaustive proof of arbitrary IC contexts. Importantly, this remains a **tagged-union output**, not a bare-root payload switch; it uses independent copies of numeric inputs and no source-system `CMP`, `GATE` or source-level `SQ` semantics. **This selector leaves the historical fragment at 4/15; unified compiler evidence is in section Q.**

## N. Typed isolated source-entry rule certificates (NOT coherent compiler coverage)

`ic_typed_entry_rules.py` adds two independently checked **isolated-redex typed projections** tied directly to the literal source RHS definitions: `INIT-Z -> SQ(Z)` and `CMP0-Z -> EQ, Z`. For `CMP0-Z`, represent the source `CMP0` as a gamma with its two auxiliary outputs and `Z` as epsilon; one gamma-epsilon reduction yields epsilon at both boundary ports, which are distinguished as `EQ:T` and `Z:N` only by source interface typing. For `INIT-Z`, represent `INIT` as a gamma with one output auxiliary and one private epsilon tag; gamma-epsilon then epsilon-epsilon yields a single epsilon at the O-typed output. The target `SQ(Z)` is represented by *erasing the independent SQ wrapper* and treating the Z child as a transparent O-typed output. These are genuine primitive IC reductions against independently checked source rule shapes, with respectively **2** and **1** IC steps, but are **not full representations of the source nodes**.

The test checks exact port-labeled IC target graph isomorphism and enumerates passive/free, epsilon eraser, and delta copier contexts on every output boundary (three possibilities for `INIT-Z`; nine for `CMP0-Z`), with three active-redex schedules and five seeds each. These are IC target contexts, **not arbitrary typed source contexts**, and are no substitute for a contextual simulation theorem. In particular an isolated transparent `SQ(Z)` cannot safely represent arbitrary `SQ` embedded in the feedback loop, and `EQ` encoded as epsilon is **not a discriminating T-valued signal** when combined with `GT`, `LT`, or `GATE`. These isolated projections provide no compiler for `INIT-S`, `CMP-S`, `CMPS-S`, `GATE-EQ` or the remaining rules. The conservative **coherent operational source-language fragment** still has certificates for **4/15** source rules, while two more **separately typed isolated-redex patterns** have local certificates. Adding 2 to 4 would incorrectly imply a single globally coherent 6-rule encoding for those historical representations. The separate full encoding in section Q is independently constructed and verified.

## O. Bounded semantic synthesis of IC carriers and gates

[ic_bounded_synthesis.py](../ic_bounded_synthesis.py) searches literal primitive IC port graphs against a declared conditional retain/erase observation contract. False is fixed to epsilon. True carriers are connected reduced gamma/epsilon graphs with one principal-root boundary and at most three cells. The generator considers **162 raw carrier matchings**, yielding **52 distinct representatives** up to exact port-labeled isomorphism. The gate family consists of **33 complete port matchings** with one epsilon, gamma, or delta cell and three boundaries `CTRL`, `DATA`, and `OUT`. All **1,716 joint candidates** are accounted for; the successful probe wiring is not imposed by the generator.

The fixed finite environment contains four payloads (epsilon, a self-paired gamma Loop, a constructor tree, and an internally cross-wired package) and four prewired consumers (retain, copy, erase, unpack), with both Boolean inputs: **32 cases per candidate**. Initial discovery uses only four coordinates: two training payloads and both inputs with passive output. It leaves **8 candidates**. Expanded probes within the same environment refute **6** of those with concrete counterexamples, leaving **2 verified candidates**. These are the two auxiliary-port orientations of a gamma gate whose principal port receives the control, paired with the one-cell Loop true carrier. The report extracts these shared predicates after verification and records the forgetting map from full observations to the initial probe signature.

The complete accounting is **33 storage-distinction rejections**, **1,675 initial concrete execution rejections**, **6 additional context counterexamples**, and **2 verified candidates**. All **1,681 concrete rejection traces** are replayed and checked against independently rebuilt inputs and task postconditions. Expanded checking performs **186 cases** (180 passing cases and 6 refutations); failed candidates stop at their first counterexample. Only the final candidates pass the entire fixed environment. Initial success is not reported as contextual correctness.

[ic_bounded_execution.py](../ic_bounded_execution.py) explores every enabled primitive active pair, merging only exact labeled-port isomorphism including cyclic wires. A successful case requires complete exploration, an acyclic reachable quotient, and the correct independent normal form at every terminal. This establishes all-schedule termination and correctness for those concrete small nets, without a fairness filter. The material bound is **64 peak live cells**; initial search budgets are **256 states / 2,048 attempted transitions** per case, and expanded-context budgets are **4,096 / 32,768**. A cutoff is incomplete verification, not success or evidence of divergence. The exploration tests include commuting independent redexes, trace replay, cyclic-wire preservation, and deliberate state/transition/material cutoffs.

The [instance description](BOUNDED_IC_INSTANCE.md) and [saved compressed JSON report](../results/native_ic_research.json.gz) specify the grammar, every candidate and outcome, counterexamples, and case-level execution summaries. This is automatic synthesis within an explicit small prior, not general discovery from arbitrary semantics, a compiler, a proof about every rooted IC package, or an adapter between the earlier numeric protocols. This synthesis adds no source-rule coverage to the historical **4/15** fragment or the separate unified compiler in section Q.

## P. Runtime-produced structure archive and independent reuse

[ic_research_pipeline.py](../ic_research_pipeline.py) prewires a native delta consumer to a discovered gate. For both inputs and the four declared payloads, primitive IC produces two exact, disjoint copies. All original payload cells have been consumed in each recorded producer run. The pipeline archives one actual runtime-created output component, giving **8 specimens**, and then checks each with an independent Boolean input and the four fixed consumers: **64 reuse cases**. Producer and reuse output correctness are checked by complete finite all-schedule exploration against independent expected graphs; the original-cell identity check applies to the recorded concrete runs.

[ic_research_artifacts.py](../ic_research_artifacts.py) serializes literal port-graph syntax and ROOT-connected reduced gamma/epsilon artifacts. Capture preserves internal wires and rejects connection to another exposed boundary. Import validates the full component's matching, connectedness, cell kinds, and absence of active pairs. The artifact records the producer's initial graph, primitive trace, source fingerprint, interface, invariants, measured costs, and explicit replacement conditions. Metadata is descriptive; the pipeline independently replays provenance, checks the whole producer result, and compares the recaptured component. The saved-report verifier also replays rejection evidence and rechecks native reuse.

The original producer network remains unchanged during subsequent reconstruction and use. Import constructs a **fresh specimen** from the recorded topology; it is build-time tooling, not a new runtime IC operation or a reset of physical matter. The archived components have **1, 3, or 5 cells**. The largest producer peak is **10 live cells**. Adding the retained original's fixed size to the exhaustively measured fresh-net peak gives a largest **derived combined peak of 20**, within the declared bound. Both allocations are charged; this sum is a compositional resource bound, not a physical co-residency measurement.

The evidence establishes this finite archive/reconstruction/consumer workflow. It does not establish autonomous discovery of a general auxiliary-structure library, arbitrary-context replacement, physical material reuse, or complete source feedback execution. The original implementations, isolated-certificate distinction, missing component adapters, and historical **4/15** fragment evidence are preserved. The separate unified compiler is evaluated in section Q. The new audits are included in [tests/run_all.sh](../tests/run_all.sh), which is run by the existing CI workflow.

## Q. Coherent 14-symbol compiler and 81 鈫?SQ(9) feedback execution

`source_ic_coherent_compiler.py` constructs the actual Figure-10-style primitive-IC program for all 14 source symbols and 15 unordered source rules. The implementation is a unified representation: each source symbol has one consistent primitive-IC footprint, and `Gamma` uses the column construction required by the Lafont transpositor/selector mechanism. The program itself has **2,937 decoded cells** (1,549 gamma, 147 delta, 1,241 epsilon); its delta-free `!Gamma` encoding has **3,231 cells** (1,990 gamma and 1,241 epsilon). These are generated and validated graphs, not conditional budget estimates.

The same report verifies native `!Gamma` decoding in **441 interactions** (peak 3,235 cells), and native copying followed by two decodes in **4,488 interactions** (peak 5,880 cells). All **14 symbol extractions** reduce to independently built templates, and all **91 unordered distinct-symbol template pairs** are distinguished. `ic_package_codec.py` additionally checks **70 package decode/copy cases** across the declared packages and schedules. `ic_fast_reducer.py` checks every primitive rule, **1,160 two-redex contexts** in both bounded orders, **200 randomized bounded prefixes**, terminal detection, and explicit cutoffs against the original reducer.

`ic_coherent_certificates.py` certifies every one of the 15 source rules by independently compiling the literal LHS and RHS, executing only primitive IC reductions, and checking exact labeled-boundary graph isomorphism. The stored certificate trace contains **427,134 primitive interactions** and is replayed record-by-record under the recorded FIFO policy. The 15 rule ranges are:

| Measurement | Range |
|---|---|
| Initial compiled cells | 6,834-7,517 |
| Primitive interactions | 7,948-84,179 |
| Peak live cells | 6,968-28,878 |

`ic_coherent_contexts.py` adds **26 finite typed-context cases**. Every free source input is asserted to have declared type `N`; selected cases fill those inputs with independently constructed unary sources `S^n(Z)` using two distinct length vectors modulo 3. LHS and literal RHS are compiled independently with `FastNet`, normalized only by primitive reduction, and compared as complete labeled-boundary graphs. This is evidence for the declared passive-output/bounded-input contract, **not** an arbitrary-context equivalence theorem.

`ic_coherent_feedback.py` compiles the complete source input graph for 81 and executes it with only primitive IC interactions. The stored FIFO trace contains **4,810,050 primitive interactions**. The run starts with **305,111 primitive cells**, peaks at **338,399 live cells**, terminates with **40,207 cells and no cyclic wires**, and yields the decoded result `SQ(9)`. Peak means `max(initial, cells after each completed primitive interaction)`; it excludes transient host bookkeeping inside a reducer call and host byte memory. The terminal graph is saved before readout and independently matches a separately compiled source-result encoding. The trace digest is re-scanned and equals the recorded digest `bdd811551ad838b8f2a29a608655d27f4b5ddb8e13e27cc2b943bf4e9ca8da62`.

Additional reports archive [input 0 yielding SQ(0)](../results/coherent_feedback_0.json.gz) and [input 2 yielding BR(1,2)](../results/coherent_feedback_2.json.gz); these are additional concrete cases, not an all-input theorem. The structural decoder checks all source symbol round trips and rejects malformed or uncovered graph structure. [Artifact-integrity tests](../tests/coherent_artifact_integrity.py) replay a valid witness and reject **13 evidence-tampering cases**.

The [rule report](../results/coherent_rule_certificates.json.gz), [rule trace](../results/coherent_rule_certificates.ictrace.gz), [context report](../results/coherent_context_cases.json.gz), [feedback report](../results/coherent_feedback_81.json.gz), [feedback trace](../results/coherent_feedback_81.ictrace.gz), and [terminal graph](../results/coherent_feedback_81.final.json.gz) are archived together. The [compiler guide](COHERENT_IC_COMPILER.md) specifies port, trace, decoder, and verification contracts.

Full verification commands are:

```sh
python ic_coherent_certificates.py --verify-report results/coherent_rule_certificates.json.gz --trace results/coherent_rule_certificates.ictrace.gz
python ic_coherent_feedback.py --verify-report results/coherent_feedback_81.json.gz --replay-trace results/coherent_feedback_81.ictrace.gz --verify-final results/coherent_feedback_81.final.json.gz
python ic_coherent_contexts.py
```

These results do not establish arbitrary-context equivalence, all possible schedules, optimality, or a physical implementation. The 81 run uses the recorded FIFO schedule and an explicit structural readout. Symbolic allocation by the Python reducer is not physical inventory. Automatic constraint discovery from arbitrary task semantics remains a separate open research line.

## R. Program-code bridge (E_code)

[ic_program_code_bridge.py](../ic_program_code_bridge.py) imports every gate/carrier pair marked verified in the frozen bounded-discovery report and checks that report's file digest, graph fingerprints, candidate accounting, and survivor list. The bridge environment E_code-v1 does not modify that report or the earlier payload environment. It adds the delta-free package codes for epsilon, gamma(epsilon,epsilon), delta(epsilon,epsilon), and the compiler-generated real Gamma program. The four consumers are retain_code, copy_code, decode, and copy_decode; true inputs retain/copy/decode the code or original object, while false inputs produce the declared epsilon outputs. Reference graphs are constructed independently from the original objects and compared as complete labeled port graphs, including all components and cyclic-wire counts.

The acceptance matrix covers both frozen gate/carrier survivors, both Boolean inputs, all four payload codes, and all four consumers: **64 FIFO bridge cases**. Every case passed under the fixed per-case bounds of **100,000 interactions** and **20,000 live cells**. Initial sizes range from **7 to 3,242 cells**, peak live cells from **7 to 6,468**, and primitive interactions from **1 to 4,489**. The 64 bridge cases use **46,496 primitive interactions** in total; every final graph had zero cyclic wires. Peak means the maximum of the initial cell count and the count after each completed atomic interaction.

For the real Gamma program with copy_code, the run archives one actual program-code product for each survivor and each first Boolean input: **4 artifacts**. The false-input artifacts each contain one epsilon cell. Each true-input artifact contains the **3,231-cell** delta-free !Gamma code. The corresponding producer starts with 3,234 cells, peaks at 6,468, and terminates with 6,462 cells; the original payload cells are absent from the terminal producer.

Each artifact is reconstructed as a fresh specimen and exercised with a new Boolean input and both decode consumers, giving **16 reuse cases**. Every case passed and used **24,416 primitive interactions** in total. Fresh-instance initial sizes range from **7 to 3,242 cells**, fresh peaks from **7 to 5,880 cells**, and interactions from **7 to 4,489**. The retained producer contributes between **2 and 6,462 cells**; the largest combined retained-plus-fresh peak is **12,342 cells**, within the declared 20,000-cell bound. This is offline archive/import evidence, not continuous reuse in one network.

The epsilon-code and delta-object-code cases are also explored over every enabled active-pair choice: both survivors, both Boolean inputs, both payload families, and both decode consumers, giving **16 complete all-schedule cases**. Each exploration is bounded by **4,096 states**, **32,768 attempted transitions**, and **128 live cells**. Every exploration was complete and acyclic, with one correct terminal state. State counts range from **5 to 408**, attempted transitions from **4 to 1,409**, peak live cells from **11 to 22**, and maximum interaction-path lengths from **4 to 21**. The real !Gamma network is checked only under FIFO; no exhaustive schedule claim is made for it.

Four durable boundary probes are archived with the same trace. Directly decoding epsilon succeeds in **6 interactions** and yields one epsilon cell. A wrong control token fails in **13 interactions**, yielding one cell instead of the three-cell delta(epsilon,epsilon) target. Swapping the gate's CTRL and DATA boundaries fails in **4 interactions**, yielding the wrong three-cell normal form. Supplying epsilon to the code input of an INIT extension takes **33 interactions** and leaves **32 residual cells**, refuting the inference that D(epsilon)=epsilon clears the whole source-symbol extension. The probes are also replayed by the original Net reducer.

The archived report is [program_code_bridge.json.gz](../results/program_code_bridge.json.gz) and its replayable trace is [program_code_bridge.ictrace.gz](../results/program_code_bridge.ictrace.gz). The trace contains **70,968 primitive pair records** with pair-record digest **6a7c3815544980bfda7eb988b373587b9533865984d1307999c62a9ed75404bd**. Full verification reconstructs the frozen inputs, replays every pair under FIFO, independently reproduces archived products, and compares every report field. The report file digest is **624976b188e7659a52a32e92fcd1c46db95a18f639c41909ddaf17eaac29ecf7**. [Artifact-integrity tests](../tests/program_code_bridge_integrity.py) reject mutated reports and traces, malformed inputs, cutoffs, incomplete graph observations, and edits to the frozen discovery report. Their mutation plumbing substitutes a small Gamma code for speed; the real Gamma program is independently covered by the archived CLI verification.

The existing source audits, primitive and component checks, discovery/report verification, macro and codec checks, coherent certificates and contexts, and feedback executions and full archived feedback replay continue to pass. The new integrity test and bridge report verification are included in [the existing CI runner](../tests/run_all.sh).

This section establishes restricted-consumer composition of frozen discovered gates with the compiler's real program code. It does not add source-rule coverage or arbitrary-context equivalence; full-program activation is now recorded separately in section S. It does not establish all-schedule behavior for the full !Gamma network, continuous native reuse, physical material reuse, or a general structure library.


## S. Safe program activation (E_activation)

[ic_safe_program_activation.py](../ic_safe_program_activation.py), [ic_program_suspension.py](../ic_program_suspension.py), and [ic_native_result_reader.py](../ic_native_result_reader.py) implement the M2 activation environment. They suspend each complete feedback program using the compiler bare extension symbols, collect the initial principal-cut endpoints, output, and every code input into one principal package, encode that package, and activate it only after the prewired grant/delivery gates. One initial literal !Gamma supplies every extension through native copying and is carried forward natively in continuation packets. The bounded native reader recognizes the original SQ/BR and unary Z/S constructors; Z supplies readiness, and BR separately joins readiness of both arguments before advance. Readiness is local constructor recognition, while later reconstruction and cleanup may overlap later stages.

The contract representation bounds are max_input = 4, max_tasks = 3, and unary_reader_depth = 5. These are builder/grammar bounds, not coverage claims. The accepted finite case list is:

- singles for inputs 0,1,2,4, each with both Boolean flags;
- two-task sequence (2,1) with all four flag patterns;
- three-task sequence (1,2,0) with flag patterns TTT,TFT,FFT;
- both frozen M1 gate/carrier survivors.

This gives 30 positive FIFO cases containing 50 task stages (28 enabled, 22 disabled). Every positive case terminated, matched its independently constructed complete labeled port graph, had no protocol violations, consumed the initial program-code cells, retained exactly the 3,231-cell !Gamma at LIBRARY, produced DONE as Loop, and had zero cyclic wires. Positive interactions total 8,661,430. Per-case initial sizes range 6,174-12,264, peaks 6,664-69,302, interactions 17,608-818,593, and final sizes 3,234-43,208. The peak is the maximum of the initial count and the count after each atomic interaction, across the entire prewired network, including future tasks, overlapping cleanup and retained code. Every case is bounded by 2,000,000 interactions and 250,000 live cells.

The independent source references are 0 -> SQ(0), 1 -> SQ(1), 2 -> BR(1,2), and 4 -> SQ(2). Enabled outputs are compiled independently from those source results; disabled outputs and statuses are epsilon. The report records native grant, delivery, and advance events. For enabled stages, advance requires the terminal-Z readiness emitter and any required BR argument join has already occurred; for disabled stages, advance requires the constant skip token.

Two durable negative probes are archived in the same trace. Reader depth 0 on enabled input 1 takes 215,876 interactions, peaks at 26,356 live cells, ends with 3,292 cells, and is rejected as a wrong normal form. Miswiring an enabled stage ready selector to the immediate skip token takes 119,599 interactions, peaks at 19,120 live cells, ends with 17,516 cells, still matches the expected whole output graph, and is rejected as a protocol violation. The second probe shows why whole-graph output alone is insufficient for activation-phase evidence.

The archived report is [safe_program_activation.json.gz](../results/safe_program_activation.json.gz) and its replayable trace is [safe_program_activation.ictrace.gz](../results/safe_program_activation.ictrace.gz). The trace contains 8,996,905 primitive pair records, including the two negative probes, with pair-record digest 50b837020764ff260a26ef1a655a1174e779fb171c5c82ec6e4ddc5348f3f940. The report file digest is 589c1a3e49411e8304d31ee2790eaab414dcb1ba5da1bb1d51183c1760efcb50. Full verification rebuilds the frozen bindings and replays every pair under FIFO. [tests/safe_program_activation_integrity.py](../tests/safe_program_activation_integrity.py) uses a reduced real-input fixture, performs one actual raw replay, mutates report fields against that replay, and checks tiny raw traces for order, truncation, and trailing records; it is not the full frozen matrix. The full matrix is replayed separately by the CLI in [the existing CI runner](../tests/run_all.sh).

Local acceptance passed the complete M2 raw replay and all 6 integrity-test groups. All 34 commands from the frozen M1 runner also passed, including the original input-81 primitive replay, coherent contexts and certificates, and frozen discovery and bridge evidence. Both new M2 entry points are included in the existing CI runner. No original report or trace was changed.

This section establishes finite FIFO evidence for safe activation, explicit disabled state, skip-and-continue behavior, one shared native program supply, and prewired native continuations. It does not claim arbitrary-context equivalence, all-schedule behavior, exhaustive coverage of the representation bounds, physical inventory, optimality, or a cost benefit. The M1 archive/reuse boundary remains unchanged.

## T. Composition arguments and schedule evidence (E_composition)

[COMPOSITION_LEMMAS.md](COMPOSITION_LEMMAS.md) gives written mathematical arguments for associative port gluing including closed wire cycles, contextual trace lifting with explicit fresh-cell maps, commuting distinct active pairs, and uniform normalization with preserved primitive-rule census. It also gives macro cancellation, principal-package copy/erase and delta-cut decode arguments, conditional compiler forward simulation, restricted constructor-forest readout, and staged/projected resource bounds. These are arguments about the specified abstract calculus. Their application to Python assumes faithful implementation of that calculus; the finite audits do not prove universal implementation conformance. The local-witness assumption binds the existing complete rule certificates. No reverse simulation, divergence reflection, arbitrary observational-context equivalence, or universal source termination result is claimed.

[ic_composition_certificates.py](../ic_composition_certificates.py) defines E_composition-v1 separately from the frozen discovery, bridge, and activation environments. Its report binds the contract and policies, primitive-rule syntax, compiler code fingerprint, discovery metadata, original rule-certificate report/trace digests, M2 report digest, finite grammar bounds and AST case list, activation inputs, and independently constructed macro initial/expected graph fingerprints. Runtime selects primitive active pairs and calls the original IC reducer. Source evaluation, constructor references, structural readout, and witness verification are separate research/verification work; their host costs are not included in native-network resource counts.

The new [finite typed grammar](../ic_typed_programs.py) admits Nat constructors with depth at most 2, nonempty Parallel width at most 2, at most 12 AST nodes, and AST depth at most 6. Validation checks complete source port matchings, the existing semantic type/polarity table, exact serialization schemas, malformed ports, aliases, and all bounds before execution. These are representation bounds, not an exhaustive-coverage claim. The selected ASTs are Check(0), Check(1), Check(2), Copy(0), Copy(2), Erase(2), Compare(0,0), Compare(0,1), Compare(1,0), Compare(1,2), Compare(1,1), Fanout(1,check,erase), Fanout(0,check,check), and Parallel(Check(0),Copy(1)). Fanout is actual source DUP-to-INIT/ERA dataflow. The independent comparison result is the EQ/GT/LT tag and abs(n-m); check results use the mathematical square-root interval.

Whole normalizations use FIFO, LIFO, and seeded selection with seed 17. The seeded policy specifies SplitMix64, rejection sampling, and swap-with-last live-pair indexing; it does not use Python's random library. Every case is bounded by 2,000,000 primitive interactions and 250,000 live cells. Peak means max(initial cells, cells after each atomic interaction). All accepted terminal graphs match independently constructed complete labeled port graphs, with zero cyclic wires and no extra components. Budgets and failures retain distinct statuses; incomplete cases are not accepted.

| Finite evidence family | Cases | Recorded primitive interactions | Initial cells | Peak live cells | Final cells |
|---|---:|---:|---:|---:|---:|
| Macro/package normalizations | 96 | 35,610 | 0–3,240 | 0–6,468 | 0–6,462 |
| Context-lifted frozen rule prefixes | 15 | 427,134 | 6,838–7,518 | 6,972–28,882 | 0–28,320 |
| Typed-program normalizations | 42 | 3,988,125 | 7,208–22,022 | 7,597–69,449 | 0–22,402 |
| Selected native activation normalizations | 12 | 3,165,222 | 6,174–12,264 | 11,254–92,752 | 10,374–32,392 |

The macro family has 32 independent constructors under each policy: M_n/M_n* for n=0..6; every selector index for widths 1..3; primitive copies of epsilon, gamma(epsilon,epsilon), Loop, and the real !Gamma code; primitive erasure of epsilon, gamma(epsilon,epsilon), delta(epsilon,epsilon), Loop, and the real Gamma; and one/two-output code decoding for those five original packages. Every declared exact interaction formula matched. M0 cancellation produces the empty graph in one interaction, with no pure wire cycle; M1 is a zero-cell identity wire with zero interactions. Copy/erase cost n+w uses auxiliary-to-auxiliary wire pairs w, not all internal wires. Real !Gamma copying costs 3,606 interactions; decoding real Gamma costs 441, and copying its code then decoding both products costs 4,488.

[ic_rule_trace_lifting.py](../ic_rule_trace_lifting.py) replays all 15 frozen source-rule certificates with a gamma frame at each original boundary, translating each newly allocated cell ID explicitly. The frame contributes 0–4 constant cells. Every prefix matches the independently constructed entire C[RHS], and measured contextual peak equals isolated peak plus frame size. Of these prefixes, 14 deliberately end with active context redexes; the empty ERA-Z case is terminal. These are selected finite C[LHS] ->* C[RHS] witnesses, not contextual normalization or arbitrary-context equivalence experiments. No rule certificate or original trace was changed.

The 14 source programs produce 42 primitive normalizations. Every source reference agrees with its independently constructed mathematical result. Its source trace supplies counts and pre-step source-symbol footprints; summing the frozen local witness lengths and censuses predicts the observed total primitive interactions and every primitive-rule count under all three policies. Their source traces collectively use every source-rule kind, without adding to or replacing the compiler coverage already recorded in section Q. Every terminal primitive graph is additionally decoded structurally without consulting source rules, checked for semantic port typing, and compared with the complete expected source output graph.

| Typed program | Source steps | Predicted native interactions per policy | Constructive staged peak bound | FIFO peak | LIFO peak | Seeded peak |
|---|---:|---:|---:|---:|---:|---:|
| Check(0) | 1 | 21,912 | 7,597 | 7,597 | 16,225 | 8,373 |
| Check(1) | 7 | 165,346 | 29,211 | 22,559 | 41,351 | 24,111 |
| Check(2) | 20 | 450,840 | 51,413 | 49,697 | 69,449 | 52,889 |
| Copy(0) | 1 | 20,964 | 7,724 | 7,724 | 16,046 | 8,320 |
| Copy(2) | 3 | 70,136 | 22,420 | 22,930 | 26,946 | 24,700 |
| Erase(2) | 3 | 30,360 | 14,552 | 14,552 | 14,552 | 14,552 |
| Compare(0,0) | 2 | 32,629 | 11,000 | 11,000 | 18,608 | 11,000 |
| Compare(0,1) | 2 | 32,557 | 14,674 | 14,674 | 22,456 | 14,674 |
| Compare(1,0) | 2 | 32,345 | 14,674 | 14,674 | 22,396 | 14,674 |
| Compare(1,2) | 4 | 54,957 | 22,022 | 22,022 | 23,820 | 22,022 |
| Compare(1,1) | 4 | 55,029 | 18,348 | 18,348 | 20,146 | 18,348 |
| Fanout(1,check,erase) | 11 | 230,050 | 36,775 | 26,301 | 55,959 | 27,505 |
| Fanout(0,check,check) | 3 | 64,788 | 15,114 | 14,536 | 24,066 | 15,350 |
| Parallel(Check(0),Copy(1)) | 3 | 67,462 | 22,213 | 22,393 | 31,279 | 24,999 |

The staged peak column is a constructive upper bound for the mathematical witness obtained by consecutively lifting source-rule certificates. That staged full-program trace is not executed here. Other interleavings can exceed it, as the table shows; that is not a failed bound on those other traces. A separate per-trace census bound, I+2*c_gd, is checked for every recorded interval. Exact final cells equal I+sum_r c_r*(rhs_cells(r)-2), native allocations equal sum_r c_r*rhs_cells(r), and total symbolic allocations include I. Runtime cells can be allocated only inside a primitive interaction. These count symbolic cells, not Python interpreter bytes or a finite physical stock.

The Parallel example tracks lineage in its actual global trace. Both components are disjoint, all their initial template cells are accounted for, and fresh cells inherit their interacting pair's owner. Each policy records the same 21,912 Check interactions and 45,550 Copy interactions. FIFO projected peaks are 7,597 and 15,252, whose sum 22,849 bounds global peak 22,393. LIFO projected peaks are 16,225 and 19,934, whose sum 36,159 bounds global peak 31,279. Seeded projected peaks are 8,019 and 17,242, whose sum 25,261 bounds global peak 24,999. These are actual projections, not separately scheduled component peaks; the seeded Check projection differs from the standalone seeded Check peak. The global final graph has 22,195 cells; native runtime allocations are 138,720 and total symbolic allocations are 157,119 under each policy. Shared M2 activation networks use one network owner and are not falsely partitioned into independent tasks.

The selected activation matrix uses the first frozen gate/carrier survivor and these prewired inputs under each policy:

| Numbers and flags | Interactions per policy | FIFO peak | LIFO peak | Seeded peak |
|---|---:|---:|---:|---:|
| (0), T | 59,800 | 11,254 | 16,466 | 12,608 |
| (2,0), TT | 597,843 | 58,556 | 92,752 | 61,424 |
| (1,0), FT | 84,696 | 11,640 | 16,526 | 12,842 |
| (1,2,0), TFT | 312,735 | 34,894 | 57,818 | 37,784 |

Every activation normalization passes the original complete-graph and native protocol checks: enabled/disabled outputs and statuses, constructor-readiness and required BR joins, grant/delivery/advance order, original program-code consumption, retained exact !Gamma at LIBRARY, and DONE as Loop. The FIFO observations agree with the earlier implementation; the added policies expand only this declared finite case list. They do not exhaust M2's input/flag/grammar bounds or prove all-schedule readiness ordering. Constructor recognition still permits later reconstruction/cleanup to overlap subsequent work.

Three negative boundaries are durable. Primitive copying deliberately bypasses the delta-free precondition on delta(epsilon,epsilon): a single delta/delta interaction yields two epsilon outputs rather than two original delta trees, and is recorded as wrong-normal-form with the entire counterexample. The public valid-copy constructor separately rejects that payload. The fresh-ID probe executes a valid contextual INIT-Z prefix of 34 interactions, then rejects stale pair (c7497,c7517); the required renamed pair is (c7497,c7518). No rejected pair is executed, and the prefix is explicitly nonterminal. Finally, the activation input-zero records have the same complete reference normal form and 59,800 interactions but different peaks, refuting the inference that equal work and result imply schedule-independent peak space. This last probe derives from existing positive records and adds no interactions.

The archive is [composition_certificates.json.gz](../results/composition_certificates.json.gz), with [composition_certificates.ictrace.gz](../results/composition_certificates.ictrace.gz). It contains 150 passing whole normalizations, 15 matched contextual prefixes, the one-interaction negative copy, and the 34-interaction fresh-ID prefix: 167 trace intervals and 7,616,126 raw pair records. The pair-record SHA-256 is c390074ec62c3cf042451d9007e4c65fb0b76f25992cd88d479e92d2ffc61a09; the compressed report SHA-256 is dab2c7cac04220b8d2719e8e2eb812d41a6d4ebf2fb0c98350736aa100e35a33. Full CLI verification reconstructs the same bindings and policies, independently checks source/reference results, replays every pair, repeats allocation/census/projection checks, and compares every report field. Policy descriptors are included in the contract covered by the trace header's bindings digest.

Local acceptance passed generation and a complete independent CLI replay of all 7,616,126 pair records with exact report equality. No positive case exhausted its fixed budget, and no frozen input, report, or trace was modified.

The integrity suites are [typed_programs_integrity.py](../tests/typed_programs_integrity.py), [schedule_audit_integrity.py](../tests/schedule_audit_integrity.py), and [composition_evidence_integrity.py](../tests/composition_evidence_integrity.py), with 14, 8, and 5 test groups respectively. They include invalid AST/interface/type rejection, source-evaluator-free builders, original-rule comparisons, representative commuting redex contexts, FIFO fidelity and seeded reproducibility, runtime-policy/contract mismatch rejection, ownership/host-allocation rejection, wrong complete graphs, cutoffs, report/resource mutations, and header/order/truncation/trailing trace corruption. Small fixtures are actual native executions and replays; the complete new archive is replayed separately. All 36 commands in the frozen M2 regression runner passed, including the original input-81 primitive replay and all frozen discovery, bridge, activation, coherent-rule and context evidence. The existing CI runner appends the three new integrity suites and full M3 replay, without an external solver or new compute dependency.

This section establishes explicit abstract-model composition arguments and finite implementation evidence with resource records. Large-network execution remains a selected-policy experiment, not exhaustive schedule exploration. The conditional abstract uniform-normalization theorem does not retroactively relabel historical FIFO archives as universally verified Python executions. M1 offline archive reconstruction, M2 local readiness, physical inventory, arbitrary-context equivalence, optimality, general semantic discovery, polynomial/complex-structure derivation, and a demonstrated reuse benefit retain their separate boundaries.

## U. Multiple observation contracts and discovered composition (E_multitask)

[ic_multitask_discovery.py](../ic_multitask_discovery.py) implements M4 with a frozen finite prior and independently specified Boolean, copying, erasure, and representation-adapter contracts. [MULTITASK_DISCOVERY.md](MULTITASK_DISCOVERY.md) describes construction and replay; [COMPOSITION_LEMMAS.md](COMPOSITION_LEMMAS.md) supplies the abstract-model lifting basis. The program architecture is a declared consumer environment, not an automatically synthesized architecture. Components are enumerated, observed, selected, and loaded as their original graph syntax; no successful gate is manually substituted after search.

Representation A has false=epsilon and true=gamma with its auxiliaries joined as Loop. B is the ordered package gamma(epsilon,A). Both have exactly 2 admitted values and are delta-free principal packages. The 36 contracts comprise every 2-input Boolean function A×A→A (16 masks), every unary Boolean function for every ordered source/target A/B pair (16 contracts), and copy/erase on A and B (4 contracts). Binary mask bits correspond to inputs 00,01,10,11; unary mask bits correspond to 0,1. Mask 8 is AND; unary mask 2 preserves the Boolean value across the declared representation change.

[ic_component_candidates.py](../ic_component_candidates.py) enumerates all complete port matchings for ordered cell-kind tuples over epsilon/gamma/delta. There is no semantic, connectedness, reducedness, or isomorphism filter. Initial detached wire cycles are excluded (`cycles=0`), while cyclic principal wiring and all subsequently produced pure wire cycles remain represented. Literal syntax duplicates under cell renaming are deliberately retained. The input-only weak observation is the first all-false tuple; the remaining fixed tuples refine the same contract.

| Interface family | Interface | Declared cells | Literal candidates | Contracts | Candidate/contract assignments |
|---|---|---:|---:|---:|---:|
| Binary Boolean | LEFT, RIGHT, OUT | 0–1 | 33 | 16 | 528 |
| Unary Boolean / adapter | IN, OUT | 0–2 | 484 | 16 | 7,744 |
| Copy | IN, OUT1, OUT2 | 0–1 | 33 | 2 | 66 |
| Erase | IN | 0–1 | 7 | 2 | 14 |
| Total | | | 557 | 36 | 8,352 |

Port parity makes some requested cell counts empty; the ledger retains the complete grammar rather than privileging known wiring. Native observation is shared only when candidate, input representation, and supplied tuple are identical. Thus the assignment matrix uses 2,228 distinct FIFO observations rather than calling a reducer separately for every expected function. Their entire initial/final graphs, trace intervals, primitive censuses, allocation counts, and resource outcomes are retained. Initial sizes range 1–5 cells, observation interactions 0–128, and observed atomic-state peaks 1–129 cells. These observations contain 10,804 recorded interactions.

The observation bounds are 128 interactions and 128 live cells. Of the observations, 2,148 reach normal forms, 64 demonstrate material violations at 129 live cells, and 16 stop incomplete at the interaction budget. The latter are replayable unfinished prefixes, not divergence or impossibility certificates and not passing cases. Nevertheless every candidate/contract assignment has a decided outcome: the affected assignments also have a different concrete wrong-normal-form or material-violation case. Rejection selects that concrete case and never uses an incomplete observation as its counterexample. No assignment remains incomplete, and no elementary budget was enlarged after search.

The weak observation leaves 586 compatible candidate/contract assignments. Full input refinement and verification reject 416 of those. Overall, 170 assignments are verified and 8,182 have concrete rejection evidence. These are literal candidate/contract pairs, not 170 semantically distinct components. In the actual archive every rejection has its first concrete counterexample; all verified input instances additionally pass exhaustive scheduling. The report exposes every individual case status, so FIFO compatibility and subsequent all-schedule outcomes can be distinguished without treating a weak observation as a certificate.

The complete function coverage is:

| Contract group | Verified literal candidates |
|---|---|
| Binary A×A→A masks 0..15 | 0,0,0,0,0,0,0,0,4,0,1,0,1,0,0,0 |
| Unary A→A masks 0..3 | 14,0,38,2 |
| Unary A→B masks 0..3 | 0,0,2,0 |
| Unary B→A masks 0..3 | 32,0,14,10 |
| Unary B→B masks 0..3 | 0,0,44,0 |
| Copy A, Copy B | 2,2 |
| Erase A, Erase B | 1,3 |

Exactly 15 contracts have verified candidates; the other 21 have no verified candidate in this fixed syntax and resource environment. Binary masks 10 and 12 are the right and left projections. In particular, no candidate is verified for OR or NOT in this prior. This is a finite-prior result, not an IC expressiveness limitation. The contracts, syntax, inputs, and graph postconditions were not narrowed to relabel those outcomes as success.

All 352 distinct verified elementary input instances are explored over every active pair under fixed limits of 4,096 quotient states, 32,768 attempted transitions, and 128 live cells. Every exploration is complete and acyclic, with the independent complete normal form at every terminal. State counts range 1–63, transitions and attempted transitions 0–136, atomic peaks 1–13 cells, and longest interaction paths 0–13. Total attempted transitions are 3,980. This is concrete all-schedule evidence for those elementary instances, not exhaustive exploration of the later composed/compiler networks.

The selected library uses the lowest verified literal fingerprint per required contract. The roles are AND on A, Copy A, A→B identity adaptation, Copy B, Erase B, and B→A identity adaptation. Copy A and Copy B select the same literal delta graph but retain separate representation contracts and witnesses. The selected AND is a gamma whose principal receives RIGHT, with LEFT at auxiliary 1 and OUT at auxiliary 2. The selected A→B adapter has gamma/epsilon cells; the selected B→A adapter has epsilon/gamma cells. These descriptions are observations of selected graph specimens, not generator restrictions. Full literal graphs, fingerprints, and source witness IDs are in the report.

Every verified B eraser is a variant: delta with its auxiliaries joined, epsilon, and gamma with its auxiliaries joined. Their fingerprints in variant order are 1bcd655e9ff66a6b1d2095cf9ab76559166b66b0010eb1200bef19df9bccb8fe, 96046a32808f434fc25b2c19280aca7b3eb65e833f03fccf11d1824694856b0d, and eea142ff5908bfd482c8d58d5a915fa2082428f6dcb327ae4ef45062cb08c63b. Selection is by fingerprint, not by post hoc cost optimization.

[ic_discovered_programs.py](../ic_discovered_programs.py) builds one fixed linear DAG. It copies a, computes AND(a,b) and AND(a,c), ANDs their results, adapts A→B, copies B, erases one copy, and adapts the other B→A. Its complete reference output is A(a AND b AND c). All component instances precede the three supplied input tokens in construction, and no constructor evaluates an answer. Missing/wrong representations, incorrect truth masks or interfaces, stale graph fingerprints, repeated consumers including reused external outputs, and forward/cyclic dependencies are rejected. Runtime only selects primitive pairs in the one prewired graph.

[ic_component_witnesses.py](../ic_component_witnesses.py) constructs actual staged global traces by matching input-value footprints, binding each original candidate instance, and translating the discovered local pair sequence with fresh-cell renaming. Local and context cell sets are disjoint. It checks every ordered port and wire, fresh-allocation counts/kinds, unchanged outside cells and non-interface wiring, exact local outputs, and disjoint output packages. These are recorded primitive interactions of the global initial graph; separate reference instances are verifier tools. Constant outside size makes each stage's global cell count equal its local count plus that exterior size, so the maximum of those local peaks plus context equals the measured staged global peak. Other schedules have their own peaks.

| Positive execution family | Cases | Recorded interactions | Initial cells | Peak live cells | Final cells |
|---|---:|---:|---:|---:|---:|
| M1 ready-input code baselines, false/true | 2 | 8,109 | 3,242 | 3,242–5,880 | 2–5,874 |
| Discovered DAG staged witnesses | 24 | 381 | 13 | 13–15 | 1 |
| Discovered DAG FIFO/LIFO/seeded joint runs | 72 | 1,143 | 13 | 13–17 | 1 |
| Compiler-facing staged witnesses | 8 | 29,976 | 3,254 | 3,254–5,880 | 2–5,874 |
| Compiler-facing FIFO/LIFO/seeded joint runs | 24 | 89,928 | 3,254 | 3,254–6,470 | 2–5,874 |

The small matrix covers all 8 triples and all 3 B-eraser variants. The native step/live-cell bounds are 4,096/256 for each whole small case. Its 24 staged witnesses comprise 192 local-stage prefixes. The joint policies are FIFO, LIFO, and SplitMix64 seeded selection with seed 17. Every joint run matches the entire independent A output and exactly the staged sum of primitive-rule censuses and interactions. No host stage transition or runtime rebuild occurs.

| B-eraser variant | Interactions per small case | Staged peak | Joint-policy peak |
|---|---:|---:|---:|
| Delta auxiliary self-wire | 16–21 | 13–15 | 13–17 |
| Epsilon | 13–18 | 13–15 | 13–17 |
| Gamma auxiliary self-wire | 12–17 | 13–15 | 13–17 |

These same-contract local cost differences do not establish a net benefit of structure reuse. Search, compilation, exploration, proof/reference construction, and host memory are outside these symbolic native counts. Runtime allocations range 12–30 cells per small case; total symbolic cells allocated, including the initial network, range 25–43.

For the compiler-facing extension, the selected delta-eraser variant's computed A output controls the first frozen M1 gate and the real !Gamma copy_decode consumer. There is one original 3,231-cell code payload. A staged witness first lifts the complete small-DAG trace through that prewired body, then requires an exact whole-graph boundary map to an independently constructed M1 ready-input instance before replaying its code-consumer witness. All 8 staged compiler cases and 24 independent joint runs pass. Every joint run consumes all original code-payload cells. True produces two exact original Gamma objects (5,874 cells total); false produces two epsilons. No extra component or pure wire cycle remains.

Each complete compiler case has bounds of 100,000 interactions and 20,000 live cells; staged parts share the remaining whole-case interaction budget. Each joint native count/census matches the sum of the discovered-DAG witness and the appropriate M1 ready-input baseline. Native runtime allocations range 4,020–11,638 and total symbolic allocations 7,274–14,892. The two standalone M1 baseline costs are 3,620 interactions for false and 4,489 for true. Their code-consumer behavior is reused under its frozen representation contract, without inferring new source-extension activation/erasure semantics.

| Input abc | Interactions per compiler case | Staged peak | FIFO peak | LIFO peak | Seeded peak |
|---|---:|---:|---:|---:|---:|
| 000 | 3,638 | 3,254 | 3,256 | 3,256 | 3,256 |
| 001 | 3,637 | 3,254 | 3,254 | 3,256 | 3,256 |
| 010 | 3,637 | 3,254 | 3,254 | 3,256 | 3,256 |
| 011 | 3,636 | 3,254 | 3,254 | 3,256 | 3,256 |
| 100 | 3,641 | 3,256 | 3,258 | 3,256 | 3,256 |
| 101 | 3,638 | 3,256 | 3,256 | 3,256 | 3,256 |
| 110 | 3,640 | 3,256 | 3,256 | 3,256 | 3,256 |
| 111 | 4,509 | 5,880 | 5,880 | 6,470 | 5,998 |

Exact primitive resource balances and the per-trace I+2*c_gd peak bound are checked throughout. The staged peak is not applied as a bound to the other policy traces; the table contains counterexamples to doing so. The counts refer to initial and post-atomic-interaction symbolic cells, including every future component and code consumer, not interpreter bytes or a physical stock of parts.

Two durable negative boundaries reuse existing observation intervals. The selected delta B eraser, applied without an adapter to A(true), performs 3 interactions and leaves zero cells but one closed wire cycle, not the empty graph; its interval is [10786,10789). The weak-observation survivor with fingerprint 01ae8b67c5ed06aa6bce79395039e535c5ea9c97f84bbe0cc90632fdf06b5648 agrees with the first false-input observation for unary A→A constant false, but returns Loop on true in 4 interactions, interval [5437,5441). Neither is counted as a valid component in the refuted contract. These also show why node counts, weak probes, and interface shape alone are insufficient replacement evidence.

The archive is [multitask_discovery.json.gz](../results/multitask_discovery.json.gz) with [multitask_discovery.ictrace.gz](../results/multitask_discovery.ictrace.gz). The raw stream has 140,341 pair records: 10,804 search-observation interactions and 129,537 positive baseline/composition interactions. Pair-record SHA-256 is 0894dea99e03f1cf8f34837c30ee61b08841fce7ed2b2d4e08051ea146afd04c. Compressed report SHA-256 is 10b65298e08c366e4a5da7ba00a14caf03e7fd6115fc2e818d77c8e42b64b08e. Generation and a complete independent CLI replay passed with exact report equality, including every rejected, resource-limited, and unfinished search prefix. No incomplete observation is a passing computation, and no candidate/contract assignment is accepted on incomplete evidence.

The new integrity suites are [component_candidates_integrity.py](../tests/component_candidates_integrity.py), [observation_contracts_integrity.py](../tests/observation_contracts_integrity.py), [discovered_programs_integrity.py](../tests/discovered_programs_integrity.py), [component_witnesses_integrity.py](../tests/component_witnesses_integrity.py), and [multitask_discovery_integrity.py](../tests/multitask_discovery_integrity.py). Their respective test-group counts are 9,11,11,10,6. They test syntax completeness and literal identity, strict interfaces/values, oracle-free builders, linear typed DAG wiring, stale specimen fingerprints, actual discovered local-trace imports and reduced staged replay, exact boundary matchings and context preservation, fresh-name shifts, allocation/budget handling, and tampered contracts, policies, traces, graphs, and resource fields. The reduced fixture is not the full matrix; the CLI independently replays that matrix in the existing CI runner.

The unchanged M3 baseline, including all 40 original runner commands, completed successfully on GitHub Actions for both main and its research branch before M4 acceptance (commit 67b7b608d6888af0da7bcd932fa1d06a97e34193). M4 changes no prior reducer, implementation, report, or trace; it appends its integrity suites and complete replay to the existing runner. No new dependency, external solver, or compute service was added.

This establishes bounded discovery under distinct observation contracts and explicit composition of selected discovered specimens into native computation and real compiler-code consumers. The written abstract-model arguments remain conditional on faithful implementation; selected-policy composed execution is not exhaustive large-network implementation verification. Arbitrary semantic synthesis/context equivalence, full source activation extensions, physical inventory, and polynomial/complex-structure derivations remain separate objectives. The finite evidence-indexed library and common-cost rebuilding/copying/reuse comparison are delivered in section V; general libraries and universal benefit claims remain open.


## V. Evidence-indexed structure library and native reuse (E_structure_library)

M5 freezes M4's verified assignments and adds a representation/interface/evidence-scoped library and a common-cost experiment. The implementation is [ic_structure_library.py](../ic_structure_library.py), [ic_structure_capsules.py](../ic_structure_capsules.py), [ic_reuse_benchmarks.py](../ic_reuse_benchmarks.py), and [ic_structure_reuse.py](../ic_structure_reuse.py). The [guide](EVIDENCE_INDEXED_STRUCTURE_LIBRARY.md) states the contract, conditional census derivation, acquisition convention, and remaining boundaries. This is a new environment, not a revision of the earlier experimental environments or their budgets.

The immutable raw catalog contains all **170** verified M4 graph/contract pairs over **115** distinct graph specimens. Verification freshly compares every field against the frozen report and replays the union of **352** referenced FIFO observations, **1,204** primitive interactions. Finite all-schedule summaries are imported from the unchanged, previously verified M4 evidence; M5 does not rerun that entire exploration or extend its scope to packaging. Exact input/output representations, ordered interface, task, and minimum evidence tier govern retrieval. Shared physical graphs retain separate semantic entries. Nested state is immutable and exported JSON is detached. The catalog uses a linear exact filter: the six workload queries examine 1,020 entries, with no claimed lookup speedup.

Every graph is assessed without normalization or hand rewriting. There are **108 eligible and 62 unsupported logical entries**, corresponding to **82 eligible and 33 unsupported distinct specimens**. Unsupported original graphs remain in the raw library with reasons; a valid task implementation can still fail the passive principal-package representation needed by this capsule mechanism. Declared free interfaces, including disconnected bodies joined by the outer frame, are allowed. Internal active/private cuts, vicious principal cycles, and detached wire cycles cannot be silently removed to make a package eligible.

The selected workloads use the actual frozen M4 AND, copy, eraser and adapter specimens, plus erasure of the original real Gamma object from M1. The latter is data erasure, not a new full source-feedback activation claim. Source graph, capsule, code and packet sizes are:

| Workload | Original cells | READY capsule cells | Code C cells | Packet P cells |
|---|---:|---:|---:|---:|
| and_A | 1 | 5 | 11 | 13 |
| copy_A | 1 | 5 | 7 | 9 |
| box_AB | 2 | 5 | 11 | 13 |
| copy_B | 1 | 5 | 7 | 9 |
| erase_B | 1 | 3 | 5 | 7 |
| unbox_BA | 2 | 5 | 11 | 13 |
| Gamma_erase | 2,937 | 2,939 | 3,233 | 3,235 |

Each packet P is gamma(C, GO Loop). Native delta copying followed by erasing one product produces a ROOT-connected archive specimen equal to P as a complete labeled port graph. **Six distinct FIFO producer traces** supply **seven typed artifact entries**; copy_A and copy_B share one physical producer but keep distinct source contracts. These prior native episodes cost **7,372 interactions and 18,034 total symbolic allocations**, recorded separately as shared acquisition for every strategy. Original source cells are consumed. Capture/import is an offline tool operation; the original archive network is not continued inside a benchmark. The artifact query also matches storage representation, storage interface, original activation interface and typed source contract. Seven queries examine 49 entries. Production evidence is FIFO only; requesting all-schedule production returns no match even when the raw component has finite all-schedule evidence.

The fixed acceptance matrix is **7 workloads ? 3 task counts (1,2,4) ? 3 strategies ? 2 reserve dispositions ? 3 schedules = 378 executions**. Schedules are FIFO, LIFO and the fixed SplitMix64/rejection seeded policy with seed 17. Inputs cycle through the declared truth table in fixed order; this is not a claim over all task sequences. Each execution has a budget of **200,000 interactions and 50,000 live cells**. All future inputs, tasks, dispatch gates, decoders, copy routers and reserve consumers are charged in its initial graph. Within each benchmark, a fresh native packet copy/erase producer and packet unpacker are included for every strategy. Literal reconstruction uses independently built copies of the same known raw capsule, not repeated discovery or compiler execution. Native fanout uses a balanced delta tree; retained_chain grants each reservoir before copying it to the current task and next stage. Both native strategies allocate exactly N code-copy routers. The final reserve is C without its GO packet wrapper, or no reserve under dispose_all.

All **378 executions and six producers passed** complete independent terminal-graph matching, exact rule-census prediction, primitive kind/allocation balances, budgets, original-source consumption and event checks. Targets include independent functional output values, every STATUS Loop, the precise reserve, all boundaries, all cells and cyclic-wire accounting. Each READY event occurs after all original unpack-frame spine cells have been consumed, and controls the next native grant. READY does not establish task completion: delta restoration, functional work and erasure may overlap. The explicit eraser-lineage count is a union of primitive events involving epsilon descendants of named consumers, not every decoder cleanup event. Every event remains charged once in the whole interaction count regardless of that attribution.

Resources are reported as I (whole initial cells), T (primitive interactions), A (total symbolic allocations including I), and P (peak after atomic interactions), alongside RHS allocations by kind, exact census, final retained versus nonreserve cells and erasure attribution. For fixed final size F, A=F+2T; A and T are consequently correlated rather than independent prices. The Pareto calculation does not attach a scalar monetary or physical-stock cost.

No native strategy dominates literal reconstruction on the full declared vector in any of the **126 comparison groups**. For every small-component group (**108 groups**), literal is the sole Pareto-front strategy. Native per-use interaction overhead over literal is **20** for and_A, **14** for either copy, **19** for either adapter and **11** for erase_B. Initial native cells equal literal for the AND/copy/adapters; erase_B needs two additional native initial cells per use. Native peaks for these small cases never improve on literal in the executed policies. These are concrete no-benefit results under the fixed protocol, not impossibility results for other representations or constructions.

Gamma trades initial/peak cells for work and total allocation. Both native strategies add **4,050 interactions and 8,100 total allocations per use** over literal. For FIFO, the complete measured vectors are:

| Disposition | Tasks | Strategy | I | T | A | P |
|---|---:|---|---:|---:|---:|---:|
| retain1 | 1 | literal | 6,182 | 10,395 | 24,024 | 6,284 |
| retain1 | 1 | native_fanout | 3,248 | 14,445 | 32,124 | 3,836 |
| retain1 | 1 | retained_chain | 3,248 | 14,445 | 32,124 | 3,836 |
| retain1 | 2 | literal | 9,125 | 13,564 | 30,363 | 9,193 |
| retain1 | 2 | native_fanout | 3,257 | 21,664 | 46,563 | 4,283 |
| retain1 | 2 | retained_chain | 3,257 | 21,664 | 46,563 | 4,239 |
| retain1 | 4 | literal | 15,011 | 19,902 | 43,041 | 15,073 |
| retain1 | 4 | native_fanout | 3,275 | 36,102 | 75,441 | 5,477 |
| retain1 | 4 | retained_chain | 3,275 | 36,102 | 75,441 | 5,029 |
| dispose_all | 1 | literal | 6,183 | 14,004 | 28,009 | 6,257 |
| dispose_all | 1 | native_fanout | 3,249 | 18,054 | 36,109 | 3,601 |
| dispose_all | 1 | retained_chain | 3,249 | 18,054 | 36,109 | 3,595 |
| dispose_all | 2 | literal | 9,126 | 17,173 | 34,348 | 9,190 |
| dispose_all | 2 | native_fanout | 3,258 | 25,273 | 50,548 | 3,974 |
| dispose_all | 2 | retained_chain | 3,258 | 25,273 | 50,548 | 3,896 |
| dispose_all | 4 | literal | 15,012 | 23,511 | 47,026 | 15,074 |
| dispose_all | 4 | native_fanout | 3,276 | 39,711 | 79,426 | 5,438 |
| dispose_all | 4 | retained_chain | 3,276 | 39,711 | 79,426 | 4,446 |

These figures include production, decoding, consumers and cleanup in each prewired run, in addition to the separately listed shared archive acquisition. Under retain1 Gamma leaves 3,233 reserve cells plus one STATUS cell per task; under dispose_all only the STATUS cells remain. The original Gamma erasure costs 3,165 interactions per task. Formula counts add native copy(C), decoder(capsule) and explicit reserve erasure to the original task census, and are independently checked against every actual rewrite.

Equal rule censuses do not fix peak: for Gamma with four tasks and retain1, LIFO peaks are **15,013 / 14,859 / 14,859** for literal / fanout / chain; seeded peaks are **15,127 / 6,049 / 5,755**, compared with the FIFO row above. Across all groups, retained_chain has a lower peak than native_fanout in **96**, the same in **21**, and a higher peak in **9**; it is not uniformly the best schedule arrangement. For the **18 Gamma groups**, the Pareto front contains all three strategies in **7**, literal plus chain in **8**, and literal plus fanout in **3**. All original groups and vectors remain in the report, including the counterexamples to a universal preferred strategy.

Two durable negative probes alter the common fixture: epsilon in place of GO terminates in a wrong complete graph after **63** interactions, and swapped gate control/data wiring does so after **56**. Their exact initial/reference/actual graphs and raw intervals are retained. Unit tests separately cover incomplete and resource-violation statuses, invalid representations and interfaces, false evidence-tier escalation, changed resource/graph/provenance/report fields, and changed trace records. Earlier source-expansion/epsilon counterexamples remain unchanged evidence; this milestone does not infer a full disabled source state merely from absence of code.

The archive is [structure_library.json.gz](../results/structure_library.json.gz), [structure_reuse.json.gz](../results/structure_reuse.json.gz), and [structure_reuse.ictrace.gz](../results/structure_reuse.ictrace.gz). The stream contains **1,260,852 raw pair records**: 7,372 producer interactions, 1,253,361 benchmark interactions and 119 negative-probe interactions. Pair-record SHA-256 is `e5a893d95ac18a5e49a0a39b499d5a7e7d6c1ad1f08e5c6dac153620be4f8409`. Compressed-file SHA-256 values are respectively `0c5ed5643cfb73d0d17ee688a80b33296c3818394a59a561ae80b62082b71255`, `8c7d797a5ec3109cf2d5d4af724963367fa9914f0ad6613f8932450bab953f1b`, and `887a827c0a55718c894828626c2972c88d0a395f765aa30e14296842993caf10`. Generation and a complete independent CLI reconstruction/replay passed with exact semantic report and manifest equality, every primitive pair, resource record, event, graph fingerprint and EOF accounted for.

The four new integrity suites contain **9, 8, 8 and 7** groups respectively: [catalog](../tests/structure_library_integrity.py), [capsules](../tests/structure_capsules_integrity.py), [constructors](../tests/reuse_benchmarks_integrity.py), and [reuse/report](../tests/structure_reuse_integrity.py). All passed locally. Capsule checks include the real Gamma complete graph round trip and two separately activated native code copies, with independent references, disjoint full outputs and consumed source cells. The original M4 baseline's **46 runner commands** were already green on main and its research branch at commit `491faa9292727cb42ee90456ccb830d4829901d6`; M5 changes no earlier reducer, implementation, report or trace, and appends its suites and complete replay to the same existing CI runner. No dependency, external solver, proof tool, or compute service was added.

This establishes a finite reusable structure catalog, native storage production, prewired staged code use and measured resource tradeoffs. The arithmetic remains conditional on the abstract proper-package/composition hypotheses and faithful implementation. Larger program activation, arbitrary-context replacement, all-schedule composed execution, general semantic discovery, a general runtime-formed structure library, physical finite inventory and universal or optimal reuse benefit remain independent research obligations.
