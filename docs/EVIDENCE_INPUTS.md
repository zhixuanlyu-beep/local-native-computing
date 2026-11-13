# Evidence input validation

The evidence readers reject ambiguous or malformed input before interpreting
it as a graph, a trace binding, or a successful computation. This is host-side
validation, separate from primitive IC semantics and native interaction costs.
[Ledger Z](CLAIM_LEDGER.md#z-evidence-input-validation-and-regression-audit)
records the reproduced defects, fixes and validation scope.

## JSON reports and trace headers

[ic_evidence_json.py](../ic_evidence_json.py) provides the shared decoder for
production JSON reading, including plain/gzip reports, trace headers, shard
metadata and the source rule table. It rejects duplicate object keys at every
nesting level, including escaped spellings of the same key. It also rejects
NaN, either infinity and floating-point overflow to infinity. Finite valid
JSON uses the standard decoder's value representation.

Without this check, the standard decoder silently keeps only the final value
of a repeated field. For example, an earlier altered `format` or `status`
could disappear before a verifier compares the parsed report. Strict decoding
does not replace reconstruction, source bindings, graph matching, trace
digests or EOF checks; each existing verifier retains those obligations.

## Literal graph schema and port types

`GraphSpec.from_dict` requires array fields `kinds`, `boundaries` and `wires`,
and permits the optional `cycles` field. Unknown fields, scalar strings used
as arrays, malformed wire arrays and byte strings used as endpoints are
rejected. The existing zero default for omitted `cycles` remains supported.
Valid canonical graph records retain the same serialization.

Direct construction and decoding both require integer cell indices and port
numbers, excluding Booleans. Python's `False == 0` and `True == 1` must not
allow a graph that succeeds in one constructor but fails its own serialized
round trip. Runtime bindings likewise reject Boolean/float port aliases before
allocating or linking any cells. Boundary labels remain strings; the generic
graph format still permits the empty string, while individual component
contracts may impose stronger label requirements.

The Boolean-size experiment additionally requires its declared fragment:
width 1..64, exactly `n-1` gamma framework cells and no detached wire cycles.
This precondition is checked before native execution. A delta-containing
network that happens to produce a correct value on one input is not evidence
for this experiment's AND framework contract. Incorrect wiring within the
declared fragment can still be executed as a negative fixture and classified
by its complete terminal graph.

## Failure cleanup and regression checks

The M4 interval reader closes its stream if header, payload length or digest
validation fails. A shard reader closes and clears its stream if the shard
header is invalid. These error paths do not leave partially opened resources
for a caller to recover from an unsuccessful reader initialization.

```sh
python tests/evidence_input_integrity.py
python tests/boolean_size_family_integrity.py
python ic_size_family_audit.py --verify-report results/size_family_audit.json
python ic_boolean_size_family.py --verify-report results/boolean_size_family.json
```

The input suite covers malformed constructors, valid graph round trips,
ambiguous/nonfinite JSON, real plain/gzip and trace-reader boundaries, and
stream cleanup. The Boolean suite separately exercises all supported widths
with fixed-seed randomized schedules, checks whole outputs and decreasing
potential, and compares work/censuses with snapshot runs. Those additional
trials are finite regression checks, not exhaustive scheduling evidence for
large graphs.

The two current size-family reports are rebuilt to bind the hardened readers.
Their execution evidence is unchanged. Earlier frozen archives and their
primitive streams are retained; the full historical CI runner verifies valid
archive compatibility using the updated readers.
