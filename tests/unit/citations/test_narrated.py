import pytest

from pytest_given.citations.narrated import (
    LooseDetails,
    NarratedCitation,
    scan_narrated,
)

GLYPHS = ['✅', '❓']
SUMMARY = '<summary>✅ <a href="r.html#scenario=t::a">Title</a></summary>'


def _only_citation(source: str) -> NarratedCitation:
    [found] = scan_narrated(source, GLYPHS)
    assert isinstance(found, NarratedCitation)
    return found


def _slice(source: str, span: tuple[int, int]) -> str:
    return source[span[0] : span[1]]


def _loose(source: str) -> list[tuple[int, str, str]]:
    found = scan_narrated(source, GLYPHS)
    assert all(isinstance(each, LooseDetails) for each in found)
    return [
        (each.line, each.href, each.reason)
        for each in found
        if isinstance(each, LooseDetails)
    ]


def _reason(source: str) -> str:
    [(_, _, reason)] = _loose(source)
    return reason


def test_a_narrated_citation_is_read_in_parts_each_placed_in_the_source() -> None:
    source = f'intro\n\n<details markdown="1">\n{SUMMARY}\n\nNarration.\n\n</details>\n'
    found = _only_citation(source)
    assert found.line == 4
    assert found.glyph.text == '✅'
    assert _slice(source, found.glyph.span) == '✅'
    assert found.opening_tag == '<details markdown="1">'
    assert _slice(source, found.opening_tag_span) == found.opening_tag
    assert found.href == 'r.html#scenario=t::a'
    assert _slice(source, found.href_span) == found.href
    assert found.text == 'Title'
    assert _slice(source, found.text_span) == 'Title'
    assert found.body == '\nNarration.\n'
    assert _slice(source, found.body_span) == '\nNarration.\n\n'
    assert found.prefix == ''
    assert found.markdown == '1'
    assert _slice(found.opening_tag, found.markdown_attribute) == ' markdown="1"'
    assert found.destination == found.href
    assert found.fragment_span is not None
    assert _slice(source, found.fragment_span) == 'scenario=t::a'


def test_whitespace_and_line_breaks_between_the_tags_are_one_space() -> None:
    source = (
        '<details markdown="1">\n<summary>\n  ✅️\n  <a href="u#x">A\nB</a>\n'
        '</summary>\n\nbody\n\n</details>\n'
    )
    found = _only_citation(source)
    assert found.glyph.text == '✅️'
    assert found.text == 'A\nB'
    assert _slice(source, found.text_span) == 'A\nB'


def test_a_copied_block_with_one_blank_line_has_an_empty_body() -> None:
    source = f'<details>\n{SUMMARY}\n\n</details>\n'
    found = _only_citation(source)
    assert found.body == ''
    assert _slice(source, found.body_span) == '\n'


def test_a_block_holding_its_own_closing_tag_has_an_empty_zero_width_body() -> None:
    source = f'<details>\n{SUMMARY}\n</details>\n'
    found = _only_citation(source)
    assert found.body == ''
    start = source.index('</details>')
    assert found.body_span == (start, start)


def test_a_closing_tag_on_the_summarys_line_is_loose() -> None:
    source = f'<details>\n{SUMMARY}</details>\n'
    assert _loose(source) == [
        (2, 'r.html#scenario=t::a', 'its </details> is not on a line of its own')
    ]


def test_text_after_a_closing_tag_is_loose() -> None:
    held = f'<details>\n{SUMMARY}\n</details> more\n'
    assert _reason(held) == 'text follows its </details>'
    closing = f'<details>\n{SUMMARY}\n\nbody\n\n</details> more\n'
    assert _reason(closing) == 'text follows its </details>'


def test_html_after_the_summary_with_no_blank_line_is_loose() -> None:
    source = f'<details>\n{SUMMARY}\n<p>x</p>\n\n</details>\n'
    assert _reason(source) == 'a blank line must follow its </summary>'
    held = f'<details>\n{SUMMARY}\n</details>\n<p>x</p>\n'
    assert _reason(held) == 'a blank line must follow its </details>'
    before_another = f'<details>\n{SUMMARY}\n<details>\n{SUMMARY}\n\n</details>\n'
    assert [reason for _, _, reason in _loose(before_another)] == [
        'a blank line must follow its </summary>',
        BURIED,
    ]


