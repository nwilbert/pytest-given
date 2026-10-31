"""Applying the rename log: chains, the stop rule, `rev` skipping, merges."""

from pytest_given import given, scenario, then, when
from pytest_given.delta import (
    RenameEntry,
    Rewrites,
    parse_rename_log,
    rewrite_case_id,
    rewrite_identities,
)
from tests.ubiquitous_language import pg


def _move(position: int, old: str, new: str, rev: str | None = None) -> RenameEntry:
    return RenameEntry(table='scenario', position=position, old=old, new=new, rev=rev)


def _identities(rewrites: Rewrites) -> dict[str, str]:
    return {old: rewrite.identity for old, rewrite in rewrites.by_identity.items()}


@scenario(
    t'A {pg["Rename log"]} chain ends at the last {pg["Scenario identity"]} '
    t'present in the after report',
    tags=['delta'],
)
def test_a_chain_ends_at_the_last_identity_present_in_after() -> None:
    with given(t'a {pg["Rename log"].l} renaming A to B, and later B to C'):
        entries = [_move(1, 'A', 'B'), _move(2, 'B', 'C')]
    with when('the before identity A is rewritten against reports that end at B or C'):
        to_c = rewrite_identities(['A'], {'C'}, entries, set())
        to_b = rewrite_identities(['A'], {'B'}, entries, set())
    with then('A ends at C when C exists, and at B when only B does'):
        assert _identities(to_c) == {'A': 'C'}
        assert _identities(to_b) == {'A': 'B'}
    with then('the rewrite to C followed both entries'):
        assert to_c.by_identity['A'].entries == tuple(entries)


@scenario(
    t'A chain that reaches nothing in the after report rewrites nothing, silently',
    tags=['delta'],
)
def test_a_chain_that_reaches_nothing_in_after_rewrites_nothing() -> None:
    with given(t'a {pg["Rename log"].l} renaming A to B'):
        entries = [_move(1, 'A', 'B')]
    with when('the after report holds neither A nor B'):
        rewrites = rewrite_identities(['A'], {'X'}, entries, set())
    with then('nothing is rewritten and nothing is warned about'):
        assert rewrites.by_identity == {}
        assert rewrites.warnings == ()


@scenario(
    t'An entry whose rev predates the range is skipped, so a reused '
    t'{pg["Scenario identity"]} pairs with its old self',
    tags=['delta'],
)
def test_an_entry_whose_rev_predates_the_range_is_skipped() -> None:
    with given(t'a {pg["Rename log"].l} entry renaming A to B at rev v1'):
        entries = [_move(1, 'A', 'B', rev='v1')]
    with when('v1 predates the range and both A and B exist in the after report'):
        skipped = rewrite_identities(['A'], {'A', 'B'}, entries, {'v1'})
    with then('A is not rewritten'):
        assert skipped.by_identity == {}
        assert skipped.warnings == ()
    with when('the same entry falls inside the range'):
        applied = rewrite_identities(['A'], {'A', 'B'}, entries, set())
    with then('A is rewritten to B, the name a new test later reused'):
        assert _identities(applied) == {'A': 'B'}


@scenario(
    t'A swap goes through a name neither test has, and a plain swap is a merge',
    tags=['delta'],
)
def test_a_swap_goes_through_a_name_neither_test_has() -> None:
    with given(t'a {pg["Rename log"].l} swapping A and B through tmp'):
        through_tmp = [_move(1, 'A', 'tmp'), _move(2, 'B', 'A'), _move(3, 'tmp', 'B')]
    with given(t'a {pg["Rename log"].l} that writes the swap as A to B, then B to A'):
        plain = [_move(1, 'A', 'B'), _move(2, 'B', 'A')]
    with when('both are applied to before and after reports holding A and B'):
        swapped = rewrite_identities(['A', 'B'], {'A', 'B'}, through_tmp, set())
        merged = rewrite_identities(['A', 'B'], {'A', 'B'}, plain, set())
    with then('the routed swap rewrites A to B and B to A'):
        assert _identities(swapped) == {'A': 'B', 'B': 'A'}
    with then('the plain swap rewrites neither, and warns once naming both entries'):
        assert merged.by_identity == {}
        (warning,) = merged.warnings
        assert '"A"' in warning
        assert plain[0].label in warning
        assert plain[1].label in warning


@scenario(
    t'A cases map from a later release leaves an earlier range alone',
    tags=['delta'],
)
def test_a_cases_map_from_a_later_release_leaves_an_earlier_range_alone() -> None:
    with given(
        t'a {pg["Rename log"].l} that renames test_pricing to test_price_list at '
        t'v0.6.0 and renames the case happy-hour at v0.7.0'
    ):
        log = parse_rename_log(
            '[[scenario]]\n'
            'old = "test_coffeeshop.py::test_pricing"\n'
            'new = "test_coffeeshop.py::test_price_list"\n'
            'cases = { "1.5-True" = "2.0-True" }\n'
            'rev = "v0.6.0"\n\n'
            '[[scenario]]\n'
            'old = "test_coffeeshop.py::test_price_list"\n'
            'cases = { "happy-hour" = "happy-hour-weekdays" }\n'
            'rev = "v0.7.0"\n',
            'given-renames.toml',
        )
        pricing = 'test_coffeeshop.py::test_pricing'
        price_list = 'test_coffeeshop.py::test_price_list'
    with when(
        'v0.5, where the test is still test_pricing, is compared with a later one'
    ):
        rewrites = rewrite_identities([pricing], {price_list}, log.entries, set())
        maps = rewrites.case_maps_of(pricing)
    with then('test_pricing is rewritten to test_price_list'):
        assert _identities(rewrites) == {pricing: price_list}
    with then('against v0.6, happy-hour keeps its ID and 1.5-True becomes 2.0-True'):
        v06_cases = {'happy-hour', '2.0-True'}
        assert rewrite_case_id('happy-hour', maps, v06_cases) == 'happy-hour'
        assert rewrite_case_id('1.5-True', maps, v06_cases) == '2.0-True'
    with then('against v0.7, happy-hour becomes happy-hour-weekdays'):
        v07_cases = {'happy-hour-weekdays', '2.0-True'}
        assert rewrite_case_id('happy-hour', maps, v07_cases) == 'happy-hour-weekdays'
        assert rewrite_case_id('1.5-True', maps, v07_cases) == '2.0-True'


