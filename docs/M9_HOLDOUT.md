# M9 held-out search costs

M9 compares four ways to reach the exact minimax FIFO cost on each of four
64-input domains of the size-four Boolean chain. The chain computes whether
some assignment satisfies the unary factor and all three binary factors.
Each input includes the two unary slots and twelve binary factor slots in
`00, 01, 10, 11` order per factor. Fixed binary entries come from the identity
relation and are loaded as individual literals in the native network.

| Domain | Free factor entries in addition to both unary slots |
| --- | --- |
| D1 | All of `f1` |
| D2 | All of `f2` |
| D3 | All of `f3` |
| D4 | `f1(0,0)`, `f1(1,1)`, `f2(0,1)`, `f3(1,0)` |

The [freeze](M9_FREEZE.json) binds the Boolean inputs, 770 raw descriptions,
ordered IR classes, M8 library digest, ranking rules, M9 source digests, and
FIFO budget. The abstraction key includes the full ordered IR, representation,
and output index. Each of the 290 classes uses its lexicographically smallest
canonical description as representative. Ranking uses the 21 M8 rules whose
matching observations all reduced worst-case FIFO cost. For each candidate,
the maximum matching conservative saving determines its terminal edge cost.
An abstract class uses the lowest terminal distance among its members. The
abstraction-only and abstraction-and-ranking orders contain exactly the 290
representatives. The other two orders contain all 770 raw descriptions.
The raw baseline follows the frozen enumeration order. Abstraction-only
uses canonical representative order. Both ranked orders break equal-distance
ties by canonical description. Internal representation, elimination-order,
and materialization edges have zero cost. Each terminal edge costs `117`
minus the candidate's maximum matched conservative saving.

## Evidence and accounting

The evaluator executes every raw description on each of the 256 small-domain
inputs, for 197,120 candidate/input checks. For each case it enumerates the
sixteen hidden assignments directly and compares the complete native terminal
graph with the expected Boolean value. Each domain keeps the entire matrix,
the minimum of the candidates' worst FIFO costs, and every tied candidate.
An unfinished or incorrect run prevents an exact target and retains its
input record and unresolved candidate. A domain can report `best-known`
when completed candidates remain, or `incomplete` otherwise.

The four search orders come from the freeze. Search queries return evidence
for one candidate at a time. The scorer alone receives the exact target and
ends the measured prefix at the first complete candidate that reaches it.
Every query is charged the sum of the candidate's interactions on all 64
inputs. The archive supplies those measured results, so each visit is charged
one candidate compilation and its attributed evaluator time. The archive
records actual evaluation compile counts separately. Creating or reconstructing
the frozen catalog also compiles each of the 770 raw descriptions. Order
preparation and query/scoring times are recorded separately from attributed
evaluator time.
Recognition counts describe rule matching for ranked orders. The M8 fields
record library size and the learning work reported by M8.

The [report](../results/m9_holdout.json.gz) retains all sixteen choices with
references to the full-domain evidence for the selected transformations.
Each distinct selected transformation is verified on all 16,384 size-four
Boolean inputs. Its correctness and worst FIFO cost are measured on that
larger domain. The exact optimality claims apply to the four 64-input domains.

## Results

All four domains have an exact target of **122 FIFO interactions** and
**52 tied raw candidates**. The methods reached the target at the same visit
number in every domain. The interaction totals sum the four search prefixes.

| Method | Visits per domain | Charged compilations across four domains | Verification interactions across four domains |
| --- | ---: | ---: | ---: |
| No concepts | 27 | 108 | 1,757,109 |
| Abstraction only | 204 | 816 | 16,122,948 |
| Ranking only | 532 | 2,128 | 42,989,100 |
| Abstraction and ranking | 204 | 816 | 16,122,948 |

The no-concept order reached the target with the fewest visits and the least
FIFO verification work in every domain. The two abstraction orders incurred
the same verification charges. Each ranked order attributes 193,620 rule
endpoint checks across 4,610 candidate edges. The report repeats the measured
shared preparation time in each group and records query/scoring and attributed
evaluator times for each prefix.

The M8 library recorded 101,504 training candidate/input checks, 322
single-edit pairs, and 22,380 rule-recognition host operations. Its recorded
serialized size is 1,449,648 bytes, including 60 induced rules and five
manual axioms. M9 transfers 21 rules from that library.

The sixteen selections refer to two full-domain runs. `Q026` was selected by
the no-concept method in each domain. The other methods selected `Q086`.
Both passed all 16,384 inputs and had a full-domain worst FIFO cost of 122.

## Reproduction

Run from the repository root with Python and the repository's requirements.

```sh
python -m ic_m9 --freeze
python -m ic_m9 --report --workers 8
python -m ic_m9 --verify-report --workers 8
python tests/m9_integrity.py
```

Both run modes use M7's FIFO pair ordering and the same six primitive rules.
The verifier reconstructs the frozen manifest and all four orders, checks
coverage and the scoring ledger, and reruns the complete native matrix and
the full-domain selections. Replay compares deterministic fields exactly
and checks that archived host times have the expected shape and finite values.
The three entry points accept optional output or report paths. Use
`--freeze-path PATH` to read a separate frozen manifest for either run mode.

For faster replay, build the optional packed C executor and set
`IC_M9_NATIVE_LIBRARY` to its absolute path. In a Visual Studio developer shell,
use `cl /nologo /std:c11 /O2 /LD ic_m9_native.c`. On Linux, use
`cc -std=c11 -O3 -shared -fPIC -o libic_m9_native.so ic_m9_native.c`.
Unset `IC_M9_NATIVE_LIBRARY` to run with the M7 Python executor. The environment
setting is inherited by parallel workers.
