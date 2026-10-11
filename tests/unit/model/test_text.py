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
        # The first span to close wins.
        ('**a`**`', [_strong(PlainSpan('a`')), PlainSpan('`')]),
        ('`a**`b**', [CodeSpan('a**'), PlainSpan('b**')]),
        # Unmatched markers and backslashes are literal.
        ('**open', [PlainSpan('**open')]),
        ('lone ` tick', [PlainSpan('lone ` tick')]),
        ('``', [PlainSpan('``')]),
        ('\\*a*', [PlainSpan('\\'), _em(PlainSpan('a'))]),
        ('***a***', [PlainSpan('*'), _strong(PlainSpan('a')), PlainSpan('*')]),
        ('**a*', [PlainSpan('*'), _em(PlainSpan('a'))]),
        # A span may cross a line break.
        ('**a\nb**', [_strong(PlainSpan('a\nb'))]),
    ],
)
def test_read_spans_finds_code_bold_and_italic(
    text: str, spans: list[InlineSpan]
) -> None:
    assert read_spans(text) == spans
