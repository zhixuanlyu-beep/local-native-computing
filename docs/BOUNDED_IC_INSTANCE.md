# A bounded observation-to-IC research instance

This instance implements one finite path through the [research framework](RESEARCH_FRAMEWORK.md): declare an observation contract, enumerate literal IC carrier and gate graphs, reject them using concrete executions, verify the surviving combinations, and archive and reuse an actual runtime-produced structure. It supplies neither a general semantic synthesis algorithm nor the complete source feedback compiler. Concrete counts and verified coverage belong to the [claim ledger](CLAIM_LEDGER.md).

## Problem and budgets

The information objects are a supplied Boolean and an independently supplied rooted opaque package. The Boolean's false carrier is fixed to epsilon; its true carrier is part of the search. A passive storage-stage decoder distinguishes carrier graph representations. The task deliberately consumes this carrier and permits payload erasure.

The required passive output is exactly the payload topology for true and epsilon for false. No additional cells or cyclic wires may remain. Other declared consumers copy, erase, or unpack that output. Their expected graphs are constructed independently of the candidate implementation. The test observer inspects complete normal-form topology with labeled boundaries and the cyclic-wire count. Allocation names and reduction order are hidden. Readout is a graph observation after quiescence, with no claim of a constant-time local completion signal.

Allowed environments are explicitly finite and fixed before search: the listed training and held-out packages, with passive, copy, erase, and unpack consumers. Initial discovery uses only a subset of these probes. Subsequent checks can refute a candidate and refine that initial candidate class; they do not change the environment contract. Each consumer is attached before execution. All enabled active-pair choices are admitted, without a fairness filter. Nothing in the runtime chooses a branch from a host observation.

`SearchBudget` separates the carrier/gate construction family, the peak live-cell bound, and the screening/state/transition search budgets. A material-bound violation is recorded as such. An incomplete exploration never becomes a successful certificate. The retained-structure pipeline separately charges fresh reconstruction and includes the retained original network in its combined live-cell bound. These are symbolic IC allocations, not a physical inventory model.

## Finite construction family

[ic_bounded_synthesis.py](../ic_bounded_synthesis.py) generates the following family directly from primitive IC syntax:

- True carriers are connected reduced gamma/epsilon graphs within the declared cell bound. Their single `ROOT` boundary meets a principal port. Every matching of the remaining ports is considered; exact labeled-port isomorphism removes duplicate representatives. Port parity rules out the even cell counts in this one-boundary family.
- Gates contain one epsilon, gamma, or delta cell and three distinct boundaries `CTRL`, `DATA`, and `OUT`. Every complete port matching is considered. Gates are not prefiltered to the intended gamma-probe wiring.
- Every carrier representative is paired with every gate. A carrier coinciding with false in isolated storage fails the information distinction. Each other pair is tested against the observation contract.

This family is a declared design prior. The search does not discover the primitive IC rules, the graph grammar, false's representation, or an unbounded solution space. Its output is a list of verified carrier/gate graphs within that prior. It does not establish that an unsuccessful candidate family has no implementation outside the chosen bounds.

Initial discovery uses an epsilon package and a nontrivial wired package. The latter prevents a constant epsilon output from passing merely because an empty payload was used. Held-out tree and internally cross-wired packages then exercise a different part of the fixed allowed payload class. A candidate that fails these later checks is rejected and its concrete counterexample retained. The generated report records every candidate, its outcome, and its rejection or incomplete verification record.

## Rejection and exhaustive verification

A deterministic screening execution can refute a candidate with a concrete wrong normal form or resource violation. A successful screening execution is insufficient for acceptance. Surviving cases are explored by [ic_bounded_execution.py](../ic_bounded_execution.py), which reduces every enabled active pair from every discovered state.

The explorer merges states only after exact port-labeled graph isomorphism, including boundary identities and cyclic wires. A graph hash is a prefilter. Cell allocation counters are irrelevant to this quotient because the rules allocate fresh names and are invariant under renaming. Each new representative retains a concrete parent and redex, so its discovery trace can be replayed using the original primitive reducer.

