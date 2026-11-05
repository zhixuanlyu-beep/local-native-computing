"""Evidence-indexed M5 retrieval over the frozen M4 discovery report.

Entries are literal structures with source evidence.  Retrieval matches
representations, interface and explicitly declared evidence scope; it never
adapts a B entry to an A request or infers applicability from a task name.
"""
from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import json
from pathlib import Path
import struct
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from ic_coherent_feedback import spec_digest
from ic_observation_contracts import FAMILIES, FAMILY_INTERFACES, TaskContract
from ic_research_artifacts import GraphSpec
from ic_schedule_audit import Schedule, ScheduledNet


ROOT = Path(__file__).parent
REPORT_PATH = ROOT / "results" / "multitask_discovery.json.gz"
TRACE_PATH = ROOT / "results" / "multitask_discovery.ictrace.gz"
M4_REPORT_SHA256 = "10b65298e08c366e4a5da7ba00a14caf03e7fd6115fc2e818d77c8e42b64b08e"
REPORT_FORMAT = "ic-multitask-discovery-v1"
TRACE_FORMAT = "IC-PAIR-U32LE-1"
EVIDENCE_TIERS = ("fifo", "all-schedules-finite")
ELEMENT_BUDGET = {"max_steps": 128, "max_cells": 128}
SCHEMA_VERSION = "ic-structure-library-v1"


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _exact_keys(value: Mapping[str, Any], keys: Sequence[str], name: str) -> None:
    if set(value) != set(keys):
        raise ValueError(f"{name} fields differ from the strict schema")


def _str_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a sequence of strings")
    if any(type(item) is not str for item in value):
        raise TypeError(f"{name} must contain only strings")
    return tuple(value)