def test_a_rewrite_onto_an_identity_that_exists_unrewritten_is_a_merge() -> None:
    entries = [_move(1, 'A', 'B')]

    rewrites = rewrite_identities(['A', 'B'], {'B'}, entries, set())

    assert rewrites.by_identity == {}
    (warning,) = rewrites.warnings
    assert '"B"' in warning
    assert entries[0].label in warning


def test_two_identities_ending_at_one_are_a_merge_naming_every_entry() -> None:
    entries = [_move(1, 'A', 'C'), _move(2, 'B', 'C')]

    rewrites = rewrite_identities(['A', 'B'], {'C'}, entries, set())

    assert rewrites.by_identity == {}
    (warning,) = rewrites.warnings
    assert '"C"' in warning
    assert all(entry.label in warning for entry in entries)


def test_a_merge_leaves_unrelated_rewrites_alone() -> None:
    entries = [_move(1, 'A', 'C'), _move(2, 'B', 'C'), _move(3, 'D', 'E')]

    rewrites = rewrite_identities(['A', 'B', 'D'], {'C', 'E'}, entries, set())

    assert _identities(rewrites) == {'D': 'E'}
    assert len(rewrites.warnings) == 1


def test_duplicate_before_identities_are_one_identity() -> None:
    rewrites = rewrite_identities(['A', 'A'], {'B'}, [_move(1, 'A', 'B')], set())

    assert _identities(rewrites) == {'A': 'B'}
    assert rewrites.warnings == ()


def test_an_identity_with_no_entries_is_left_alone() -> None:
    rewrites = rewrite_identities(['A'], {'A'}, [_move(1, 'X', 'Y')], set())

    assert rewrites == Rewrites(by_identity={}, warnings=(), unmoved_case_maps={})


def test_an_entry_applies_only_after_the_chain_has_reached_its_old() -> None:
    entries = [_move(1, 'B', 'C'), _move(2, 'A', 'B')]

    rewrites = rewrite_identities(['A'], {'B', 'C'}, entries, set())

    assert _identities(rewrites) == {'A': 'B'}


def test_a_chain_through_a_name_missing_from_after_still_reaches_the_stop() -> None:
    entries = [_move(1, 'A', 'B'), _move(2, 'B', 'C')]

    rewrites = rewrite_identities(['A'], {'C'}, entries, set())

    assert _identities(rewrites) == {'A': 'C'}
    assert rewrites.by_identity['A'].entries == tuple(entries)


def test_a_rewrite_carries_the_cases_maps_up_to_its_stop() -> None:
    entries = [
        RenameEntry(
            table='scenario', position=1, old='A', new='B', cases=(('x', 'y'),)
        ),
        RenameEntry(table='scenario', position=2, old='B', cases=(('y', 'z'),)),
        RenameEntry(table='scenario', position=3, old='B', new='C'),
        RenameEntry(table='scenario', position=4, old='C', cases=(('z', 'w'),)),
    ]

    to_b = rewrite_identities(['A'], {'B'}, entries, set())
    to_c = rewrite_identities(['A'], {'C'}, entries, set())

    assert to_b.by_identity['A'].case_maps == ((('x', 'y'),), (('y', 'z'),))
    assert to_c.by_identity['A'].case_maps == (
        (('x', 'y'),),
        (('y', 'z'),),
        (('z', 'w'),),
    )
    assert to_c.case_maps_of('A') == to_c.by_identity['A'].case_maps


def test_a_cases_only_entry_for_a_stay_put_identity_still_maps_its_cases() -> None:
    entries = [
        RenameEntry(table='scenario', position=1, old='A', cases=(('x', 'y'),)),
        _move(2, 'A', 'B'),
        RenameEntry(table='scenario', position=3, old='A', cases=(('p', 'q'),)),
    ]

    rewrites = rewrite_identities(['A'], {'A'}, entries, set())

    assert rewrites.by_identity == {}
    assert rewrites.case_maps_of('A') == ((('x', 'y'),),)
    assert rewrites.case_maps_of('unknown') == ()


def test_a_merge_keeps_the_cases_maps_of_the_identity_that_stayed() -> None:
    entries = [
        RenameEntry(table='scenario', position=1, old='A', cases=(('x', 'y'),)),
        _move(2, 'A', 'B'),
    ]

    rewrites = rewrite_identities(['A', 'B'], {'B'}, entries, set())

    assert rewrites.by_identity == {}
    assert rewrites.case_maps_of('A') == ((('x', 'y'),),)


def test_a_case_id_follows_the_maps_to_the_last_id_present_in_after() -> None:
    maps = [(('a', 'b'),), (('b', 'c'),)]

    assert rewrite_case_id('a', maps, {'b', 'c'}) == 'c'
    assert rewrite_case_id('a', maps, {'b'}) == 'b'
    assert rewrite_case_id('a', maps, {'z'}) == 'a'
    assert rewrite_case_id('a', [], {'a'}) == 'a'
    assert rewrite_case_id('q', maps, {'c'}) == 'q'
