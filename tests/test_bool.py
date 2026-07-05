from functools import reduce


def test_equals_true(ab_cnf, solver):
    cnf, (a, b) = ab_cnf
    cnf.equals(a, b).set_literal(a)
    sol = solver.solve(cnf)
    assert sol
    assert sol[a]
    assert sol[b]


def test_equals_false(ab_cnf, solver):
    cnf, (a, b) = ab_cnf
    cnf.equals(a, b).set_literal(-b)
    sol = solver.solve(cnf)
    assert sol
    assert not sol[a]
    assert not sol[b]


def test_equals_unsat(ab_cnf, solver):
    cnf, (a, b) = ab_cnf
    cnf.equals(a, b).set_literals([a, -b])
    sol = solver.solve(cnf)
    assert not sol


def test_and_true(n_cnf, solver):
    cnf, primary, literals = n_cnf
    cnf.equals_and(primary, literals).set_literal(primary)
    sol = solver.solve(cnf)
    assert sol
    assert sol[primary]
    assert all(sol[lit] for lit in literals)


def test_and_false(n_cnf, solver):
    cnf, primary, literals = n_cnf
    cnf.equals_and(primary, literals).set_literal(-primary)
    sol = solver.solve(cnf)
    assert sol
    assert not sol[primary]
    assert any(not sol[lit] for lit in literals)


def test_and_unsat(n_cnf, solver):
    cnf, primary, literals = n_cnf
    cnf.equals_and(primary, literals).set_literals([primary, -literals[0]])
    sol = solver.solve(cnf)
    assert not sol


def test_or_true(n_cnf, solver):
    cnf, primary, literals = n_cnf
    cnf.equals_or(primary, literals).set_literal(primary)
    sol = solver.solve(cnf)
    assert sol
    assert sol[primary]
    assert any(sol[lit] for lit in literals)


def test_or_false(n_cnf, solver):
    cnf, primary, literals = n_cnf
    cnf.equals_or(primary, literals).set_literal(-primary)
    sol = solver.solve(cnf)
    assert sol
    assert not sol[primary]
    assert all(not sol[lit] for lit in literals)


def test_or_unsat(n_cnf, solver):
    cnf, primary, literals = n_cnf
    cnf.equals_or(primary, literals).set_literals([-primary, literals[0]])
    sol = solver.solve(cnf)
    assert not sol


def test_xor_true(n_cnf, solver, rng):
    cnf, _, literals = n_cnf
    cnf.xor(literals)
    literals_to_set = rng.sample(literals, rng.randint(0, len(literals) - 1))
    set_literals = [var if rng.randint(0, 1) else -var for var in literals_to_set]
    cnf.set_literals(set_literals)
    sol = solver.solve(cnf)
    assert sol
    for lit in literals_to_set:
        if lit in set_literals:
            assert sol[lit]
        if -lit in set_literals:
            assert not sol[lit]
    value = reduce(lambda x, y: x ^ y, (sol[var] for var in literals))
    assert not value
