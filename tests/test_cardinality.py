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
