"""The longest common subsequence steps and word diffs align by."""

from collections.abc import Callable

from pytest_given.delta.lcs import lcs_pairs

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
