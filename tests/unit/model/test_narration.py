"""The pure rules over `Narration` parts."""

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from pytest_given.markdown import EmphasisSpan, PlainSpan
from pytest_given.model import (
    ColumnId,
    Definition,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    PytestGivenError,
    TermId,
    boolean_phrases,
    merged_literals,
    narration_of,
    narration_text,
    placeholder_token,
    read_definition,
    read_narration,
    render_interpolation,
    spanned_part,
    texts_in_context,
    with_case_id,
    without_case_id,
)


def test_narration_text_rejects_unknown_variant() -> None:
    # The exhaustive match guards against a NarrationPart variant being added
    # without a text branch — which would drop it from `text` silently, and
    # `text` is what the report's search box and a `jq` query read.
    with pytest.raises(AssertionError):
        narration_text([cast(Any, object())])


def _value(expression: str) -> NarrationValue:
    return NarrationValue(rendered='v', expression=expression)


@pytest.mark.parametrize(
    ('parts', 'kind', 'index'),
    [
        (
            [
                NarrationLiteral(value='`run '),
                _value('cmd'),
                NarrationLiteral(value='`'),
            ],
            'a code span',
            1,
        ),
        (
            [
                NarrationLiteral(value='**'),
                NarrationTermRef(
                    term_id=TermId('guest'), display='Guest', expression='guest'
                ),
                NarrationLiteral(value='** books'),
            ],
            'bold',
            1,
        ),
        (
            [
                NarrationLiteral(value='a *'),
                NarrationPlaceholder(name='size', column_id=ColumnId('size')),
                NarrationLiteral(value=' cup*'),
            ],
            'italics',
            1,
        ),
        (
            [
                NarrationLiteral(value='*`code` '),
                _value('x'),
                NarrationLiteral(value='*'),
            ],
            'italics',
            1,
        ),
        (
            [
                NarrationLiteral(value='**a** `b` '),
                _value('x'),
                NarrationLiteral(value=' `c '),
                _value('y'),
                NarrationLiteral(value='`'),
            ],
            'a code span',
            3,
        ),
    ],
    ids=[
        'code-around-value',
        'bold-around-term-ref',
        'italic-around-placeholder',
        'italic-holding-code',
        'after-other-spans',
    ],
)
def test_spanned_part_names_the_span_and_the_part_it_holds(
    parts: list[NarrationPart], kind: str, index: int
) -> None:
    assert spanned_part(parts) == (kind, parts[index])


def test_read_narration_reads_a_stretch_with_the_characters_around_it() -> None:
    """A `*` after a letter and before punctuation opens no span."""
    stretch = narration_of([NarrationLiteral(value='*"x"* y')])
    assert read_narration(stretch) == [
        EmphasisSpan(strong=False, content=(PlainSpan(text='"x"'),)),
        PlainSpan(text=' y'),
    ]
    assert read_narration(stretch, before='t') == [PlainSpan(text='*"x"* y')]


def test_texts_in_context_flanks_each_text_by_its_neighbours() -> None:
    assert list(texts_in_context(['ab', '', 'c'], before='<', after='>')) == [
        ('<', 'c'),
        ('b', 'c'),
        ('b', '>'),
    ]


@pytest.mark.parametrize(
    'parts',
    [
        [NarrationLiteral(value='plain `code` and **bold**')],
        [NarrationLiteral(value='`run` '), _value('cmd')],
        [
            _value('a'),
            NarrationLiteral(value=' * '),
            _value('b'),
            NarrationLiteral(value=' *'),
        ],
        [
            NarrationLiteral(value='`x` '),
            NarrationValue(rendered='`', expression='tick'),
        ],
    ],
    ids=['literal-only', 'code-beside-value', 'spaced-asterisks', 'backtick-in-value'],
)
def test_spanned_part_finds_none_when_every_span_stays_in_its_text(
    parts: list[NarrationPart],
) -> None:
    assert spanned_part(parts) is None


@pytest.mark.parametrize(
    ('format_spec', 'phrases'),
    [
        ('pins it|does not pin it', ('pins it', 'does not pin it')),
        ('a | b', ('a', 'b')),
        ('', None),
        ('.2f', None),
        ('|>5', None),
        ('a|', None),
        ('a|b|c', None),
        (' |b', None),
        ('a| ', None),
    ],
)
def test_boolean_phrases_reads_a_phrase_spec(
    format_spec: str, phrases: tuple[str, str] | None
) -> None:
    assert boolean_phrases(format_spec) == phrases