A complete finite acyclic execution graph certifies that every maximal execution of that concrete initial net terminates. All its terminal graphs must meet the independently built postcondition. Reachable cycles represent possible infinite executions in the quotient; the cycle-lifting helper remaps concrete cell identities when repeating them. State, transition, and material cutoffs leave the exploration incomplete. Finite dead ends, wrong results, possible infinite runs, and unexplored runs are distinct outcomes.

The report's scope is the listed inputs and consumers. Agreement there is not arbitrary-context equivalence. Counterexamples are stronger in the negative direction: one replayed permitted execution suffices to refute that candidate's universal task claim.

Initial and expanded probe observations form two finite signatures. Projecting the expanded signature onto the original training probes recovers the initial signature. The report records this forgetting map and the local interface predicates shared by the final candidates. Refining this probe partition does not change the fixed environment or establish a decision procedure for true contextual equivalence.

## What the discovered interface means

The smallest verified carrier/gate combination can be inspected as a local contract. The self-paired gamma carrier `Loop` and a gamma probe give a particularly direct mechanism: a gamma-gamma interaction splices the probe's two auxiliary contexts together, whereas an epsilon at its principal port produces epsilon at both contexts. One context is the output and the other is the payload root. The task chooses no runtime rewrite based on a decoded Boolean.

This local mechanism is already related to the selector probes documented in the ledger. The added result is a finite semantics-driven graph search, complete candidate accounting, executable rejection traces, and exhaustive validation of the declared small compositions. It does not count as a new source-language rule certificate.

The search also includes the older `gamma(epsilon,epsilon)` candidate carrier. Structural distinction from epsilon during storage does not ensure that the same distinction survives a particular consumer. Its failed gate combinations provide concrete protocol counterexamples. They do not prove global equivalence of that carrier with epsilon or impossibility of all adapters.

## Native production, archive, and reuse

[ic_research_pipeline.py](../ic_research_pipeline.py) attaches a delta consumer to a discovered gate before execution. Native gamma/delta/epsilon reductions produce two independent rooted copies. The pipeline checks their complete expected graph and disjoint components, then checks absence of original payload cells in the recorded concrete producer runs. The archived component is therefore an actual product of evolution.

[ic_research_artifacts.py](../ic_research_artifacts.py) records its literal graph syntax, root interface, source-graph fingerprint, original input graph, primitive reduction trace, construction contract, and costs. Capture traverses the entire component, including internal wiring; it rejects an active component or one connected to another open boundary. Import validates the structural constraints. A metadata assertion is not treated as a proof: the pipeline independently replays the producer and compares the recaptured graph with the archived specimen.

The next experiment uses a separate Boolean input and a fresh specimen instantiated from the archive. Its builder reads the saved graph and the new input, not the old task's answer. A native consumer is prewired, all reachable schedules are checked, and the original producer network is compared before and after reuse. Export and reconstruction are offline research tools; the subsequent runtime still consists only of primitive IC reductions. Fresh allocation is charged, and the original delivered structure remains present.

This is a finite artifact workflow. It retains and reconstructs a runtime-created structure with explicit conditions. It does not learn an unbounded library, reuse physical matter without reconstruction, or establish replacement under arbitrary consumers.

## Reproduce

Install the pinned repository dependency, then run:

```sh
python ic_bounded_execution.py
python ic_research_artifacts.py
python ic_bounded_synthesis.py
python ic_research_pipeline.py --report results/native_ic_research.json.gz
python ic_research_pipeline.py --verify-report results/native_ic_research.json.gz
```

The report command writes the complete candidate records, replayable counterexamples, per-case execution summaries, and archived artifacts. A `.gz` suffix compresses the UTF-8 JSON. The verification command reads the saved report, replays its counterexamples and producers, and checks native reuse in the declared environments. A [saved report](../results/native_ic_research.json.gz) is included. The other entry points exercise the supporting checks separately; the integrated pipeline and supporting checks are included in [the repository runner](../tests/run_all.sh).

The complete source compiler, protocol adapters outside this instance, general constraint discovery, stronger contextual replacement, and physical resource models retain their separate obligations in the [framework](RESEARCH_FRAMEWORK.md#8-next-obligations-and-reporting-discipline).
