# M8 bounded counting and concept induction

M8 exhausts the M7 Boolean chain grammar at sizes 2 and 3. The host
reference enumerates all assignments of the hidden binary variables
and counts those that satisfy the unary factor and every pair factor.
A second evaluator walks the frozen ordered IR and interprets AND as
integer multiplication and OR as integer addition. For every input and
raw candidate, the two counts must agree and positivity must match the
complete Boolean terminal recorded in M7. The host evaluator preserves
multiplicity. Two contributions of value 1 sum to 2, whereas replacing
their sum with Boolean OR produces 1.

| Chain size | Raw candidates | Boolean inputs | Count comparisons |
|---:|---:|---:|---:|
| 2 | 18 | 64 | 1,152 |
| 3 | 98 | 1,024 | 100,352 |
| Total | 116 | | 101,504 |

The [M8 contract](M8_FREEZE.json) pins the accepted M7 FIFO archive at
`8e7956d`. Each candidate's cost is its maximum complete FIFO primitive
interaction count over its original M7 domain. The costs describe the native
Boolean graph, while the numerical count is computed on the host.

## Single-edit comparisons

The learner compares raw candidates that differ by one materialization bit,
one adjacent swap in the elimination order, or a switch between the P and
S representations. Each unordered pair contributes one observation. The
orientation sets a materialization bit, moves from the lexicographically
earlier order to the later one, or switches from P to S. The cost delta
subtracts the source candidate's worst FIFO cost from the target's.

| Edit | Improved | Tied | Degraded | Worst FIFO delta range |
|---|---:|---:|---:|---:|
| Set one materialization bit | 16 | 144 | 0 | −110 to 0 |
| Swap adjacent eliminations | 56 | 32 | 16 | −146 to +110 |
| Switch P to S | 58 | 0 | 0 | −165 to −29 |
| Total | 130 | 176 | 16 | |

A predicate uses at most two conditions on step position, incident factor
count, result scope width, and downstream references per table entry.
The learner obtains these features by following factor scopes through the
elimination order. It uses the edited step for a bit flip and the first
of the two swapped steps for a swap. For a representation switch in
variable elimination it uses the first position where the order differs
from ascending order, with step zero as the default. Direct candidates
have no elimination features. Each condition is tested on both endpoints.
A single condition compares a feature with an observed value using
equality or an inclusive bound. A two-condition predicate combines
equalities on different features.
A concept needs at least two distinct ordered compiled IR pairs, with both
endpoints verified in the full count matrix. The IR signature includes
the operation sequence and operand indices, output mapping, and
representation. Multiple raw descriptions can support the same compiled
IR pair and still count as one.

The library contains **60 automatically discovered rules** and five
manual algebra axioms for associativity, commutativity, and
distributivity. It retains cost ranges, ties, cost increases, and
counterexamples for weaker predicates. For example, every size-2
materialization flip ties, which defeats a rule claiming that setting
any materialization bit saves FIFO work. A rule whose worst observed
delta is negative has a conservative saving equal to the magnitude
of that endpoint. Rule C060 matches eight P-to-S observations with
two distinct IR pairs. Its conditions require two incoming factors
and two downstream references per produced entry. The observed
delta range of −133 to −83 gives a conservative saving of 83.

Recognition overhead is expressed as a bound on atom comparisons
for a scan of the relevant single-edit pairs with features available.
Both the observed savings and the support counts are scoped to the
two frozen domains.

## Reproduction

Run from the repository root.

```sh
python -m ic_m8 --report results/m8_concept_library.json.gz
python -m ic_m8 --verify-report results/m8_concept_library.json.gz
python tests/m8_integrity.py
```

The [versioned evidence](../results/m8_concept_library.json.gz) includes
the count comparisons, candidate matches, unfinished records, observed
cost deltas, and the concept library. Verification checks the source freeze
and exact M7 report digest, reruns the host counting matrix, and uses an
independent implementation to reconstruct the library from the frozen raw
candidates and measured costs. The independent M7 native replay command
is documented in the [M7 guide](LOCALIZATION_OPTIMIZATION.md).

The M8 integrity tests exercise the full count matrix and reject an altered
terminal, count total, pinned archive, and missing or modified concept
evidence. Compatibility checks passed for the full M7 native replay, all
16 M7 integrity tests, and the earlier size-family report verifiers.
