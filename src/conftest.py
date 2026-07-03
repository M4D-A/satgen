import random
import pytest


def pytest_addoption(parser):
    parser.addoption("--seed", type=int, default=None, help="Fix random seed for reproducibility")


@pytest.fixture
def rng(request):
    seed = request.config.getoption("--seed")
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    request.node.user_properties.append(("seed", seed))
    return random.Random(seed)
