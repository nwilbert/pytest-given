"""Pairing two glossaries' terms: the rename log, kinds, changes, derived facts."""

from pytest_given import given, scenario, then, when
from pytest_given.delta import RenameEntry, RenameLog
from pytest_given.delta.terms import align_terms, term_facts
from pytest_given.model import Glossary, GlossaryTerm, TermFacts, TermId
from tests.ubiquitous_language import pg
from tests.unit.delta.builders import lit, narr, ref, report, scn, step, term


def _glossary(*terms: GlossaryTerm) -> Glossary:
    return Glossary(list(terms))


def _log(*moves: tuple[str, str]) -> RenameLog:
    return RenameLog(
        entries=tuple(
            RenameEntry(table='term', position=position, old=old, new=new)
            for position, (old, new) in enumerate(moves, start=1)
        )
    )


def _facts_of(
    *terms: GlossaryTerm, mentions: list[tuple[str, str]]
) -> dict[TermId, TermFacts]:
    scenarios = [
        scn(
            f't.py::test_{index}',
            'a scenario',
            step('given', narr(lit('uses '), ref(term_id, display))),
        )
        for index, (term_id, display) in enumerate(mentions)
    ]
    return term_facts(report(*scenarios, glossary=_glossary(*terms)))


@scenario(
    t'A renamed {pg["Term"].l} pairs only through a `[[term]]` entry in the '
    t'{pg["Rename log"].l}',
    tags=['delta'],
)
def test_a_renamed_term_pairs_only_through_a_term_entry() -> None:
    with given(
        t'a {pg["Glossary"].l} whose guest term is called visitor in the next one, '
        t'and a {pg["Rename log"].l} with a `[[term]]` entry for guest'
    ):
        before = report(glossary=_glossary(term('guest', 'Guest')))
        after = report(glossary=_glossary(term('visitor', 'Visitor')))
        log = _log(('guest', 'visitor'))
    with when('the terms are aligned with and without the entry'):
        with_entry = align_terms(before, after, log, set())
        without = align_terms(before, after, RenameLog(), set())
    with then('the entry pairs them, and the renamed term reads as changed'):
        (paired,) = with_entry.delta.terms
        assert (paired.change, paired.paired_by) == ('changed', 'rename-log')
        assert paired.before == term('guest', 'Guest')
        assert paired.after == term('visitor', 'Visitor')
    with then('without the entry the term is removed and the new one added'):
        assert [(delta.change, delta.paired_by) for delta in without.delta.terms] == [
            ('removed', None),
            ('added', None),
        ]
    with then('a narration ref to guest is rewritten to visitor with the entry'):
        assert with_entry.term_id(TermId('guest')) == 'visitor'
        assert without.term_id(TermId('guest')) == 'guest'


@scenario(
    t'A {pg["Term"].l} whose kind changed is listed twice',
    tags=['delta'],
)
def test_a_term_whose_kind_changed_is_listed_twice() -> None:
    with given(
        t'a {pg["Term"].l} that is an object in one {pg["Glossary"].l} and an actor '
        t'in the next'
    ):
        before = report(glossary=_glossary(term('guest', 'Guest', kind='object')))
        after = report(glossary=_glossary(term('guest', 'Guest', kind='actor')))
    with when('the terms are aligned'):
        alignment = align_terms(before, after, RenameLog(), set())
    with then('it is removed under its old kind and added under its new one'):
        removed, added = alignment.delta.terms
        assert (removed.change, removed.before) == (
            'removed',
            term('guest', 'Guest', kind='object'),
        )
        assert removed.after is None
        assert (added.change, added.after) == (
            'added',
            term('guest', 'Guest', kind='actor'),
        )
        assert added.before is None
        assert alignment.delta.unchanged == ()
    with then('narration refs to it still compare as the same term'):
        assert alignment.term_id(TermId('guest')) == 'guest'


def test_a_kindless_term_pairs_with_itself_and_unpairs_from_a_kinded_one() -> None:
    before = report(
        glossary=_glossary(term('a', 'A', kind=None), term('b', 'B', kind=None))
    )
    after = report(
        glossary=_glossary(term('a', 'A', kind=None), term('b', 'B', kind='actor'))
    )

    alignment = align_terms(before, after, RenameLog(), set())

    assert [
        (delta.change, delta.before is None) for delta in alignment.delta.terms
    ] == [
        ('removed', False),
        ('added', True),
    ]
    assert [(pair.before, pair.after) for pair in alignment.delta.unchanged] == [
        ('a', 'a')
    ]


