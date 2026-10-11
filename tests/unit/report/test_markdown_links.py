"""Inline links found in a Markdown document, with the source spans an
update rewrites."""

import pytest

from pytest_given.report.markdown_links import MarkdownLink, scan_links

GLYPHS = ('✅', '❌', '🟠', '🔵', '❓', '✓', '✗', '○', '⊗', '?')


def _one(source: str) -> MarkdownLink:
    links = scan_links(source, GLYPHS)
    assert len(links) == 1, links
    return links[0]


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
    assert link.glyph == '✅'
    assert _at(source, link.glyph_span) == '✅'


def test_a_variation_selector_is_part_of_the_glyph() -> None:
    assert _one('✅\ufe0f [t](u)\n').glyph == '✅\ufe0f'


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
    assert link.glyph == '✅'
    assert link.line == 2


def test_a_question_mark_ending_a_sentence_is_no_glyph() -> None:
    assert _one('Is it done? [t](u)\n').glyph is None


@pytest.mark.parametrize('source', ['**✅** [t](u)\n', '✅ *[t](u)*\n', 'x✅ [t](u)\n'])
def test_a_formatted_or_glued_glyph_is_not_read(source: str) -> None:
    assert _one(source).glyph is None


@pytest.mark.parametrize('glyph', ['✓', '✗', '○', '⊗', '?'])
def test_text_glyphs_and_a_typed_question_mark_are_read(glyph: str) -> None:
    assert _one(f'{glyph} [](u)\n').glyph == glyph


def test_link_text_wrapped_in_a_blockquote_leaves_out_the_markers() -> None:
    source = '> ✅ [a long\n> title](u) after\n'
    link = _one(source)
    assert link.text == 'a long\ntitle'
    assert link.trailing_span(0, 0) == (link.end, link.end)
    assert _at(source, link.text_span) == 'a long\n> title'
    assert link.trailing == ' after'


@pytest.mark.parametrize(
    ('source', 'trailing'),
    [
        ('✅ [t](u)\n(1 ✅) more\nnext\n', '\n(1 ✅) more'),
        ('> ✅ [t](u)\n> (1 ✅)\n> next\n', '\n(1 ✅)'),
        ('- ✅ [t](u)\r\n  (1 ✅)\r\n', '\n  (1 ✅)'),
    ],
)
def test_trailing_text_runs_on_across_one_line_break(
    source: str, trailing: str
) -> None:
    link = _one(source)
    assert link.trailing == trailing
    whole = link.trailing_span(0, len(trailing))
    assert whole[0] == link.end
    assert _at(source, whole).endswith(trailing.split('\n')[-1])
    summary = link.trailing_span(trailing.index('('), trailing.index(')') + 1)
    assert _at(source, summary) == '(1 ✅)'


def test_a_citation_in_a_table_cell() -> None:
    link = _one('| Kind | Link |\n|---|---|\n| tag | 🔵 [a](u) (1 ✅) |\n')
    assert link.in_table_row
    assert link.glyph == '🔵'
    assert link.trailing == ' (1 ✅) '
    assert link.line == 3


def test_a_table_opens_a_sibling_list_item() -> None:
    assert _one('- a\n- | x | b |\n  |---|---|\n  | [y](v) | c |\n').in_table_row


@pytest.mark.parametrize(
    'source', ['- p\n| [a](u) | b |\n|---|---|\n', '> p\n| [a](u) | b |\n|---|---|\n']
)
def test_a_lazy_line_starts_no_table(source: str) -> None:
    assert not _one(source).in_table_row


def test_an_escaped_pipe_stays_inside_the_cell() -> None:
    assert _one('| A |\n|---|\n| [a \\| b](u) |\n').text == 'a \\| b'


@pytest.mark.parametrize(
    'source',
    [
        '```\n✅ [t](u)\n```\n',
        '~~~markdown\n✅ [t](u)\n~~~\n',
        '    ✅ [t](u)\n',
        '`✅ [t](u)`\n',
        '``a ` [t](u) b``\n',
        '- item\n\n  ```\n  ✅ [t](u)\n  ```\n',
        '- item\n  - nested\n\n        ✅ [t](u)\n',
        '> ```\n> ✅ [t](u)\n> ```\n',
        '<!-- ✅ [t](u) -->\n',
        '<!--\n✅ [t](u)\n-->\n',
        '<details>\n✅ [t](u)\n</details>\n',
        '1. ```\n   ✅ [t](u)\n   ```\n',
        '- ~~~\n  ✅ [t](u)\n  ~~~\n',
        '- - ```\n    ✅ [t](u)\n    ```\n',
        '> - ```\n>   ✅ [t](u)\n>   ```\n',
        '- > ```\n  > ✅ [t](u)\n  > ```\n',
        '- <details>\n  ✅ [t](u)\n  </details>\n',
        '-     ✅ [t](u)\n',
        # A line that starts a block ends the list item it is not indented
        # into, so what follows is no longer read inside the item.
        '- item\n## Head\n\n    ✓ [t](u)\n',
        '- item\n<div>\n\n    ✓ [t](u)\n',
        '- item\n> quote\n\n    ✓ [t](u)\n',
        '- item\n---\n\n    ✓ [t](u)\n',
        '- item\n  ```\n```\n✓ [t](u)\n```\n',
        '> - item\n\n    ✓ [t](u)\n',
    ],
)
def test_code_and_html_blocks_hold_no_links(source: str) -> None:
    assert scan_links(source, GLYPHS) == []


def test_a_fence_opened_on_a_list_marker_line_closes_in_the_item() -> None:
    assert _one('- ```\n  ✅ [t](u)\n  ```\n\n[after](v)\n').url == 'v'


