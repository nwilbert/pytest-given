"""The Markdown writer: text written so a Markdown viewer shows what the HTML
report shows."""

import pytest
from markdown_it import MarkdownIt

from pytest_given.model import (
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    TermId,
    param_id,
)
from pytest_given.report.html_renderer import _make_narration_filter
from pytest_given.report.markdown_writer import (
    code_span_markdown,
    literal_markdown,
    narration_markdown,
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
        ('***a***', '\\*\\*\\*a\\*\\*\\*'),
    ],
)
def test_a_plain_string_keeps_the_spans_the_report_renders(
    text: str, written: str
) -> None:
    assert narration_markdown(Narration(text=text)) == written


def test_a_pipe_in_a_code_span_is_escaped_only_in_a_table_row() -> None:
    narration = Narration(text='the `a|b` form')
    assert narration_markdown(narration) == 'the `a|b` form'
    assert narration_markdown(narration, in_table_row=True) == 'the `a\\|b` form'


@pytest.mark.parametrize(
    ('content', 'written'),
    [('a|b', '`a|b`'), (' x ', '`  x  `'), ('  ', '`  `')],
)
def test_a_code_span_shows_its_content_as_written(content: str, written: str) -> None:
    assert code_span_markdown(content) == written
    assert _MARKDOWN.renderInline(written) == f'<code>{content}</code>'


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
        'a**(b)** and (**c**) x**.y** and **(d)**e',
        '*a *b* and *2 * 3* and **a **b** and **c ** d**',
        'snake**case** and **x.** and **a*b**',
        '***a*** and **a* and *a**',
        '*matches `*.py`* and **run `a**b`**',
        '`a``b` and ``c``',
    ],
)
def test_a_markdown_viewer_renders_the_spans_the_report_does(text: str) -> None:
    narration = Narration(text=text)
    rendered = _MARKDOWN.render(narration_markdown(narration))
    html = _make_narration_filter(param_color_map={}, glossary=None)(narration)
    assert rendered == f'<p>{html}</p>\n'


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


def test_a_marker_at_a_literal_s_edge_flanks_by_the_part_beside_it() -> None:
    narration = Narration(
        text='a**(b)** and (c)**(d)**',
        parts=(
            NarrationValue(rendered='a', expression='a'),
            NarrationLiteral(value='**(b)** and '),
            NarrationValue(rendered='(c)', expression='c'),
            NarrationLiteral(value='**(d)**'),
        ),
    )
    written = narration_markdown(narration)
    assert written == 'a\\*\\*(b)\\*\\* and (c)**(d)**'
    assert _MARKDOWN.renderInline(written) == 'a**(b)** and (c)<strong>(d)</strong>'


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


@pytest.mark.parametrize(
    ('marker', 'written'), [('`', '`a`\\`b\\`'), ('*', '*a*\\*b\\*')]
)
def test_no_two_spans_touch_across_an_empty_value(marker: str, written: str) -> None:
    narration = Narration(
        text=f'{marker}a{marker}{marker}b{marker}',
        parts=(
            NarrationLiteral(value=f'{marker}a{marker}'),
            NarrationValue(rendered='', expression='nothing'),
            NarrationLiteral(value=f'{marker}b{marker}'),
        ),
    )
    html = _make_narration_filter(param_color_map={}, glossary=None)(narration)
    assert narration_markdown(narration) == written
    assert _MARKDOWN.renderInline(written) == html.replace(
        '<span class="value-highlight"></span>', ''
    )


def test_an_underscore_between_a_value_and_a_literal_is_intraword() -> None:
    narration = Narration(
        text='foo_suffix and _x',
        parts=(
            NarrationValue(rendered='foo', expression='name'),
            NarrationLiteral(value='_suffix and '),
            NarrationTermRef(term_id=TermId('t'), display='T'),
            NarrationLiteral(value='_x'),
        ),
    )
    assert narration_markdown(narration) == 'foo_suffix and T\\_x'


def test_literal_markdown_reads_an_edge_underscore_against_its_neighbours() -> None:
    assert literal_markdown('_b_', before='a', after='c') == '_b_'
    assert literal_markdown('_b_', before='.', after=' ') == '\\_b\\_'
