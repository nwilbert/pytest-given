"""The Markdown writer: text written so a Markdown viewer shows what the HTML
report shows, and a citation's link text read back as the title it renders."""

import pytest
from markdown_it import MarkdownIt

from pytest_given.model import (
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    TermId,
    narration_of,
    param_id,
)
from pytest_given.report.inline_markdown import render_spans
from pytest_given.report.link_text import (
    fold_whitespace,
    link_text,
    literal_markdown,
    narration_markdown,
    plain_link_text,
    spans_markdown,
)

_MARKDOWN = MarkdownIt('commonmark').enable(['table', 'strikethrough'])


@pytest.mark.parametrize(
    ('text', 'written'),
    [
        ('a [b] c', 'a \\[b\\] c'),
        ('[text](url)', '\\[text\\](url)'),
        ('2 * 3', '2 \\* 3'),
        ('**x**', '\\*\\*x\\*\\*'),
        ('~~gone~~', '\\~\\~gone\\~\\~'),
        ('<title> tag', '\\<title> tag'),
        ('a<br>b', 'a\\<br>b'),
        ('&amp;', '\\&amp;'),
        ('a | b', 'a \\| b'),
        ('$x$', '\\$x\\$'),
        ('back\\slash', 'back\\\\slash'),
        ('_lead and trail_', '\\_lead and trail\\_'),
        ('__init__', '\\_\\_init\\_\\_'),
        ('snake_case and 2_3', 'snake_case and 2_3'),
        ('a `--given-md` flag', 'a \\`--given-md\\` flag'),
        ('two\nlines', 'two\nlines'),
    ],
)
def test_literal_markdown_escapes_every_inline_marker(text: str, written: str) -> None:
    assert literal_markdown(text) == written


@pytest.mark.parametrize(
    ('text', 'written'),
    [
        ('Books a **suite**', 'Books a **suite**'),
        ('a `x*y` and *z*', 'a `x*y` and *z*'),
        ('**`.l`**', '**`.l`**'),
        ('2 * 3 * 4', '2 \\* 3 \\* 4'),
        ('__init__ runs', '\\_\\_init\\_\\_ runs'),
        ('**a [b] | c**', '**a \\[b\\] \\| c**'),
        ('one ` tick', 'one \\` tick'),
        ('***a***', '\\***a**\\*'),
    ],
)
def test_spans_markdown_keeps_the_spans_the_report_renders(
    text: str, written: str
) -> None:
    assert spans_markdown(text) == written


def test_a_pipe_in_a_code_span_is_escaped_only_in_a_table_row() -> None:
    assert spans_markdown('the `a|b` form') == 'the `a|b` form'
    assert spans_markdown('the `a|b` form', in_table_row=True) == 'the `a\\|b` form'


@pytest.mark.parametrize(
    'text',
    [
        'Books a **suite**',
        '2 * 3 * 4',
        '__init__ and _x_ and snake_case',
        '**`.l`** and `a*b*c`',
        'a*b*c',
        '***a***',
        '**a*',
        '**open and *close',
        'lone ` tick and ``',
        'back\\slash *a*',
        '1 < 2 & [x](y)',
        '<br> stays',
        '**a `b|c` d**',
        '*a `b*c` d*',
        '`a**`b**',
        '**a`**`',
        'x ~~y~~ $z$ <https://example.org>',
    ],
)
def test_a_markdown_viewer_renders_the_spans_the_report_does(text: str) -> None:
    rendered = _MARKDOWN.render(spans_markdown(text))
    assert rendered == f'<p>{render_spans(text)}</p>\n'


def test_a_narration_reads_spans_only_within_one_literal() -> None:
    narration = Narration(
        text='**Guest books** a *suite*',
        parts=(
            NarrationLiteral(value='**'),
            NarrationTermRef(term_id=TermId('guest'), display='Guest'),
            NarrationLiteral(value=' books** a *suite*'),
        ),
    )
    assert narration_markdown(narration) == '\\*\\*Guest books\\*\\* a *suite*'


def test_a_narration_writes_values_placeholders_and_term_refs_literally() -> None:
    narration = Narration(
        text='a *b* {c} d_',
        parts=(
            NarrationLiteral(value='a '),
            NarrationValue(rendered='*b*', expression='b'),
            NarrationLiteral(value=' '),
            NarrationPlaceholder(name='c', column_id=param_id('c')),
            NarrationLiteral(value=' '),
            NarrationTermRef(term_id=TermId('d'), display='d_'),
        ),
    )
    written = narration_markdown(narration, term_ref=lambda display: f'«{display}»')
    assert written == 'a \\*b\\* {c} «d\\_»'


def test_a_narration_reads_on_one_line() -> None:
    parts_less = Narration(text='act **one**\nact two')
    with_parts = Narration(
        text='a\nb\r\nc',
        parts=(
            NarrationLiteral(value='a\n'),
            NarrationValue(rendered='b\r\nc', expression='b'),
        ),
    )
    assert narration_markdown(parts_less) == 'act **one** act two'
    assert narration_markdown(with_parts) == 'a b c'


def test_a_tag_or_story_title_is_link_text_written_literally() -> None:
    assert link_text('spec/**x**') == 'spec/\\*\\*x\\*\\*'


def test_a_scenario_title_is_link_text_with_its_spans() -> None:
    assert link_text(Narration(text='Books a **suite**')) == 'Books a **suite**'


_TITLES = [
    'One xfailed case makes its parametrized scenario an expected failure',
    'a [b] *c* ~d~ <e> &f; |g| $h$ _i_ j_k \\ ` `code|x` ``',
    'Rendering {price} for a guest',
    'multi\nline\r\ntitle',
    '**`.l`** and __init__ and ***a***',
]

_NARRATIONS: list[tuple[NarrationPart, ...]] = [
    (
        NarrationLiteral(value='**'),
        NarrationTermRef(term_id=TermId('guest'), display='Guest'),
        NarrationLiteral(value=' books**'),
    ),
    (
        NarrationLiteral(value='Split *a* '),
        NarrationValue(rendered='[a*b`|c]', expression=''),
    ),
]


@pytest.mark.parametrize(
    'title',
    [
        *_TITLES,
        *(Narration(text=title) for title in _TITLES),
        *(narration_of(parts) for parts in _NARRATIONS),
    ],
)
@pytest.mark.parametrize('in_table_row', [False, True])
def test_written_text_reads_back_as_the_title(
    title: Narration | str, in_table_row: bool
) -> None:
    written = link_text(title, in_table_row=in_table_row)
    text = title if isinstance(title, str) else title.text
    assert plain_link_text(written, in_table_row=in_table_row) == fold_whitespace(text)


def test_a_hand_written_text_without_escapes_reads_as_the_title() -> None:
    assert plain_link_text('snake_case & friends') == 'snake_case & friends'


def test_an_unpaired_backtick_reads_literally() -> None:
    assert plain_link_text('one ` tick') == 'one ` tick'


def test_text_wrapped_across_lines_folds_to_one() -> None:
    assert plain_link_text('a long\n   title') == 'a long title'