def _bool_tuple(value: Any, name: str) -> tuple[bool, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a sequence of booleans")
    if any(type(item) is not bool for item in value):
        raise TypeError(f"{name} must contain only booleans")
    return tuple(value)


def _digest(value: Any) -> str:
    if type(value) is not str or len(value) != 64 or any(
            c not in "0123456789abcdef" for c in value):
        raise ValueError("a source SHA-256 field has invalid encoding")
    return value


def _pair_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _freeze_json(value: Any):
    """Recursively detach owned JSON data from the mutable source report."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if type(value) in (list, tuple):
        return tuple(_freeze_json(item) for item in value)
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise TypeError("library-owned JSON fields must contain only JSON values")


def _deep_json_copy(value: Any):
    """Return a fully detached ordinary-JSON copy of a frozen mapping tree."""
    if isinstance(value, Mapping):
        return {key: _deep_json_copy(item) for key, item in value.items()}
    if type(value) in (list, tuple):
        return [_deep_json_copy(item) for item in value]
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise TypeError("library-owned JSON fields must contain only JSON values")


def _entry_fingerprint(graph_sha256, task_descriptor, evidence_scope):
    return spec_digest(_deep_json_copy({
        "graph_sha256": graph_sha256,
        "task_descriptor": task_descriptor,
        "evidence_scope": list(evidence_scope),
    }))


@dataclass(frozen=True)
class TraceBinding:
    """The raw M4 trace interval and digest bound to one source case."""

    start_record: int
    length_records: int
    pair_digest: str

    def __post_init__(self):
        if type(self.start_record) is not int or self.start_record < 0:
            raise ValueError("trace start must be a non-negative integer")
        if type(self.length_records) is not int or self.length_records < 0:
            raise ValueError("trace length must be a non-negative integer")
        if _digest(self.pair_digest) != self.pair_digest:
            raise ValueError("invalid trace pair digest")

    def to_dict(self):
        return {"start_record": self.start_record,
                "length_records": self.length_records,
                "pair_digest": self.pair_digest}

    @classmethod
    def from_dict(cls, data):
        data = _mapping(data, "trace binding")
        _exact_keys(data, ("start_record", "length_records", "pair_digest"), "trace binding")
        return cls(data["start_record"], data["length_records"], data["pair_digest"])


@dataclass(frozen=True)
class SourceCase:
    """One fixed finite input case and its full source observation."""

    bits: tuple[bool, ...]
    observation_id: int
    initial_graph_sha256: str
    final_graph_sha256: str
    status: str
    terminal: bool
    primitive_interactions: int
    resources: Mapping[str, Any]
    initial_graph: Mapping[str, Any]
    final_graph: Mapping[str, Any]
    expected_graph_sha256: str
    trace: TraceBinding

    def __post_init__(self):
        object.__setattr__(self, "resources", _freeze_json(self.resources))
        object.__setattr__(self, "initial_graph", _freeze_json(self.initial_graph))
        object.__setattr__(self, "final_graph", _freeze_json(self.final_graph))
        _bool_tuple(self.bits, "bits")
        if type(self.observation_id) is not int or self.observation_id < 0:
            raise ValueError("observation ID must be a non-negative integer")
        _digest(self.initial_graph_sha256)
        _digest(self.final_graph_sha256)
        _digest(self.expected_graph_sha256)
        if not isinstance(self.trace, TraceBinding):
            raise TypeError("case trace must be a TraceBinding")
        _mapping(self.resources, "resources")
        _mapping(self.initial_graph, "initial graph")
        _mapping(self.final_graph, "final graph")
        if self.status not in ("normal-form", "resource-violation", "incomplete"):
            raise ValueError("unknown source observation status")
        if type(self.terminal) is not bool:
            raise TypeError("terminal must be boolean")
        if type(self.primitive_interactions) is not int or self.primitive_interactions < 0:
            raise ValueError("primitive interaction count must be non-negative")
        if self.primitive_interactions != self.trace.length_records:
            raise ValueError("case trace length differs from primitive interactions")
        if self.status != "normal-form" or self.terminal is not True:
            raise ValueError("a catalog source case must be a terminal normal form")

    def to_dict(self):
        return {
            "bits": list(self.bits),
            "observation_id": self.observation_id,
            "initial_graph_sha256": self.initial_graph_sha256,
            "final_graph_sha256": self.final_graph_sha256,
            "status": self.status,
            "terminal": self.terminal,
            "primitive_interactions": self.primitive_interactions,
            "resources": _deep_json_copy(self.resources),
            "initial_graph": _deep_json_copy(self.initial_graph),
            "final_graph": _deep_json_copy(self.final_graph),
            "expected_graph_sha256": self.expected_graph_sha256,
            "trace": self.trace.to_dict(),
        }

    @classmethod
    def from_dict(cls, data):
        data = _mapping(data, "source case")
        _exact_keys(data, ("bits", "observation_id", "initial_graph_sha256",
                           "final_graph_sha256", "status", "terminal",
                           "primitive_interactions", "resources", "initial_graph",
                           "final_graph", "expected_graph_sha256", "trace"), "source case")
        return cls(_bool_tuple(data["bits"], "bits"), data["observation_id"],
                   data["initial_graph_sha256"], data["final_graph_sha256"],
                   data["status"], data["terminal"], data["primitive_interactions"],
                   data["resources"], data["initial_graph"], data["final_graph"],
                   data["expected_graph_sha256"], TraceBinding.from_dict(data["trace"]))


@dataclass(frozen=True)
class ScheduleProofSummary:
    """A trusted-report import of an exhaustive schedule proof summary."""

    check_id: int
    status: str
    execution: Mapping[str, Any]

    def __post_init__(self):
        object.__setattr__(self, "execution", _freeze_json(self.execution))
        if type(self.check_id) is not int or self.check_id < 0:
            raise ValueError("schedule check ID must be a non-negative integer")
        if self.status not in ("passed", "incomplete", "resource-violation",
                               "wrong-normal-form", "reachable-cycle"):
            raise ValueError("unknown schedule proof status")
        _mapping(self.execution, "schedule execution")

    def to_dict(self):
        return {"check_id": self.check_id, "status": self.status,
                "execution": _deep_json_copy(self.execution)}

    @classmethod
    def from_dict(cls, data):
        data = _mapping(data, "schedule proof")
        _exact_keys(data, ("check_id", "status", "execution"), "schedule proof")
        return cls(data["check_id"], data["status"], data["execution"])


@dataclass(frozen=True)
class LibraryEntry:
    """One verified graph/contract/evidence-scope assignment."""

    id: str
    task_name: str
    task_descriptor: Mapping[str, Any]
    input_reprs: tuple[str, ...]
    output_reprs: tuple[str, ...]
    interface: tuple[str, ...]
    graph: Mapping[str, Any]
    graph_sha256: str
    candidate_id: str
    source_report_sha256: str
    cases: tuple[SourceCase, ...]
    all_schedule_checks: tuple[ScheduleProofSummary, ...]
    evidence_scope: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "task_descriptor", _freeze_json(self.task_descriptor))
        object.__setattr__(self, "graph", _freeze_json(self.graph))
        if type(self.id) is not str or not self.id:
            raise ValueError("entry ID must be a nonempty string")
        _str_tuple(self.input_reprs, "input representations")
        _str_tuple(self.output_reprs, "output representations")
        _str_tuple(self.interface, "interface")
        _mapping(self.task_descriptor, "task descriptor")
        _mapping(self.graph, "graph")
        _digest(self.graph_sha256)
        _digest(self.candidate_id)
        _digest(self.source_report_sha256)
        if not isinstance(self.cases, tuple) or not self.cases or any(
                not isinstance(case, SourceCase) for case in self.cases):
            raise ValueError("an entry needs a nonempty tuple of source cases")
        if not isinstance(self.all_schedule_checks, tuple) or any(
                not isinstance(check, ScheduleProofSummary)
                for check in self.all_schedule_checks):
            raise TypeError("schedule proofs must be a tuple of summaries")
        task = TaskContract(self.task_name, self.task_descriptor["family"],
                            self.input_reprs, self.output_reprs,
                            self.task_descriptor["mask"])
        _exact_keys(self.task_descriptor, ("name", "family", "input_reprs",
                                           "output_reprs", "mask", "interface"),
                    "task descriptor")
        GraphSpec.from_dict(self.graph)
        if self.task_descriptor.get("name") != self.task_name:
            raise ValueError("task descriptor name differs from the entry task name")
        if list(self.task_descriptor["interface"]) != list(self.interface):
            raise ValueError("entry interface differs from its task descriptor")
        if task.interface != self.interface or self.interface != FAMILY_INTERFACES[task.family]:
            raise ValueError("entry interface is not the fixed family interface")
        if not self.all_schedule_checks:
            raise ValueError("an entry needs at least one exhaustive schedule proof")
        if not isinstance(self.evidence_scope, tuple) or not self.evidence_scope:
            raise ValueError("an entry needs an explicit ordered evidence scope")
        if any(tier not in EVIDENCE_TIERS for tier in self.evidence_scope):
            raise ValueError("unknown evidence tier")
        if tuple(sorted(self.evidence_scope, key=EVIDENCE_TIERS.index)) != self.evidence_scope:
            raise ValueError("evidence tiers must use the declared order")
        if "all-schedules-finite" in self.evidence_scope and not self.all_schedule_checks:
            raise ValueError("all-schedules evidence needs schedule proof summaries")
        for check in self.all_schedule_checks:
            if check.status != "passed":
                raise ValueError("a catalog entry cannot use an unpassed schedule proof")
        if spec_digest(_deep_json_copy(self.graph)) != self.graph_sha256:
            raise ValueError("entry graph fingerprint differs from its graph")
        if self.graph_sha256 != self.candidate_id:
            raise ValueError("entry graph and candidate fingerprints differ")
        if self.source_report_sha256 != M4_REPORT_SHA256:
            raise ValueError("entry does not bind the frozen M4 report")
        expected_id = self.entry_id()
        if self.id != expected_id:
            raise ValueError("entry ID differs from its evidence-scope fingerprint")
        task_inputs = task.inputs()
        if len(self.cases) != len(task_inputs):
            raise ValueError("entry cases do not cover the fixed finite input domain")
        for case, bits in zip(self.cases, task_inputs):
            if case.bits != bits:
                raise ValueError("entry cases are not in the declared input order")

    def entry_id(self) -> str:
        return _entry_fingerprint(self.graph_sha256, self.task_descriptor,
                                  self.evidence_scope)

    @property
    def minimum_evidence(self) -> str:
        return self.evidence_scope[-1]


    def to_dict(self):
        return {
            "id": self.id,
            "task_name": self.task_name,
            "task_descriptor": _deep_json_copy(self.task_descriptor),
            "input_reprs": list(self.input_reprs),
            "output_reprs": list(self.output_reprs),
            "interface": list(self.interface),
            "graph": _deep_json_copy(self.graph),
            "graph_sha256": self.graph_sha256,
            "candidate_id": self.candidate_id,
            "source_report_sha256": self.source_report_sha256,
            "cases": [case.to_dict() for case in self.cases],
            "all_schedule_checks": [check.to_dict() for check in self.all_schedule_checks],
            "evidence_scope": list(self.evidence_scope),
        }

    @classmethod
    def from_dict(cls, data):
        data = _mapping(data, "library entry")
        _exact_keys(data, ("id", "task_name", "task_descriptor", "input_reprs",
                           "output_reprs", "interface", "graph", "graph_sha256",
                           "candidate_id", "source_report_sha256", "cases",
                           "all_schedule_checks", "evidence_scope"), "library entry")
        return cls(data["id"], data["task_name"], data["task_descriptor"],
                   _str_tuple(data["input_reprs"], "input representations"),
                   _str_tuple(data["output_reprs"], "output representations"),
                   _str_tuple(data["interface"], "interface"), data["graph"],
                   data["graph_sha256"], data["candidate_id"],
                   data["source_report_sha256"],
                   tuple(SourceCase.from_dict(case) for case in data["cases"]),
                   tuple(ScheduleProofSummary.from_dict(check)
                         for check in data["all_schedule_checks"]),
                   _str_tuple(data["evidence_scope"], "evidence scope"))


@dataclass(frozen=True)
class Catalog:
    """An immutable tuple of entries plus the source report binding."""

    entries: tuple[LibraryEntry, ...]
    source_report_sha256: str
    source_binding: Mapping[str, Any]

    def __post_init__(self):
        object.__setattr__(self, "source_binding", _freeze_json(self.source_binding))
        if not isinstance(self.entries, tuple) or any(
                not isinstance(entry, LibraryEntry) for entry in self.entries):
            raise TypeError("catalog entries must be a tuple of LibraryEntry")
        _digest(self.source_report_sha256)
        _mapping(self.source_binding, "source binding")
        ids = [entry.id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("catalog contains duplicate entry IDs")
        if any(entry.source_report_sha256 != self.source_report_sha256
               for entry in self.entries):
            raise ValueError("catalog entry source report differs from catalog source")

    def query(self, input_reprs, output_reprs, interface, task_name=None,
              minimum_evidence="fifo"):
        input_reprs = _str_tuple(input_reprs, "input representations")
        output_reprs = _str_tuple(output_reprs, "output representations")
        interface = _str_tuple(interface, "interface")
        if task_name is not None and type(task_name) is not str:
            raise TypeError("task_name must be a string or None")
        if minimum_evidence not in EVIDENCE_TIERS:
            raise ValueError("minimum evidence must be one of " + ", ".join(EVIDENCE_TIERS))
        required = EVIDENCE_TIERS[:EVIDENCE_TIERS.index(minimum_evidence) + 1]
        return tuple(entry for entry in self.entries
                     if entry.input_reprs == input_reprs
                     and entry.output_reprs == output_reprs
                     and entry.interface == interface
                     and (task_name is None or entry.task_name == task_name)
                     and all(tier in entry.evidence_scope for tier in required))

    def get_entry(self, entry_id):
        if type(entry_id) is not str:
            raise TypeError("entry ID must be a string")
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        raise KeyError(entry_id)

    def to_dict(self):
        return {
            "schema_version": SCHEMA_VERSION,
            "source_report_sha256": self.source_report_sha256,
            "source_binding": _deep_json_copy(self.source_binding),
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data):
        data = _mapping(data, "catalog")
        _exact_keys(data, ("schema_version", "source_report_sha256",
                           "source_binding", "entries"), "catalog")
        if data["schema_version"] != SCHEMA_VERSION:
            raise ValueError("unknown structure-library schema version")
        return cls(tuple(LibraryEntry.from_dict(entry) for entry in data["entries"]),
                   data["source_report_sha256"], data["source_binding"])


def _load_frozen_report(report_path=REPORT_PATH) -> tuple[Path, dict[str, Any]]:
    report_path = Path(report_path)
    raw = report_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != M4_REPORT_SHA256:
        raise ValueError("frozen M4 report digest changed")
    if report_path.suffix != ".gz":
        raise ValueError("the frozen M4 report must be gzip-encoded")
    report = json.loads(gzip.decompress(raw).decode("utf-8"))
    if report.get("format") != REPORT_FORMAT or report.get("status") != "passed":
        raise ValueError("the frozen M4 report is not accepted evidence")
    return report_path, report


def _entry_from_outcome(row, outcome, task_data, report, check_ids):
    observations = report["discovery"]["observations"]
    checks = report["discovery"]["all_schedule_checks"]
    task = TaskContract(task_data["name"], task_data["family"],
                        tuple(task_data["input_reprs"]),
                        tuple(task_data["output_reprs"]), task_data["mask"])
    if outcome["task"] != task.name or outcome["status"] != "verified":
        raise ValueError("the report does not verify this assignment")
    if tuple(task_data["interface"]) != task.interface:
        raise ValueError("serialized task interface differs from its fixed contract")
    graph = row["graph"]
    if type(row["index"]) is not int or row["index"] < 0:
        raise ValueError("candidate row index is invalid")
    if spec_digest(graph) != row["candidate_id"]:
        raise ValueError("candidate row fingerprint differs from its graph")
    cases = []
    for bits, case in zip(task.inputs(), outcome["cases"]):
        observation = observations[case["observation"]]
        if (type(case["observation"]) is not int or not 0 <= case["observation"] < len(observations)
                or case["status"] != "matched" or type(case["expected_graph_sha256"]) is not str):
            raise ValueError("verified outcome case schema is invalid")
        if (observation["candidate_id"] != row["candidate_id"]
                or tuple(observation["input_reprs"]) != task.input_reprs
                or tuple(observation["bits"]) != bits
                or observation["status"] != "normal-form"
                or observation["terminal"] is not True
                or case["status"] != "matched"):
            raise ValueError("verified outcome refers to an unmatched source observation")
        if (spec_digest(observation["initial_graph"]) != observation["initial_graph_sha256"]
                or spec_digest(observation["final_graph"]) != observation["final_graph_sha256"]
                or case["expected_graph_sha256"] != spec_digest(
                    GraphSpec.from_net(observations_expected(task, bits)).to_dict())):
            raise ValueError("verified source case graph digest mismatch")
        start = observation["trace_offset_records"]
        length = observation["primitive_interactions"]
        if type(start) is not int or start < 0 or type(length) is not int or length < 0:
            raise ValueError("source observation trace interval is invalid")
        if start + length > report["trace"]["steps"]:
            raise ValueError("source observation trace interval exceeds the M4 trace")
        interval = report["trace_intervals"][case["observation"]]
        cases.append(SourceCase(bits, case["observation"],
                                observation["initial_graph_sha256"],
                                observation["final_graph_sha256"],
                                observation["status"], observation["terminal"],
                                length, observation["resources"],
                                observation["initial_graph"], observation["final_graph"],
                                case["expected_graph_sha256"],
                                TraceBinding(start, length, _pair_digest(interval))))
    schedule_checks = []
    for check_id in check_ids:
        if type(check_id) is not int or not 0 <= check_id < len(checks):
            raise ValueError("schedule check reference is invalid")
        check = checks[check_id]
        if (check["id"] != check_id or check["status"] != "passed"
                or check["observation"] not in {case["observation"] for case in outcome["cases"]}
                or check["expected_graph_sha256"] not in
                {case["expected_graph_sha256"] for case in outcome["cases"]}):
            raise ValueError("verified outcome refers to an unpassed schedule proof")
        schedule_checks.append(ScheduleProofSummary(check_id, check["status"], check["execution"]))
    descriptor = dict(task_data)
    return LibraryEntry(_entry_fingerprint(row["candidate_id"], descriptor,
                                           EVIDENCE_TIERS),
                        task.name, descriptor, task.input_reprs,
                        task.output_reprs, task.interface, graph, row["candidate_id"],
                        row["candidate_id"], M4_REPORT_SHA256, tuple(cases),
                        tuple(schedule_checks), EVIDENCE_TIERS)


def observations_expected(task, bits):
    """Late import avoids a constructor/expectation import cycle."""
    from ic_observation_contracts import expected
    return expected(task, bits)


def build_catalog(report_path=REPORT_PATH, trace_path=TRACE_PATH) -> Catalog:
    """Import every verified graph row without rerunning the M4 search."""
    report_path, report = _load_frozen_report(report_path)
    tasks = {task["name"]: task for task in report["bindings"]["tasks"]}
    binding = {
        "format": report["format"], "metadata": report["metadata"],
        "trace": report["trace"], "contract": report["bindings"]["contract"],
        "contract_sha256": report["bindings"]["contract_sha256"],
        "frozen_reports": report["bindings"]["frozen_reports"],
    }
    trace = _IntervalTrace(trace_path, binding)
    entries = []
    try:
        intervals = {}
        source_report = {**report, "trace_intervals": intervals}
        for family in FAMILIES:
            for row in report["discovery"]["candidate_ledgers"][family]:
                for outcome in row["outcomes"]:
                    if outcome["status"] != "verified":
                        continue
                    task_data = tasks[outcome["task"]]
                    if task_data["family"] != family:
                        raise ValueError("outcome task family differs from its ledger")
                    check_ids = _verified_check_ids(outcome)
                    for case in outcome["cases"]:
                        oid = case["observation"]
                        if oid not in intervals:
                            observation = report["discovery"]["observations"][oid]
                            intervals[oid] = trace.raw_bytes(
                                observation["trace_offset_records"],
                                observation["primitive_interactions"])
                    entries.append(_entry_from_outcome(row, outcome, task_data,
                                                       source_report, check_ids))
    finally:
        trace.close()
    return Catalog(tuple(entries), M4_REPORT_SHA256, binding)


def _verified_check_ids(outcome):
    checks = outcome.get("all_schedule_checks")
    if not isinstance(checks, list) or not checks or any(type(x) is not int for x in checks):
        raise ValueError("verified outcome lacks its exhaustive schedule checks")
    return tuple(checks)


class _IntervalTrace:
    """Read arbitrary trace intervals while validating the M4 header."""

    def __init__(self, path, source_binding):
        self.path = Path(path)
        self.stream = gzip.open(self.path, "rb")
        try:
            self.header = json.loads(self.stream.readline())
            self.payload_start = self.stream.tell()
        except BaseException:
            self.stream.close()
            raise
        expected = {"format": TRACE_FORMAT, "scope": source_binding["metadata"]["scope"],
                    "bindings_sha256": source_binding["metadata"]["bindings_sha256"]}
        if self.header != expected:
            raise ValueError("M4 trace header binding mismatch")
        self.stream.seek(self.payload_start)
        summary = source_binding["trace"]
        digest, records = hashlib.sha256(), 0
        while block := self.stream.read(1024 * 1024):
            if len(block) % 8:
                raise ValueError("truncated M4 primitive pair record")
            digest.update(block)
            records += len(block) // 8
        if (records != summary["steps"]
                or digest.hexdigest() != summary["sha256_of_pair_records"]):
            raise ValueError("M4 trace payload differs from its report summary")
        self.stream.seek(self.payload_start)

    def interval(self, binding: TraceBinding) -> tuple[tuple[str, str], ...]:
        raw = self.raw_bytes(binding.start_record, binding.length_records)
        if _pair_digest(raw) != binding.pair_digest:
            raise ValueError("M4 local observation pair digest mismatch")
        return tuple(tuple("c" + str(value) for value in pair)
                     for pair in struct.iter_unpack("<II", raw))

    def raw_bytes(self, start_record, length_records):
        self.stream.seek(self.payload_start + 8 * start_record)
        raw = self.stream.read(8 * length_records)
        if len(raw) != 8 * length_records:
            raise ValueError("truncated M4 local observation trace")
        return raw

    def close(self):
        self.stream.close()


def _replay_case(entry, source_case, trace):
    pairs = trace.interval(source_case.trace)
    if source_case.primitive_interactions != len(pairs):
        raise ValueError("replay pair count differs from its source case")
    initial = GraphSpec.from_dict(source_case.initial_graph)
    if spec_digest(initial.to_dict()) != source_case.initial_graph_sha256:
        raise ValueError("replay initial graph fingerprint mismatch")
    net = initial.instantiate(ScheduledNet(Schedule("fifo")))
    budget = ELEMENT_BUDGET
    steps = 0
    while True:
        if len(net.nodes) > budget["max_cells"]:
            status = "resource-violation"
            break
        pair = net.next_active()
        if pair is None:
            status = "normal-form"
            break
        if steps >= budget["max_steps"]:
            status = "incomplete"
            break
        if steps >= len(pairs) or pairs[steps] != pair:
            raise ValueError("replay pair differs from the FIFO source trace")
        net.reduce(*pair)
        steps += 1
    if steps != len(pairs):
        raise ValueError("replay terminated before consuming its trace interval")
    final_spec = GraphSpec.from_net(net).to_dict()
    if (status != source_case.status or steps != source_case.primitive_interactions
            or bool(net.active()) == source_case.terminal
            or spec_digest(final_spec) != source_case.final_graph_sha256):
        raise ValueError("replay result differs from its source observation")
    _compare_canonical("resources", net.statistics(), source_case.resources)
    _compare_canonical("final graph", final_spec, source_case.final_graph)
    task = TaskContract(entry.task_name, entry.task_descriptor["family"],
                        entry.input_reprs, entry.output_reprs, entry.task_descriptor["mask"])
    if (spec_digest(GraphSpec.from_dict(source_case.initial_graph).to_dict())
            != source_case.initial_graph_sha256):
        raise ValueError("source initial graph changed during replay")
    expected_digest = spec_digest(GraphSpec.from_net(
        observations_expected(task, source_case.bits)).to_dict())
    if expected_digest != source_case.expected_graph_sha256:
        raise ValueError("replay expected output fingerprint differs")
    return {"observation": source_case.observation_id,
            "primitive_interactions": steps, "status": status}


def _compare_canonical(name, left, right):
    if spec_digest(_jsonable(left)) != spec_digest(_jsonable(right)):
        raise ValueError(f"source and rebuilt {name} differ")


def _jsonable(value):
    return _deep_json_copy(value)


def verify_catalog(catalog, report_path=REPORT_PATH, trace_path=TRACE_PATH) -> dict[str, Any]:
    """Fresh source comparison plus FIFO replay of every referenced case."""
    fresh = build_catalog(report_path)
    if spec_digest(catalog.to_dict()) != spec_digest(fresh.to_dict()):
        raise ValueError("catalog differs from a fresh source-report reconstruction")
    trace = _IntervalTrace(trace_path, fresh.source_binding)
    replayed = 0
    primitive_interactions = 0
    seen = set()
    try:
        for entry in catalog.entries:
            for source_case in entry.cases:
                if source_case.observation_id in seen:
                    continue
                seen.add(source_case.observation_id)
                result = _replay_case(entry, source_case, trace)
                replayed += 1
                primitive_interactions += result["primitive_interactions"]
    finally:
        trace.close()
    if replayed != len(seen):
        raise AssertionError("replay accounting differs from its union")
    return {
        "schema_version": SCHEMA_VERSION,
        "source_report_sha256": M4_REPORT_SHA256,
        "entries": len(catalog.entries),
        "verified_assignments": sum(len(entry.cases) for entry in catalog.entries),
        "replayed_observations": replayed,
        "primitive_interactions": primitive_interactions,
        "trace": dict(fresh.source_binding["trace"]),
        "status": "passed",
    }


def main():
    catalog = build_catalog()
    print("PASS:", len(catalog.entries), "verified evidence-indexed entries")


if __name__ == "__main__":
    main()
