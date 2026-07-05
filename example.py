"""Incremental SAT solving — two demos with a real-vs-fake timing comparison.

Same graph 3-colouring problem as before, scaled up (30 nodes, ~60 edges) so
solve time is measurable. Only the `solve(...)` call is timed; CNF
construction and blocker/assumption bookkeeping are excluded.

Two workloads:

  Demo 1  Solution enumeration
          Real: one persistent `IncrementalSolver`, `add_clause` per blocker.
          Fake: `Solver().solve(cnf)` each iteration — pysat solver is
                rebuilt from scratch each call, learned clauses discarded.

  Demo 2  Assumption-based what-if
          Real: `solver.solve(assumptions=[lit])` — assumption applied for
                one call, formula and learned clauses untouched.
          Fake: append a unit clause to the CNF, `Solver().solve(cnf)`,
                pop the clause. No CNF rebuild inside the timer either,
                so this is the most solve-time-only comparison possible.

Run from the project root:

    python example.py
"""

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sat.cnf import CNF
from sat.solver import Solver, IncrementalSolver


SOLVER_NAME = "cadical153"
COLOURS = ["r", "g", "b"]
NUM_NODES = 15
NUM_EDGES = 30
SEED = 42


def build_graph() -> dict[str, list[str]]:
    """Random graph that is guaranteed 3-colourable — nodes are partitioned
    into 3 classes and only inter-class edges are permitted, so the class
    assignment itself is a witness colouring."""
    rng = random.Random(SEED)
    nodes = [f"n{i}" for i in range(NUM_NODES)]
    classes = [rng.randrange(len(COLOURS)) for _ in nodes]
    allowed = [
        (i, j)
        for i in range(NUM_NODES)
        for j in range(i + 1, NUM_NODES)
        if classes[i] != classes[j]
    ]
    picked = rng.sample(allowed, min(NUM_EDGES, len(allowed)))
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for i, j in picked:
        adj[nodes[i]].append(nodes[j])
        adj[nodes[j]].append(nodes[i])
    return adj


GRAPH = build_graph()


def build_cnf() -> tuple[CNF, dict[str, list]]:
    cnf = CNF()
    node_lits: dict[str, list] = {}
    for node in GRAPH:
        lits = cnf.reserve_names(f"{node}_{c}" for c in COLOURS)
        node_lits[node] = lits
        cnf.exactly(lits, 1)
    seen: set[tuple[str, str]] = set()
    for u, neighbours in GRAPH.items():
        for v in neighbours:
            edge = tuple(sorted((u, v)))
            if edge in seen:
                continue
            seen.add(edge)
            for idx in range(len(COLOURS)):
                cnf.nand(node_lits[u][idx], node_lits[v][idx])
    return cnf, node_lits


def tracked_ids(node_lits: dict[str, list]) -> set[int]:
    return {abs(lit.value()) for lits in node_lits.values() for lit in lits}


# --------------------------- Demo 1: enumeration ---------------------------


def enumerate_real() -> tuple[float, int]:
    cnf, node_lits = build_cnf()
    keep = tracked_ids(node_lits)
    solve_time = 0.0
    count = 0
    with IncrementalSolver(SOLVER_NAME, cnf) as solver:
        while True:
            t0 = time.perf_counter()
            sol = solver.solve()
            solve_time += time.perf_counter() - t0
            if not sol:
                break
            count += 1
            blocker = [-i for i in sol.assignment() if abs(i) in keep]
            solver.add_clause(blocker)
    return solve_time, count


def enumerate_fake() -> tuple[float, int]:
    cnf, node_lits = build_cnf()
    keep = tracked_ids(node_lits)
    solver = Solver(SOLVER_NAME)
    solve_time = 0.0
    count = 0
    while True:
        t0 = time.perf_counter()
        sol = solver.solve(cnf)
        solve_time += time.perf_counter() - t0
        if not sol:
            break
        count += 1
        cnf.exclude_by_values([i for i in sol.assignment() if abs(i) in keep])
    return solve_time, count


# --------------------------- Demo 2: assumptions ---------------------------


def assume_real() -> tuple[float, int, int]:
    cnf, node_lits = build_cnf()
    solve_time = 0.0
    queries = sat_count = 0
    with IncrementalSolver(SOLVER_NAME, cnf) as solver:
        for lits in node_lits.values():
            for lit in lits:
                t0 = time.perf_counter()
                sol = solver.solve(assumptions=[lit.value()])
                solve_time += time.perf_counter() - t0
                queries += 1
                sat_count += int(bool(sol))
    return solve_time, queries, sat_count


def assume_fake() -> tuple[float, int, int]:
    cnf, node_lits = build_cnf()
    solver = Solver(SOLVER_NAME)
    solve_time = 0.0
    queries = sat_count = 0
    for lits in node_lits.values():
        for lit in lits:
            # Push assumption as a unit clause, solve, pop — keeps the CNF
            # rebuild cost out of the timed section so we measure pure solve.
            cnf._cnf.clauses.append([lit.value()])
            t0 = time.perf_counter()
            sol = solver.solve(cnf)
            solve_time += time.perf_counter() - t0
            cnf._cnf.clauses.pop()
            queries += 1
            sat_count += int(bool(sol))
    return solve_time, queries, sat_count


# ------------------------------- reporting --------------------------------


def fmt(total_s: float, n: int) -> str:
    per_us = total_s / n * 1e6 if n else 0.0
    return f"{total_s * 1000:8.1f} ms total   {per_us:7.1f} µs/solve"


def main() -> None:
    n_edges = sum(len(v) for v in GRAPH.values()) // 2
    print(f"graph:  {NUM_NODES} nodes, {n_edges} edges, {len(COLOURS)} colours")
    print(f"solver: {SOLVER_NAME}")
    print()

    print("Demo 1: enumerate ALL colourings")
    print("-" * 62)
    real_t, real_n = enumerate_real()
    fake_t, fake_n = enumerate_fake()
    print(f"  real: {fmt(real_t, real_n)}   ({real_n} solutions)")
    print(f"  fake: {fmt(fake_t, fake_n)}   ({fake_n} solutions)")
    assert real_n == fake_n, \
        f"enumeration incomplete or divergent — real={real_n} fake={fake_n}"
    print(f"  speedup: {fake_t / real_t:.1f}×")
    print()

    print("Demo 2: assumption-based what-if")
    print("-" * 62)
    real_t, real_q, real_s = assume_real()
    fake_t, fake_q, fake_s = assume_fake()
    print(f"  real: {fmt(real_t, real_q)}   ({real_s}/{real_q} SAT)")
    print(f"  fake: {fmt(fake_t, fake_q)}   ({fake_s}/{fake_q} SAT)")
    assert (real_q, real_s) == (fake_q, fake_s), \
        "SAT/UNSAT verdicts must agree — same formula, same queries."
    print(f"  speedup: {fake_t / real_t:.1f}×")


if __name__ == "__main__":
    main()
