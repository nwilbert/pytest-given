"""The GFM pipe tables in a Markdown document, read into glossary rows.

markdown-it-py finds the tables, so a table counts where a renderer shows one
and a cell a row leaves out reads as empty. Column selection accepts a header
name (case-insensitive) or a 0-based index.
"""

# A suite with no file glossary never loads markdown-it.
__lazy_modules__ = ['markdown_it']

import functools
from collections.abc import Iterator
from dataclasses import dataclass

from markdown_it import MarkdownIt

from ..model import (
    CodeSpan,
    EmphasisSpan,
    InlineSpan,
    PlainSpan,
    PytestGivenError,
    read_spans,
)

type ColumnSpec = int | str


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
    specs = (term_column, definition_column) + (
        () if kind_column is None else (kind_column,)
    )
    for table in _tables(text):
        if _addresses_another_table(specs, table.header):
            continue
        saw_table = True
        term_idx = _resolve_column(term_column, table.header)
        definition_idx = _resolve_column(definition_column, table.header)
        kind_idx = (
            _resolve_column(kind_column, table.header)
            if kind_column is not None
            else None
        )
        for line, cells in table.rows:
            kind_value = (
                _strip_emphasis(cells[kind_idx]) if kind_idx is not None else ''
            )
            rows.append(
                GlossaryRow(
                    term=_strip_emphasis(cells[term_idx]),
                    definition=cells[definition_idx],
                    kind=kind_value or None,
                    line=line,
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


@dataclass(frozen=True)
class _Table:
    header: list[str]
    # Each data row's line and its cells, as many as the header has.
    rows: list[tuple[int, list[str]]]


def _tables(text: str) -> Iterator[_Table]:
    rows: list[tuple[int, list[str]]] = []
    cells: list[str] | None = None
    for token in _block_parser().parse(text):
        match token.type:
            case 'table_open':
                rows = []
            case 'tr_open':
                assert token.map is not None
                cells = []
                rows.append((token.map[0] + 1, cells))
            case 'inline' if cells is not None:
                cells.append(token.content)
            case 'tr_close':
                cells = None
            case 'table_close':
                (_, header), *body = rows
                yield _Table(header, body)


@functools.cache
def _block_parser() -> MarkdownIt:
    # The preset stops reading blocks nested 20 deep; a renderer does not.
    return (
        MarkdownIt('commonmark', {'maxNesting': 100}).enable('table').disable('inline')
    )


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
