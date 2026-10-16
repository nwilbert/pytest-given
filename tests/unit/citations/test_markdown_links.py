"""Inline links found in a Markdown document, with the source spans an
update rewrites."""

import pytest

from pytest_given.citations.check import _READ_GLYPHS
from pytest_given.citations.markdown_links import MarkdownLink, scan_links

GLYPHS = _READ_GLYPHS


def _one(source: str) -> MarkdownLink:
    links = scan_links(source, GLYPHS)
    assert len(links) == 1, links
    return links[0]


def _glyph(link: MarkdownLink) -> str | None:
    return None if link.glyph is None else link.glyph.text


def _at(source: str, span: tuple[int, int] | None) -> str:
    assert span is not None
    return source[span[0] : span[1]]


def test_a_link_reports_its_text_url_and_spans() -> None:
    source = 'see [the title](https://x.org/r.html#tag=a) here\n'
    link = _one(source)
    assert (link.text, link.url, link.line) == (
        'the title',
        'https://x.org/r.html#tag=a',
        1,
    )
    assert _at(source, link.text_span) == 'the title'
    assert _at(source, link.url_span) == 'https://x.org/r.html#tag=a'
    assert source[link.end :] == ' here\n'
    assert link.trailing == ' here'
    assert link.glyph is None


def test_a_glyph_leading_the_line_is_read() -> None:
    source = '✅ [t](u)\n'
    link = _one(source)
    assert link.glyph is not None
    assert link.glyph.text == _at(source, link.glyph.span) == '✅'


def test_a_variation_selector_is_part_of_the_glyph() -> None:
    glyph = _one('✅\ufe0f [t](u)\n').glyph
    assert glyph is not None
    assert (glyph.text, glyph.bare) == ('✅\ufe0f', '✅')


@pytest.mark.parametrize(
    'source',
    [
        '- ✅ [t](u)\n',
        '> ✅ [t](u)\n',
        '1. 🔵 [t](u)\n',
        'text ❌ [t](u)\n',
        '(✅ [t](u))\n',
    ],
)
def test_a_glyph_after_a_marker_whitespace_or_paren_is_read(source: str) -> None:
    assert _one(source).glyph is not None


def test_a_line_break_between_glyph_and_link_is_whitespace() -> None:
    link = _one('the work is done ✅\n[t](u)\n')
    assert _glyph(link) == '✅'
    assert link.line == 2


def test_a_question_mark_ending_a_sentence_is_no_glyph() -> None:
    assert _one('Is it done? [t](u)\n').glyph is None


@pytest.mark.parametrize('source', ['**✅** [t](u)\n', '✅ *[t](u)*\n', 'x✅ [t](u)\n'])
def test_a_formatted_or_glued_glyph_is_not_read(source: str) -> None:
    assert _one(source).glyph is None


@pytest.mark.parametrize('glyph', ['✓', '✗', '○', '⊗', '?'])
def test_text_glyphs_and_a_typed_question_mark_are_read(glyph: str) -> None:
    assert _glyph(_one(f'{glyph} [](u)\n')) == glyph


def test_link_text_wrapped_in_a_blockquote_leaves_out_the_markers() -> None:
    source = '> ✅ [a long\n> title](u) after\n'
    link = _one(source)
    assert link.text == 'a long\ntitle'
    assert source[link.end - 1 : link.end + 1] == ') '
    assert _at(source, link.text_span) == 'a long\n> title'
    assert link.trailing == ' after'