def test_a_changed_definition_is_a_word_diff_of_the_two() -> None:
    before = report(glossary=_glossary(term('guest', 'Guest', definition='a person')))
    after = report(
        glossary=_glossary(term('guest', 'Guest', definition='a paying person'))
    )

    alignment = align_terms(before, after, RenameLog(), set())

    (delta,) = alignment.delta.terms
    assert (delta.change, delta.paired_by) == ('changed', 'term-id')
    assert [segment.mark for segment in delta.definition] == [
        'equal',
        'added',
        'equal',
    ]
    assert delta.before_facts == TermFacts()
    assert delta.after_facts == TermFacts()


def test_a_changed_canonical_name_alone_is_changed_without_a_definition_diff() -> None:
    before = report(glossary=_glossary(term('guest', 'Guest', definition='a person')))
    after = report(glossary=_glossary(term('guest', 'Visitor', definition='a person')))

    alignment = align_terms(before, after, RenameLog(), set())

    (delta,) = alignment.delta.terms
    assert delta.change == 'changed'
    assert delta.definition == ()


def test_a_missing_definition_reads_as_empty() -> None:
    before = report(glossary=_glossary(term('guest', 'Guest')))
    after = report(glossary=_glossary(term('guest', 'Guest', definition='a person')))

    (delta,) = align_terms(before, after, RenameLog(), set()).delta.terms

    assert [segment.mark for segment in delta.definition] == ['added']


def test_a_facts_only_difference_leaves_the_term_unchanged() -> None:
    guest = term('guest', 'Guest')
    before = report(
        scn('t.py::test_a', 'a', step('given', narr(ref('guest', 'Guest')))),
        glossary=_glossary(guest),
    )
    after = report(
        scn('t.py::test_a', 'a', step('given', narr(ref('guest', 'Guest')))),
        scn('t.py::test_b', 'b', step('given', narr(ref('guest', 'Alice')))),
        glossary=_glossary(guest),
    )

    alignment = align_terms(before, after, RenameLog(), set())

    assert alignment.delta.terms == ()
    assert [(pair.before, pair.after) for pair in alignment.delta.unchanged] == [
        ('guest', 'guest')
    ]


def test_facts_are_stored_for_each_side_a_listed_term_has() -> None:
    before = report(
        scn('t.py::test_a', 'a', step('given', narr(ref('room', 'Room')))),
        glossary=_glossary(term('room', 'Room'), term('gone', 'Gone')),
    )
    after = report(
        scn('t.py::test_a', 'a', step('given', narr(ref('room', 'Room')))),
        scn('t.py::test_b', 'b', step('given', narr(ref('room', 'Suite')))),
        glossary=_glossary(
            term('room', 'Room', definition='a place'), term('new', 'New')
        ),
    )

    alignment = align_terms(before, after, RenameLog(), set())

    by_change = {
        (delta.change, (delta.before or delta.after).id): delta  # type: ignore[union-attr]
        for delta in alignment.delta.terms
    }
    changed = by_change[('changed', 'room')]
    assert changed.before_facts == TermFacts(scenario_count=1)
    assert changed.after_facts == TermFacts(other_forms=('Suite',), scenario_count=2)
    removed = by_change[('removed', 'gone')]
    assert (removed.before_facts, removed.after_facts) == (TermFacts(), None)
    added = by_change[('added', 'new')]
    assert (added.before_facts, added.after_facts) == (None, TermFacts())


def test_other_forms_are_instances_then_activity_forms_in_first_seen_order() -> None:
    facts = _facts_of(
        term('guest', 'Guest', kind='actor'),
        mentions=[('guest', 'Alice'), ('guest', 'Guest'), ('guest', 'Bob')],
    )

    assert facts[TermId('guest')] == TermFacts(
        other_forms=('Alice', 'Bob'), scenario_count=3
    )


def test_a_term_with_no_references_has_empty_facts() -> None:
    facts = _facts_of(term('guest', 'Guest'), mentions=[])

    assert facts == {TermId('guest'): TermFacts()}


def test_a_report_without_a_glossary_has_no_facts() -> None:
    assert term_facts(report()) == {}


