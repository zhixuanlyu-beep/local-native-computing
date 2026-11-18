# M7: verifiable localization optimization

The current research route is **problem specification → generate localization
transforms → verify correctness → compare native costs → accumulate relations
between transforms and structures**. M1–M6 remain the execution, audit and replay
foundation. M7 implements an exact optimizer for one finite declared class;
numerical handoff, general concept learning and domain networks are later work.

The problem is the Boolean chain
`Z = OR_(x1,...,xn) alpha(x1) AND product_i f_i(xi,xi+1)`, for `n=2,3`.
Inputs are `alpha(0), alpha(1)`, then each binary factor's entries in row/column
lexicographic order. All 64 and 1,024 Boolean inputs are tested. A transform is
chosen once per size: its objective is the maximum complete FIFO interaction
count over that entire input domain.

The raw grammar contains the direct enumeration baseline and every variable
elimination permutation, every whole-table materialize/recompute bit vector
(including the last table), and a global S or P representation. Direct products
and ORs associate left. Elimination multiplies incident factors in source-number
order, then ORs the two variable values; newly produced factors receive increasing
source numbers. Raw descriptions remain distinct even when their graphs agree.
There are `2 + 2*n!*2**n` descriptions: 18 and 98, yielding exactly 101,504 FIFO
candidate/input checks.

S stores a two-slot package of selector principal and selector output. P stores
the existing three-slot A/selector control package. True selects the first branch.
AND selects `b` or false, OR selects true or `b`, NOT selects false or true.
Selection consumes P's bypass A value with epsilon. Copying uses delta; erasure
uses epsilon. Output decoding leaves exactly one A value at `OUT`; complete
graph matching rejects garbage and bare wire cycles. Input slots are loaded
once and distributed by native fanout. Recomputed tables expand at each use;
materialized table entries are evaluated once and distributed by native fanout.
No input-sensitive simplification or implicit common-expression merge is allowed.
For each materialized table, the compiler visits its entries in lexicographic
order before later tables. Within each entry and the final expression, it visits
operands left to right. The native copy chain gives earlier consumers earlier
output ports. Both choices are part of the frozen construction.

`ic_localization` exposes `ChainProblem`, immutable `Transform`,
`enumerate_transforms`, `build_network` and an independent direct-enumeration
`reference`. Compilation depends only on the problem and transform. Construction
loads input literals without consulting `reference`. Node creation and wire
insertion order are deterministic and affect the fixed FIFO experiment.

```sh
python -m ic_localization --report results/localization.json.gz --trace results/localization.ictrace.gz
python -m ic_localization --verify-report results/localization.json.gz --trace results/localization.ictrace.gz
```

`--workers N` parallelizes independent candidates with the standard library;
it does not change native schedules or costs. `docs/M7_FREEZE.json` binds the
contract, full input and candidate manifests, six original rules, source and
component fingerprints, execution limits and policies before comparison. Source
changes require a new freeze and a full new search. The report preserves ordinary
case graph digests, exact costs, rule censuses and correctness status. Full graphs
and primitive traces cover the chosen optimum representative, both direct
baselines, foundation cases and negative witnesses. All optimum descriptions are
reported; canonical JSON lexicographic order selects the archived representative.

Every run is bounded by 2,000,000 interactions and 250,000 live cells, including
the initial graph. Work includes copying, adapters, decoding and cleanup to a
complete normal form. The report also records initial cells, peak live cells,
runtime allocation, rule census, algebra operation counts, and host compilation,
construction, reference checking, execution, validation and total search times.
Wall times are measurements and are excluded from exact replay equality.
The verifier checks their field names and finite nonnegative values. Every
other field, including the types of recorded costs and the primitive pair
stream's ending, must match the reconstruction.

The 32 S/P foundation instances cover AND(4), OR(4), NOT(2), copy(2), erase(2),
decode(2) for each representation. Each runs FIFO, LIFO and seeded-17, plus full
small-network schedule exploration bounded by 4,096 states, 32,768 attempted
transitions and 128 live cells. The optimum representative and both direct
baselines also run all inputs under LIFO and seeded-17. Those costs are reported
separately and never substituted for FIFO's objective.

`class-optimal` requires every raw candidate/input run to complete and match its
independent reference. Otherwise the report states `best-known` and lists the
unfinished range. Implementation acceptance and measured cost benefit are
separate conclusions. This class provides no claim of universal optimality,
universal materialization benefit, arbitrary-context equivalence or physical
runtime improvement. Negative gains belong in the evidence ledger too.

M8 will use these concrete transforms and costs to freeze a bounded counting
experiment for concept induction. M9 will use frozen held-out tasks and account
for recognition/search/learning cost and library size. M10 can expand factor
structures, representations and transformation rules while strengthening bounds
and proofs. Distinguish model impossibility, budget infeasibility and unknown
search outcomes throughout.