def test_a_closing_tag_in_a_fenced_body_block_is_body() -> None:
    source = f'<details>\n{SUMMARY}\n\n```\n</details>\n```\n\n</details>\n'
    found = _only_citation(source)
    assert found.body == '\n```\n</details>\n```\n'


def test_an_unclosed_block_is_loose() -> None:
    source = f'<details>\n{SUMMARY}\n\ntext\n'
    assert _loose(source) == [(2, 'r.html#scenario=t::a', 'no </details> closes it')]


def test_two_in_a_row_leave_the_first_unclosed() -> None:
    source = f'<details>\n{SUMMARY}\n\ntext\n\n<details>\n{SUMMARY}\n\n</details>\n'
    first, second = scan_narrated(source, GLYPHS)
    assert isinstance(first, LooseDetails)
    assert first.reason == 'no </details> closes it'
    assert isinstance(second, NarratedCitation)


BURIED = 'a blank line must separate it from the HTML above it'


def test_a_details_line_inside_a_larger_html_block_is_loose() -> None:
    copied = f'<details markdown="1">\n{SUMMARY}\n\n</details>\n'
    first, second = scan_narrated(copied + copied, GLYPHS)
    assert isinstance(first, NarratedCitation)
    assert first.body == ''
    assert isinstance(second, LooseDetails)
    assert (second.line, second.reason) == (6, BURIED)


def test_the_first_of_two_blocks_holding_their_closing_tags_is_read() -> None:
    held = f'<details markdown="1">\n{SUMMARY}\n</details>\n'
    first, second = scan_narrated(held + held, GLYPHS)
    assert isinstance(first, NarratedCitation)
    assert isinstance(second, LooseDetails)
    assert (second.line, second.reason) == (5, BURIED)


def test_a_details_line_buried_under_other_html_is_loose() -> None:
    source = f'<div>\n<details>\n<p>x</p>\n{SUMMARY}\n\n</details>\n'
    assert _loose(source) == [(4, 'r.html#scenario=t::a', BURIED)]


def test_a_details_line_above_a_buried_citation_is_one_finding() -> None:
    source = f'<details>\n<details>{SUMMARY}\n\n</details>\n'
    assert _loose(source) == [(2, 'r.html#scenario=t::a', BURIED)]


def test_a_summary_cut_off_from_its_details_is_loose() -> None:
    reason = (
        'its <summary> is separated from <details> by a blank line or a list '
        "item's or quote's edge"
    )
    blank_line = f'<details markdown="1">\n\n{SUMMARY}\n\nbody\n\n</details>\n'
    assert _loose(blank_line) == [(3, 'r.html#scenario=t::a', reason)]
    unindented = f'- <details markdown="1">\n{SUMMARY}\n\n  body\n\n  </details>\n'
    assert _loose(unindented) == [(2, 'r.html#scenario=t::a', reason)]


def test_a_details_line_after_a_prettier_ignore_comment_is_loose() -> None:
    wrapped = (
        '<!-- prettier-ignore-start -->\n'
        f'<details markdown="1">\n{SUMMARY}\n\n</details>\n'
        '<!-- prettier-ignore-end -->\n'
    )
    first, second = scan_narrated(wrapped + wrapped, GLYPHS)
    assert isinstance(first, NarratedCitation)
    assert first.body == ''
    assert isinstance(second, LooseDetails)
    assert (second.line, second.reason) == (9, BURIED)


def test_an_authors_details_line_inside_a_larger_html_block_is_ignored() -> None:
    source = (
        f'<details>\n{SUMMARY}\n\n</details>\n'
        '<details>\n<summary>Notes</summary>\n\n</details>\n'
        '<details>\n<summary>✅ no link</summary>\n\n</details>\n'
    )
    assert len(scan_narrated(source, GLYPHS)) == 1


def test_an_anchor_with_other_attributes_is_loose() -> None:
    source = (
        '<details>\n<summary>✅ <a class="x" href="u#s">T</a></summary>\n\n</details>\n'
    )
    assert _loose(source) == [(2, 'u#s', 'its <a> takes attributes besides href')]