@pytest.mark.parametrize('format_spec', ['a|a', 'a | a'])
def test_boolean_phrases_refuses_identical_phrases(format_spec: str) -> None:
    with pytest.raises(PytestGivenError) as excinfo:
        boolean_phrases(format_spec)
    assert format_spec in str(excinfo.value)


@pytest.mark.parametrize(
    ('value', 'format_spec', 'rendered'),
    [
        (True, 'a|b', 'a'),
        (False, 'a|b', 'b'),
        (True, 'a | b', 'a'),
        (False, 'a | b', 'b'),
        (True, '|>5', '||||1'),
        (1.5, '.2f', '1.50'),
    ],
)
def test_render_interpolation_words_a_boolean_and_formats_the_rest(
    value: object, format_spec: str, rendered: str
) -> None:
    assert render_interpolation(value, None, format_spec) == rendered


@pytest.mark.parametrize('format_spec', ['a|', 'a|b|c'])
def test_render_interpolation_leaves_a_broken_spec_to_format(format_spec: str) -> None:
    with pytest.raises(ValueError, match='Invalid format specifier') as excinfo:
        render_interpolation(True, None, format_spec)
    assert format_spec in str(excinfo.value)


def test_render_interpolation_refuses_identical_phrases() -> None:
    with pytest.raises(PytestGivenError, match=r'a\|a'):
        render_interpolation(True, None, 'a|a')


@pytest.mark.parametrize(
    ('value', 'conversion', 'format_spec', 'type_name'),
    [
        (1, None, 'a|b', 'int'),
        (None, None, 'a|b', 'NoneType'),
        ('x', None, 'a|b', 'str'),
        (True, 'r', 'a|b', 'bool'),
        (datetime(2026, 1, 1, 14, 30, tzinfo=UTC), None, '%H|%M', 'datetime'),
    ],
)
def test_render_interpolation_refuses_a_phrase_spec_on_anything_but_a_bare_boolean(
    value: object, conversion: str | None, format_spec: str, type_name: str
) -> None:
    with pytest.raises(PytestGivenError) as excinfo:
        render_interpolation(value, conversion, format_spec)
    assert format_spec in str(excinfo.value)
    assert type_name in str(excinfo.value)


@pytest.mark.parametrize(
    ('format_spec', 'token'),
    [
        ('', '{pinned}'),
        ('.2f', '{pinned}'),
        ('|>5', '{pinned}'),
        ('pins it|does not pin it', '{pins it / does not pin it}'),
        ('a | b', '{a / b}'),
    ],
)
def test_placeholder_token_shows_both_phrases_of_a_phrase_spec(
    format_spec: str, token: str
) -> None:
    part = NarrationPlaceholder(
        name='pinned', column_id=ColumnId('pinned'), format_spec=format_spec
    )
    assert placeholder_token(part) == token
    assert narration_text([part]) == token


_PHASE_REF = NarrationTermRef(term_id=TermId('phase'), display='Phase')


def test_read_definition_passes_a_ref_through_and_reads_the_literals() -> None:
    definition = Definition(
        'In one **Phase**, *nested*.',
        (
            NarrationLiteral(value='In one '),
            _PHASE_REF,
            NarrationLiteral(value=', *nested*.'),
        ),
    )
    assert read_definition(definition) == [
        PlainSpan('In one '),
        _PHASE_REF,
        PlainSpan(', '),
        EmphasisSpan(False, (PlainSpan('nested'),)),
        PlainSpan('.'),
    ]


def test_read_definition_reads_a_literal_s_edge_against_the_ref_beside_it() -> None:
    definition = Definition(
        '**Phase****(b)**', (_PHASE_REF, NarrationLiteral(value='**(b)**'))
    )
    assert read_definition(definition) == [_PHASE_REF, PlainSpan('**(b)**')]


def test_merged_literals_joins_each_run_of_adjacent_literals() -> None:
    value = _value('n')
    assert merged_literals(
        [
            NarrationLiteral(value='a '),
            NarrationLiteral(value='b '),
            value,
            NarrationLiteral(value=' c'),
        ]
    ) == (NarrationLiteral(value='a b '), value, NarrationLiteral(value=' c'))


def test_without_case_id_undoes_with_case_id_for_that_case_only() -> None:
    title = narration_of([NarrationLiteral(value='Stay')])

    suffixed = with_case_id(title, 't.py::test_stay[1-2]')

    assert suffixed.text == 'Stay [1-2]'
    assert without_case_id(suffixed, 't.py::test_stay[1-2]') == title
    assert without_case_id(suffixed, 't.py::test_stay[3]') == suffixed
