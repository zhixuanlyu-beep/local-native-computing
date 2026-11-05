# Local Native Computing

This repository studies how a task's observable meaning can be met by local constraints, constrained materials, local evolution, and stable readout. Its concrete vehicle is Lafont's Interaction Combinators (IC): finite port graphs whose gamma, delta, and epsilon cells interact through six local rewrite rules.

The research route is:

1. **Observation semantics** — state the information objects, boundary observations, visible and hidden state, allowed environments, and resource bounds.
2. **Local constraints** — derive port, type, capacity, and invariant conditions that materials must satisfy.
3. **Constrained materials** — construct or select IC representations that preserve information during the declared storage stage.
4. **Local evolution** — let only declared local IC interactions execute under the allowed environments and schedules.
5. **Readout and retained structure** — decode boundary results and record reusable components with their contracts and replacement conditions.

[docs/RESEARCH_FRAMEWORK.md](docs/RESEARCH_FRAMEWORK.md) defines this route and maps the existing implementations to it. The repository currently supports source-level feedback audits, literal IC reductions, structural source-net storage, a coherent four-rule typed fragment, and several native IC components. It does not yet contain a complete IC compilation and execution of the source feedback program.

Two related but distinct lines of work are kept separate:

- **Constraint discovery from problem semantics** is the broader research goal. No automatic algorithm for deriving local constraints from arbitrary task semantics is implemented.
- **Compilation of known source rules** is the current concrete engineering line. It has a coherent typed four-rule fragment and two separately typed isolated projections, but not a globally coherent source-to-IC compiler.

The [claim ledger](docs/CLAIM_LEDGER.md) is the sole source for detailed evidence, test sizes, coverage counts, and proof boundaries. Read it before interpreting any result.

## Quick start

```sh
python -m pip install -r requirements.txt
bash tests/run_all.sh
```

The scripts are also runnable individually. The test suite uses Python 3.11+ and NetworkX 3.6.1.

## Research map

| Route stage | Current repository evidence |
|---|---|
| Observation semantics and contracts | The framework defines problem inputs, observation boundaries, environments, and resource bounds. |
| Structural representation | `source_ic_structure_encoding.py` stores finite source nets losslessly as primitive IC data. |
| Primitive local mechanisms | The IC verifier and copy/erase demos exercise the six Lafont rules on literal gamma/delta/epsilon graphs. |
| Coherent typed fragment | `ic_unary_operational_fragment.py` operationally refines four typed source rules. |
| Isolated projections | `ic_typed_entry_rules.py` certifies two typed source-entry redexes separately from the coherent fragment. |
| Restricted-consumer components | The comparator provides path readout; difference, pruning, and selector scripts check native behavior under declared interfaces and consumers. |
| Full program execution | Not established; the complete source-to-IC compiler and the `81 -> SQ(9)` IC trace remain open. |

## Repository layout

### Research documents and audits

- `docs/RESEARCH_FRAMEWORK.md`: research route, terminology, component contracts, and evidence boundaries.
- `docs/CLAIM_LEDGER.md`: executable evidence, conditional results, coverage boundaries, and open goals.
- `source_feedback_audit.py`, `source_rule_audit_v3.py`: source-level feedback simulator and rule audit.
- `lafont_sigma_width_audit.py`, `lafont_phi_psi_split.py`, `lafont_15_rules_phi_psi_split.json`: source-level rule decomposition data.
- `lafont_macro_budget_v2.py`: conditional static accounting for one proposed Figure-10 macro expansion.

### IC primitives and structural encoding

- `ic_primitive_port_verifier.py`: literal gamma/delta/epsilon port-graph reducer for the six Lafont rules.
- `ic_gamma_tree_copy_demo.py`, `ic_reduced_package_copy_demo.py`, `ic_tree_erase_demo.py`: primitive IC copy and erase experiments.
- `source_ic_structure_encoding.py`: lossless source port-net data encoding in primitive gamma/epsilon IC, with native delta copying and epsilon erasure.

### Operational fragments and components

- `ic_unary_operational_fragment.py`: coherent operational IC simulation for the typed source rules `ERA-Z`, `ERA-S`, `DUP-Z`, and `DUP-S`.
- `ic_signed_unary_comparator.py`: complementary unary-chain comparator using primitive IC annihilations.
- `ic_composable_signed_difference.py`: two native IC channels producing rooted unary data at fixed output ports.
- `ic_tagged_unary_case.py`: alternate tagged unary encoding with a one-step local zero/successor discriminator.
- `ic_signed_branch_pruning.py`: comparator-driven branch erasure with explicit interface restrictions.
- `ic_signed_sum_selector.py`: single-output native IC tagged sum with checked downstream consumers.
- `ic_three_way_selector.py`: three-way tagged selector with an equality payload and native consumers.
- `ic_typed_entry_rules.py`: isolated typed certificates for `INIT-Z` and `CMP0-Z`.

### Continuous audit

- `.github/workflows/audit.yml`: runs all audits on pushes and pull requests.

## Running individual audits

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
python ic_composable_signed_difference.py
python ic_tagged_unary_case.py
python ic_signed_branch_pruning.py
python ic_signed_sum_selector.py
python ic_three_way_selector.py
python ic_typed_entry_rules.py
python lafont_sigma_width_audit.py
python lafont_phi_psi_split.py
python lafont_macro_budget_v2.py
```

## Budget correction

The earlier `ic_feedback_audit_bundle.zip` figures are obsolete. Its accounting used the source interaction interface width for the `T_sigma` macro, while the supplied noncanonical Figure-6 split applies sigma only to cross-half wiring strands. The corrected conditional budget, its assumptions, and the current cell and free-port counts are recorded in [claim ledger §D](docs/CLAIM_LEDGER.md#d-conditional-macro-budget). No completed Figure-10 IC port graph has been built or independently reduced.

## Remaining gaps

1. Expand the Figure-10 macros into complete gamma/delta/epsilon port pairings.
2. Generate and check IC simulation certificates for all source rules.
3. Expand the actual IC initial network for input 81 and reduce it to the encoding of `SQ(9)`.
4. Verify source-to-IC output decoding and runtime resource bounds for the concrete compiler.
5. Derive local constraints automatically from broader task semantics.
6. After the compiler is complete, study synthesis from polynomial-term structure and the three-cycle or complex-structure claim.

## Source

Yves Lafont, *Interaction Combinators*, Information and Computation 137 (1997), 69-101, DOI: 10.1006/inco.1997.2643. Relevant figures: 2, 4-10.
