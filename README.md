# Local Native Computing: Interaction Combinators and local feedback

Research code and reproducible audits for a local-computation approach based on Lafont's Interaction Combinators (IC).

**Current boundary:** the repository validates a finite source-level feedback system and several genuine three-symbol IC mechanisms. It does not yet contain a complete IC compilation of the source feedback program. See [the claim ledger](docs/CLAIM_LEDGER.md) before interpreting any result.

## Quick start

```sh
python -m pip install -r requirements.txt
bash tests/run_all.sh
```

The scripts are also runnable individually. The test suite uses Python 3.11+ and NetworkX 3.6.1.

## Repository layout

- `source_feedback_audit.py`, `source_rule_audit_v3.py`: source-level feedback simulator and rule audit.
- `ic_primitive_port_verifier.py`: literal gamma/delta/epsilon port-graph reducer for the six Lafont rules.
- `source_ic_structure_encoding.py`: lossless source port-net **data** encoding in primitive gamma/epsilon IC, with native delta copying and epsilon erasure; not a source-to-IC evaluator.
- `ic_unary_operational_fragment.py`: genuine operational IC simulations for four typed source rules `ERA-Z`, `ERA-S`, `DUP-Z`, `DUP-S`, with context checks.
- `ic_signed_unary_comparator.py`: original complementary unary-chain comparator using only primitive IC gamma/epsilon annihilations; signed difference is read from its stable residual topology.
- `ic_gamma_tree_copy_demo.py`, `ic_reduced_package_copy_demo.py`, `ic_tree_erase_demo.py`: primitive IC copy/erase experiments.
- `lafont_sigma_width_audit.py`, `lafont_phi_psi_split.py`, `lafont_15_rules_phi_psi_split.json`: source-level rule decomposition data.
- `lafont_macro_budget_v2.py`: conditional static accounting for one proposed Figure-10 macro expansion.
- `docs/CLAIM_LEDGER.md`: what is established, what is only conditional, and what remains open.
- `.github/workflows/audit.yml`: runs all audits on pushes and pull requests.

---

# IC local feedback research: independently runnable audit (2026-11-04)

## Scope

This bundle contains **two distinct levels** of formal graph rewriting:

- `source_feedback_audit.py` and `source_rule_audit_v3.py` validate the **14-symbol / 15-rule source interaction system**, including its finite unary-square-checking feedback.
- `ic_primitive_port_verifier.py`, `ic_gamma_tree_copy_demo.py`, `ic_reduced_package_copy_demo.py`, and `ic_tree_erase_demo.py` implement and test **actual three-symbol Lafont IC reductions** (gamma, delta, epsilon). They do **not** compile the source system into IC.
- `lafont_phi_psi_split.py` constructs the **15 complete source-level noncanonical phi/psi/sigma port splits**, and checks their exact reconstruction. The resulting JSON is **not yet an IC target port graph**.
- `lafont_macro_budget_v2.py` computes a **conditional static node budget** for the particular Figure-10 macro choices. It checks all 30 single-port subpackage parity conditions. It is **not** an operational IC simulator for the compiler or a per-rule reduction certificate.

## Important correction

The previous `ic_feedback_audit_bundle.zip` reported **197 delta** in the decoded Gamma package and **592 exposed ports** after the delta cut. Those figures are **obsolete**. Its accounting incorrectly used the **source interaction interface width `arity(A)+arity(B)`** for the `T_sigma` macro. In the supplied noncanonical Figure-6 split, sigma only acts on **cross-half wiring strands**. Their widths are 0 in 10 rules, 1 in 4 rules, and 2 in 1 rule. This changes the T_sigma contribution from 52 delta to **2 delta**. With epsilon fillers for 166 undefined entries and the specified standard macro choices, the revised budget is:

- Decoded `Gamma`: **1549 gamma + 147 delta + 1241 epsilon = 2937 cells**.
- Cut `Gamma'`: **442 free ports** (3*147 + 1), with no delta.
- Encoded `!Gamma`: **1990 gamma + 1241 epsilon = 3231 cells**, with no delta.

These counts use algebraic macro expansions and port-parity verification. **No completed Figure-10 IC port graph has been built or independently reduced yet.**

## Running

Requires Python 3.11+ and NetworkX 3.6.1. In the repository root:

```sh
bash tests/run_all.sh
```