@pytest.mark.parametrize(
    'source',
    [
        '> ```\n> code\n\n[after](v)\n',
        '> > ```\n> > code\n> [after](v)\n',
        '> - ```\n>   code\n>\n> [after](v)\n',
        '- item\n\n  ```\n  code\n\nPara [after](v)\n',
        '- a\n\n  - b\n\n    ```\n    code\n\n  [after](v)\n',
        '- ```\n  code\n- [after](v)\n',
        '- ```\n  [code](u)\n```\n[code](u)\n```\n[after](v)\n',
    ],
)
def test_a_fence_ends_with_its_container(source: str) -> None:
    assert [link.url for link in scan_links(source)] == ['v']


@pytest.mark.parametrize(
    'source',
    ['- item\nlazy\n\n  [t](u)\n', '1. one\n| a | b |\n|---|---|\n\n    [t](u)\n'],
)
def test_a_lazy_line_keeps_the_list_item_open(source: str) -> None:
    assert _one(source).url == 'u'


@pytest.mark.parametrize(
    'source',
    [
        '- a\n-\n    four [l](u)\n',
        '- a\n- \n    four [l](u)\n',
        '- a\n- \n\tTab [l](u)\n',
        '- a\n===\n    four [l](u)\n',
        '> p\n===\n    four [l](u)\n',
    ],
)
def test_a_lazy_line_is_no_setext_underline(
    source: str,
) -> None:
    assert _one(source).url == 'u'


@pytest.mark.parametrize(
    ('source', 'urls'),
    [
        ('p\n2) d\n\n    four [l](u)\n', []),
        ('p\n0. d\n\n    four [l](u)\n', []),
        ('p\n10. > j\n===\n      six [s](s)\n', []),
        ('p\n*\n        eight [e](e)\n', ['e']),
        ('- a\n  2. b\n\n      six [s](s)\n', []),
        ('p\n01. d\n\n     five [l](u)\n', ['u']),
        ('> p\n2) d\n\n    four [l](u)\n', ['u']),
    ],
)
def test_only_a_nonempty_item_from_one_interrupts_a_paragraph(
    source: str, urls: list[str]
) -> None:
    assert [link.url for link in scan_links(source)] == urls


@pytest.mark.parametrize(
    'source',
    [
        '-\n\n    four [l](u)\n',
        '- \n   \n    four [l](u)\n',
        '1. c\n- \n\n    four [l](u)\n',
        '> -\n>\n>     four [l](u)\n',
    ],
)
def test_a_list_item_opened_on_an_empty_line_ends_at_a_blank_line(source: str) -> None:
    assert scan_links(source) == []


@pytest.mark.parametrize(
    ('source', 'urls'),
    [
        ('- item\n>\n    code [x](u)\n', []),
        ('- > h [a](a)\n>\n  ```\n> q [b](b)\n', ['a']),
        ('2) two\n    ```\n>\n\n\tTab [x](u)\n', []),
        ('> - a\n\n>     code [x](u)\n', []),
    ],
)
def test_a_blank_line_outside_a_list_items_quote_ends_the_item(
    source: str, urls: list[str]
) -> None:
    assert [link.url for link in scan_links(source)] == urls


@pytest.mark.parametrize(
    'source', ['> - a\n>\n>     b [x](u)\n', '- > a\n  >\n  > b [x](u)\n']
)
def test_a_blank_line_inside_a_list_items_quote_keeps_the_item(source: str) -> None:
    assert _one(source).url == 'u'


@pytest.mark.parametrize(
    ('source', 'urls'),
    [
        ('- > [a\n> b](u)\n', []),
        ('- > item\n> [quote](v)\n  ```\n[after](w)\n', ['v']),
    ],
)
def test_a_quote_marker_outside_a_list_item_opens_a_new_quote(
    source: str, urls: list[str]
) -> None:
    assert [link.url for link in scan_links(source)] == urls


@pytest.mark.parametrize(
    'source', ['- > a [wrapped\n  > text](u)\n', '10. > a [wrapped\n    > text](u)\n']
)
def test_link_text_wrapped_in_a_blockquote_inside_a_list_item(source: str) -> None:
    assert _one(source).text == 'wrapped\ntext'


def test_an_indented_line_continuing_a_paragraph_is_no_code() -> None:
    assert _one('para\n    [t](u)\n').text == 't'


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


def test_an_inner_link_deactivates_the_outer_bracket() -> None:
    assert [link.url for link in scan_links('[a [b](u) c](v)\n')] == ['u']


def test_a_code_span_hides_a_closing_bracket() -> None:
    assert _one('[a `]` b](u)\n').text == 'a `]` b'


def test_empty_link_text_is_a_link() -> None:
    source = '? [](u#scenario=x)\n'
    link = _one(source)
    assert link.text == ''
    assert link.text_span[0] == link.text_span[1] == source.index(']')


def test_links_in_headings_setext_and_crlf_lines() -> None:
    source = '# [h](u1)\r\nsetext [s](u2)\r\n---\r\ntext [p](u3)\r\n***\r\n'
    links = scan_links(source)
    assert [(link.url, link.line) for link in links] == [
        ('u1', 1),
        ('u2', 2),
        ('u3', 4),
    ]
    assert all(
        source[link.url_span[0] : link.url_span[1]] == link.url for link in links
    )


def test_an_autolink_and_inline_html_hide_brackets() -> None:
    assert scan_links('<a href="[x](y)">z</a> <https://x.org/[a](b)>\n') == []


def test_a_tab_indented_line_is_code() -> None:
    assert scan_links('\t✅ [t](u)\n') == []
