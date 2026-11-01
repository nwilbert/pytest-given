"""The longest common subsequence, which steps and words align by."""

from collections.abc import Callable, Iterator, Sequence

type Anchor = tuple[int, int]


def lcs_gaps[T](
    a: Sequence[T], b: Sequence[T], equal: Callable[[T, T], bool]
) -> Iterator[tuple[range, range, Anchor | None]]:
    """The stretches of `a` and `b` between the pairs of `lcs_pairs`, each with
    the pair that ends it; the last stretch runs to both ends and has none."""
    start_a = start_b = 0
    for index_a, index_b in lcs_pairs(a, b, equal):
        yield range(start_a, index_a), range(start_b, index_b), (index_a, index_b)
        start_a, start_b = index_a + 1, index_b + 1
    yield range(start_a, len(a)), range(start_b, len(b)), None


def lcs_pairs[T](
    a: Sequence[T], b: Sequence[T], equal: Callable[[T, T], bool]
) -> list[Anchor]:
    """The index pairs of one longest common subsequence, increasing on both
    sides: of equally long ones, the one taking each match earliest."""
    # A common prefix is what that tie-break takes anyway, so it costs no table.
    # A common suffix is not: an earlier match can win over it.
    prefix = 0
    while prefix < min(len(a), len(b)) and equal(a[prefix], b[prefix]):
        prefix += 1
    pairs = [(index, index) for index in range(prefix)]
    rest_a, rest_b = a[prefix:], b[prefix:]
    # lengths[i][j]: the LCS length of rest_a[i:] and rest_b[j:].
    lengths = [[0] * (len(rest_b) + 1) for _ in range(len(rest_a) + 1)]
    for index_a in reversed(range(len(rest_a))):
        for index_b in reversed(range(len(rest_b))):
            lengths[index_a][index_b] = (
                lengths[index_a + 1][index_b + 1] + 1
                if equal(rest_a[index_a], rest_b[index_b])
                else max(lengths[index_a + 1][index_b], lengths[index_a][index_b + 1])
            )
    index_a = index_b = 0
    while index_a < len(rest_a) and index_b < len(rest_b):
        if equal(rest_a[index_a], rest_b[index_b]):
            pairs.append((prefix + index_a, prefix + index_b))
            index_a += 1
            index_b += 1
        elif lengths[index_a + 1][index_b] >= lengths[index_a][index_b + 1]:
            index_a += 1
        else:
            index_b += 1
    return pairs
