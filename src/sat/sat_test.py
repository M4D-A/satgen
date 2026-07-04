import pytest
from functools import reduce
from sat.cnf import CNF
from sat.solver import Solver


solver_names = Solver.builtin_solvers
print(len(solver_names))
solvers = [Solver(solver_name) for solver_name in solver_names]

max_variables = 8
epochs = range(16)

@pytest.fixture(params=solvers, ids=solver_names)
def solver(request):
    return request.param

@pytest.fixture
def ab_cnf():
    cnf = CNF()
    literals = cnf.reserve_names(["a", "b"])
    return (cnf, literals)

@pytest.fixture(params=range(2, max_variables))
def n_cnf(request):
    cnf = CNF()
    primary_literal = cnf.reserve_name("p")
    literals = cnf.reserve_names(f"l_{i}" for i in range(request.param))
    return (cnf, primary_literal, literals)

@pytest.fixture(params=range(1, max_variables + 1))
def binary_cnf(request):
    n = request.param
    cnf = CNF()
    a_lits = cnf.reserve_names([f"a{i}" for i in range(n)])
    b_lits = cnf.reserve_names([f"b{i}" for i in range(n)])
    return (cnf, a_lits, b_lits)

@pytest.fixture(params=range(1, max_variables + 1))
def ternary_cnf(request):
    n = request.param
    cnf = CNF()
    a_lits = cnf.reserve_names([f"a{i}" for i in range(n)])
    b_lits = cnf.reserve_names([f"b{i}" for i in range(n)])
    c_lits = cnf.reserve_names([f"c{i}" for i in range(n)])
    return (cnf, a_lits, b_lits, c_lits)


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


def test_atleast(n_cnf, solver, rng):
    cnf, _, literals = n_cnf
    set_vars_num = rng.randint(0, len(literals) - 1)
    literals_to_set = rng.sample(literals, set_vars_num)
    set_literals = [var if rng.randint(0, 1) else -var for var in literals_to_set]
    set_false_num = sum([1 for var in set_literals if -var])
    max_lower_bound = len(literals) - set_false_num
    lower_bound = rng.randint(1, max_lower_bound)
    cnf.atleast(literals, lower_bound)
    cnf.set_literals(set_literals)
    sol = solver.solve(cnf)
    assert sol
    assert sum(sol[lit] for lit in literals) >= lower_bound


def test_atmost(n_cnf, solver, rng):
    cnf, _, literals = n_cnf
    set_vars_num = rng.randint(0, len(literals) - 1)
    literals_to_set = rng.sample(literals, set_vars_num)
    set_literals = [var if rng.randint(0, 1) else -var for var in literals_to_set]
    set_true_num = sum([1 for lit in set_literals if lit])
    upper_bound = rng.randint(set_true_num, len(literals) - 1)
    cnf.atmost(literals, upper_bound)
    cnf.set_literals(set_literals)
    sol = solver.solve(cnf)
    assert sol
    assert sum(sol[lit] for lit in literals) <= upper_bound


def test_add_words(ternary_cnf, solver, rng):
    cnf, a_lits, b_lits, c_lits = ternary_cnf
    cnf.add_words(a_lits, b_lits, c_lits)

    n = len(a_lits)
    a_val = rng.randint(0, 2**n - 1)
    b_val = rng.randint(0, 2**n - 1)

    cnf.set_word(a_lits, a_val);
    cnf.set_word(b_lits, b_val);

    sol = solver.solve(cnf)
    assert sol
    assert sol.value_of(c_lits) == (a_val + b_val) % (2**n)


def test_add_words_unsat(ternary_cnf, solver, rng):
    cnf, a_lits, b_lits, c_lits = ternary_cnf
    cnf.add_words(a_lits, b_lits, c_lits)

    n = len(a_lits)
    a_val = rng.randint(0, 2**n - 1)
    b_val = rng.randint(0, 2**n - 1)
    correct = (a_val + b_val) % (2**n)
    wrong = (correct + rng.randint(1, 2**n - 1)) % (2**n)

    cnf.set_word(a_lits, a_val);
    cnf.set_word(b_lits, b_val);
    cnf.set_word(c_lits, wrong);

    sol = solver.solve(cnf)
    assert not sol


def test_add_words_solve_b(ternary_cnf, solver, rng):
    cnf, a_lits, b_lits, c_lits = ternary_cnf
    cnf.add_words(a_lits, b_lits, c_lits)

    n = len(a_lits)
    a_val = rng.randint(0, 2**n - 1)
    c_val = rng.randint(0, 2**n - 1)

    cnf.set_word(a_lits, a_val);
    cnf.set_word(c_lits, c_val);

    sol = solver.solve(cnf)
    assert sol
    assert (a_val + sol.value_of(b_lits)) % (2**n) == c_val


