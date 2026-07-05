import sys
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sat.cnf import CNF
from sat.solver import Solver

WORD_SIZE = 4
KEY_WORDS = 64
STATE_WORDS = 64
SOLVER_NAME = "cadical153"

SBOX = [
    0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0xA, 0xD,
    0x3, 0xE, 0xF, 0x8, 0x4, 0x7, 0x1, 0x2,
]


# ----------------------------- reference impl ------------------------------


def sbox(word: int):
    return SBOX[word]

def xor(lhs: int, rhs: int):
    return lhs ^ rhs

def add(lhs: int, rhs: int):
    return (lhs + rhs) % (2 ** WORD_SIZE)

def push(lhs: int, state: list[int]):
    return [lhs] + state[:-1]

def rotate(state: list[int]):
    return [state[-1]] + state[:-1]

def step(key: list[int], state: list[int]):
    k = key[0]
    new_word = sbox(xor(add(state[1], state[-1]), k))
    key = rotate(key)
    state = push(new_word, state)
    return key, state

def round(key: list[int], state: list[int]):
    for _ in range(len(key)):
        key, state = step(key, state)
    return key, state

def generate(key: list[int], iv: list[int], blocks: int) -> list[int]:
    """Run `blocks` rounds and return all output state words concatenated."""
    key = list(key)
    state = list(iv)
    stream = []
    for _ in range(blocks):
        key, state = round(key, state)
        stream += state
    return stream


# ----------------------------- CNF encoding --------------------------------


def build_cnf(num_blocks: int):
    """Encode `num_blocks` rounds of the cipher as a CNF formula.

    Returns (cnf, key_lits, iv_lits, block_lits) where:
      key_lits  — list of KEY_WORDS word-literal-lists for the initial key
      iv_lits   — list of STATE_WORDS word-literal-lists for the IV
      block_lits — list of num_blocks × STATE_WORDS word-literal-lists,
                   one per output block
    """
    cnf = CNF()

    key_lits = [
        cnf.reserve_names([f"k{w}b{b}" for b in range(WORD_SIZE)])
        for w in range(KEY_WORDS)
    ]

    iv_lits = [
        cnf.reserve_names([f"iv{w}b{b}" for b in range(WORD_SIZE)])
        for w in range(STATE_WORDS)
    ]

    cur_key = list(key_lits)
    cur_state = list(iv_lits)
    block_lits = []

    for t in range(num_blocks * KEY_WORDS):
        # sum = add(state[1], state[-1])
        sum_lits = cnf.reserve_names([f"sm{t}b{b}" for b in range(WORD_SIZE)])
        cnf.add_words(cur_state[1], cur_state[-1], sum_lits)

        # xored = xor(sum, key[0])
        xr_lits = cnf.reserve_names([f"xr{t}b{b}" for b in range(WORD_SIZE)])
        cnf.xor_words(sum_lits, cur_key[0], xr_lits)

        # new_word = sbox(xored)
        nw_lits = cnf.reserve_names([f"nw{t}b{b}" for b in range(WORD_SIZE)])
        cnf.sbox(xr_lits, nw_lits, SBOX)

        # push and rotate are pure rewiring — no new clauses
        cur_state = [nw_lits] + cur_state[:-1]
        cur_key = [cur_key[-1]] + cur_key[:-1]

        if (t + 1) % KEY_WORDS == 0:
            block_lits.append(list(cur_state))

    return cnf, key_lits, iv_lits, block_lits


# ----------------------------- key recovery --------------------------------


rng = random.Random()
key = [rng.randrange(2 ** WORD_SIZE) for _ in range(KEY_WORDS)]
iv  = [rng.randrange(2 ** WORD_SIZE) for _ in range(STATE_WORDS)]

stream = generate(key, iv, 2)
blocks = [stream[:STATE_WORDS], stream[STATE_WORDS:]]

print(f"key:    {[hex(w) for w in key]}")
print(f"iv:     {[hex(w) for w in iv]}")
for i, block in enumerate(blocks):
    print(f"block{i}: {[hex(w) for w in block]}")
print()

cnf, key_lits, iv_lits, block_lits = build_cnf(2)

for w, word_lits in enumerate(iv_lits):
    cnf.set_word(word_lits, iv[w])
for b, block in enumerate(blocks):
    for w, word_val in enumerate(block):
        cnf.set_word(block_lits[b][w], word_val)

sol = Solver(SOLVER_NAME).solve(cnf)

if sol:
    recovered = [sol.value_of(word_lits) for word_lits in key_lits]
    print(f"recovered: {[hex(w) for w in recovered]}")
    print(f"match: {recovered == key}")
else:
    print("UNSAT — encoding is broken")
