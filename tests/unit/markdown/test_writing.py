import pytest
from markdown_it import MarkdownIt

from pytest_given.markdown import code_span_markdown, literal_markdown

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
    ('content', 'written'),
    [('a|b', '`a|b`'), (' x ', '`  x  `'), ('  ', '`  `')],
)
def test_a_code_span_shows_its_content_as_written(content: str, written: str) -> None:
    assert code_span_markdown(content) == written
    assert _MARKDOWN.renderInline(written) == f'<code>{content}</code>'


def test_literal_markdown_reads_an_edge_underscore_against_its_neighbours() -> None:
    assert literal_markdown('_b_', before='a', after='c') == '_b_'
    assert literal_markdown('_b_', before='.', after=' ') == '\\_b\\_'
