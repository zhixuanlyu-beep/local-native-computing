# Local Native Computing

This repository studies how a task's observable meaning can be met by local constraints, constrained materials, local evolution, and stable readout. Its concrete vehicle is Lafont's Interaction Combinators (IC): finite port graphs whose gamma, delta, and epsilon cells interact through six local rewrite rules.

The research route is:

1. **Observation semantics** — state the information objects, boundary observations, visible and hidden state, allowed environments, and resource bounds.
2. **Local constraints** — derive port, type, capacity, and invariant conditions that materials must satisfy.
3. **Constrained materials** — construct or select IC representations that preserve information during the declared storage stage.
4. **Local evolution** — let only declared local IC interactions execute under the allowed environments and schedules.
5. **Readout and retained structure** — decode boundary results and record reusable components with their contracts and replacement conditions.

[docs/RESEARCH_FRAMEWORK.md](docs/RESEARCH_FRAMEWORK.md) defines this route and maps the existing implementations to it. The repository now includes a complete coherent source-to-IC compiler for the 14-symbol / 15-rule system, complete rule certificates, declared finite typed-context checks, and the concrete 81 -> SQ(9) primitive-IC feedback execution.

Two related but distinct lines of work are kept separate:

- **Constraint discovery from problem semantics** has a bounded carrier/gate graph-search instance with executable counterexamples and retained-artifact reuse. General derivation from arbitrary task semantics remains open.
- **Compilation of known source rules** now has a unified primitive-IC compiler and the concrete 81 -> SQ(9) execution; arbitrary-context equivalence, all-schedule verification, and automatic rule discovery remain open.

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
| Coherent typed fragment | `ic_unary_operational_fragment.py` operationally refines a restricted typed source fragment. |
| Isolated projections | `ic_typed_entry_rules.py` certifies typed source-entry redexes separately from the coherent fragment. |
| Restricted-consumer components | The comparator provides path readout; difference, pruning, and selector scripts check native behavior under declared interfaces and consumers. |
| Bounded semantic synthesis and reuse | A finite literal-IC graph search refines candidates with counterexamples; native copy products are archived and reconstructed for independent-input consumer checks. |
| Full program execution | The unified compiler certifies the full source rule table and executes input 81 to `SQ(9)`; measurements and limits are in [ledger Q](docs/CLAIM_LEDGER.md#q-coherent-14-symbol-compiler-and-81--sq9-feedback-execution). |

## Repository layout

### Research documents and audits

- `docs/RESEARCH_FRAMEWORK.md`: research route, terminology, component contracts, and evidence boundaries.
- `docs/CLAIM_LEDGER.md`: executable evidence, conditional results, coverage boundaries, and open goals.
- `docs/COHERENT_IC_COMPILER.md`: unified compiler conventions, trace format, structural readout, and reproduction commands.
- `docs/BOUNDED_IC_INSTANCE.md`: a runnable finite observation-to-IC instance and its exact scope.
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

### Unified source-to-IC compiler and feedback execution

- `source_ic_coherent_compiler.py`: actual Figure-10-style construction for all 14 symbols and 15 rules.
- `lafont_ic_macro_builder.py`, `ic_package_codec.py`: Lafont macro builders, package encoder, and `!Gamma` decoder.
- `ic_fast_reducer.py`: FIFO-indexed native primitive-IC reducer.
- `ic_coherent_certificates.py`: complete rule certificates with a replayable primitive trace.
- `ic_coherent_contexts.py`: finite typed-context refinement cases.
- `ic_coherent_output_decoder.py`: structural source-graph and output decoder.
- `ic_coherent_feedback.py`: complete compiled feedback execution, trace replay, final-graph verification, and readout.
- `results/coherent_rule_certificates.json.gz`, `results/coherent_rule_certificates.ictrace.gz`, `results/coherent_feedback_81.json.gz`, `results/coherent_feedback_81.final.json.gz`, `results/coherent_feedback_81.ictrace.gz`, `results/coherent_context_cases.json.gz`: stored certificate and execution evidence.

### Bounded discovery and retained artifacts

- `ic_bounded_synthesis.py`: finite carrier/gate port-graph enumeration, semantic screening, counterexamples, and context refinement.
- `ic_bounded_execution.py`: complete small execution graphs over all active-pair choices, with exact isomorphism and explicit cutoffs.
- `ic_research_artifacts.py`: literal graph templates and validated ROOT-component archives.
- `ic_research_pipeline.py`: native production, provenance replay, fresh reconstruction, and independent reuse.
- `results/native_ic_research.json.gz`: complete candidate records and archived artifacts; replay with `python ic_research_pipeline.py --verify-report results/native_ic_research.json.gz`.

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
python ic_bounded_execution.py
python ic_research_artifacts.py
python ic_research_pipeline.py
python lafont_ic_macro_builder.py
python ic_package_codec.py
python ic_coherent_output_decoder.py
python ic_fast_reducer.py
python tests/coherent_artifact_integrity.py
python ic_coherent_certificates.py --verify-report results/coherent_rule_certificates.json.gz --trace results/coherent_rule_certificates.ictrace.gz
python ic_coherent_contexts.py
python ic_coherent_feedback.py --verify-report results/coherent_feedback_81.json.gz --replay-trace results/coherent_feedback_81.ictrace.gz --verify-final results/coherent_feedback_81.final.json.gz
python lafont_sigma_width_audit.py
python lafont_phi_psi_split.py
python lafont_macro_budget_v2.py
```

## Budget correction

The earlier `ic_feedback_audit_bundle.zip` figures are obsolete. Its accounting used the source interaction interface width for the `T_sigma` macro, while the supplied noncanonical Figure-6 split applies sigma only to cross-half wiring strands. The corrected conditional budget is recorded in [claim ledger §D](docs/CLAIM_LEDGER.md#d-conditional-macro-budget). Actual generated graphs now confirm the same convention and inventories; measured rule certificates and the concrete feedback run are recorded in [claim ledger §Q](docs/CLAIM_LEDGER.md#q-coherent-14-symbol-compiler-and-81--sq9-feedback-execution).

## Remaining gaps

1. Extend finite typed-context checks beyond the current passive-output/bounded-unary-input contract toward broader contextual-equivalence evidence.
2. Verify additional feedback inputs and schedules without claiming all executions from a single FIFO run.
3. Derive local constraints automatically from broader task semantics.
4. Study synthesis from polynomial-term structure and the three-cycle or complex-structure claim.
5. Keep physical-inventory, optimality, and arbitrary-context claims separate from symbolic allocation and measured concrete runs.

## Source

Yves Lafont, *Interaction Combinators*, Information and Computation 137 (1997), 69-101, DOI: 10.1006/inco.1997.2643. Relevant figures: 2, 4-10.
