"""The longest common subsequence steps and word diffs align by."""

from collections.abc import Callable

from pytest_given.delta.lcs import lcs_gaps, lcs_pairs

_SAME: Callable[[str, str], bool] = str.__eq__


def test_pairs_one_longest_common_subsequence_in_increasing_order() -> None:
    # b d a b: one of the length-4 subsequences
    assert lcs_pairs('abcbdab', 'bdcaba', _SAME) == [(1, 0), (4, 1), (5, 3), (6, 4)]


def test_identical_sequences_pair_every_item() -> None:
    assert lcs_pairs('abc', 'abc', _SAME) == [(0, 0), (1, 1), (2, 2)]


def test_disjoint_or_empty_sequences_pair_nothing() -> None:
    assert lcs_pairs('abc', 'xyz', _SAME) == []
    assert lcs_pairs('', 'abc', _SAME) == []
    assert lcs_pairs('abc', '', _SAME) == []


def test_equality_is_the_callers() -> None:
    assert lcs_pairs(
        ['A', 'b'], ['a', 'B'], lambda one, other: one.lower() == other.lower()
    ) == [
        (0, 0),
        (1, 1),
    ]


def test_identical_sequences_compare_each_pair_once() -> None:
    compared: list[tuple[str, str]] = []

    def same(one: str, other: str) -> bool:
        compared.append((one, other))
        return one == other

    assert lcs_pairs('abcd', 'abcd', same) == [(0, 0), (1, 1), (2, 2), (3, 3)]
    assert compared == [('a', 'a'), ('b', 'b'), ('c', 'c'), ('d', 'd')]


def test_a_common_suffix_still_yields_to_an_earlier_match() -> None:
    assert lcs_pairs('yxy', 'y', _SAME) == [(0, 0)]
    assert lcs_pairs('ab' + 'yxy', 'ab' + 'y', _SAME) == [(0, 0), (1, 1), (2, 2)]


def test_gaps_run_between_the_pairs_and_past_the_last() -> None:
    assert list(lcs_gaps('axbc', 'abyc', _SAME)) == [
        (range(0), range(0), (0, 0)),
        (range(1, 2), range(1, 1), (2, 1)),
        (range(3, 3), range(2, 3), (3, 3)),
        (range(4, 4), range(4, 4), None),
    ]
