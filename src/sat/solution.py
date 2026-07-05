from pysat.formula import IDPool
from sat.literal import Literal


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