def test_without_a_before_glossary_every_after_term_is_added() -> None:
    after = report(glossary=_glossary(term('guest', 'Guest'), term('room', 'Room')))

    alignment = align_terms(report(), after, _log(('x', 'guest')), set())

    assert [(delta.change, delta.before) for delta in alignment.delta.terms] == [
        ('added', None),
        ('added', None),
    ]
    assert alignment.delta.before is None
    assert alignment.delta.after is after.glossary
    assert alignment.term_id(TermId('guest')) == 'guest'
    assert alignment.term_id(TermId('x')) == 'x'


def test_without_an_after_glossary_every_before_term_is_removed() -> None:
    before = report(glossary=_glossary(term('guest', 'Guest')))

    alignment = align_terms(before, report(), _log(('guest', 'visitor')), set())

    assert [(delta.change, delta.after) for delta in alignment.delta.terms] == [
        ('removed', None)
    ]
    assert alignment.term_id(TermId('guest')) == 'guest'


def test_two_missing_glossaries_give_an_empty_delta() -> None:
    alignment = align_terms(report(), report(), RenameLog(), set())

    assert alignment.delta.terms == ()
    assert alignment.delta.unchanged == ()
    assert (alignment.delta.before, alignment.delta.after) == (None, None)
    assert alignment.warnings == ()


def test_terms_follow_the_after_order_with_removed_ones_after_their_predecessor() -> (
    None
):
    before = report(
        glossary=_glossary(
            term('a', 'A'), term('gone', 'Gone'), term('b', 'B', definition='x')
        )
    )
    after = report(
        glossary=_glossary(
            term('b', 'B', definition='y'), term('a', 'A'), term('c', 'C')
        )
    )

    alignment = align_terms(before, after, RenameLog(), set())

    assert [
        (delta.change, (delta.after or delta.before).id)  # type: ignore[union-attr]
        for delta in alignment.delta.terms
    ] == [('changed', 'b'), ('removed', 'gone'), ('added', 'c')]
    assert [(pair.before, pair.after) for pair in alignment.delta.unchanged] == [
        ('a', 'a')
    ]


def test_a_rev_skipped_entry_does_not_pair() -> None:
    before = report(glossary=_glossary(term('guest', 'Guest')))
    after = report(glossary=_glossary(term('visitor', 'Visitor')))
    log = RenameLog(
        entries=(
            RenameEntry(table='term', position=1, old='guest', new='visitor', rev='r1'),
        )
    )

    alignment = align_terms(before, after, log, {'r1'})

    assert [delta.change for delta in alignment.delta.terms] == ['removed', 'added']
    assert alignment.term_id(TermId('guest')) == 'guest'


def test_a_renamed_term_whose_kind_changed_is_listed_twice_with_a_warning() -> None:
    """Its refs still follow the rename, as a kind change alone keeps them."""
    before = report(glossary=_glossary(term('guest', 'Guest', kind='actor')))
    after = report(glossary=_glossary(term('visitor', 'Visitor', kind='object')))

    alignment = align_terms(before, after, _log(('guest', 'visitor')), set())

    assert [delta.change for delta in alignment.delta.terms] == ['removed', 'added']
    assert alignment.term_id(TermId('guest')) == 'visitor'
    assert alignment.warnings == (
        (
            'rename log: term "guest" became "visitor" and its kind changed from '
            'actor to object, so the glossary lists it removed and added; its '
            'term refs still compare as one term'
        ),
    )


def test_a_merging_rename_warns_and_pairs_nothing_by_it() -> None:
    before = report(glossary=_glossary(term('a', 'A'), term('b', 'B')))
    after = report(glossary=_glossary(term('c', 'C')))

    alignment = align_terms(before, after, _log(('a', 'c'), ('b', 'c')), set())

    assert len(alignment.warnings) == 1
    assert [delta.change for delta in alignment.delta.terms] == [
        'removed',
        'removed',
        'added',
    ]


def test_a_missing_definition_and_an_empty_one_are_the_same() -> None:
    before = report(glossary=_glossary(term('guest', 'Guest', definition=None)))
    after = report(glossary=_glossary(term('guest', 'Guest', definition='')))

    alignment = align_terms(before, after, RenameLog(), set())

    assert alignment.delta.terms == ()
    assert [(pair.before, pair.after) for pair in alignment.delta.unchanged] == [
        ('guest', 'guest')
    ]
