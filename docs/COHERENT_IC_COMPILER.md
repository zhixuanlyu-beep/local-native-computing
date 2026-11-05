# Coherent source-to-IC compiler

This is the interface guide for the unified compiler and its artifacts. The [claim ledger](CLAIM_LEDGER.md#q-coherent-14-symbol-compiler-and-81--sq9-feedback-execution) is the sole authority for measured counts and proof boundaries. This page explains conventions and verification commands without maintaining a second set of test totals.

## Scope

`source_ic_coherent_compiler.py` compiles the fixed 14-symbol, 15-rule source interaction system to literal gamma/delta/epsilon Interaction Combinator graphs. Source reduction is never called at runtime. A compiled graph evolves only through the six primitive IC rewrite rules.

The compiler takes a complete source-level port matching, including external `F` boundaries. It lowers every source occurrence with the same symbol representation, expands the actual primitive-IC graph, and returns a native `Net` or `FastNet`.

## Port conventions

Source order is preserved:

- source principal port 0 becomes the lowered cell's principal port;
- source auxiliary ports `1..arity(symbol)` become lowered auxiliary ports in the same order;
- source external boundaries keep distinct labels and participate in the final labeled-boundary graph comparison.

The Figure-10 construction follows the actual port wiring in the implementation:

- each symbol has an `M_n` frame and a selector; the selected output enters the frame principal, while the selector principal enters a transpositor slot;
- the ordered source data ports are the frame's interior auxiliaries, excluding the first genetic-code slot and the last control slot;
- the lowered symbol's outer principal is the transpositor root;
- an `<alpha>` extension adds a code port, which is fanned to the decoder and frame code slot;
- the decoder selects a `Gamma` column, and the transpositor exchanges that column with the control strand;
- half-packages use `M^*`, `<alpha>` cells, fanout, and the supplied phi/psi interfaces and crossing strands.

Here `Gamma_i` is a column, not a scalar menu entry. For source pair `(i,j)`, side `i` receives the half-package owned by `i`. This preserves source interaction orientation while using one representation for all 14 symbols.

## Program and extraction evidence

The saved rule report records the generated program and code inventories, native decode and copy/decode costs, every symbol extraction, and pairwise template discrimination. Their measured values are in [ledger Q](CLAIM_LEDGER.md#q-coherent-14-symbol-compiler-and-81--sq9-feedback-execution). These are measurements of this representation, not optimality claims.

The delta-cut codec groups deleted delta ports in the logical frame order `(principal cuts, auxiliary-1 cuts, auxiliary-2 cuts, original root)`. Its decoder connects those slots to delta ports 0, 1, 2, and the output. Packages must be reduced, have one principal root, contain no cyclic wires, and have every principal path reach that root. A merely inactive graph with a disconnected or vicious component is rejected. `M_0` is epsilon and `M_1` is a wire; mirrored gamma combs use the same logical leaf order. These conventions generate the same inventories as the historical conditional macro budget, now checked on actual graphs.

## Rule certificates

`ic_coherent_certificates.py` independently compiles each literal LHS and RHS. It reduces the LHS only by primitive IC interactions and compares the complete labeled-boundary graphs for exact port-graph isomorphism. The archived certificate covers the entire fixed source rule table; totals and ranges are in the ledger.

Full certificate replay is:

```sh
python ic_coherent_certificates.py \
  --verify-report results/coherent_rule_certificates.json.gz \
  --trace results/coherent_rule_certificates.ictrace.gz
```

This verifies report and trace metadata, digests, rule order, recorded resources, final properties, codec evidence, and symbol extraction, and replays the stored trace against freshly compiled LHS graphs.

## Finite typed contexts

`ic_coherent_contexts.py` records each rule's full declared source interface as `source_interface_types`. That field is metadata about the declared interface, not a claim about which ports remain free after an input is attached.

For each rule, every free source input is asserted to have semantic type `N`. Selected cases attach independently constructed `S^n(Z)` unary inputs. The audit uses two distinct per-port length vectors modulo 3 and the empty vector for rules with no `N` input. LHS and literal RHS are compiled independently, reduced only by primitive IC rules, and compared as whole labeled-boundary graphs.

The passing finite cases have a passive-output, bounded-unary-input contract. Their count is recorded in the ledger. Running `python ic_coherent_contexts.py` regenerates the cases and compares every record with the archived report; `--report PATH` writes a regenerated report. This does not establish arbitrary-context equivalence.

## Feedback execution

`ic_coherent_feedback.py` constructs the source input with `make_sim`, compiles it, and executes it using only primitive IC interactions. The archived input-81 execution decodes as `SQ(9)`; its initial, peak, final, and interaction measurements are recorded in the ledger. `FastNet` calls the original `Net.reduce` rules and splicing implementation. It adds an incremental active-pair index and FIFO queue, with whole-graph checks outside each reduction; no source rule dispatch is added.

Reported peak live cells are `max(initial, cells_after_each_completed_primitive_interaction)`. The metric does not count transient host bookkeeping inside a reducer call or host byte memory.

The terminal graph is saved before readout. Verification independently reconstructs the expected source result and compares the complete terminal IC graph with an independently compiled source-result encoding.

Light final-artifact verification is:

```sh
python ic_coherent_feedback.py \
  --verify-report results/coherent_feedback_81.json.gz \
  --trace results/coherent_feedback_81.ictrace.gz \
  --verify-final results/coherent_feedback_81.final.json.gz
```

Full runtime replay is:

```sh
python ic_coherent_feedback.py \
  --verify-report results/coherent_feedback_81.json.gz \
  --replay-trace results/coherent_feedback_81.ictrace.gz \
  --verify-final results/coherent_feedback_81.final.json.gz
```

Full replay starts from a freshly compiled input graph, executes every recorded primitive action under the recorded FIFO policy, and compares report fields including peak, raw final graph digest, final graph-spec digest, decoded result, and step count. Artifact-integrity tests intentionally alter fields to confirm that tampering is rejected.

The light command verifies artifact integrity and the structural terminal result. It does not execute intermediate transitions or independently measure the recorded peak. The full command does both. To perform a fresh run rather than replay a witness:

```sh
python ic_coherent_feedback.py --input 81 --trace pairs.gz --final-graph final.json.gz --report run.json.gz
```

## Trace and observer contracts

Each gzip trace starts with one UTF-8 JSON header and a newline, followed by little-endian unsigned 32-bit cell-ID pairs. The feedback header identifies format `IC-PAIR-U32LE-1`, input, initial-graph hash, program hash, and FIFO policy. Pair-record hashes cover the uncompressed binary records. The rule trace identifies the program, source rule table, scope, and FIFO policy; its report records each certificate's offset and length. Replay requires each recorded pair to be the next actual FIFO redex and rejects a cutoff, trailing records, or a nonterminal end.

The feedback report binds the exact serialized terminal `GraphSpec` through `final_graph_spec_sha256`. This digest uses snapshot cell numbering. `final_graph_sha256` instead covers the actual runtime identifiers and adjacency order; full replay checks it. The light command uses the snapshot digest and does not infer a runtime-ID hash from renumbered cells.

The output decoder matches complete source-symbol template footprints, recovers ordered source ports, and follows unary constructors from `OUT`. It does not call source reduction or use an expected answer to choose a parse. The graph matcher preserves cell kinds, port numbers, boundary labels, and cyclic-wire counts, and rejects uncovered closed cell components. Readout traverses graph structure and is not a constant-time local completion signal.

## Fresh execution versus post-hoc oracle

The `SQ(9)` output is produced by fresh primitive-IC execution of the compiled input graph. The source simulator is not consulted during runtime. The expected result is used only after execution as a post-hoc task oracle, together with whole-graph isomorphism against an independently compiled output. This is stronger than decoding a value alone, but it remains concrete-input evidence.

The archived run uses FIFO active-pair scheduling. Full trace replay proves that exact execution is reproducible; it does not enumerate all schedules. Additional stored runs for inputs 0 and 2 do not make the result an all-input theorem.

## Historical relationship

Earlier results remain valid but scoped to their own representations:

- the four-rule typed fragment is not part of the unified 15-rule compiler;
- the two isolated entry projections are not combined into the unified compiler;
- their separate certificates should neither be added to nor subtracted from the unified 15/15 coverage.

The unified compiler closes the former “complete compiler remains open” gap. It does not convert those historical results into arbitrary-context theorems.

## Limits

- Context checks cover the declared finite cases, not arbitrary contexts.
- Rule and feedback evidence uses the recorded FIFO schedule.
- Concrete runs do not establish asymptotic optimality or a universal resource bound.
- Python allocation is symbolic; it is not a physical finite inventory.
- The compiler starts from a known source system and does not automatically discover constraints from arbitrary task semantics.
