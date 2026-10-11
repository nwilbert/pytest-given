import time

import pytest

from pytest_given.model import (
    CodeSpan,
    EmphasisSpan,
    InlineSpan,
    PlainSpan,
    PytestGivenError,
    derived_id,
    id_derive,
    plural,
    read_spans,
    s_form,
    table_cell_spans,
)


def test_derived_id_returns_none_where_id_derive_raises() -> None:
    assert derived_id('---') is None
    with pytest.raises(PytestGivenError, match='derived id is empty'):
        id_derive('---')


def test_derived_id_agrees_with_id_derive_on_a_derivable_name() -> None:
    assert derived_id('Flat White') == id_derive('Flat White') == 'flat-white'


@pytest.mark.parametrize('name', ['\u212a', '\u0130'])
def test_a_character_that_lowercases_into_ascii_still_derives(name: str) -> None:
    """The fold happens after `str.lower`, so a non-ASCII character whose
    lowercase form is ASCII does have a slug. A predicate that tested the
    original characters for ASCII-ness would wrongly call these underivable."""
    assert derived_id(name) is not None
    assert derived_id(name) == id_derive(name)


@pytest.mark.parametrize(
    ('word', 's_form_of_word'),
    [
        ('room', 'rooms'),
        ('book', 'books'),
        ('bus', 'buses'),
        ('box', 'boxes'),
        ('watch', 'watches'),
        ('wish', 'wishes'),
        ('category', 'categories'),
        ('key', 'keys'),
        ('buy', 'buys'),
        ('booking request', 'booking requests'),
        ('API', 'APIs'),
        ('SMS', 'SMSs'),
        ('Y', 'Ys'),
    ],
)
def test_s_form_follows_the_regular_english_spelling_rules(
    word: str, s_form_of_word: str
) -> None:
    assert s_form(word) == s_form_of_word


def test_plural_agrees_the_noun_with_its_count() -> None:
    assert [plural(count, 'story') for count in (0, 1, 2)] == [
        '0 stories',
        '1 story',
        '2 stories',
    ]


@pytest.mark.parametrize(
    ('row', 'cells'),
    [
        ('| a | b |', [' a ', ' b ']),
        ('a | b', ['a ', ' b']),
        (r'| a \| b | c |', [r' a \| b ', ' c ']),
        # An escaped backslash still escapes the pipe after it, as GFM splits
        # the row before it reads escapes.
        (r'| a \\| b | c |', [r' a \\| b ', ' c ']),
        (r'| `a\|b` | c |', [r' `a\|b` ', ' c ']),
        ('| | a |', [' ', ' a ']),
        ('|', []),
    ],
)
def test_table_cell_spans_split_a_row_on_its_unescaped_pipes(
    row: str, cells: list[str]
) -> None:
    assert [row[start:end] for start, end in table_cell_spans(row)] == cells


def _strong(*content: PlainSpan | CodeSpan) -> EmphasisSpan:
    return EmphasisSpan(strong=True, content=content)


def _em(*content: PlainSpan | CodeSpan) -> EmphasisSpan:
    return EmphasisSpan(strong=False, content=content)