def test_a_single_quoted_href_is_loose() -> None:
    source = "<details>\n<summary>✅ <a href='u#s'>T</a></summary>\n\n</details>\n"
    assert _loose(source) == [(2, 'u#s', 'its href is not in double quotes')]


def test_text_after_the_anchor_is_loose() -> None:
    source = '<details>\n<summary>✅ <a href="u#s">T</a> more</summary>\n\n</details>\n'
    assert _reason(source) == 'text follows </a>'
    upper = '<details>\n<summary>✅ <a href="u#s">T</A> more</summary>\n\n</details>\n'
    assert _reason(upper) == 'text follows </a>'
    unclosed = '<details>\n<summary>✅ <a href="u#s">T</a> more\n\n</details>\n'
    assert _reason(unclosed) == 'text follows </a>'


def test_an_authors_details_is_ignored() -> None:
    source = '<details><summary>Notes</summary>\n\nx\n\n</details>\n'
    assert scan_narrated(source, GLYPHS) == []
    source = '<details>\n<summary>✅ no link</summary>\n\n</details>\n'
    assert scan_narrated(source, GLYPHS) == []


def test_a_list_item_prefix_is_read_off_the_body() -> None:
    source = f'- <details>\n  {SUMMARY}\n\n  text\n\n  </details>\n'
    found = _only_citation(source)
    assert found.prefix == '  '
    assert found.body == '\ntext\n'
    assert found.body_span == (
        source.index('\n\n  text') + 1,
        source.index('  </details>'),
    )


def test_a_blockquote_prefix_is_read_off_the_body_and_blank_lines_read_empty() -> None:
    source = f'> <details>\n> {SUMMARY}\n>\n> text\n>\n> </details>\n'
    found = _only_citation(source)
    assert found.prefix == '> '
    assert found.body == '\ntext\n'


def test_crlf_reads_as_lf() -> None:
    source = f'<details>\r\n{SUMMARY}\r\n\r\ntext\r\n\r\n</details>\r\n'
    assert _only_citation(source).body == '\ntext\n'


def test_the_destination_resolves_character_references() -> None:
    source = (
        '<details>\n<summary>✅ <a href="u?a=1&amp;b=2&#35;s">T</a></summary>\n'
        '\n</details>\n'
    )
    found = _only_citation(source)
    assert found.destination == 'u?a=1&b=2#s'
    assert found.fragment_span is not None
    assert _slice(source, found.fragment_span) == 's'


def test_a_destination_without_a_fragment_has_no_fragment_span() -> None:
    source = '<details>\n<summary>✅ <a href="u.html">T</a></summary>\n\n</details>\n'
    assert _only_citation(source).fragment_span is None


@pytest.mark.parametrize(
    'summary',
    [
        '<summary>✅ <a href="u#s">T</summary>',
        '<summary class="x">✅ <a href="u#s">T</a></summary>',
        '<summary>✅ <a href="u#s">T</a>',
        '<summary>✅ <a href="u#s">T</a></summary> more',
    ],
)
def test_a_summary_in_no_other_shape_is_loose_for_it(summary: str) -> None:
    source = f'<details>\n{summary}\n\n</details>\n'
    assert _reason(source) == 'its summary is not the glyph, a space and the link alone'


def test_a_closing_tag_in_another_container_does_not_close_it() -> None:
    source = f'<details>\n{SUMMARY}\n\n> </details>\n\n</details>\n'
    assert _only_citation(source).body == '\n> </details>\n'


def test_the_markdown_attribute_is_read_among_the_others() -> None:
    def opening(tag: str) -> NarratedCitation:
        return _only_citation(f'{tag}\n{SUMMARY}\n\n</details>\n')

    quoted = opening('<details title="see markdown here" open>')
    assert quoted.markdown is None
    assert quoted.markdown_attribute == (len('<details'), len('<details'))
    single = opening("<details open MARKDOWN='1'>")
    assert single.markdown == '1'
    assert _slice(single.opening_tag, single.markdown_attribute) == " MARKDOWN='1'"
    assert opening('<details markdown>').markdown == ''