@pytest.mark.parametrize(
    ('source', 'trailing'),
    [
        ('✅ [t](u)\n(1 ✅) more\nnext\n', '\n(1 ✅) more'),
        ('> ✅ [t](u)\n> (1 ✅)\n> next\n', '\n(1 ✅)'),
        ('- ✅ [t](u)\r\n  (1 ✅)\r\n', '\n(1 ✅)'),
    ],
)
def test_trailing_text_runs_on_across_one_line_break(
    source: str, trailing: str
) -> None:
    link = _one(source)
    assert link.trailing == trailing
    whole = link.trailing_span(0, len(trailing))
    assert source[whole[0] - 1] == ')'
    assert _at(source, whole).endswith(trailing.split('\n')[-1])
    summary = link.trailing_span(trailing.index('('), trailing.index(')') + 1)
    assert _at(source, summary) == '(1 ✅)'


def test_a_citation_in_a_table_cell() -> None:
    link = _one('| Kind | Link |\n|---|---|\n| tag | 🔵 [a](u) (1 ✅) |\n')
    assert link.in_table_row
    assert _glyph(link) == '🔵'
    assert link.trailing == ' (1 ✅) '
    assert link.line == 3


def test_a_table_interrupts_a_paragraph() -> None:
    link = _one('text\n| a | [b](u) |\n|---|---|\n')
    assert link.in_table_row
    assert link.trailing == ' '


def test_a_heading_interrupts_a_paragraph() -> None:
    assert _one('text\n# [b](u)\nmore\n').trailing == ''


def test_a_cell_past_the_header_is_dropped() -> None:
    source = '| a | b |\n|---|---|\n| [x](u) | c | [y](w) |\n'
    assert [link.url for link in scan_links(source)] == ['u']


@pytest.mark.parametrize(
    'source',
    [
        '> ' * 25 + '[t](u)\n',
        ''.join(f'{"  " * depth}- item\n' for depth in range(12))
        + '  ' * 12
        + '[t](u)\n',
    ],
)
def test_a_deeply_nested_link_is_read(source: str) -> None:
    assert _at(source, _one(source).url_span) == 'u'


def test_cells_alike_are_placed_left_to_right() -> None:
    source = '> | [a](u) | [a](u) |\n> |---|---|\n'
    first, second = scan_links(source)
    assert first.url_span < second.url_span
    assert _at(source, second.url_span) == 'u'


def test_an_escaped_pipe_stays_inside_the_cell() -> None:
    source = '| A |\n|---|\n| [a \\| b](u) |\n'
    link = _one(source)
    assert link.text == 'a \\| b'
    assert _at(source, link.url_span) == 'u'


@pytest.mark.parametrize(
    'source',
    [
        '```\n✅ [t](u)\n```\n',
        '~~~markdown\n✅ [t](u)\n~~~\n',
        '    ✅ [t](u)\n',
        '`✅ [t](u)`\n',
        '``a ` [t](u) b``\n',
        '- item\n\n  ```\n  ✅ [t](u)\n  ```\n',
        '<!-- ✅ [t](u) -->\n',
        '<!--\n✅ [t](u)\n-->\n',
        '<details>\n✅ [t](u)\n</details>\n',
        '<script>\n\n✅ [t](u)\n</script>\n',
        '<pre>\n\n✅ [t](u)\n</pre>\n',
    ],
)
def test_code_and_html_blocks_hold_no_links(source: str) -> None:
    assert scan_links(source, GLYPHS) == []


@pytest.mark.parametrize(
    'source', ['- > a [wrapped\n  > text](u)\n', '10. > a [wrapped\n    > text](u)\n']
)
def test_link_text_wrapped_in_a_blockquote_inside_a_list_item(source: str) -> None:
    link = _one(source)
    assert link.text == 'wrapped\ntext'
    assert _at(source, link.url_span) == 'u'


@pytest.mark.parametrize(
    'source', ['para\n    [t](u)\n', '- a\n\n  \tb [t](u)\n', '- a\n  \t[t](u)\n']
)
def test_an_indented_line_is_placed_past_its_indent(source: str) -> None:
    link = _one(source)
    assert _at(source, link.text_span) == 't'
    assert _at(source, link.url_span) == 'u'


