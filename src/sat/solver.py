from pysat.solvers import Solver as PySolver
from subprocess import Popen, PIPE
from sat.cnf import CNF, IDPool, Literal

import threading
import queue

# Low-level solver output: satisfiability flag plus the signed assignment.
RawSolution = tuple[bool, list[int]]

class Solution:
    """A solved CNF result.

    Wraps the solver's satisfiability flag and signed assignment, and — given
    the originating CNF's variable pool — lets you query variable values by
    name (`sol["a"]`), by `Literal` (`sol[a]`), or by raw id (`sol[3]`).
    Truthiness reports satisfiability, so `if sol:` means "is sat".

    Query keys respect sign: a negated `Literal` or negative id returns the
    negated value. Reading any value from an unsatisfiable solution raises.
    """

    def __init__(self, sat: bool, assignment: list[int], v_pool: IDPool | None = None):
        self._sat = sat
        self._assignment = list(assignment)
        # Variables asserted False in the model; anything else reads as True,
        # matching a full solver model (and defaulting don't-cares to True).
        self._false_ids = {-lit for lit in self._assignment if lit < 0}
        self._v_pool = v_pool

    @property
    def sat(self) -> bool:
        return self._sat

    def __bool__(self) -> bool:
        return self._sat

    def assignment(self) -> list[int]:
        """The raw signed assignment as returned by the solver."""
        return list(self._assignment)

    def _resolve(self, key: str | Literal | int) -> int:
        """Resolve a name / Literal / id key to a signed variable id."""
        if isinstance(key, Literal):
            return key.value()
        if isinstance(key, bool):
            raise TypeError("bool is not a valid variable key")
        if isinstance(key, int):
            return key
        if isinstance(key, str):
            if self._v_pool is None or key not in self._v_pool.obj2id:
                raise KeyError(f"Unknown variable name: {key!r}")
            return self._v_pool.obj2id[key]
        raise TypeError(f"Unsupported key type: {type(key).__name__}")

    def __getitem__(self, key: str | Literal | int) -> bool:
        if not self._sat:
            raise ValueError("cannot query an unsatisfiable solution")
        signed = self._resolve(key)
        value = abs(signed) not in self._false_ids
        return value if signed > 0 else not value

    def value(self, key: str | Literal | int) -> bool:
        """Explicit alias for `sol[key]`."""
        return self[key]

    def __contains__(self, key: str | Literal | int) -> bool:
        try:
            signed = self._resolve(key)
        except (KeyError, TypeError):
            return False
        if self._v_pool is not None:
            return abs(signed) in self._v_pool.id2obj
        return abs(signed) in {abs(lit) for lit in self._assignment}

    def value_of(self, literals: list[Literal]) -> int:
        """Interpret a list of literals as an unsigned integer, LSB first."""
        return sum(int(self[lit]) << i for i, lit in enumerate(literals))

    def assign(self, literals: list[Literal]) -> list[Literal]:
        """Return each literal with its sign set by the solution, ignoring input signs."""
        if not self._sat:
            raise ValueError("cannot query an unsatisfiable solution")
        return [abs(lit) if self[abs(lit)] else -abs(lit) for lit in literals]

    def true_names(self) -> list[str]:
        """Names of all registered variables assigned True."""
        if not self._sat or self._v_pool is None:
            return []
        return [name for name, vid in self._v_pool.obj2id.items()
                if vid not in self._false_ids]

    def __repr__(self) -> str:
        if not self._sat:
            return "Solution(unsat)"
        return f"Solution(sat, {len(self._assignment)} vars)"


