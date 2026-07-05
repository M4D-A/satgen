import random
import pytest
from sat.cnf import CNF
from sat.solver import Solver


def pytest_addoption(parser):
    parser.addoption("--seed", type=int, default=None, help="Fix random seed for reproducibility")


@pytest.fixture
def rng(request):
    seed = request.config.getoption("--seed")
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    request.node.user_properties.append(("seed", seed))
    return random.Random(seed)


solver_names = Solver.builtin_solvers
solvers = [Solver(name) for name in solver_names]

max_variables = 8


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
