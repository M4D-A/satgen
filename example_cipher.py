"""Toy SPN cipher — SAT-based key recovery, ad-hoc vs. warmed-up solver.

Cipher: 16-bit block, 16-bit key, R rounds of {AddRoundKey, S-box on every
4-bit nibble, bit permutation} followed by a final AddRoundKey. Uses the
PRESENT S-box. No key schedule — the same key is used every round. This is
insecure but the CNF is large enough that key recovery does real work.

The base formula encodes NUM_BLOCKS independent cipher instances that all share
the same key. Each block contributes one (ptx, ctx) pair as assumptions, so
more blocks → fewer spurious keys returned by the solver.

Three experiments:

  1. Ad-hoc.   Fresh IncrementalSolver bootstrapped with the cipher CNF, then
               immediately solve for the target (ptx, ctx) pairs → recover a key.

  2. Warmed.   Fresh IncrementalSolver bootstrapped with the same cipher CNF,
               then K exploratory solves with random (ptx, ctx) pairs (each
               generated from a random key), then solve for the same target.

  3. Progressive priming.  Reveal progressively more bits of all target pairs
               as assumptions before the full solve.

Reported: total elapsed and target-solve time in isolation for all three.

Run from project root:

    python example_cipher.py
"""

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sat.cnf import CNF
from sat.solver import IncrementalSolver


SOLVER_NAME = "cadical153"
BLOCK_BITS = 20
KEY_BITS = 20
NUM_ROUNDS = 6
NUM_BLOCKS = 2   # known-plaintext pairs per solve; more → fewer spurious keys
NUM_WARMUPS = 12
SEED_TARGET = 0xDEAD
SEED_WARMUP = 0xBEEF

# Step sizes swept in Experiment 3. Each s produces the schedule
#   k = s, 2s, 3s, ..., largest multiple of s below BLOCK_BITS.
STEP_SIZES = [1, 2, 4, 8]

# PRESENT 4-bit S-box.
SBOX = [
    0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0xA, 0xD,
    0x3, 0xE, 0xF, 0x8, 0x4, 0x7, 0x1, 0x2,
]

# Bit permutation of the 16-bit state: bit i moves to position PERM[i].
# Chosen so that consecutive nibbles get spread across all four output nibbles.
PERM = [
    (i * 4) % (BLOCK_BITS - 1) if i != BLOCK_BITS - 1 else BLOCK_BITS - 1
    for i in range(BLOCK_BITS)
]


# ------------------------------ reference impl -----------------------------


