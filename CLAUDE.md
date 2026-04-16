# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
just venv                            # enter virtualenv shell (venv/)
pytest src/                          # run all tests
pytest src/sat/sat_test.py           # run SAT tests only
pytest src/ -k "test_xor"           # run a single test by name
```

No build step — this is a pure Python library.

## Architecture

**satgen** is a Python library with two independent modules:

### `src/sat/` — SAT/CNF constraint solver

- **`cnf.py`**: Builds CNF (Conjunctive Normal Form) formulas. `Literal` wraps a pysat variable ID with a name. `CNF` builds formulas incrementally via `set_literal()`, `equals()`, `nand()`, `xor()`, `atleast()`/`atmost()`/`exactly()`, etc. Internally uses pysat's `IDPool` for bidirectional name↔ID mapping and `CardEnc` for cardinality constraints. User variables are lowercase; internally generated auxiliary variables are uppercase (e.g. `A0`, `A1`).

- **`solver.py`**: Wraps multiple SAT backends behind a uniform interface. Built-in solvers come from pysat (cadical, glucose, minisat, lingeling, mapleSAT, and variants). External solver `kissat` is invoked via subprocess with threading for I/O. All solvers return `tuple[bool, list[int]]` — satisfiability flag plus signed variable assignments.


### Dependencies

- **pysat**: SAT solvers and CNF utilities (`IDPool`, `CardEnc`, built-in solvers)
- **pytest**: Testing

### Test strategy

Tests use heavy parametrization — all constraint types are tested across all 13 built-in solver backends × 32–64 random epochs each. When adding new CNF operations, follow this pattern in `sat_test.py`.
