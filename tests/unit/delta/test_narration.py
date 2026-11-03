"""Comparing two narrations as they read, and diffing them by word."""

from collections.abc import Mapping

from pytest_given import given, scenario, then, when
from pytest_given.delta.narration import (
    Reading,
    narrations_equal,
    reading_words,
    similarity,
    term_forms,
    tokens,
    word_diff,
)
from pytest_given.model import (
    ColumnId,
    DiffSegment,
    Glossary,
    GlossaryTerm,
    Mark,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationValue,
    TermId,
    narration_text,
)
from tests.ubiquitous_language import pg
from tests.unit.delta.builders import lit, narr, ph, ref, term


def _reading(
    *terms: GlossaryTerm,
    renames: Mapping[str, str] | None = None,
    columns: Mapping[str, str] | None = None,
) -> Reading:
    term_ids = renames or {}
    column_keys = columns or {}
    return Reading(
        glossary=Glossary(terms=list(terms)) if terms else None,
        term_id=lambda term_id: TermId(term_ids.get(term_id, term_id)),
        column=lambda part: column_keys.get(part.column_id, part.column_id),
    )


def _plain(text: str) -> Narration:
    return Narration(text=text)


def _equal(before: Narration, after: Narration, reading: Reading | None = None) -> bool:
    plain = reading or _reading()
    return narrations_equal(before, plain, after, plain)


def _segment(mark: Mark, *parts: NarrationPart) -> DiffSegment:
    """A run whose side or sides read `parts` alike."""
    return DiffSegment(
        mark=mark,
        before=parts if mark != 'added' else (),
        after=parts if mark != 'removed' else (),
    )


@scenario(
    t'A value compares by what it renders, not its source expression',
    tags=['delta'],
)
def test_a_value_compares_by_what_it_renders() -> None:
    with given(
        t'a {pg["Narration"].l} that interpolates 200 ml from the expression volume'
    ):
        valued = narr(
            lit('Brew '), NarrationValue(rendered='200 ml', expression='volume')
        )
    with given('a plain narration that reads the same'):
        plain = _plain('Brew 200 ml')
    with when('the two are compared'):
        same = _equal(valued, plain)
    with then('they are equal'):
        assert same


def test_a_value_s_changed_word_is_marked_alone_and_keeps_it_a_value() -> None:
    def price(rendered: str) -> Narration:
        return narr(lit('pays '), NarrationValue(rendered=rendered, expression='p'))

    def value(rendered: str) -> NarrationValue:
        return NarrationValue(rendered=rendered, expression='p')

    assert word_diff(price('5 EUR'), _reading(), price('6 EUR'), _reading()) == (
        _segment('equal', lit('pays ')),
        _segment('removed', value('5')),
        _segment('added', value('6')),
        _segment('equal', value(' EUR')),
    )


@scenario(
    t'A placeholder compares by the column it points at',
    tags=['delta'],
)
def test_a_placeholder_compares_by_its_column() -> None:
    with given(
        'a before placeholder whose column pairs with the after column `derived:1`'
    ):
        before = narr(lit('pour '), ph('size', 'derived:0'))
        before_reading = _reading(columns={'derived:0': 'derived:1'})
    with given('an after placeholder of another name and format spec in that column'):
        after = narr(
            lit('pour '),
            NarrationPlaceholder(
                name='size2', column_id=ColumnId('derived:1'), format_spec='>3'
            ),
        )
    with when('the two are compared'):
        same = narrations_equal(before, before_reading, after, _reading())
    with then('they are equal'):
        assert same
    with when('the before placeholder is read without the column pairing'):
        unpaired = narrations_equal(before, _reading(), after, _reading())
    with then('they differ'):
        assert not unpaired


