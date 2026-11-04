# Claim ledger and proof boundaries

This document separates results that have executable evidence from claims that remain unproved.

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

`ic_primitive_port_verifier.py` implements the six original interaction rules over explicit port graphs. The remaining IC demo scripts test:

- copying finite gamma/epsilon constructor trees;
- copying delta-free reduced packages with internal wiring;
- erasing finite trees with an epsilon interaction structure.

These are actual gamma/delta/epsilon reductions. They are not a compilation of the 14-symbol source system.

## C. Source-level Lafont decomposition

`lafont_phi_psi_split.py` constructs 15 noncanonical source-level phi/psi/sigma splits. It reconstructs each original RHS exactly. The sigma widths are 0 in 10 rules, 1 in 4 rules, and 2 in 1 rule, for six crossing strands total.

The JSON output is a source-level split specification, not an IC target graph.

## D. Conditional macro budget

`lafont_macro_budget_v2.py` counts one specified set of Figure-10 macro expansions and epsilon fillers for undefined rule entries. Its current conditional budget is:

- decoded Gamma: 1549 gamma + 147 delta + 1241 epsilon = 2937 cells;
- delta-cut Gamma-prime: 442 free ports;
- encoded delta-free package: 1990 gamma + 1241 epsilon = 3231 cells.

The script checks package port-parity constraints. These counts are conditional static accounting, not a generated or reduced complete IC graph. Alternative macro conventions or a different valid decomposition may change the budget.

## E. Not yet established

The project does **not** yet contain:

1. the fully expanded IC port graph for the Figure-10 compiler;
2. a concrete IC decoder graph with a reduction certificate `!Gamma -> Gamma`;
3. 15 rule-by-rule IC simulation certificates;
4. the compiled IC initial graph for input 81;
5. a reduction of that graph to the encoded `SQ(9)` result;
6. an automatic compiler from polynomial-term structure to the source rule package;
7. a derivation of the three-cycle or `J^2 = -I` from the polynomial's initial IC graph.

The project therefore establishes source-level feedback and several primitive IC mechanisms, but not yet a complete source-to-IC feedback compiler or emergent complex structure.
## F. Lossless source-net storage in primitive IC (structural bridge)

`source_ic_structure_encoding.py` provides a concrete, injective **ordered representation** of finite, fully paired source port nets using only primitive `gamma`/`epsilon` nodes and wires. The representation records source symbol tags (not source evaluator functions), ordered ports, boundary positions, and the complete wire matching. It does not consult source rewrite rules or output values to encode a net. A structural decoder recovers the source snapshot exactly.

One primitive IC `delta` attached to the root of that *closed, delta-free reduced package* duplicates the encoding, and one `epsilon` erases it, using **only primitive IC reductions**. Tests exercise the 15 source-rule RHS nets, initial source nets for `N=0..200`, and 60 arbitrary typed port matchings (including cycles and disconnected components). For copying/erasing this particular representation, the observed count is `payload_IC_cells + original_internal_wire_pairs`; this is an encoding/copy resource count, **not** a source square-checker reduction count.

For `N=81`, the initial source structure encodes as **533 gamma/epsilon IC cells**, containing **83 original source wire pairs**. Copying or erasing it takes **616 primitive IC reductions**. These numbers represent the encoded **initial problem data only**; they do not imply an IC computation of `SQ(9)`, a runtime rule compiler, or an output decoder. The representation's node order and boundary order are part of its chosen syntax, not canonical graph-isomorphism invariants. Source symbolic types are represented as unary data tags, not active IC node kinds.

**New bridge achieved:** source program graphs can exist *as data* inside literal 3-symbol IC nets and be copied/erased locally. **Open:** produce local IC machinery which interprets or compiles the source rules into runtime reductions, with 15 per-rule simulation certificates and the concrete `81 -> SQ(9)` IC trace. The earlier Figure-10 macro budget and full compiler proof gaps remain unchanged.

## G. Four SOURCE rules operationally refined to primitive IC

`ic_unary_operational_fragment.py` defines a separately typed, closed-net operational refinement for source symbols `Z,S,DUP,ERA`. The representation is `Z -> epsilon`, `ERA -> epsilon`, `DUP -> delta`, and `S(x) -> gamma(x,epsilon-tag)`. The source type/polarity context distinguishes `Z` and `ERA`; **the raw target graph alone does not injectively distinguish them**, and the translation is restricted to well-typed source nets of this fragment.

All four source rules (`ERA-Z`, `ERA-S`, `DUP-Z`, `DUP-S`) have independently translated IC LHS and RHS structures and primitive reduction certificates of length **1, 2, 1, and 2** respectively. A local certificate checks colored-free-port graph isomorphism. In addition, the test checks **400 randomly wired well-typed closed source contexts**, independently computes their expected source one-step result, and compares it with primitive IC reduction. Complete unary copy and erase programs `S^n(Z)` are tested for `n=0..200`; an entire closed copy-then-erase program also reduces without invoking any source rules at runtime.

This constitutes genuine partial operational compilation for **4 of 15 source rules**, **not** a compiler for the 14-symbol square checker or a derivation of imaginary numbers. The other 11 rules, including INIT, CMP, GATE and output representation, remain open. The theorem is a one-step refinement for the four-rule typed sublanguage, not a proof that arbitrary untyped IC contexts reflect valid source interactions. Source-level success and compiled IC success must still be separately distinguished.

## H. Pure IC signed unary cancellation; observable before global quiescence

`ic_signed_unary_comparator.py` constructs two independently specified gamma/epsilon unary chains oriented in opposite directions, each with a gamma/epsilon *zero sentinel*. The two outer principal ports are connected to form one gamma-gamma active pair. The builder uses `m` and `n` **only as independent chain lengths**; it neither compares them nor constructs an answer-specific result. The original six IC rewrite rules are the only runtime operations.

**Inductive mechanism.** While both chains have an unmatched gamma, a gamma-gamma collision splices the two continuation ports (left auxiliary 1 to right auxiliary 2) into the next collision and separately connects their two epsilon tags. Each collision thus creates exactly one independent epsilon-epsilon garbage redex. With `k=min(m,n)+1`, including the two zero sentinels, exactly `k` gamma-gamma collisions take place. The two observation boundaries then connect directly when `m=n`, otherwise via an oriented chain of `|m-n|` surviving gamma/epsilon pairs. Entering from boundary A through gamma auxiliary 1 means `m>n`; entering through gamma principal 0 means `m<n`. The residual chain length is exactly `|m-n|`. The output path contains no active pairs, and epsilon-tag garbage is disconnected from it. All remaining `k` epsilon-epsilon redexes may be reduced in any order without affecting the observation.

Therefore the **complete** IC reduction count is `2*(min(m,n)+1)`; if the causal gamma frontier is reduced first, the result becomes readable after `min(m,n)+1` interactions, *strictly before total quiescence*. This is an observer-extracted fact, not a signal propagated to a source `GATE` or `CMP`. The observer traverses a possibly long output path: it is a read-only macro observation, **not** a constant-time local cell detecting the sign or magnitude.

Tests run all `0<=m,n<25` under three reduction policies (1,875 runs), plus eight larger edge cases with randomized schedules and explicit early-read audits. These are finite tests backed by the elementary inductive wiring argument; they are not exhaustive model checking of arbitrary IC contexts. The comparison encodings are distinct from the typed four-rule embedding in section G; no adapter or `CMP` source-rule simulation is currently implemented. This achievement should not increase the count of source rules operationally compiled, which remains **4/15**.