def test_xor_words(ternary_cnf, solver, rng):
    cnf, a_lits, b_lits, c_lits = ternary_cnf
    cnf.xor_words(a_lits, b_lits, c_lits)

    n = len(a_lits)
    a_val = rng.randint(0, 2**n - 1)
    b_val = rng.randint(0, 2**n - 1)

    cnf.set_word(a_lits, a_val);
    cnf.set_word(b_lits, b_val);

    sol = solver.solve(cnf)
    assert sol
    assert sol.value_of(c_lits) == a_val ^ b_val


def test_xor_words_unsat(ternary_cnf, solver, rng):
    cnf, a_lits, b_lits, c_lits = ternary_cnf
    cnf.xor_words(a_lits, b_lits, c_lits)

    n = len(a_lits)
    a_val = rng.randint(0, 2**n - 1)
    b_val = rng.randint(0, 2**n - 1)
    c_val = a_val ^ b_val ^ 1

    cnf.set_word(a_lits, a_val);
    cnf.set_word(b_lits, b_val);
    cnf.set_word(c_lits, c_val);

    sol = solver.solve(cnf)
    assert not sol


def test_eq_words(binary_cnf, solver, rng):
    cnf, a_lits, b_lits = binary_cnf
    cnf.eq_words(a_lits, b_lits)

    n = len(a_lits)
    a_val = rng.randint(0, 2**n - 1)

    cnf.set_word(a_lits, a_val)
    sol = solver.solve(cnf)

    assert sol
    assert sol.value_of(b_lits) == a_val


def test_eq_words_unsat(binary_cnf, solver, rng):
    cnf, a_lits, b_lits = binary_cnf
    cnf.eq_words(a_lits, b_lits)

    n = len(a_lits)
    a_val = rng.randint(0, 2**n - 1)
    b_val = (a_val + rng.randint(1, 2**n - 1)) % (2**n)

    cnf.set_word(a_lits, a_val)
    cnf.set_word(b_lits, b_val)

    sol = solver.solve(cnf)
    assert not sol


def test_permute_words(binary_cnf, solver, rng):
    cnf, a_lits, b_lits = binary_cnf

    n = len(a_lits)
    perm = list(range(n))
    rng.shuffle(perm)
    cnf.permute_words(a_lits, b_lits, perm)

    a_val = rng.randint(0, 2**n - 1)
    cnf.set_word(a_lits, a_val)
    sol = solver.solve(cnf)
    assert sol
    expected_b_val = 0
    for i in range(n):
        expected_b_val |= ((a_val >> i) & 1) << perm[i]
    assert sol.value_of(b_lits) == expected_b_val


def test_permute_words_unsat(binary_cnf, solver, rng):
    cnf, a_lits, b_lits = binary_cnf
    n = len(a_lits)
    perm = list(range(n))
    rng.shuffle(perm)
    cnf.permute_words(a_lits, b_lits, perm)
    a_val = rng.randint(0, 2**n - 1)
    correct_b_val = 0
    for i in range(n):
        correct_b_val |= ((a_val >> i) & 1) << perm[i]
    wrong_b_val = (correct_b_val + rng.randint(1, 2**n - 1)) % (2**n)
    cnf.set_word(a_lits, a_val)
    cnf.set_word(b_lits, wrong_b_val)
    sol = solver.solve(cnf)
    assert not sol


def test_sbox(binary_cnf, solver, rng):
    cnf, a_lits, b_lits = binary_cnf
    n = len(a_lits)
    table = list(range(2**n))
    rng.shuffle(table)
    cnf.sbox(a_lits, b_lits, table)

    a_val = rng.randint(0, 2**n - 1)

    cnf.set_word(a_lits, a_val)
    sol = solver.solve(cnf)
    assert sol
    assert sol.value_of(b_lits) == table[a_val]


def test_sbox_unsat(binary_cnf, solver, rng):
    cnf, a_lits, b_lits = binary_cnf
    n = len(a_lits)
    table = list(range(2**n))
    rng.shuffle(table)
    cnf.sbox(a_lits, b_lits, table)
    a_val = rng.randint(0, 2**n - 1)
    correct_b_val = table[a_val]
    wrong_b_val = (correct_b_val + rng.randint(1, 2**n - 1)) % (2**n)
    cnf.set_word(a_lits, a_val)
    cnf.set_word(b_lits, wrong_b_val)
    sol = solver.solve(cnf)
    assert not sol

