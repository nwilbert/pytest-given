"""The GFM pipe tables in a Markdown document, read into glossary rows.

A table counts where a renderer shows one, and a cell a row leaves out reads
as empty. Column selection accepts a header name (case-insensitive) or a
0-based index. A row's section is the nearest top-level heading above its
table.
"""

import re
from dataclasses import dataclass

from ..markdown import (
    DocumentBlock,
    Heading,
    Paragraph,
    Table,
    document_blocks,
    read_spans,
    span_text,
)
from ..model import PytestGivenError

type ColumnSpec = int | str

# A line starting with a bold span closed right before a colon.
_TERM_LINE = re.compile(r'^\*\*[^*\n].*?\*\*:', re.MULTILINE)


@dataclass(frozen=True)
class GlossaryRow:
    term: str
    definition: str
    kind: str | None
    line: int
    section: str | None = None
    avoid: tuple[str, ...] = ()


def parse_glossary_tables(
    text: str,
    *,
    term_column: ColumnSpec,
    definition_column: ColumnSpec,
    kind_column: ColumnSpec | None,
    avoid_column: ColumnSpec | None,
) -> list[GlossaryRow]:
    rows: list[GlossaryRow] = []
    saw_table = False
    optional = (kind_column, avoid_column)
    specs = (
        term_column,
        definition_column,
        *(spec for spec in optional if spec is not None),
    )
    blocks = document_blocks(text)
    title = title_level(blocks)
    section: str | None = None
    for found in blocks:
        block = found.block
        if isinstance(block, Heading):
            if found.top_level:
                section = heading_section(block, title_level=title, holders=frozenset())
            continue
        if not isinstance(block, Table):
            continue
        header = block.header.contents
        if _addresses_another_table(specs, header):
            continue
        saw_table = True
        term_idx = _resolve_column(term_column, header)
        definition_idx = _resolve_column(definition_column, header)
        kind_idx = (
            _resolve_column(kind_column, header) if kind_column is not None else None
        )
        avoid_idx = (
            _resolve_column(avoid_column, header) if avoid_column is not None else None
        )
        for row in block.rows:
            cells = row.contents
            kind_value = (
                _strip_emphasis(cells[kind_idx]) if kind_idx is not None else ''
            )
            rows.append(
                GlossaryRow(
                    term=_strip_emphasis(cells[term_idx]),
                    definition=cells[definition_idx],
                    kind=kind_value or None,
                    line=row.line,
                    section=section,
                    avoid=tuple(split_avoid(cells[avoid_idx]))
                    if avoid_idx is not None
                    else (),
                )
            )
    if not rows:
        raise PytestGivenError(
            "the glossary file's Markdown table has no data rows."
            if saw_table
            else 'found no Markdown pipe table in the glossary file (a table '
            'needs a header row followed by a |---|---| separator row).'
        )
    return rows


def split_avoid(text: str) -> list[str]:
    """The text split on commas outside parentheses, entries stripped and
    empty ones dropped."""
    entries: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == '(':
            depth += 1
        elif char == ')':
            depth = max(depth - 1, 0)
        elif char == ',' and depth == 0:
            entries.append(text[start:index])
            start = index + 1
    entries.append(text[start:])
    return [entry.strip() for entry in entries if entry.strip()]


def heading_section(
    heading: Heading, *, title_level: int | None, holders: frozenset[str]
) -> str | None:
    """The section a heading names: its text as plain text, or `None` for the
    title, an empty heading and a heading whose lowercased text is in
    `holders`."""
    if heading.level == title_level:
        return None
    name = _strip_emphasis(heading.text)
    if not name or name.lower() in holders:
        return None
    return name


def title_level(blocks: list[DocumentBlock]) -> int | None:
    """1 when exactly one top-level heading has level 1, the file's title."""
    top_titles = [
        found
        for found in blocks
        if found.top_level
        and isinstance(found.block, Heading)
        and found.block.level == 1
    ]
    return 1 if len(top_titles) == 1 else None


def has_tables(text: str) -> bool:
    return any(isinstance(found.block, Table) for found in document_blocks(text))


def has_term_lines(text: str) -> bool:
    return any(
        found.top_level
        and isinstance(found.block, Paragraph)
        and _TERM_LINE.search(found.block.run.text)
        for found in document_blocks(text)
    )


def _strip_emphasis(cell: str) -> str:
    """The cell's text with the reader's spans unwrapped."""
    return ''.join(span_text(span) for span in read_spans(cell)).strip()


def _addresses_another_table(specs: tuple[ColumnSpec, ...], header: list[str]) -> bool:
    """Whether *header* belongs to a table this spec is not about.

    Only decidable when every column is named and none of the names is there:
    then the table is somebody else's, which is what lets a glossary file hold
    prose tables beside the glossary. Resolving *some* of the names is a real
    glossary table with a wrong column, and an index spec addresses any table
    at all — both still raise.
    """
    named = [spec for spec in specs if isinstance(spec, str)]
    if len(named) != len(specs):
        return False
    lowered = {cell.lower() for cell in header}
    return not any(name.lower() in lowered for name in named)


def _resolve_column(spec: ColumnSpec, header: list[str]) -> int:
    if isinstance(spec, int):
        if 0 <= spec < len(header):
            return spec
        raise PytestGivenError(
            f'column index {spec} is out of range for a table with '
            f'{len(header)} column(s): {header!r}.'
        )
    lowered = [cell.lower() for cell in header]
    try:
        return lowered.index(spec.lower())
    except ValueError:
        raise PytestGivenError(
            f'column {spec!r} not found in table header {header!r}.'
        ) from None
