"""The longest common subsequence, which steps and words align by."""

from collections.abc import Callable, Sequence


def lcs_pairs[T](
    a: Sequence[T], b: Sequence[T], equal: Callable[[T, T], bool]
) -> list[tuple[int, int]]:
    """The index pairs of one longest common subsequence, increasing on both
    sides: of equally long ones, the one taking each match earliest."""
    # lengths[i][j]: the LCS length of a[i:] and b[j:].
    lengths = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for index_a in reversed(range(len(a))):
        for index_b in reversed(range(len(b))):
            lengths[index_a][index_b] = (
                lengths[index_a + 1][index_b + 1] + 1
                if equal(a[index_a], b[index_b])
                else max(lengths[index_a + 1][index_b], lengths[index_a][index_b + 1])
            )
    pairs: list[tuple[int, int]] = []
    index_a = index_b = 0
    while index_a < len(a) and index_b < len(b):
        if equal(a[index_a], b[index_b]):
            pairs.append((index_a, index_b))
            index_a += 1
            index_b += 1
        elif lengths[index_a + 1][index_b] >= lengths[index_a][index_b + 1]:
            index_a += 1
        else:
            index_b += 1
    return pairs
