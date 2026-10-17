"""Holds the link scanner to markdown-it-py's own inline links over every
Markdown file the repository tracks: both must find the same links, with the
same destination, the same text once escapes are resolved, and in a table cell
alike."""

import itertools
import subprocess
from pathlib import Path
from urllib.parse import unquote

import pytest
from markdown_it import MarkdownIt
from markdown_it.token import Token

from pytest_given.citations.markdown_links import scan_links
from pytest_given.markdown import fold_whitespace, plain_link_text

_ROOT = Path(__file__).parents[3]
_FIXTURE = 'tests/unit/citations/fixtures/citation-forms.md'
_MARKDOWN = MarkdownIt('commonmark').enable(['table', 'strikethrough'])

# Destination, text, and whether the link sits in a table cell.
type FoundLink = tuple[str, str, bool]


def _documents() -> list[str]:
    listing = subprocess.run(
        ['git', 'ls-files', '-z', '--', '*.md'],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted({name for name in listing.stdout.split('\0') if name} | {_FIXTURE})


@pytest.mark.parametrize('document', _documents())
def test_the_scanner_finds_the_links_markdown_it_finds(document: str) -> None:
    source = (_ROOT / document).read_text(encoding='utf-8')
    parsed, references = _parsed(source)

    def compared(links: list[FoundLink]) -> list[FoundLink]:
        return [link for link in links if link[0] not in references]

    assert compared(_scanned(source)) == compared(parsed)


def _scanned(source: str) -> list[FoundLink]:
    return [
        (
            unquote(link.destination),
            plain_link_text(link.text, in_table_row=link.in_table_row),
            link.in_table_row,
        )
        for link in scan_links(source)
    ]


def _parsed(source: str) -> tuple[list[FoundLink], set[str]]:
    """markdown-it-py's inline links, and the hrefs of reference definitions:
    a reference-style link is a link to markdown-it, never to the scanner."""
    env: dict[str, object] = {}
    links: list[FoundLink] = []
    tokens = _MARKDOWN.parse(source, env)
    for opener, token in itertools.pairwise(tokens):
        if token.type == 'inline':
            in_cell = opener.type in ('th_open', 'td_open')
            links.extend(_inline_links(token.children or [], in_cell))
    references = env.get('references', {})
    assert isinstance(references, dict)
    return links, {unquote(reference['href']) for reference in references.values()}


def _inline_links(children: list[Token], in_cell: bool) -> list[FoundLink]:
    found: list[FoundLink] = []
    stack: list[tuple[bool, str, list[str]]] = []
    for child in children:
        if child.type == 'link_open':
            stack.append((child.markup == 'autolink', str(child.attrGet('href')), []))
        elif child.type == 'link_close':
            autolink, href, parts = stack.pop()
            if not autolink:
                found.append((unquote(href), fold_whitespace(''.join(parts)), in_cell))
        elif stack:
            stack[-1][2].append(_source_text(child))
    return found


def _source_text(child: Token) -> str:
    match child.type:
        case 'code_inline':
            return child.markup + child.content + child.markup
        case 'softbreak' | 'hardbreak':
            return ' '
        case 'image':
            return f'![{child.content}]({child.attrGet("src")})'
        case 'text' | 'html_inline':
            return child.content
        case _:
            return child.markup
