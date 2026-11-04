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
