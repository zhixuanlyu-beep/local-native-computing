# Input size, uniform construction, and local execution

A fixed function can use both a growing graph and a growing number of local
interactions. The primitive rule table stays fixed, while initial size, runtime
allocation, and work can all grow. A short recipe does not remove the cost of
constructing or evaluating its outputs. Concrete evidence and formulas are in
[ledger X](CLAIM_LEDGER.md#x-size-parametric-construction-and-tree-copy-audit).

“Relational Ontologies” is not a separately implemented formalism here. This
guide uses the project's actual model: finite ordered-port IC graphs and six
primitive rewrite rules. A mathematical relation `R_f(x,y) iff y=f(x)` specifies
acceptable answers; it supplies neither an evaluator nor a unit-cost primitive
for finding them.

## Fixed descriptions, generated instances, and evolving graphs

| Object | Fixed for an implementation | Potentially growing |
|---|---|---|
| Description `P_f` | Builder/evaluator code, cell kinds and rewrite rules | Builder parameters |
| Instance `G_0(x)` | Representation and interface conventions | Encoded input, adapters, consumers, reserves, prewired tasks |
| Evolution `G_0 -> G_1 -> ...` | Local rewrite semantics | Live cells, allocations, interactions and dependencies |

Fixed rule count is not fixed cell count: gamma/delta commutation replaces two
cells with four. Fixed modules may also be reused over successive steps. But a
fixed complete finite-state graph, with no growing storage or external input
channel, cannot hold arbitrarily much distinguishable input. Streaming, external
memory, unbounded labels, and physical replenishment require explicit contracts.
Symbolic allocation is not an implementation of a finite physical inventory.

## Contract for “compress, expand, then evaluate”

Declare a representation and input-size measure `s(x)=n`. The proposed two-stage
organization requires one effective generator and a contract of the form

```text
C_n = Build(P_f, n)
Obs(Eval(Plug(C_n, Encode(x)))) = f(x)    for every admitted x with s(x)=n.
```

`Build` cannot consult the values of `x`. Its descriptor includes the function
and representation, not merely `n`. Encoding/plugging the actual input still
costs work. Correctness is relative to the observation/environment contract,
including termination/readiness. Evaluation may consume the IC specimen.

Keep four claims separate:

1. A bound `|G_0(x)| <= S(n)` does not make topology a function only of `n`.
   Equal-size input graphs can have different edges and runtime behavior.
2. A separately chosen `C_n` for every size does not supply one generator.
3. A computable generator need not be efficient. Polynomial-time uniformity
   requires a polynomial bound in `n`, for example with generator input `1^n`.
   Polynomial time in the bit length of binary `n` is a different requirement.
4. A finite description is not necessarily shorter than every generated member.
   Emitting an explicit description of length `L` still requires `Omega(L)`
   time on a bounded-output machine.

Uniform Boolean circuits are a useful comparison, with an additional
generation requirement; cyclic, allocating IC nets are not themselves Boolean
circuits. See Anderson and Dawar, [P-uniform circuits, §2.2, Definition 6](https://doi.org/10.1007/s00224-016-9692-2).

For a total computable Boolean function, a possible computable generator
enumerates all length-`n` inputs, computes their answers, and emits a truth-table
circuit. This establishes effective construction with potentially enormous
cost, not an efficient IC compiler or a polynomial-time uniform family.
Partial computations require suitable restrictions/bounds for finite full
unfolding; there is no general terminating full-unfolding procedure.

## Expansion and computation may be interleaved

Input-dependent branches can produce different runtime graphs even when they
share a size bound. Expansion may wait until a branch is known. Alternatively,
a size-dependent framework can simulate all choices, but this requires a
justified execution bound and an explicit simulation overhead.

Here, reduction means primitive runtime rewriting. Some reductions copy or
decode structure; others compute, select, or erase. Host construction is not a
native reduction, and reduction is not synonymous with decompression. Native
expansion needs an IC interface and a charged primitive trace of its own.

## Cost contract

Declare the model, size unit, schedule, stopping observation, and included
structures. A worst-case claim needs its input and schedule quantifiers;
otherwise retain the actual measured input and policy.

| Quantity | Required accounting |
|---|---|
| Description `D` | Generator/program, representation, rules and parameter encoding |
| Build/encode/plug `B` | Discovery/compilation, graph generation, input encoding, wiring and adapters; separate host and native work |
| Initial live cells `I` | All cells before the native interval, including dormant future tasks |
| Initial interfaces and wiring | Report boundary, wire and detached-wire-cycle inventories separately; these are not added to `I` |
| Work `W` | All primitive interactions in the interval |
| Allocation `A` | Initial cells `I` plus every allocated RHS cell; also report runtime cell allocation separately |
| Space `P` | Peak live cells at initial/post-atomic-rewrite states; host bytes and rewrite temporaries are separate |
| Dependency measure `R` | Explicitly defined circuit depth, causal depth or synchronous rounds |
| Readout `Q` | Traversal, decoding and/or native consumers, with readiness and cleanup conventions |

`I`, `A`, final cells `F`, and `P` all count cells. The identity `A = F + 2W`
therefore concerns cell allocation only. Boundary and wire inventories remain
part of full structural accounting, with their own units. For example, the
64-leaf copy case has `I=128` cells, 2 boundaries and 129 wires; these are
three separate measurements, not a combined value of `I`.

Only add `B + W + Q` after placing them in a common cost model. Host API calls,
IC interactions and elapsed seconds cannot be added without a conversion.
In a common sequential model, total time includes build, input handling,
evaluation and readout. Native copying, decoding and erasure cannot disappear
into an uncharged preparation stage.

For `m` same-size evaluations, an immutable compiled description can amortize
build cost as `B(n)/m`. Mutable specimens may require reconstruction, native
copying, reset and retained storage; charge those per-use costs and lifetimes.
The [M5 comparison](EVIDENCE_INDEXED_STRUCTURE_LIBRARY.md) already charges
complete declared native strategies without claiming universal reuse benefit.

## Executable example: two tree families

[ic_size_family_audit.py](../ic_size_family_audit.py) uses the unchanged literal
reducer and existing ordered tree builder/decoder. A fixed generator takes `n`
epsilon leaves and a family, builds the full gamma/epsilon tree, and attaches
one delta copier and two labeled outputs. The balanced family splits leaves
in half; the comb splits off one. Both depend only on size and family.

Construction records `cell`, `boundary` and `link` calls before any rewrite.
These counts omit host shape-generation, validation and scheduler overhead;
they are not total build time. Execution records every primitive pair, rule
census, allocation and atomic-state peak. A shared visited set for both decoded
ordered copies accounts for all terminal cells; cyclic wires are rejected.

`first-active` is a deterministic sequential policy. `snapshot-rounds` reduces
all pairs present at round start, deferring new pairs to the next round. The
host simulates each round sequentially. The count models unlimited simultaneous
disjoint rewrites, not host time or a general minimum-depth theorem.

The formulas and measured matrix are in [ledger X](CLAIM_LEDGER.md#x-size-parametric-construction-and-tree-copy-audit).
Equal size and work can coexist with different synchronous rounds. This is a
structural-family demonstration: all leaves are epsilon, and the generator
chooses the entire tree. It does not test arbitrary same-length bitstrings,
prove all-schedule behavior, or unfold the complete feedback compiler.

```sh
python tests/size_family_integrity.py
python ic_size_family_audit.py --report results/size_family_audit.json
python ic_size_family_audit.py --verify-report results/size_family_audit.json
```

Verification rebuilds every case, reruns primitive rules, checks whole outputs,
and compares every report field and pair sequence. Source SHA-256 bindings cover
the audit, reducer, tree helper and strict JSON reader. This is finite
reproducible evidence; [input validation](EVIDENCE_INPUTS.md) describes rejected
malformed report inputs.

## Existing project results and remaining obligations

The [Boolean-family follow-up](BOOLEAN_SIZE_FAMILY.md) separately supplies
actual value-bearing inputs to a framework built only from size. It checks
the AND task on all inputs through width 4 and a declared larger sample, with
small all-schedule exploration. This addresses the earlier tree-copy audit's
same-length-input limitation for that concrete task; its evidence remains
separate in [ledger Y](CLAIM_LEDGER.md#y-input-bearing-uniform-and-frameworks).

| Mechanism | Existing meaning | Further size-family obligation |
|---|---|---|
| Structural source encoding | Store/decode a finite source graph as data | Bound encoding/decoding; storage is not source execution |
| Coherent compiler | Fixed templates per source symbol and fixed primitive rules | Declare representation, build cost, runtime bounds and observations across a family |
| M3 resources | Separate work, allocation and peak for selected programs | Preserve schedule quantifiers; equal work does not imply equal peak |
| M5 reuse | Finite evidence-indexed strategies and common native costs | Charge per-use preparation/storage; a recipe is not a free copyable specimen |
| M6 continuation | Native result-controlled enable/skip with inputs prewired | Include dormant tasks in `I`; result numerals as subsequent inputs remain open |

Feedback natural inputs use unary source constructors. A bound in numeral
value is not automatically a bound in binary bit length. Future reports should
name abstract input size and concrete source/IC size separately.
