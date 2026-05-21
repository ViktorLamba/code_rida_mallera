from functools import lru_cache
from itertools import combinations, product
from math import comb


class ReedMullerError(ValueError):
    pass


def parse_bits(raw, expected_length=None, field_name="bits"):
    bits = [char for char in raw.strip() if char in "01"]
    if not bits:
        raise ReedMullerError(f"Поле {field_name} должно содержать хотя бы один бит.")
    if expected_length is not None and len(bits) != expected_length:
        raise ReedMullerError(
            f"Поле {field_name} должно содержать ровно {expected_length} бит."
        )
    return [int(bit) for bit in bits]


def format_bits(bits, group=8):
    text = "".join(str(bit) for bit in bits)
    return " ".join(text[index : index + group] for index in range(0, len(text), group))


def parameters(r, m):
    if r < 0 or m < 1 or r > m:
        raise ReedMullerError("Параметры должны удовлетворять 0 <= r <= m и m >= 1.")

    n = 2**m
    k = sum(comb(m, degree) for degree in range(r + 1))
    d = 2 ** (m - r)
    t = (d - 1) // 2
    return {"r": r, "m": m, "n": n, "k": k, "d": d, "t": t}


@lru_cache(maxsize=None)
def points(m):
    return tuple(product((0, 1), repeat=m))


@lru_cache(maxsize=None)
def monomials(r, m):
    result = [()]
    for degree in range(1, r + 1):
        result.extend(combinations(range(m), degree))
    return tuple(result)


@lru_cache(maxsize=None)
def generator_matrix(r, m):
    rows = []
    for monomial in monomials(r, m):
        row = []
        for point in points(m):
            value = 1
            for variable in monomial:
                value &= point[variable]
            row.append(value)
        rows.append(tuple(row))
    return tuple(rows)


def encode(message, r, m):
    params = parameters(r, m)
    if len(message) != params["k"]:
        raise ReedMullerError(f"Сообщение должно иметь длину k = {params['k']} бит.")

    codeword = [0] * params["n"]
    for bit, row in zip(message, generator_matrix(r, m)):
        if bit:
            codeword = [left ^ right for left, right in zip(codeword, row)]
    return codeword


def decode_recursive(received, r, m):
    params = parameters(r, m)
    if len(received) != params["n"]:
        raise ReedMullerError(f"Кодовое слово должно иметь длину n = {params['n']} бит.")

    if params["k"] <= 20:
        return nearest_codeword(tuple(received), r, m)

    return _decode_recursive(tuple(received), r, m)


@lru_cache(maxsize=64)
def all_codewords(r, m):
    params = parameters(r, m)
    if params["k"] > 20:
        raise ReedMullerError("Точный перебор доступен только при k <= 20.")

    words = []
    for value in range(2 ** params["k"]):
        message = [(value >> shift) & 1 for shift in range(params["k"] - 1, -1, -1)]
        words.append(tuple(encode(message, r, m)))
    return tuple(words)


def nearest_codeword(received, r, m):
    best_word = None
    best_distance = len(received) + 1
    for codeword in all_codewords(r, m):
        current_distance = distance(received, codeword)
        if current_distance < best_distance:
            best_word = codeword
            best_distance = current_distance
            if current_distance == 0:
                break
    return list(best_word)


def _decode_recursive(received, r, m):
    n = 2**m
    if r == 0:
        ones = sum(received)
        bit = 1 if ones * 2 >= n else 0
        return [bit] * n

    if r == m:
        return list(received)

    half = n // 2
    left = received[:half]
    right = received[half:]

    noisy_v = tuple(a ^ b for a, b in zip(left, right))
    decoded_v = _decode_recursive(noisy_v, r - 1, m - 1)

    noisy_u = []
    for a, b, v in zip(left, right, decoded_v):
        corrected_from_right = b ^ v
        noisy_u.append(a if a == corrected_from_right else a)

    decoded_u = _decode_recursive(tuple(noisy_u), r, m - 1)
    return decoded_u + [u ^ v for u, v in zip(decoded_u, decoded_v)]


def message_from_codeword(codeword, r, m):
    matrix = [list(column) for column in zip(*generator_matrix(r, m))]
    augmented = [row + [bit] for row, bit in zip(matrix, codeword)]
    rows = len(augmented)
    cols = len(augmented[0]) - 1
    pivot_row = 0
    pivots = []

    for col in range(cols):
        pivot = None
        for row in range(pivot_row, rows):
            if augmented[row][col]:
                pivot = row
                break
        if pivot is None:
            continue

        augmented[pivot_row], augmented[pivot] = augmented[pivot], augmented[pivot_row]
        for row in range(rows):
            if row != pivot_row and augmented[row][col]:
                augmented[row] = [
                    left ^ right for left, right in zip(augmented[row], augmented[pivot_row])
                ]
        pivots.append(col)
        pivot_row += 1
        if pivot_row == cols:
            break

    solution = [0] * cols
    for row, col in enumerate(pivots):
        solution[col] = augmented[row][-1]
    return solution


def distance(left, right):
    return sum(a != b for a, b in zip(left, right))


def flip_positions(bits, raw_positions):
    result = list(bits)
    positions = []
    for chunk in raw_positions.replace(",", " ").split():
        try:
            position = int(chunk)
        except ValueError as exc:
            raise ReedMullerError("Позиции ошибок должны быть целыми числами.") from exc
        if position < 1 or position > len(result):
            raise ReedMullerError(f"Позиция {position} вне диапазона 1..{len(result)}.")
        result[position - 1] ^= 1
        positions.append(position)
    return result, positions