@pytest.mark.parametrize(
    ('text', 'spans'),
    [
        ('plain', [PlainSpan('plain')]),
        ('', []),
        ('`code`', [CodeSpan('code')]),
        ('**bold**', [_strong(PlainSpan('bold'))]),
        ('*italic*', [_em(PlainSpan('italic'))]),
        (
            'a **b** and *c* and `d`',
            [
                PlainSpan('a '),
                _strong(PlainSpan('b')),
                PlainSpan(' and '),
                _em(PlainSpan('c')),
                PlainSpan(' and '),
                CodeSpan('d'),
            ],
        ),
        ('a*b*c', [PlainSpan('a'), _em(PlainSpan('b')), PlainSpan('c')]),
        # A marker touching a space on its inner side opens or closes nothing.
        ('2 * 3 * 4', [PlainSpan('2 * 3 * 4')]),
        ('** b **', [PlainSpan('** b **')]),
        ('*a *', [PlainSpan('*a *')]),
        # Underscores never format.
        ('__init__, _x_ and snake_case', [PlainSpan('__init__, _x_ and snake_case')]),
        # Code inside bold, and nothing else nests.
        ('**`.l`**', [_strong(CodeSpan('.l'))]),
        ('**a *b* c**', [_strong(PlainSpan('a *b* c'))]),
        ('`a*b*c`', [CodeSpan('a*b*c')]),
        # A code span binds tighter than bold and italic: a marker inside one
        # neither opens nor closes.
        ('*matches `*.py`*', [_em(PlainSpan('matches '), CodeSpan('*.py'))]),
        ('**run `a**b`**', [_strong(PlainSpan('run '), CodeSpan('a**b'))]),
        ('**a`**`', [PlainSpan('**a'), CodeSpan('**')]),
        ('`a**`b**', [CodeSpan('a**'), PlainSpan('b**')]),
        ('*a `b*c` d', [PlainSpan('*a '), CodeSpan('b*c'), PlainSpan(' d')]),
        ('*a `b* c', [_em(PlainSpan('a `b')), PlainSpan(' c')]),
        # Unmatched markers and backslashes are literal.
        ('**open', [PlainSpan('**open')]),
        ('lone ` tick', [PlainSpan('lone ` tick')]),
        ('``', [PlainSpan('``')]),
        # A backtick in a run of them is literal, so no two code spans touch.
        ('`a``b`', [PlainSpan('`a``b`')]),
        ('``a``', [PlainSpan('``a``')]),
        ('\\*a*', [PlainSpan('\\'), _em(PlainSpan('a'))]),
        # A marker is a whole run of asterisks, never part of a longer one.
        ('***a***', [PlainSpan('***a***')]),
        ('**a*', [PlainSpan('**a*')]),
        # A marker that cannot close does not end a span: it is content, and a
        # nearer opener pairs with the closer instead.
        ('*a *b*', [PlainSpan('*a '), _em(PlainSpan('b'))]),
        ('**a **b**', [PlainSpan('**a '), _strong(PlainSpan('b'))]),
        ('*2 * 3*', [_em(PlainSpan('2 * 3'))]),
        # Beside punctuation, a marker opens or closes as CommonMark's
        # flanking rules say.
        ('a**(b)**', [PlainSpan('a**(b)**')]),
        ('**(b)**a', [PlainSpan('**(b)**a')]),
        (
            'a (**b**) **(c)** d',
            [
                PlainSpan('a ('),
                _strong(PlainSpan('b')),
                PlainSpan(') '),
                _strong(PlainSpan('(c)')),
                PlainSpan(' d'),
            ],
        ),
        ('snake**case**', [PlainSpan('snake'), _strong(PlainSpan('case'))]),
        ('Ein **„Zimmer“**', [PlainSpan('Ein '), _strong(PlainSpan('„Zimmer“'))]),
        # A span may cross a line break.
        ('**a\nb**', [_strong(PlainSpan('a\nb'))]),
    ],
)
def test_read_spans_finds_code_bold_and_italic(
    text: str, spans: list[InlineSpan]
) -> None:
    assert read_spans(text) == spans


@pytest.mark.parametrize(
    ('before', 'after', 'spans'),
    [
        ('', '', [_strong(PlainSpan('(b)'))]),
        (' ', '.', [_strong(PlainSpan('(b)'))]),
        ('a', '', [PlainSpan('**(b)**')]),
        ('', 'a', [PlainSpan('**(b)**')]),
        # A neighbour is context only: no span reaches into it.
        ('', '*', [_strong(PlainSpan('(b)'))]),
    ],
)
def test_read_spans_flanks_by_the_text_around_it(
    before: str, after: str, spans: list[InlineSpan]
) -> None:
    assert read_spans('**(b)**', before=before, after=after) == spans


def test_no_span_opens_right_after_a_marker_before_the_text() -> None:
    assert read_spans('`b`', before='`') == [PlainSpan('`b`')]
    assert read_spans('*b*', before='*') == [PlainSpan('*b*')]
    assert read_spans('`a`', after='`') == [CodeSpan('a')]
    assert read_spans('*a*', after='*') == [_em(PlainSpan('a'))]


@pytest.mark.parametrize(
    'text',
    ['*a ' * 20_000, '**a ' * 20_000, '`a ' * 20_000, '*a `b` ' * 20_000],
    ids=['italic', 'bold', 'code', 'italic-over-code'],
)
def test_read_spans_takes_linear_time_over_unclosed_markers(text: str) -> None:
    start = time.perf_counter()
    read_spans(text)
    assert time.perf_counter() - start < 1
