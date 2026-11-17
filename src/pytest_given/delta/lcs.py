"""The longest common subsequence, which steps and words align by."""

from collections.abc import Callable, Iterable, Iterator, Sequence

from ..model import Mark

type Anchor = tuple[int, int]
type Gap = tuple[range, range, Anchor | None]
type Pairing = tuple[int | None, int | None]


def lcs_gaps[T](
    a: Sequence[T], b: Sequence[T], equal: Callable[[T, T], bool]
) -> Iterator[Gap]:
    """The stretches of `a` and `b` between the pairs of `lcs_pairs`."""
    return anchor_gaps(lcs_pairs(a, b, equal), len(a), len(b))


def marked_items[T](
    a: Sequence[T], b: Sequence[T], equal: Callable[[T, T], bool]
) -> Iterator[tuple[Mark, T | None, T | None]]:
    """Each item marked, every gap between matches read removed-then-added;
    an equal item comes with both sides' own."""
    for gap_a, gap_b, anchor in lcs_gaps(a, b, equal):
        for index in gap_a:
            yield 'removed', a[index], None
        for index in gap_b:
            yield 'added', None, b[index]
        if anchor is not None:
            yield 'equal', a[anchor[0]], b[anchor[1]]


def greedy_pairs(
    gap_a: range, gap_b: range, first_match: Callable[[int, int], int | None]
) -> Iterator[Pairing]:
    """Each index of `gap_a` pairs with `first_match(index_a, cursor)`, an index
    of `gap_b` from `cursor` on, the one past the last pairing; else it stands
    alone. The indexes of `gap_b` left unpaired stand alone too, in order."""
    cursor = gap_b.start
    for index_a in gap_a:
        match = first_match(index_a, cursor)
        if match is None:
            yield index_a, None
            continue
        yield from ((None, skipped) for skipped in range(cursor, match))
        yield index_a, match
        cursor = match + 1
    yield from ((None, skipped) for skipped in range(cursor, gap_b.stop))


def anchor_gaps(anchors: Iterable[Anchor], len_a: int, len_b: int) -> Iterator[Gap]:
    """The stretches between `anchors`, which increase on both sides, each with
    the anchor that ends it; the last stretch runs to both ends and has none."""
    start_a = start_b = 0
    for index_a, index_b in anchors:
        yield range(start_a, index_a), range(start_b, index_b), (index_a, index_b)
        start_a, start_b = index_a + 1, index_b + 1
    yield range(start_a, len_a), range(start_b, len_b), None


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