class Solver:
    external_solvers = {
        # "kissat": ["-q"],
        # "kissat": [],
        # "cms":["--verb", "0"],
        # "parkissat": ["-v=1", "-c=8", "-max-memory=8"]
    }

    builtin_solvers = [
        "kissat",
        "cadical103",
        "cadical153",
        "gluecard3",
        "gluecard4",
        "glucose3",
        "glucose4",
        "glucose42",
        "lingeling",
        "maplechrono",
        "maplecm",
        "maplesat",
        "mergesat3",
        "minicard",
        "minisat22",
        "minisat-gh",
    ]

    available_solvers = list(external_solvers.keys()) + builtin_solvers

    def __init__(self, name: str, args=None):
        if name not in Solver.available_solvers:
            raise ValueError(f"Solver {name} not supported")
        self.__name = name
        self.__args = args

    def solve(self, cnf: CNF) -> Solution:
        if self.__name in self.builtin_solvers:
            raw = self._solve_builtin(cnf)
        elif self.__name in self.external_solvers:
            raw = self._solve_external(cnf)
        else:
            raise ValueError(f"Solver {self.__name} not supported")

        sat, ids = raw
        return Solution(sat, ids, cnf.v_pool())

    def _solve_builtin(self, cnf: CNF) -> RawSolution:
        clauses = cnf.clauses()
        with PySolver(name=self.__name, bootstrap_with=clauses) as builtin_solver:
            if builtin_solver.solve():
                ids = builtin_solver.get_model()
                if ids:
                    return (True, ids)
                else:
                    return (False, [])
            else:
                return (False, [])

    def _solve_external(self, cnf: CNF) -> RawSolution:
        args = self.external_solvers[self.__name]
        if self.__args is not None:
            args += self.__args
        p = Popen([self.__name, *args], stdin=PIPE, stdout=PIPE, stderr=PIPE)

        clauses = cnf._cnf.clauses
        cls_num = len(clauses)
        step = 20000

        def producer(out_q):
            header = f"p cnf {cnf._cnf.nv} {cls_num}\n"
            out_q.put(header)
            for i in range(0, cls_num, step):
                slice = clauses[i : i + step]
                string = " 0\n".join([" ".join([str(lit) for lit in cl]) for cl in slice]) + " 0\n"
                out_q.put(string)
            out_q.put(None)

        def consumer(in_q, p):
            while True:
                item = in_q.get()
                if item is None:
                    break
                p.stdin.write(item.encode())
            p.stdin.close()

        q = queue.Queue()
        t1 = threading.Thread(target=producer, args=(q,))
        t2 = threading.Thread(target=consumer, args=(q, p))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert p.stdout is not None
        out = p.stdout.read()

        string = out.decode("utf-8")
        return self._parse_solution(string)

    @staticmethod
    def _parse_solution(string: str) -> RawSolution:
        string = string.lower()
        if "unsat" in string:
            return (False, [])

        def is_int(s):
            return s.isdigit() or (s[0] == "-" and s[1:].isdigit())

        ints = [int(s) for s in string.split() if is_int(s)]
        ids = [i for i in ints if i != 0]
        return (True, ids)


class IncrementalSolver:

    # Glucose-family solvers require `incr=True`
    _needs_incr_flag = {"glucose3", "glucose4", "glucose42", "gluecard3", "gluecard4"}

    def __init__(self, name: str, base_cnf: CNF):
        if name not in Solver.builtin_solvers:
            raise ValueError(
                f"Solver {name} not supported for incremental use "
                f"(builtins only: {Solver.builtin_solvers})"
            )

        self.__name = name
        kwargs = {"incr": True} if name in self._needs_incr_flag else {}
        self._solver = PySolver(name=name, **kwargs)
        self._solver.append_formula(base_cnf.clauses())
        self._v_pool = base_cnf.v_pool()

    def name(self) -> str:
        return self.__name

    def solve(self, assumptions: list[int] | None = None) -> Solution:
        sat = True if self._solver.solve(assumptions=assumptions or []) else False
        model = self._solver.get_model() or [] if sat else []
        return Solution(sat, model, self._v_pool)

    def get_core(self) -> list[int]:
        """Unsat core over the last `solve()` assumptions, or [] if none."""
        return self._solver.get_core() or []

    def stats(self) -> dict:
        """Solver-reported accounting (conflicts, decisions, propagations, ...)."""
        return dict(self._solver.accum_stats() or {})

    def add_clause(self, clause: list[int]) -> None:
        self._solver.add_clause(clause)

    def close(self) -> None:
        self._solver.delete()

    def __enter__(self) -> IncrementalSolver:
        return self

    def __exit__(self, *_) -> None:
        self.close()
