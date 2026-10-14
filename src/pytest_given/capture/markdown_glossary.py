"""Minimal GFM pipe-table parser for file-backed glossaries.

Parses every pipe table in a Markdown document into GlossaryRow records.
Not a full CommonMark parser — it recognizes pipe tables, honors `\\|`
escapes, and skips fenced code blocks. Column selection accepts a header
name (case-insensitive) or a 0-based index.
"""

import re
from dataclasses import dataclass

from ..model import (
    CodeSpan,
    EmphasisSpan,
    InlineSpan,
    PlainSpan,
    PytestGivenError,
    read_spans,
    table_cell_spans,
)

type ColumnSpec = int | str

_SEPARATOR_CELL = re.compile(r'^:?-+:?$')
_FENCE = re.compile(r'^\s*(```|~~~)')


@dataclass(frozen=True)
class GlossaryRow:
    term: str
    definition: str
    kind: str | None
    line: int


def parse_glossary_tables(
    text: str,
    *,
    term_column: ColumnSpec,
    definition_column: ColumnSpec,
    kind_column: ColumnSpec | None,
) -> list[GlossaryRow]:
    rows: list[GlossaryRow] = []
    saw_table = False
    lines = text.splitlines()
    in_code = False
    index = 0
    specs = (term_column, definition_column) + (
        () if kind_column is None else (kind_column,)
    )
    while index < len(lines):
        line = lines[index]
        if _FENCE.match(line):
            in_code = not in_code
            index += 1
            continue
        if in_code or not _is_table_row(line):
            index += 1
            continue
        if index + 1 >= len(lines) or not _is_separator_row(lines[index + 1]):
            index += 1
            continue
        header = _split_row(line)
        if _addresses_another_table(specs, header):
            # A table this spec cannot address at all is somebody else's — a
            # glossary file is a document, and named columns are what lets one
            # hold prose tables beside the glossary. An index spec cannot make
            # the distinction, so under one every table still contributes.
            index += 1
            continue
        saw_table = True
        term_idx = _resolve_column(term_column, header)
        definition_idx = _resolve_column(definition_column, header)
        kind_idx = (
            _resolve_column(kind_column, header) if kind_column is not None else None
        )
        index += 2  # consume header + separator
        required_width = (
            max(term_idx, definition_idx, kind_idx if kind_idx is not None else -1) + 1
        )
        while (
            index < len(lines)
            and _is_table_row(lines[index])
            and not _FENCE.match(lines[index])
        ):
            cells = _split_row(lines[index])
            if len(cells) < required_width:
                raise PytestGivenError(
                    f'data row at line {index + 1} has {len(cells)} column(s), '
                    f'but {required_width} column(s) required.'
                )
            kind_value = (
                _strip_emphasis(cells[kind_idx]) if kind_idx is not None else ''
            )
            rows.append(
                GlossaryRow(
                    term=_strip_emphasis(cells[term_idx]),
                    definition=cells[definition_idx],
                    kind=kind_value or None,
                    line=index + 1,
                )
            )
            index += 1
    if not rows:
        raise PytestGivenError(
            "the glossary file's Markdown table has no data rows."
            if saw_table
            else 'found no Markdown pipe table in the glossary file (a table '
            'needs a header row followed by a |---|---| separator row).'
        )
    return rows


def _strip_emphasis(cell: str) -> str:
    """The cell's text with the reader's spans unwrapped. Applied to term and
    kind cells so a glossary written with emphasized term names renders clean
    pills."""
    return ''.join(_span_text(span) for span in read_spans(cell)).strip()


def _span_text(span: InlineSpan) -> str:
    match span:
        case PlainSpan(text=text) | CodeSpan(text=text):
            return text
        case EmphasisSpan(content=content):
            return ''.join(_span_text(part) for part in content)


def _is_table_row(line: str) -> bool:
    return '|' in line


def _is_separator_row(line: str) -> bool:
    cells = _split_row(line)
    return bool(cells) and all(_SEPARATOR_CELL.match(cell) for cell in cells)


def _split_row(line: str) -> list[str]:
    return [
        line[start:end].replace('\\|', '|').strip()
        for start, end in table_cell_spans(line)
    ]


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