@pytest.mark.parametrize(
    'source', ['a\0 [t](u)\r\n', '> | a\0 | [t](u) |\r\n> |---|---|\r\n']
)
def test_a_character_markdown_it_rewrites_keeps_the_spans(source: str) -> None:
    link = _one(source)
    assert _at(source, link.text_span) == 't'
    assert _at(source, link.url_span) == 'u'


@pytest.mark.parametrize(
    'source',
    [
        '![alt](img.png)\n',
        '[label]: https://x.org\n',
        '[ref][label]\n',
        '\\[t](u)\n',
        '[t] (u)\n',
        '[t](u\n',
        '[t](<u)\n',
        '[t](u "unclosed)\n',
        '[t](a( )\n',
        '<https://x.org>\n',
    ],
)
def test_images_references_escapes_and_broken_forms_are_no_links(source: str) -> None:
    assert scan_links(source) == []


def test_a_link_around_an_image_is_read() -> None:
    assert _one('[![badge](img.svg)](https://x.org)\n').url == 'https://x.org'


def test_nested_brackets_and_balanced_parens() -> None:
    link = _one('[a [b] c](https://x.org/a_(b))\n')
    assert (link.text, link.url) == ('a [b] c', 'https://x.org/a_(b)')


def test_an_escaped_paren_stays_inside_the_destination() -> None:
    assert _one('[t](a\\)b)\n').url == 'a\\)b'


@pytest.mark.parametrize(
    'source',
    [
        '[t](<a b.html> "title")\n',
        "[t](<a b.html> 'title')\n",
        '[t](<a b.html> (title))\n',
    ],
)
def test_a_link_with_a_title_and_an_angle_destination(source: str) -> None:
    assert _one(source).url == 'a b.html'


@pytest.mark.parametrize(
    ('url', 'destination'),
    [
        ('a\\_b', 'a_b'),
        ('a&amp;b', 'a&b'),
        ('a&#35;b&#x23;c', 'a#b#c'),
        ('a\\&amp;b', 'a&amp;b'),
        ('a&nosuch;b', 'a&nosuch;b'),
        ('a\\b', 'a\\b'),
    ],
)
def test_the_destination_resolves_escapes_and_entity_references(
    url: str, destination: str
) -> None:
    assert _one(f'[t]({url})\n').destination == destination


@pytest.mark.parametrize('url', ['u#tag=a', 'u\\#tag=a', 'u&#35;tag=a', 'u&num;tag=a'])
def test_the_fragment_span_starts_past_the_hash_as_rendered(url: str) -> None:
    source = f'[t]({url})\n'
    assert _at(source, _one(source).fragment_span) == 'tag=a'


def test_a_link_without_a_fragment_has_no_fragment_span() -> None:
    assert _one('[t](u)\n').fragment_span is None


def test_an_inner_link_deactivates_the_outer_bracket() -> None:
    assert [link.url for link in scan_links('[a [b](u) c](v)\n')] == ['u']


def test_a_code_span_hides_a_closing_bracket() -> None:
    assert _one('[a `]` b](u)\n').text == 'a `]` b'


def test_empty_link_text_is_a_link() -> None:
    source = '? [](u#scenario=x)\n'
    link = _one(source)
    assert link.text == ''
    assert link.text_span[0] == link.text_span[1] == source.index(']')


def test_links_in_headings_setext_and_any_line_break() -> None:
    source = (
        '# [h](u1) #\r\nsetext [s](u2)\r\n---\r\ntext [p](u3)\r***\n## # [x](u4) ##\n'
    )
    links = scan_links(source)
    assert [(link.url, link.line) for link in links] == [
        ('u1', 1),
        ('u2', 2),
        ('u3', 4),
        ('u4', 6),
    ]
    assert all(_at(source, link.url_span) == link.url for link in links)


def test_an_autolink_and_inline_html_hide_brackets() -> None:
    assert scan_links('<a href="[x](y)">z</a> <https://x.org/[a](b)>\n') == []