Individual scripts can also be run:

```sh
python source_rule_audit_v3.py
python source_feedback_audit.py
python ic_primitive_port_verifier.py
python ic_gamma_tree_copy_demo.py
python ic_reduced_package_copy_demo.py
python ic_tree_erase_demo.py
python source_ic_structure_encoding.py
python ic_unary_operational_fragment.py
python ic_signed_unary_comparator.py
python lafont_sigma_width_audit.py
python lafont_phi_psi_split.py
python lafont_macro_budget_v2.py
```

- The IC primitive verifier checks the six original rules and **1160 two-redex local diamonds** (paired port contexts, with cyclic-wire handling).
- The IC gamma-tree copier checks balanced full binary trees to depth six and **200 random ordered irregular trees**. Copying an original delta-free gamma/epsilon constructor tree with `n` cells takes exactly `n` IC interactions and yields two disjoint copies. For full balanced trees, the maximal parallel redex layers have sizes `1,2,4,...,2^depth`; no clock is needed to perform the transitions.
- The IC reduced-package copier checks a gamma node with a self-wire, a 3-gamma package with two non-tree internal wires, and **200 randomly generated delta-free wired reduced packages**. For these packages, IC copying takes exactly `#gamma + #epsilon + #internal_wiring_pairs` interactions and reproduces two disjoint, structurally identical copies. The deltas at internal wiring pairs annihilate via the original delta-delta rule.
- The IC tree eraser checks **200 random gamma/delta/epsilon trees**. One epsilon on the principal root erases the tree in exactly `n` interactions for a tree with `n` cells.
- The source square checker validates `N=0..200`, including `81 -> SQ(9)` in 279 **source** interactions, not IC interactions.

## Source

Yves Lafont, *Interaction Combinators*, Information and Computation 137 (1997), 69-101, DOI: 10.1006/inco.1997.2643. Relevant figures: 2, 4-10.

## New: structural source-net encoding (not source-rule execution)

`source_ic_structure_encoding.py` produces fully paired primitive IC gamma/epsilon packages from arbitrary finite source-node port matchings, retaining source node tags and ordered wire topology. All 15 source-rule RHS structures and source initial states for N=0..200 round-trip exactly. A primitive IC delta/epsilon copies/erases the encoded **data** using only IC rewrites. For the initial N=81 source structure: 533 IC payload cells + 83 source wires = 616 IC copy/erase steps. This **does not compute SQ(9)**; the source rewrite interpreter/compiler and local runtime execution remain open.

## New: four-rule **operational** compiler fragment

The typed unary sublanguage `{Z,S,DUP,ERA}` now has four source-rule certificates executed **only by primitive IC**: `ERA-Z` (1), `ERA-S` (2), `DUP-Z` (1), and `DUP-S` (2) primitive reductions. They are checked on local interfaces and randomized typed closed contexts, with unary copying, erasure, and closed copy-then-erase programs. The embedding uses `Z -> epsilon`, `ERA -> epsilon`, `DUP -> delta`, and `S -> gamma(child,epsilon)`. The two epsilon source symbols are distinct by source typing, not by their bare IC encoding. This remains a **restricted typed fragment**, not an operational lowering for the full 14-symbol source program.

## New: signed unary comparison by native IC (component only)

Complementary gamma/epsilon unary chains cancel via gamma-gamma interactions and expose a stable oriented residual wire path. Two boundary endpoints distinguish equal, greater-than, and less-than; the residual gamma count is the exact absolute difference. For two lengths `m,n`, the system performs `min(m,n)+1` gamma collisions and the same number of independent epsilon-epsilon cleanups. The result can be read **before** the cleanup ends, with no source rule interpreter at runtime. Unlike the four-rule unary fragment, this is a **separate component** and not yet an operational compilation of CMP/CMP0/CMPS. See `docs/CLAIM_LEDGER.md` §H.

## Remaining gaps

1. Expand the Figure-10 macros into complete gamma/delta/epsilon port pairings.
2. Generate and check the 15 source-rule to IC multi-step reduction certificates.
3. Expand the actual IC initial network for N=81 and reduce it to the encoding of SQ(9).
4. Verify source-to-IC output decoding and runtime resource bounds for the concrete compiler.
5. Only after that, address synthesis from polynomial-term structure and the three-cycle/complex-structure claim.