def encrypt(key: int, ptx: int) -> int:
    """Reference encryption used to generate (ptx, ctx) pairs for the demo."""
    state = ptx
    for r in range(NUM_ROUNDS):
        state ^= key
        # S-box each 4-bit nibble.
        new = 0
        for nib in range(BLOCK_BITS // 4):
            new |= SBOX[(state >> (4 * nib)) & 0xF] << (4 * nib)
        state = new
        # Permute, except after the last round.
        if r < NUM_ROUNDS - 1:
            permuted = 0
            for i in range(BLOCK_BITS):
                permuted |= ((state >> i) & 1) << PERM[i]
            state = permuted
    state ^= key
    return state


# ------------------------------ CNF encoding -------------------------------


def build_cipher_cnf() -> tuple[CNF, list, list[list], list[list]]:
    """Build a CNF encoding NUM_BLOCKS independent cipher instances sharing one key.

    Returns (cnf, key_lits, ptxs_lits, ctxs_lits) where ptxs_lits and
    ctxs_lits are lists of length NUM_BLOCKS.
    """
    cnf = CNF()
    key = cnf.reserve_names([f"key_{i}" for i in range(KEY_BITS)])
    ptxs, ctxs = [], []

    for b in range(NUM_BLOCKS):
        ptx = cnf.reserve_names([f"ptx_b{b}_{i}" for i in range(BLOCK_BITS)])
        ctx = cnf.reserve_names([f"ctx_b{b}_{i}" for i in range(BLOCK_BITS)])
        ptxs.append(ptx)
        ctxs.append(ctx)

        state = ptx
        for r in range(NUM_ROUNDS):
            xored = cnf.reserve_names([f"x_b{b}_r{r}_{i}" for i in range(BLOCK_BITS)])
            cnf.xor_words(state, key, xored)

            sboxed = cnf.reserve_names([f"s_b{b}_r{r}_{i}" for i in range(BLOCK_BITS)])
            for nib in range(BLOCK_BITS // 4):
                cnf.sbox(xored[4 * nib:4 * (nib + 1)],
                         sboxed[4 * nib:4 * (nib + 1)],
                         SBOX)

            if r < NUM_ROUNDS - 1:
                permuted = cnf.reserve_names([f"p_b{b}_r{r}_{i}" for i in range(BLOCK_BITS)])
                cnf.permute_words(sboxed, permuted, PERM)
                state = permuted
            else:
                state = sboxed

        cnf.xor_words(state, key, ctx)

    return cnf, key, ptxs, ctxs


# ------------------------------ helpers ------------------------------------


def value_to_assumptions(bits, value: int) -> list[int]:
    return [bits[i].value() if ((value >> i) & 1) else -bits[i].value()
            for i in range(len(bits))]


def extract_int(model_ids: list[int], bits) -> int:
    positive = {i for i in model_ids if i > 0}
    result = 0
    for i, lit in enumerate(bits):
        if lit.value() in positive:
            result |= 1 << i
    return result


def solve_for_key(solver: IncrementalSolver,
                  ptxs_lits, ctxs_lits, key_lits,
                  ptx_vals: list[int], ctx_vals: list[int]) -> tuple[float, int]:
    assumptions = []
    for ptx_lits, ctx_lits, ptx_val, ctx_val in zip(ptxs_lits, ctxs_lits, ptx_vals, ctx_vals):
        assumptions += value_to_assumptions(ptx_lits, ptx_val)
        assumptions += value_to_assumptions(ctx_lits, ctx_val)
    t0 = time.perf_counter()
    sol = solver.solve(assumptions=assumptions)
    dt = time.perf_counter() - t0
    if not sol:
        raise RuntimeError("unexpected UNSAT — encoding is broken")
    return dt, extract_int(sol.assignment(), key_lits)


def warm_up_progressive(solver: IncrementalSolver,
                        ptxs_lits, ctxs_lits,
                        target_ptxs: list[int], target_ctxs: list[int],
                        step: int = 1) -> tuple[float, int]:
    """Prime the solver by revealing progressively more bits of all target pairs.

    Bits are revealed in chunks of `step` across every block simultaneously,
    so the schedule is k = step, 2·step, ..., largest multiple below BLOCK_BITS.
    """
    total = 0.0
    steps = 0
    for k in range(step, BLOCK_BITS, step):
        assumptions = []
        for ptx_lits, ctx_lits, target_ptx, target_ctx in zip(
                ptxs_lits, ctxs_lits, target_ptxs, target_ctxs):
            assumptions += value_to_assumptions(ptx_lits[:k], target_ptx)
            assumptions += value_to_assumptions(ctx_lits[:k], target_ctx)
        t0 = time.perf_counter()
        sol = solver.solve(assumptions=assumptions)
        total += time.perf_counter() - t0
        steps += 1
        if not sol:
            raise RuntimeError(f"unexpected UNSAT at k={k}")
    return total, steps


# ------------------------------ demo ---------------------------------------


def main() -> None:
    cnf, key_lits, ptxs_lits, ctxs_lits = build_cipher_cnf()
    print(f"CNF: {len(cnf.clauses())} clauses, "
          f"{NUM_ROUNDS} rounds, {BLOCK_BITS}-bit block/key, {NUM_BLOCKS} block(s)")

    rng_t = random.Random(SEED_TARGET)
    target_key = rng_t.randrange(1 << KEY_BITS)
    target_ptxs = [rng_t.randrange(1 << BLOCK_BITS) for _ in range(NUM_BLOCKS)]
    target_ctxs = [encrypt(target_key, p) for p in target_ptxs]
    print(f"target: key={target_key:#06x} "
          + "  ".join(f"ptx={p:#06x} ctx={c:#06x}"
                      for p, c in zip(target_ptxs, target_ctxs)))

    print()
    print("Experiment 1: ad-hoc (no warm-up)")
    print("-" * 62)
    with IncrementalSolver(SOLVER_NAME, cnf) as solver:
        adhoc_dt, recovered = solve_for_key(
            solver, ptxs_lits, ctxs_lits, key_lits, target_ptxs, target_ctxs)
    assert all(encrypt(recovered, p) == c for p, c in zip(target_ptxs, target_ctxs))
    match = "(== target)" if recovered == target_key else "(other valid key)"
    print(f"  target solve: {adhoc_dt * 1000:8.1f} ms   key={recovered:#06x} {match}")
    print(f"  total:        {adhoc_dt * 1000:8.1f} ms")

    print()
    print(f"Experiment 2: warm-up first ({NUM_WARMUPS} random probes), then target")
    print("-" * 62)
    warm_time = 0.0
    with IncrementalSolver(SOLVER_NAME, cnf) as solver:
        rng_w = random.Random(SEED_WARMUP)
        for _ in range(NUM_WARMUPS):
            wk = rng_w.randrange(1 << KEY_BITS)
            wps = [rng_w.randrange(1 << BLOCK_BITS) for _ in range(NUM_BLOCKS)]
            wcs = [encrypt(wk, wp) for wp in wps]
            dt, _ = solve_for_key(solver, ptxs_lits, ctxs_lits, key_lits, wps, wcs)
            warm_time += dt
        warmed_dt, recovered = solve_for_key(
            solver, ptxs_lits, ctxs_lits, key_lits, target_ptxs, target_ctxs)
    assert all(encrypt(recovered, p) == c for p, c in zip(target_ptxs, target_ctxs))
    total = warm_time + warmed_dt
    match = "(== target)" if recovered == target_key else "(other valid key)"
    print(f"  warm-up:      {warm_time * 1000:8.1f} ms   ({NUM_WARMUPS} probes)")
    print(f"  target solve: {warmed_dt * 1000:8.1f} ms   key={recovered:#06x} {match}")
    print(f"  total:        {total * 1000:8.1f} ms")

    print()
    print("Experiment 3: progressive priming with target bits, varying step size")
    print("-" * 62)
    prog_results: list[tuple[int, float, int, float]] = []  # (step, warm, probes, target)
    for step in STEP_SIZES:
        with IncrementalSolver(SOLVER_NAME, cnf) as solver:
            prog_warm_time, prog_steps = warm_up_progressive(
                solver, ptxs_lits, ctxs_lits, target_ptxs, target_ctxs, step=step)
            prog_target_dt, prog_recovered = solve_for_key(
                solver, ptxs_lits, ctxs_lits, key_lits, target_ptxs, target_ctxs)
        assert all(encrypt(prog_recovered, p) == c for p, c in zip(target_ptxs, target_ctxs))
        prog_results.append((step, prog_warm_time, prog_steps, prog_target_dt))
        match = "(== target)" if prog_recovered == target_key else "(other valid key)"
        print(f"  step={step:2d}  probes={prog_steps:2d}  "
              f"warm-up={prog_warm_time * 1000:8.1f} ms  "
              f"target={prog_target_dt * 1000:7.1f} ms  "
              f"total={(prog_warm_time + prog_target_dt) * 1000:8.1f} ms  "
              f"key={prog_recovered:#06x} {match}")

    print()
    print("Comparison — target-solve time in isolation")
    print("-" * 62)
    print(f"  ad-hoc:                    {adhoc_dt * 1000:9.1f} ms   (baseline)")
    print(f"  random probes:             {warmed_dt * 1000:9.1f} ms   "
          f"({adhoc_dt / warmed_dt:7.2f}× vs baseline)")
    for step, _, _, pt_dt in prog_results:
        ratio = adhoc_dt / pt_dt if pt_dt > 0 else float("inf")
        print(f"  progressive prime, s={step:<2d}   {pt_dt * 1000:9.1f} ms   "
              f"({ratio:7.2f}× vs baseline)")

    print()
    print("Comparison — total wall time (warm-up + target)")
    print("-" * 62)
    print(f"  ad-hoc:                    {adhoc_dt * 1000:9.1f} ms   (baseline)")
    print(f"  random probes:             {total * 1000:9.1f} ms   "
          f"({total / adhoc_dt:7.2f}× vs baseline)")
    for step, warm, _, pt_dt in prog_results:
        tot = warm + pt_dt
        ratio = tot / adhoc_dt if adhoc_dt > 0 else float("inf")
        print(f"  progressive prime, s={step:<2d}   {tot * 1000:9.1f} ms   "
              f"({ratio:7.2f}× vs baseline)")


if __name__ == "__main__":
    main()
