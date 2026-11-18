"""Frozen Boolean-chain syntax and value-independent localization compilation."""
from collections import Counter, deque
from dataclasses import dataclass
from itertools import permutations, product

from ic_primitive_port_verifier import Net
from ic_research_artifacts import GraphSpec
from .backend import literal, boolean_and, boolean_or, copy_value, decode


@dataclass(frozen=True)
class ChainProblem:
    n: int

    def __post_init__(self):
        if type(self.n) is not int or self.n not in (2, 3):
            raise ValueError("M7 freezes chain sizes 2 and 3")

    @property
    def input_bits(self):
        return 2+4*(self.n-1)

    def inputs(self):
        return product((False, True), repeat=self.input_bits)

    def validate_bits(self, bits):
        if type(bits) is not tuple or len(bits) != self.input_bits or any(type(b) is not bool for b in bits):
            raise ValueError("inputs must be an exact tuple of Boolean slots")
        return bits


@dataclass(frozen=True)
class Transform:
    kind: str
    order: tuple = ()
    materialize: tuple = ()
    representation: str = "S"

    def __post_init__(self):
        if self.kind not in ("direct", "ve") or self.representation not in ("S", "P"):
            raise ValueError("unknown transform kind or representation")
        if type(self.order) is not tuple or type(self.materialize) is not tuple:
            raise TypeError("order and materialize must be immutable tuples")
        if self.kind == "direct":
            if self.order or self.materialize:
                raise ValueError("direct enumeration has no elimination flags")
        elif (len(self.order) not in (2, 3) or any(type(v) is not int for v in self.order)
              or sorted(self.order) != list(range(len(self.order)))
              or len(self.materialize) != len(self.order) or any(type(b) is not bool for b in self.materialize)):
            raise ValueError("VE requires a permutation and one Boolean per elimination")

    def to_dict(self):
        return {"kind": self.kind, "order": list(self.order),
                "materialize": list(self.materialize), "representation": self.representation}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {"kind", "order", "materialize", "representation"}:
            raise ValueError("invalid transform record")
        return cls(data["kind"], tuple(data["order"]), tuple(data["materialize"]), data["representation"])


def enumerate_transforms(problem):
    if not isinstance(problem, ChainProblem):
        raise TypeError("expected ChainProblem")
    for rep in ("S", "P"):
        yield Transform("direct", representation=rep)
    for rep in ("S", "P"):
        for order in permutations(range(problem.n)):
            for flags in product((False, True), repeat=problem.n):
                yield Transform("ve", order, flags, rep)


def reference(problem, bits):
    """Independent direct evaluation; no compiler or backend is consulted."""
    problem.validate_bits(bits)
    for assignment in product((0, 1), repeat=problem.n):
        if bits[assignment[0]] and all(
                bits[2+4*i+2*assignment[i]+assignment[i+1]] for i in range(problem.n-1)):
            return True
    return False


@dataclass(frozen=True)
class IROp:
    kind: str
    arguments: tuple


@dataclass(frozen=True)
class CompiledTransform:
    problem: ChainProblem
    transform: Transform
    ir: tuple
    output: int
    materialized_entries: int

    @property
    def operation_counts(self):
        census = Counter(op.kind for op in self.ir)
        return {"AND": census["and"], "OR": census["or"],
                "input_slots": census["input"], "materialized_entries": self.materialized_entries}


def compile_transform(problem, transform):
    """Only input slots and declared materialized table roots are shared.

    Each recomputed syntax reference expands to fresh operations. Traverse
    materialized roots in elimination/table order, then the output, using
    left-to-right DFS. No input values are available during compilation.
    """
    if not isinstance(problem, ChainProblem) or not isinstance(transform, Transform):
        raise TypeError("expected ChainProblem and Transform")
    if transform.kind == "ve" and len(transform.order) != problem.n:
        raise ValueError("elimination permutation does not match problem size")
    source = [IROp("input", (i,)) for i in range(problem.input_bits)]

    def node(kind, arguments):
        index = len(source)
        source.append(IROp(kind, tuple(arguments)))
        return index

    def fold(kind, arguments):
        arguments = list(arguments)
        if not arguments:
            raise ValueError("empty product or sum is outside the frozen grammar")
        root = arguments[0]
        for argument in arguments[1:]:
            root = node(kind, (root, argument))
        return root

    forced = []
    if transform.kind == "direct":
        terms = []
        for assignment in product((0, 1), repeat=problem.n):
            terms.append(fold("and", [assignment[0]] + [
                2+4*i+2*assignment[i]+assignment[i+1] for i in range(problem.n-1)]))
        output = fold("or", terms)
    else:
        factors = [(0, (0,), {(v,): v for v in (0, 1)})]
        factors.extend((i+1, (i, i+1), {(a, b): 2+4*i+2*a+b for a, b in product((0, 1), repeat=2)})
                       for i in range(problem.n-1))
        for step, variable in enumerate(transform.order):
            incident = sorted((factor for factor in factors if variable in factor[1]), key=lambda f: f[0])
            scope = tuple(sorted(set().union(*(set(f[1]) for f in incident))-{variable}))
            table = {}
            for values in product((0, 1), repeat=len(scope)):
                assignment = dict(zip(scope, values))
                terms = []
                for value in (0, 1):
                    assignment[variable] = value
                    terms.append(fold("and", [f[2][tuple(assignment[v] for v in f[1])] for f in incident]))
                table[values] = fold("or", terms)
                if transform.materialize[step]:
                    forced.append(table[values])
            factors = [f for f in factors if variable not in f[1]]
            factors.append((problem.n+step, scope, table))
        if len(factors) != 1 or factors[0][1]:
            raise AssertionError("chain elimination must leave one scalar")
        output = factors[0][2][()]

    ir = list(source[:problem.input_bits])
    shared = set(forced)
    memo = {i: i for i in range(problem.input_bits)}

    def expand(index):
        if index in memo:
            return memo[index]
        operation = source[index]
        args = tuple(expand(child) for child in operation.arguments)
        fresh = len(ir)
        ir.append(IROp(operation.kind, args))
        if index in shared:
            memo[index] = fresh
        return fresh

    for root in forced:
        expand(root)
    result = expand(output)
    return CompiledTransform(problem, transform, tuple(ir), result, len(forced))


def build_network(problem, transform, bits, *, compiled=None):
    problem.validate_bits(bits)
    compiled = compile_transform(problem, transform) if compiled is None else compiled
    if not isinstance(compiled, CompiledTransform) or compiled.problem != problem or compiled.transform != transform:
        raise ValueError("compiled transform belongs to a different problem or transform")
    uses = [0]*len(compiled.ir)
    for operation in compiled.ir:
        if operation.kind != "input":
            for index in operation.arguments:
                uses[index] += 1
    uses[compiled.output] += 1
    net = Net()
    rep = transform.representation
    inputs = [literal(net, rep, bit) for bit in bits]
    available = [deque(copy_value(net, port, uses[i])) for i, port in enumerate(inputs)]
    for index, operation in enumerate(compiled.ir[problem.input_bits:], problem.input_bits):
        left, right = (available[i].popleft() for i in operation.arguments)
        builder = boolean_and if operation.kind == "and" else boolean_or
        port = builder(net, rep, left, right)
        available.append(deque(copy_value(net, port, uses[index])))
    decode(net, rep, available[compiled.output].popleft(), net.boundary("OUT"))
    if any(available):
        raise AssertionError("unconsumed linear IR ports")
    return GraphSpec.from_net(net)
