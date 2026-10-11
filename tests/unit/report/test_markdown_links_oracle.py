"""Holds the hand-written link scanner to markdown-it-py over every Markdown
file the repository tracks: both must find the same inline links, with the
same destination and the same text once escapes are resolved."""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

import pytest
from markdown_it import MarkdownIt
from markdown_it.token import Token

from pytest_given.report.link_text import fold_whitespace, plain_link_text
from pytest_given.report.markdown_links import scan_links

_ROOT = Path(__file__).parents[3]
_FIXTURE = 'tests/unit/report/fixtures/citation-forms.md'
_MARKDOWN = MarkdownIt('commonmark').enable(['table', 'strikethrough'])
_URL_ESCAPE = re.compile(r'\\([!-/:-@\[-`{-~])')

type FoundLink = tuple[str, str]

# Constructs the scanner deliberately reads differently, by file: the links
# to leave out of both sides, each with the reason in a comment.
KNOWN_DIFFERENCES: dict[str, list[FoundLink]] = {
    _FIXTURE: [
        # markdown-it continues a quote at a `>` indented 4 columns; CommonMark
        # reads indented code, as the scanner does.
        ('https://example.org/edge/12', 'Indented quote marker'),
        # markdown-it ends a nested quote's paragraph at an indented fence
        # opener; CommonMark continues it lazily, as the scanner does.
        ('https://example.org/edge/13', 'Indented fence opener'),
    ]
}


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
    ignored = set(KNOWN_DIFFERENCES.get(document, []))

    def compared(links: list[FoundLink]) -> list[FoundLink]:
        return [
            link for link in links if link[0] not in references and link not in ignored
        ]

    assert compared(_scanned(source)) == compared(parsed)


def _scanned(source: str) -> list[FoundLink]:
    return [
        (
            unquote(_URL_ESCAPE.sub(r'\1', link.url)),
            plain_link_text(link.text, in_table_row=link.in_table_row),
        )
        for link in scan_links(source)
    ]


def _parsed(source: str) -> tuple[list[FoundLink], set[str]]:
    """markdown-it-py's inline links, and the hrefs of reference definitions:
    a reference-style link is a link to markdown-it, never to the scanner."""
    env: dict[str, object] = {}
    links: list[FoundLink] = []
    for token in _MARKDOWN.parse(source, env):
        if token.type == 'inline':
            links.extend(_inline_links(token.children or []))
    references = env.get('references', {})
    assert isinstance(references, dict)
    return links, {unquote(reference['href']) for reference in references.values()}


def _inline_links(children: list[Token]) -> list[FoundLink]:
    found: list[FoundLink] = []
    stack: list[tuple[bool, str, list[str]]] = []
    for child in children:
        if child.type == 'link_open':
            stack.append((child.markup == 'autolink', str(child.attrGet('href')), []))
        elif child.type == 'link_close':
            autolink, href, parts = stack.pop()
            if not autolink:
                found.append((unquote(href), fold_whitespace(''.join(parts))))
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
