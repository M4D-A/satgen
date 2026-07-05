from collections.abc import Iterable
from pysat.formula import CNF as CNF_core, IDPool
from pysat.card import CardEnc
from itertools import product
from sat.literal import Literal


class CNF():
    def __init__(self):
        self._cnf = CNF_core()
        self._v_pool = IDPool(start_from=1)
        self._v_counter = 0

        self._max_clause_len = 3
        self._caridnality_enc = 1

    def __str__(self) -> str:
        clauses = self.clauses()
        string = "clauses:\n" + \
            "\n".join([str(clause) for clause in clauses]) + "\n\n"
        string += "literals:\n" + \
            "\n".join([f"{name}: {value}" for name,
                      value in self._v_pool.obj2id.items()]) + "\n"
        return string

    def clauses(self) -> list[list]:
        return self._cnf.clauses

    def v_pool(self) -> IDPool:
        return self._v_pool

    def to_file(self, file_name: str) -> None:
        buffer_size = 1024*1024
        header = f"p cnf {self._cnf.nv} {len(self._cnf.clauses)}\n"
        string = ' 0\n'.join([' '.join([str(lit) for lit in cl])
                             for cl in self._cnf.clauses]) + ' 0\n'
        with open(file_name, "w", buffering=buffer_size) as fp:
            fp.write(header + string)

    def to_dimacs(self) -> str:
        header_lines = [f"p cnf {self._cnf.nv} {len(self._cnf.clauses)}"]
        clause_lines = [" ".join(map(str, clause)) + " 0" for clause in self._cnf.clauses]
        lines = "\n".join(header_lines + clause_lines) + "\n"
        return lines

    def check_name(self, name: str) -> bool:
        return name in self._v_pool.obj2id.keys()

    def check_id(self, id: int) -> bool:
        return abs(id) in self._v_pool.obj2id.values()

    def verify_literals(self, literals: list[Literal]) -> bool:
        for lit in literals:
            name = lit.name()
            if not self.check_name(name):
                return False
            found = self.name_to_literal(name)
            if found is None or not (abs(lit) == abs(found)):
                return False
        return True

    def reserve_name(self, name: str) -> Literal:
        assert name[0].islower(), "Regular variable name cannot start with uppercase letter"
        assert name not in self._v_pool.obj2id, "Name already registered"
        id = self._v_pool.id(name)
        return Literal(name, id)

    def reserve_names(self, names: Iterable[str]) -> list[Literal]:
        return [self.reserve_name(name) for name in names]

    def _reserve_internal(self) -> Literal:
        name = f"A{self._v_counter}"
        self._v_counter += 1
        assert name not in self._v_pool.obj2id, "Name already registered"
        id = self._v_pool.id(name)
        return Literal(name, id)

    def _reserve_internals(self, n: int) -> list[Literal]:
        return [self._reserve_internal() for _ in range(n)]

    def name_to_literal(self, name: str) -> Literal:
        assert name in self._v_pool.obj2id.keys(), "Name not found in the pool"
        id = self._v_pool.id(name)
        return Literal(name, id)

    def id_to_literal(self, id: int) -> Literal:
        abs_id = abs(id)
        pool = self._v_pool
        assert abs_id in pool.obj2id.values(), "ID not found in the pool"
        name = str(pool.obj(abs_id))
        return Literal(name, id)

    def set_literal(self, literal: Literal, value: bool | None = None) -> "CNF":
        lval = literal.value()
        if value is not None:
            sign = 1 if value else -1
            lval = sign * abs(lval)
        self._cnf.append([lval])
        return self

    def set_literals(self, literals: list[Literal]) -> "CNF":
        for lit in literals:
            self.set_literal(lit)
        return self

    def set_word(self, literals: list[Literal], value) -> "CNF":
        for i, lit in enumerate(literals):
            self.set_literal(lit, bool((value >> i) & 1))
        return self

    def equals(self, literal_a: Literal, literal_b: Literal) -> "CNF":
        lval_a = literal_a.value()
        lval_b = literal_b.value()
        self._cnf.append([-lval_a, lval_b])
        self._cnf.append([lval_a, -lval_b])
        return self

    def equals_and(self, literal_a: Literal, literals_b: list[Literal]) -> "CNF":
        lval_a = literal_a.value()
        self._cnf.append([lval_a] + [-(b_elem.value())
                         for b_elem in literals_b])
        new_clauses = [[-lval_a, b_elem.value()] for b_elem in literals_b]
        self._cnf.clauses += new_clauses
        return self

    def equals_and_by_values(self, literal_a: int, literals_b: list[int]) -> "CNF":
        header_clauses = [[literal_a] + [-b_elem for b_elem in literals_b]]
        new_clauses = header_clauses + [[-literal_a, b_elem] for b_elem in literals_b]
        self._cnf.clauses += new_clauses
        return self

    def equals_or(self, literal_a: Literal, literals_b: list[Literal]) -> "CNF":
        lval_a = literal_a.value()
        self._cnf.append([-lval_a] + [b_elem.value()
                         for b_elem in literals_b])
        new_clauses = [[lval_a, -b_elem.value()] for b_elem in literals_b]
        self._cnf.clauses += new_clauses
        return self

    def xor(self, literals: list[Literal]) -> "CNF":
        clause_len = self._max_clause_len
        if clause_len and clause_len <= 2:
            raise ValueError("split must be greater than 2 if set to True")
        if not clause_len or len(literals) <= clause_len:
            ones = [[1, -1] for _ in literals]
            ids = [a_elem.value() for a_elem in literals]
            for prod in product(*ones):
                if (sum(prod) - len(literals) + 2) % 4 == 0:
                    self._cnf.append(
                        [one * a_id for one, a_id in zip(prod, ids)])
        else:
            _ = [a_elem.value() for a_elem in literals]
            slice = literals[:clause_len - 1]
            aux_literal = self._reserve_internal()
            self.xor([aux_literal] + slice)
            self.xor([aux_literal] + literals[clause_len - 1:])
        return self

    def atleast(self, literals: list[Literal], lower_bound: int) -> "CNF":
        ids = [lit.value() for lit in literals]
        clauses = CardEnc.atleast(
            ids,
            lower_bound,
            encoding=self._caridnality_enc,
            vpool=self._v_pool
        )
        self._cnf.extend(clauses)
        return self

    def atmost(self, literals: list[Literal], upper_bound: int) -> "CNF":
        ids = [lit.value() for lit in literals]
        clauses = CardEnc.atmost(
            ids,
            upper_bound,
            encoding=self._caridnality_enc,
            vpool=self._v_pool
        )
        self._cnf.extend(clauses)
        return self

    def exactly(self, literals: list[Literal], upper_bound: int) -> "CNF":
        ids = [lit.value() for lit in literals]
        clauses = CardEnc.equals(
            ids,
            upper_bound,
            encoding=self._caridnality_enc,
            vpool=self._v_pool
        )
        self._cnf.extend(clauses)
        return self

    def nand(self, literal_a: Literal, literal_b: Literal) -> "CNF":
        lval_a = literal_a.value()
        lval_b = literal_b.value()
        self._cnf.append([-lval_a, -lval_b])
        return self

    def add_words(self, a: list[Literal], b: list[Literal], c: list[Literal]) -> "CNF":
        n = len(a)
        assert len(b) == n and len(c) == n, "All three lists must have the same length"

        carries = self._reserve_internals(n)
        self.set_literal(carries[0], False)

        for i in range(n):
            # c[i] = a[i] XOR b[i] XOR carry[i]  ↔  a[i] XOR b[i] XOR carry[i] XOR c[i] = 0
            self.xor([a[i], b[i], carries[i], c[i]])

            if i < n - 1:
                # carry[i+1] = majority(a[i], b[i], carry[i]) #TODO: maj(out, [in])
                ai, bi, cin, cout = a[i].value(), b[i].value(), carries[i].value(), carries[i + 1].value()
                self._cnf.append([-cout, ai, bi])
                self._cnf.append([-cout, ai, cin])
                self._cnf.append([-cout, bi, cin])
                self._cnf.append([-ai, -bi, cout])
                self._cnf.append([-ai, -cin, cout])
                self._cnf.append([-bi, -cin, cout])

        return self

    def eq_words(self, a: list[Literal], b: list[Literal]) -> "CNF":
        n = len(a)
        assert len(b) == n, "Both lists must have the same length"
        for i in range(n):
            self.equals(a[i], b[i])
        return self

    def permute_words(self, a: list[Literal], b: list[Literal], perm: list[int]) -> "CNF":
        n = len(a)
        assert len(b) == n and len(perm) == n, "All arguments must have the same length"
        for i in range(n):
            self.equals(a[i], b[perm[i]])
        return self

    def sbox(self, a: list[Literal], b: list[Literal], table: list[int]) -> "CNF":
        n = len(a)
        assert len(b) == n, "Input and output words must have the same length"
        assert len(table) == 2 ** n, "Table must have 2^n entries for n-bit input"
        assert set(table) == set(range(2 ** n)), "Table must be a bijection"
        for in_val in range(2 ** n):
            out_val = table[in_val]
            for j in range(n):
                clause = []
                for k in range(n):
                    bit = (in_val >> k) & 1
                    clause.append(-a[k].value() if bit else a[k].value())
                out_bit = (out_val >> j) & 1
                clause.append(b[j].value() if out_bit else -b[j].value())
                self._cnf.clauses.append(clause)
        return self

    def xor_words(self, a: list[Literal], b: list[Literal], c: list[Literal]) -> "CNF":
        n = len(a)
        assert len(b) == n and len(c) == n, "All three lists must have the same length"

        for i in range(n):
            # c[i] = a[i] XOR b[i] ↔  a[i] XOR b[i] XOR c[i] = 0
            self.xor([a[i], b[i], c[i]])

        return self

    def exclude(self, literals: list[Literal]) -> "CNF":
        aux_literal = self._reserve_internal()
        self.equals_and(aux_literal, literals)
        self.set_literal(-aux_literal)
        return self

    def exclude_by_values(self, literals: list[int]) -> "CNF":
        clause = [-lit for lit in literals]
        self._cnf.clauses.append(clause)
        return self
