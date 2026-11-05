# Composition contracts and reproducible evidence

M3 connects local compiler witnesses to complete finite typed programs. [COMPOSITION_LEMMAS.md](COMPOSITION_LEMMAS.md) gives the mathematical arguments and their hypotheses. [Claim ledger §T](CLAIM_LEDGER.md#t-composition-arguments-and-schedule-evidence-e_composition) records all measured coverage, costs, digests, and acceptance results. The archived experiments remain distinct from the written arguments.

## Evidence layers

The abstract IC port-graph calculus has one principal port per cell, linear port matchings, and a deterministic rule for each interacting pair of kinds. Gluing resolves paths through the interface and retains closed wire cycles. Two different current redexes have disjoint cells and persist across one another's rewrites. Their replacements commute up to fresh-cell renaming. The strict diamond argument, with rule labels retained, gives equal terminal graphs, interaction lengths, and primitive-rule counts whenever a finite normalization exists. It does not give equal peak space.

This mathematical statement assumes the abstract rule and gluing definitions. The Python reducer is executable code, whose implementation conformance is tested on declared finite inputs. No finite collection of audits is presented as a proof of every Python execution. Historical FIFO archives retain their original evidence scope.

Macro cancellation, delta-free package copying, package erasure, and decoding have separate hypotheses. In particular, a primitive delta is not a copier for arbitrary delta-bearing data. The source compiler lowers each symbol to one fixed ordered-port template, so source gluing is preserved by construction. Given the frozen local rule witnesses and faithful primitive rewriting, a finite source reduction can be simulated by lifting each local witness into its surrounding graph. This is a forward simulation argument; reverse simulation, divergence reflection, and arbitrary-context observational equivalence are not supplied.

## Fixed finite environment

`E_composition-v1` is independent of the discovery, bridge, and activation environments. It imports their frozen evidence without editing their contracts. `ic_composition_certificates.py` binds the contract, exact constructor cases, grammar bounds, primitive rules, compiler code, discovery metadata, and original rule/activation evidence fingerprints.

The finite source syntax in `ic_typed_programs.py` includes natural constructors, feedback checks, copy, erase, comparison, fanout into check/erase consumers, and disjoint parallel composition. Bounds on natural depth, AST size/depth, and parallel width make the syntax finite. Builders check complete port matchings and the source type/polarity table; malformed interfaces and out-of-grammar terms are rejected before execution. These are representation bounds; the archived case list is a selected subset.

Expected diagrams are assembled independently using mathematical constructor results. A separate source evaluator checks those diagrams and records a source rule trace. Neither operation participates in native execution. The actual final primitive graph must match the entire independently compiled result, including labels, extra components, and cyclic wires. The structural decoder then reconstructs the finite source output forest without consulting source rules and is compared with that independent diagram.

Large expected graphs have boundary-rooted components and use the linear boundary-forced matcher, which rejects any unmatched closed component. `full_match` additionally permits exact general graph isomorphism for tiny closed graphs under its explicit size threshold; it does not silently accept closed garbage in large graphs.

The macro family exercises frame cancellation and selection, principal-package encoding/decoding, valid primitive copying, and erasure. Context lifting takes each frozen local source-rule trace, attaches literal gamma frames at the original boundaries, and translates all newly allocated cell IDs explicitly. Only the interior certificate is replayed. The context may contain active pairs at the end: this is an exact `C[LHS] ->* C[RHS]` prefix, not a contextual normalization experiment.

## Scheduling and resources

Complete positive examples run with FIFO, LIFO, and a fixed seeded policy. FIFO retains the existing active-pair insertion order. LIFO selects the newest surviving pair. The seeded policy uses the specified SplitMix64 stream, rejection sampling, and a swap-with-last live-pair index, avoiding Python-version-dependent random choices. Repeated queries without an interaction return the same selected pair. Pair selection changes; every rewrite still calls the original primitive reducer.

The resource ledger records initial cells, peak live cells, terminal cells, native cell allocations, primitive-rule counts, and pure wire cycles. Runtime allocations must occur inside a primitive interaction. The exact rule balance checks the final cell count; a positive-growth rule count gives a conservative peak bound. These are symbolic counts at atomic IC states, not host bytes, a finite physical inventory, or a benefit comparison.

A source trace predicts the total native interaction count and primitive-rule census by summing frozen local witness costs. It also gives a constructive staged peak bound from each source-state footprint and local witness peak. This bound describes that staged simulation, not every possible interleaving. For disjoint `Parallel` programs, lineage tracking projects the actual global trace into its components; the sum of those projected peaks bounds the observed global peak. The implementation does not substitute separately scheduled component peaks into that inequality.

The initial ownership partition uses the compiler's declared insertion-order lowering: one contiguous complete template per source cell. It checks both total size and the corresponding cell-kind sequences before tracking lineage. The projected-peak sum can be loose because different components may reach their peaks at different times. Structural source-graph equality preserves labels, kinds, and port indices; semantic boundary typing is checked separately against the source type table.

Selected M2 sequences are also executed under the alternative policies. Their full result graphs, retained program code, original-code consumption, and native grant/delivery/advance conditions remain checked. This expands finite schedule evidence while preserving the constructor-recognition boundary of M2 readiness and the offline reconstruction boundary of M1 archives.

## Reproduction and rejection

```sh
python tests/typed_programs_integrity.py
python tests/schedule_audit_integrity.py
python tests/composition_evidence_integrity.py
python ic_composition_certificates.py --report results/composition_certificates.json.gz --trace results/composition_certificates.ictrace.gz
python ic_composition_certificates.py --verify-report results/composition_certificates.json.gz --trace results/composition_certificates.ictrace.gz
```

The primitive trace uses the existing gzip JSON header and little-endian cell-ID pair format. Each case records its interval and resource ledger. Verification reconstructs all inputs and policies, replays every pair, independently repeats reference checks, and compares the complete report. Changed bindings, pair order, truncated/trailing traces, and altered graph/resource claims are rejected.

The archive includes a delta-copy precondition counterexample, rejection of stale unrenamed witness IDs, and a counterexample to schedule-independent peak space. Wrong final graphs and resource violations preserve concrete graphs. Interaction exhaustion is incomplete evidence. None is counted as a passing positive case, and the environment is not narrowed after a failure.

The peak counterexample refers to its activation-case records. It requires every compared policy to match the same complete independent reference graph and to have equal interaction counts before differing peaks count as a refutation. It makes no inference about peak space from equal work alone.

The existing CI runner retains the earlier audits and appends these integrity checks and the full new replay. General semantic discovery, arbitrary observational contexts, physical stock, polynomial/complex-structure derivations, and a general structure library remain separate goals.
