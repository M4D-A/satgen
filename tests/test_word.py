def test_add_words(ternary_cnf, solver, rng):
    cnf, a_lits, b_lits, c_lits = ternary_cnf
    cnf.add_words(a_lits, b_lits, c_lits)

    n = len(a_lits)
    a_val = rng.randint(0, 2**n - 1)
    b_val = rng.randint(0, 2**n - 1)

    cnf.set_word(a_lits, a_val)
    cnf.set_word(b_lits, b_val)

    sol = solver.solve(cnf)
    assert sol
    assert sol.value_of(c_lits) == (a_val + b_val) % (2**n)

    cnf.exclude(sol.assign(c_lits))
    assert not solver.solve(cnf)


def test_add_words_unsat(ternary_cnf, solver, rng):
    cnf, a_lits, b_lits, c_lits = ternary_cnf
    cnf.add_words(a_lits, b_lits, c_lits)

    n = len(a_lits)
    a_val = rng.randint(0, 2**n - 1)
    b_val = rng.randint(0, 2**n - 1)
    correct = (a_val + b_val) % (2**n)
    wrong = (correct + rng.randint(1, 2**n - 1)) % (2**n)

    cnf.set_word(a_lits, a_val)
    cnf.set_word(b_lits, b_val)
    cnf.set_word(c_lits, wrong)

    sol = solver.solve(cnf)
    assert not sol


def test_add_words_solve_b(ternary_cnf, solver, rng):
    cnf, a_lits, b_lits, c_lits = ternary_cnf
    cnf.add_words(a_lits, b_lits, c_lits)

    n = len(a_lits)
    a_val = rng.randint(0, 2**n - 1)
    c_val = rng.randint(0, 2**n - 1)

    cnf.set_word(a_lits, a_val)
    cnf.set_word(c_lits, c_val)

    sol = solver.solve(cnf)
    assert sol
    assert (a_val + sol.value_of(b_lits)) % (2**n) == c_val

    cnf.exclude(sol.assign(b_lits))
    assert not solver.solve(cnf)


def test_xor_words(ternary_cnf, solver, rng):
    cnf, a_lits, b_lits, c_lits = ternary_cnf
    cnf.xor_words(a_lits, b_lits, c_lits)

    n = len(a_lits)
    a_val = rng.randint(0, 2**n - 1)
    b_val = rng.randint(0, 2**n - 1)

    cnf.set_word(a_lits, a_val)
    cnf.set_word(b_lits, b_val)

    sol = solver.solve(cnf)
    assert sol
    assert sol.value_of(c_lits) == a_val ^ b_val

    cnf.exclude(sol.assign(c_lits))
    assert not solver.solve(cnf)


def test_xor_words_unsat(ternary_cnf, solver, rng):
    cnf, a_lits, b_lits, c_lits = ternary_cnf
    cnf.xor_words(a_lits, b_lits, c_lits)

    n = len(a_lits)
    a_val = rng.randint(0, 2**n - 1)
    b_val = rng.randint(0, 2**n - 1)
    c_val = a_val ^ b_val ^ 1

    cnf.set_word(a_lits, a_val)
    cnf.set_word(b_lits, b_val)
    cnf.set_word(c_lits, c_val)

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

    cnf.exclude(sol.assign(b_lits))
    assert not solver.solve(cnf)


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

    cnf.exclude(sol.assign(b_lits))
    assert not solver.solve(cnf)


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

    cnf.exclude(sol.assign(b_lits))
    assert not solver.solve(cnf)


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