@scenario(
    t'A {pg["Term ref"].l} compares by term and form, not by its display',
    tags=['delta'],
)
def test_a_term_ref_compares_by_term_and_form() -> None:
    with given(
        t'a before {pg["Term ref"].l} to room, lowercased, and a '
        t'{pg["Rename log"].l} renaming room to suite'
    ):
        before = narr(lit('book a '), ref('room', 'room'))
        before_reading = _reading(term('room', 'Room'), renames={'room': 'suite'})
        after_reading = _reading(term('suite', 'Suite'))
    with when(
        t'it is compared with suite, lowercased, and with suite in its {pg["S-form"]}'
    ):
        lowercased = narrations_equal(
            before,
            before_reading,
            narr(lit('book a '), ref('suite', 'suite')),
            after_reading,
        )
        plural = narrations_equal(
            before,
            before_reading,
            narr(lit('book a '), ref('suite', 'Suites')),
            after_reading,
        )
    with then('the same form is equal and the other form differs'):
        assert lowercased
        assert not plural
    with when(t'two {pg["Instance"].l.s} of guest, Alice and Bob, are compared'):
        guests = _reading(term('guest', 'Guest', kind='actor'))
        instances = narrations_equal(
            narr(ref('guest', 'Alice')), guests, narr(ref('guest', 'Bob')), guests
        )
    with then('they differ'):
        assert not instances


@scenario(
    t'A word diff keeps {pg["Term ref"].l.s}, placeholders and inline spans whole',
    tags=['delta'],
)
def test_a_word_diff_keeps_term_refs_placeholders_and_spans_whole() -> None:
    with given('the before narration `the **later** booking is cancelled`'):
        before = _plain('the **later** booking is cancelled')
    with given(
        t'the after narration `the **late** {{Booking}} is cancelled and refunded`, '
        t'with a {pg["Term ref"].l} to booking'
    ):
        after = narr(
            lit('the **late** '),
            ref('booking', 'Booking'),
            lit(' is cancelled and refunded'),
        )
        reading = _reading(term('booking', 'Booking'))
    with when('the two are diffed by word'):
        segments = word_diff(before, _reading(), after, reading)
    with then(
        t'the bold span and the {pg["Term ref"].l} that replaced booking are each '
        t'marked whole, and the added words follow the unchanged ones'
    ):
        assert segments == (
            _segment('equal', lit('the ')),
            _segment('removed', lit('**later**')),
            _segment('added', lit('**late**')),
            _segment('equal', lit(' ')),
            _segment('removed', lit('booking')),
            _segment('added', ref('booking', 'Booking')),
            _segment('equal', lit(' is cancelled')),
            _segment('added', lit(' and refunded')),
        )
    with when('the placeholder points at another column in the after narration'):
        moved = word_diff(
            narr(lit('pour '), ph('size', 'derived:0')),
            _reading(),
            narr(lit('pour '), ph('size', 'derived:1')),
            _reading(),
        )
    with then('the placeholder reads removed and added whole'):
        assert moved == (
            _segment('equal', lit('pour ')),
            _segment('removed', ph('size', 'derived:0')),
            _segment('added', ph('size', 'derived:1')),
        )


def test_a_lowercase_canonical_reads_as_bare_and_lowercased() -> None:
    assert term_forms('guest', term('guest', 'guest')) == {'bare', 'l'}
    assert term_forms('guests', term('guest', 'guest')) == {'s', 'l.s'}
    assert term_forms('Alice', term('guest', 'guest')) == frozenset()
    assert term_forms('guest', None) == frozenset()


def test_the_lowercased_form_keeps_acronyms_as_the_handle_does() -> None:
    assert term_forms('API key', term('api-key', 'API Key')) == {'l'}
    assert term_forms('API keys', term('api-key', 'API Key')) == {'l.s'}


def test_a_display_kept_while_the_canonical_was_recapitalized_compares_equal() -> None:
    before = narr(ref('guest', 'guest'))
    after = narr(ref('guest', 'guest'))
    assert narrations_equal(
        before,
        _reading(term('guest', 'guest')),
        after,
        _reading(term('guest', 'Guest')),
    )


def test_an_unknown_term_compares_by_display() -> None:
    assert _equal(narr(ref('ghost', 'Ghost')), narr(ref('ghost', 'Ghost')))
    assert not _equal(narr(ref('ghost', 'Ghost')), narr(ref('ghost', 'Ghosts')))
    assert not _equal(narr(ref('ghost', 'Ghost')), narr(ref('other', 'Ghost')))


def test_a_term_ref_never_equals_a_word() -> None:
    reading = _reading(term('guest', 'Guest'))
    assert not narrations_equal(
        narr(ref('guest', 'Guest')), reading, _plain('Guest'), reading
    )


