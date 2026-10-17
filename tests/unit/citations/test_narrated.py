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
    assert scan_narrated(source, GLYPHS) == [
        LooseDetails(
            line=2,
            href='r.html#scenario=t::a',
            reason='its </details> is not on a line of its own',
        )
    ]


def test_a_closing_tag_in_a_fenced_body_block_is_body() -> None:
    source = f'<details>\n{SUMMARY}\n\n```\n</details>\n```\n\n</details>\n'
    found = _only_citation(source)
    assert found.body == '\n```\n</details>\n```\n'


def test_an_unclosed_block_is_loose() -> None:
    source = f'<details>\n{SUMMARY}\n\ntext\n'
    assert scan_narrated(source, GLYPHS) == [
        LooseDetails(
            line=2, href='r.html#scenario=t::a', reason='no </details> closes it'
        )
    ]


def test_two_in_a_row_leave_the_first_unclosed() -> None:
    source = f'<details>\n{SUMMARY}\n\ntext\n\n<details>\n{SUMMARY}\n\n</details>\n'
    first, second = scan_narrated(source, GLYPHS)
    assert isinstance(first, LooseDetails)
    assert first.reason == 'no </details> closes it'
    assert isinstance(second, NarratedCitation)


BURIED = LooseDetails(
    line=6,
    href='r.html#scenario=t::a',
    reason='a blank line must separate it from the HTML above it',
)


def test_a_details_line_inside_a_larger_html_block_is_loose() -> None:
    copied = f'<details markdown="1">\n{SUMMARY}\n\n</details>\n'
    first, second = scan_narrated(copied + copied, GLYPHS)
    assert isinstance(first, NarratedCitation)
    assert first.body == ''
    assert second == BURIED


def test_a_details_line_after_a_prettier_ignore_comment_is_loose() -> None:
    wrapped = (
        '<!-- prettier-ignore-start -->\n'
        f'<details markdown="1">\n{SUMMARY}\n\n</details>\n'
        '<!-- prettier-ignore-end -->\n'
    )
    first, second = scan_narrated(wrapped + wrapped, GLYPHS)
    assert isinstance(first, NarratedCitation)
    assert first.body == ''
    assert second == LooseDetails(line=9, href=BURIED.href, reason=BURIED.reason)


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
    [found] = scan_narrated(source, GLYPHS)
    assert found == LooseDetails(
        line=2, href='u#s', reason='its <a> takes attributes besides href'
    )


def test_text_after_the_anchor_is_loose() -> None:
    source = '<details>\n<summary>✅ <a href="u#s">T</a> more</summary>\n\n</details>\n'
    [found] = scan_narrated(source, GLYPHS)
    assert isinstance(found, LooseDetails)
    assert found.reason == 'text follows </a>'


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


def test_an_anchor_never_closed_is_loose() -> None:
    source = '<details>\n<summary>✅ <a href="u#s">T</summary>\n\n</details>\n'
    [found] = scan_narrated(source, GLYPHS)
    assert isinstance(found, LooseDetails)
    assert found.reason == 'its summary is not the glyph, a space and the link alone'


def test_a_closing_tag_in_another_container_does_not_close_it() -> None:
    source = f'<details>\n{SUMMARY}\n\n> </details>\n\n</details>\n'
    assert _only_citation(source).body == '\n> </details>\n'
