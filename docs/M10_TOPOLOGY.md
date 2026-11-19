# M10 four-variable topology search

M10 compares exhaustive evaluation with certificate pruning on a four-variable
star and cycle. A unary factor attaches to variable `0`. The result is true if
one of the 16 assignments satisfies that factor and every binary factor.

| Topology | Binary factor order | Free binary entries |
| --- | --- | --- |
| `star4` | `01, 02, 03` | `f01(0,0)`, `f01(1,1)`, `f02(0,1)`, `f03(1,0)` |
| `cycle4` | `01, 03, 12, 23` | `f01(0,0)`, `f03(1,1)`, `f12(0,1)`, `f23(1,0)` |

Each 64-input search domain varies both unary entries and the four listed
binary entries in Boolean lexicographic order. The remaining entries come
from the identity relation. All entries are installed as individual graph
inputs. The star uses 14 slots and the cycle uses 18. Original factor IDs
follow the table order after unary ID `0`. Generated IDs start at the number
of original factors. The independent reference enumerates all variable
assignments directly over the topology's edge tables.

The freeze records the topology, slots, input vectors, raw candidate order,
budget, and implementation digests. Both searches visit the same 770
candidates in M9 raw order for each topology. Each execution uses FIFO with
ceilings of 2,000,000 interactions and 250,000 live cells. [Freeze manifest](M10_FREEZE.json)

## Certificates and verification

Exhaustive evaluation runs all 98,560 candidate and search input pairs. A
candidate's cost is its maximum complete FIFO count across the 64 cases. The
certificate search visits the same candidates and inputs in order. A new
upper bound requires a correct completion on all 64 cases in that group.

Each primitive interaction removes two cells and may allocate more. If the
initial graph has `N0` live cells and the reference terminal has `N*`, the
static lower bound is `ceil(max(N0 - N*, 0) / 2)`. When that bound is
insufficient, the certificate search runs FIFO up to the earlier of step
`U + 1` and the original execution limits. Reaching `U + 1` within the limits
excludes the candidate for the incumbent `U`. Both tests require strict
inequality, so candidates that can tie remain eligible. The archive records
the incumbent's complete evidence and the exclusion's graph, input, and
bound data. A wrong terminal establishes incorrectness. An inconclusive
cutoff remains unresolved.

For each topology the holdout replays the lexicographically smallest
canonical description among the optimum ties. The freeze takes the 256
lowest `SHA-256` ranks over vectors outside the search domain, with the bit
string breaking any hash tie. The archive contains individual holdout
results and the measured worst cost. The exact optimum is scoped to the 64
search cases for each topology.

## Measured results

Both methods found the same exact costs and tie sets. The exhaustive run
completed all 98,560 cases with correct terminals. The certificate run
resolved all 1,540 candidate visits and produced 1,146 exclusions.

| Topology | Exact worst FIFO steps | Tied candidates | Holdout selection | Correct holdouts | Worst holdout FIFO steps |
| --- | ---: | ---: | --- | ---: | ---: |
| `star4` | 82 | 96 | `Q146` | 256 / 256 | 82 |
| `cycle4` | 266 | 64 | `Q178` | 256 / 256 | 266 |

- Star ties are `Q146–Q161`, `Q178–Q193`, `Q242–Q257`, `Q274–Q289`, `Q338–Q353`, and `Q370–Q385`.
- Cycle ties are `Q154–Q161`, `Q178–Q193`, `Q250–Q257`, `Q282–Q289`, `Q338–Q353`, and `Q378–Q385`.

Each row below used 770 candidate visits and 770 compilations. Complete
input checks count terminal evaluations used for ordinary verification.
FIFO executions also include the prefix attempts that served as exclusion
witnesses. Graph constructions include the static witnesses.

| Topology | Search | Complete input checks | FIFO executions | Graph constructions | FIFO steps | Static proofs | Prefix proofs | Host seconds |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `star4` | Exhaustive | 49,280 | 49,280 | 49,280 | 19,306,760 | 0 | 0 | 349.096 |
| `star4` | Certificates | 14,912 | 14,981 | 15,449 | 4,747,927 | 468 | 69 | 97.369 |
| `cycle4` | Exhaustive | 49,280 | 49,280 | 49,280 | 23,568,008 | 0 | 0 | 429.301 |
| `cycle4` | Certificates | 10,304 | 10,817 | 10,913 | 3,356,827 | 96 | 513 | 68.069 |

The star saved 14,558,833 FIFO steps (75.41%). The cycle saved 20,211,181
steps (85.76%). Certificate construction, execution, and recording are
included in the certificate group times. The two topologies ran in
parallel and the experiment took 500.445 seconds of wall time.

The verifier reconstructed every certificate after generation using the
recorded exhaustive cases and Python prefix replay. That check took 4.681
seconds for the star and 19.475 seconds for the cycle, with 22.730 seconds
of wall time for the full generation-time verification pass including the
holdouts. A separate `--verify-report` run also rebuilds every exhaustive
case before checking the certificates and replaying the holdouts. That run
passed in 407.446 seconds of wall time. The star and cycle verification
jobs took 313.854 and 405.823 seconds respectively.

All 11 M10 integrity tests passed, including the optional C/Python comparison.
The M7 localization, M8 concept library, and M9 holdout integrity suites and
archive replays also passed.

## Reproduce

Run from `ic-research-docs`.

```text
python -m ic_m10 --freeze
python -m ic_m10 --report
python -m ic_m10 --verify-report
python tests/m10_integrity.py
```

The measured search uses the C FIFO reducer built from `ic_m9_native.c` with
MSVC 14.44. Set `IC_M9_NATIVE_LIBRARY` to the compiled library's absolute
path to select it. Without that variable the searches run in Python. The
verifier uses Python to check FIFO prefixes and negative witnesses with
either setting. The optional C/Python test compares full terminals and
cutoff graphs in both topologies.

The compressed report stores the complete case evidence, certificate search
history, holdout records, and run and verification measurements. [Report archive](../results/m10_topology.json.gz)