def test_literals_split_into_words_spaces_and_whole_spans() -> None:
    read = tokens(
        _plain('see `a b` and *very much* [the docs](https://x.y/z) now'), _reading()
    )
    assert [(token.kind, token.key) for token in read] == [
        ('word', 'see'),
        ('space', ' '),
        ('code', '`a b`'),
        ('space', ' '),
        ('word', 'and'),
        ('space', ' '),
        ('emphasis', '*very much*'),
        ('space', ' '),
        ('link', '[the docs](https://x.y/z)'),
        ('space', ' '),
        ('word', 'now'),
    ]
    assert read[2].parts == (NarrationLiteral(value='`a b`'),)


def test_a_span_reads_with_its_neighbouring_parts() -> None:
    # Followed by a letter, the closing `*` after punctuation cannot close.
    read = tokens(
        narr(lit('*x.*'), NarrationValue(rendered='y', expression='y')), _reading()
    )
    assert [(token.kind, token.key) for token in read] == [
        ('word', '*x.*'),
        ('word', 'y'),
    ]


def test_a_changed_link_is_marked_whole() -> None:
    before = _plain('read [the docs](https://a.b/old) first')
    after = _plain('read [the docs](https://a.b/new) first')
    assert word_diff(before, _reading(), after, _reading()) == (
        _segment('equal', lit('read ')),
        _segment('removed', lit('[the docs](https://a.b/old)')),
        _segment('added', lit('[the docs](https://a.b/new)')),
        _segment('equal', lit(' first')),
    )


def test_spaces_compare_equal_whatever_they_hold() -> None:
    assert _equal(_plain('a  b'), _plain('a b'))
    assert not _equal(_plain('a b'), _plain('a b c'))


def test_an_equal_term_ref_keeps_each_side_s_display() -> None:
    """Renamed, so it compares equal, yet each side reads its own name."""
    before = narr(lit('a '), ref('room', 'room'))
    after = narr(lit('a '), ref('suite', 'suite'))
    assert word_diff(
        before,
        _reading(term('room', 'Room'), renames={'room': 'suite'}),
        after,
        _reading(term('suite', 'Suite')),
    ) == (
        DiffSegment(
            mark='equal',
            before=(lit('a '), ref('room', 'room')),
            after=(lit('a '), ref('suite', 'suite')),
        ),
    )


def test_each_side_keeps_its_own_spaces() -> None:
    """The space after `Dana` pairs with one of the after side's: it stays on
    each side, so neither side's words run together."""
    before = narr(ref('desk', 'Dana'), lit(' has one free room'))
    after = _plain('the front desk has one free room')
    segments = word_diff(before, _reading(), after, _reading())
    assert [
        ''.join(narration_text(segment.before) for segment in segments),
        ''.join(narration_text(segment.after) for segment in segments),
    ] == ['Dana has one free room', 'the front desk has one free room']
    assert segments == (
        _segment('removed', ref('desk', 'Dana')),
        _segment('added', lit('the')),
        _segment('equal', lit(' ')),
        _segment('added', lit('front desk ')),
        _segment('equal', lit('has one free room')),
    )


def test_spaces_of_another_width_stay_each_side_s_own() -> None:
    assert word_diff(_plain('X\tY a'), _reading(), _plain(' a'), _reading()) == (
        _segment('removed', lit('X')),
        DiffSegment(mark='equal', before=(lit('\t'),), after=(lit(' '),)),
        _segment('removed', lit('Y ')),
        _segment('equal', lit('a')),
    )


def test_two_empty_narrations_diff_to_nothing() -> None:
    assert word_diff(_plain(''), _reading(), _plain(''), _reading()) == ()


def test_similarity_counts_shared_tokens_without_spaces() -> None:
    def similar(before: str, after: str) -> float:
        return similarity(
            reading_words(_plain(before), _reading()),
            reading_words(_plain(after), _reading()),
        )

    assert similar('a b c', 'a b c') == 1.0
    assert similar('a b', 'c d') == 0.0
    assert similar('a b', 'a  c d') == 0.4
    assert similar('', '') == 1.0
