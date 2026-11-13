# Size-only frameworks with separately supplied Boolean inputs

This experiment implements the two-stage contract from
[the size/uniformity guide](SIZE_AND_UNIFORMITY.md) for an ordered AND fold.
The framework is generated from input length and a fixed shape policy. Input
values are encoded afterward, and the original IC rules compute the result.
Measured coverage, costs and limits are in
[ledger Y](CLAIM_LEDGER.md#y-input-bearing-uniform-and-frameworks).

## Representation and gate

The experiment uses the existing M4 representation A: epsilon is false, and a
gamma whose two auxiliary ports are wired together is true. Both values occupy
one cell, although their kinds and wire counts differ. These are distinct
literal graphs, not unbounded scalar labels.

One gamma implements the binary AND gate with LEFT at principal port 0, RIGHT
at auxiliary port 1, and OUT at auxiliary port 2. Its primitive reductions are:

| LEFT | RIGHT | Complete output | Primitive interactions |
|---|---|---|---:|
| false | false | One epsilon at OUT | 2 |
| false | true | One epsilon at OUT | 3 |
| true | false | One epsilon at OUT | 1 |
| true | true | One Loop at OUT | 1 |

For true LEFT, gamma/gamma annihilation and the Loop wire connect RIGHT to OUT.
For false LEFT, gamma/epsilon erasure creates an OUT epsilon and an eraser for
RIGHT. Erasing a false RIGHT takes one epsilon/epsilon step; erasing a true
RIGHT takes a gamma/epsilon step followed by epsilon/epsilon cleanup.
This is a directly specified literal gate, not a new component-discovery or
frozen-library-retrieval result. Representation meanings are imported from
the existing observation contracts.

## Construction and execution boundary

`build_framework(n, shape)` has no input-value argument. It returns an immutable
`GraphSpec` with `n-1` gamma gates, `n` labeled inputs and one output. The
balanced policy splits each interval into floor/ceiling halves. The left-comb
policy puts the first `n-1` inputs in the left subtree and the final input on
the right. This is the opposite comb orientation to the earlier tree-copy
generator; shape names are deliberately distinct.

`plug_inputs(spec, bits)` instantiates that same syntax, encodes each supplied
bit independently through `value_spec`, and connects the existing input
boundaries through `macro_connect`. It does not evaluate conjunction, alter
gate wiring based on values, select a ready-made answer, or run reductions.
The immutable framework remains available for later fresh instances.
Each execution instantiates and charges its own graph; this is description
reuse, not reuse of a consumed runtime specimen.

The resulting graph has `2n-1` cells for every input tuple of length `n`.
With `t` true inputs it has `2n-1+t` wires: input encoding can change the
instance without changing its framework. The report binds the exact framework
specification and digest, encoded initial-graph digest, every primitive pair,
final whole graph, rule census, allocation and atomic-state peak.

Execution selects active pairs using first-active, last-active or
snapshot-rounds policies and invokes the unchanged `Net.reduce`. The scalar
`all(bits)` reference is computed only for offline postcondition checking.
A terminal graph passes only if it is isomorphic to the entire independently
constructed A output at the fixed OUT boundary. Extra components and cyclic
wires cannot pass merely because an apparent output bit is correct.

The shipped builder accepts `1 <= n <= 64`. Its recursive size-only recipe
exhibits the proposed organization, while implementation evidence remains
finite. It does not establish a uniform compiler for arbitrary functions.

Input plugging also checks the declared width, gamma-only framework inventory
and absence of detached wire cycles before execution. See
[the evidence-input contract](EVIDENCE_INPUTS.md) for graph and report validation.

## Work, space and round interpretation

Framework construction has `n-1` cells, `n+1` boundaries and `2n-1` wires,
with zero primitive reductions. Those graph counts omit host construction,
validation, scheduling, readout and exhaustive-exploration time.

Only gamma/epsilon, gamma/gamma and epsilon/epsilon rules can occur in these
networks. Live cell count stays constant on gamma/epsilon and falls by two on
either annihilation, so the atomic-state peak is the initial size. This does
not make total allocation or work constant: gamma/epsilon allocates two new
epsilon cells. For a correct terminal with one output cell,

```text
I = P = 2n-1
runtime allocation = 2 * count(ge)
A = I + runtime allocation = 1 + 2W
W = n-1 + count(ge)
```

At the same size and even with the same framework, work depends on input
values. The two-input table above is the smallest concrete example. In the
left comb, an all-true input and an input with only its last bit false both
use one annihilation per gate; putting the only false bit first causes erasure
of the remaining true values instead.

Snapshot rounds reduce all pairs active at round start and defer new pairs.
They are modeled rounds of local graph rewriting, including cleanup; the host
executes their interactions sequentially. A local AND gate can annihilate
after its LEFT result arrives, before its RIGHT result is ready. Consequently
ordinary Boolean-circuit depth is not this metric. For all-true balanced
inputs, rounds satisfy `R(1)=0` and
`R(n)=max(R(floor(n/2))+1, R(ceil(n/2)))`, giving `floor(log2(n))`.
For the all-true left comb the count is `n-1`. These are scoped structural
arguments and checked examples, not hardware latency or an optimality claim.

## Abstract argument and implementation evidence

Under the original primitive-rule and linear-gluing definitions, the four
elementary reductions above supply a staged normalization of any finite ordered
tree of these gates: normalize both child subtrees, then apply the appropriate
local gate trace. Induction gives the AND output with no extra components.
This is a constructive abstract argument using the contextual lifting
assumptions in [the composition lemmas](COMPOSITION_LEMMAS.md), separate from
an unbounded conformance proof for the Python implementation.

Termination also has a simple abstract bound: let `G,E` count gamma and epsilon
cells. The nonnegative potential `2G+E` decreases on every applicable rule
(by 1, 4 or 2). Initially it is `3n-2+t <= 4n-2`. This explains why finite
budgets can cover the shipped width bound; it is not a claim of minimum work.
The larger composed networks still have only their recorded implementation
schedules, while exact exploration establishes all-schedule behavior only for
the concrete small graphs listed in the report.

The report exhausts all input tuples through width 4. At widths 8,16,32,64 it
uses five declared tuples: all-false, all-true, alternating false-first,
only-first-false and only-last-false. Every tuple uses both shapes and all
three policies. Exact bounded exploration covers all inputs through width 3
under both shapes. Duplicate framework syntax at widths 1 and 2 is retained
as separate shape configurations, not counted as new distinct graphs.

Negative fixtures preserve zero/partial interaction cutoffs, an initial
material violation, a quiescent wrong whole output and an unfinished schedule
exploration. They remain distinct from successful computations and exhaustive
schedule evidence. The integrity suite also checks oracle-free construction,
unaltered internal framework wiring, all width-5 inputs, strict parameters and
adversarial report edits.

## Reproduction

```sh
python tests/boolean_size_family_integrity.py
python ic_boolean_size_family.py --report results/boolean_size_family.json
python ic_boolean_size_family.py --verify-report results/boolean_size_family.json
```

Verification rebuilds all frameworks and inputs, reruns every selected policy
and small exploration, reconstructs the negative probes, and compares every
semantic report field, primitive pair and source binding. The compact JSON
retains the full data; detailed measured totals remain in ledger Y. This
experiment does not extend M4 discovery, full-feedback compilation, native
size-descriptor decompression, physical inventory, or reuse-benefit claims.
