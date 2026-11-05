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
