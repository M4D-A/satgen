from pysat.solvers import Solver as PySolver
from sat.cnf import CNF
from sat.solution import Solution
from sat.solver import Solver


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

    def __enter__(self) -> "IncrementalSolver":
        return self

    def __exit__(self, *_) -> None:
        self.close()
