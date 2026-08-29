"""Minimal GFM pipe-table parser for file-backed glossaries.

Parses every pipe table in a Markdown document into GlossaryRow records.
Not a full CommonMark parser — it recognizes pipe tables, honors `\\|`
escapes, and skips fenced code blocks. Column selection accepts a header
name (case-insensitive) or a 0-based index.
"""

import re
from dataclasses import dataclass

from ..model import EMPHASIS, PytestGivenError

type ColumnSpec = int | str

_SEPARATOR_CELL = re.compile(r'^:?-+:?$')
_FENCE = re.compile(r'^\s*(```|~~~)')
_SPLIT_ON_UNESCAPED_PIPE = re.compile(r'(?<!\\)\|')


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
    description_column: ColumnSpec,
    kind_column: ColumnSpec | None,
) -> list[GlossaryRow]:
    rows: list[GlossaryRow] = []
    lines = text.splitlines()
    in_code = False
    index = 0
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
        term_idx = _resolve_column(term_column, header)
        desc_idx = _resolve_column(description_column, header)
        kind_idx = (
            _resolve_column(kind_column, header) if kind_column is not None else None
        )
        index += 2  # consume header + separator
        required_width = (
            max(term_idx, desc_idx, kind_idx if kind_idx is not None else -1) + 1
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
                _strip_emphasis(cells[kind_idx].strip()) if kind_idx is not None else ''
            )
            rows.append(
                GlossaryRow(
                    term=_strip_emphasis(cells[term_idx]),
                    definition=cells[desc_idx],
                    kind=kind_value or None,
                    line=index + 1,
                )
            )
            index += 1
    if not rows:
        raise PytestGivenError(
            'found no Markdown pipe table in the glossary file (a table needs a '
            'header row followed by a |---|---| separator row).'
        )
    return rows


def _strip_emphasis(cell: str) -> str:
    """Unwrap inline Markdown emphasis (`code`, **bold**, __bold__, *italic*)
    from a cell, leaving its text content. Applied to term and kind cells so a
    glossary written with emphasized term names renders clean pills.

    Nesting unwraps by recursing into each match rather than by re-running the
    pattern over the whole string: a repeated whole-string pass re-enters a
    code span it has already unwrapped and strips markup that is literal
    there, so `` `a*b*c` `` canonicalized to `abc` while the identical markup
    in a definition cell rendered as `a*b*c`.
    """
    return EMPHASIS.sub(_unwrap_emphasis, cell).strip()


def _unwrap_emphasis(match: re.Match[str]) -> str:
    code, bold_star, bold_underscore, italic = match.groups()
    if code is not None:
        return code
    inner = next(g for g in (bold_star, bold_underscore, italic) if g is not None)
    return EMPHASIS.sub(_unwrap_emphasis, inner)


def _is_table_row(line: str) -> bool:
    return '|' in line


def _is_separator_row(line: str) -> bool:
    cells = _split_row(line)
    return len(cells) > 0 and all(_SEPARATOR_CELL.match(cell) for cell in cells)


def _split_row(line: str) -> list[str]:
    stripped = line.strip().removeprefix('|')
    if stripped.endswith('|') and not stripped.endswith('\\|'):
        stripped = stripped[:-1]
    cells = _SPLIT_ON_UNESCAPED_PIPE.split(stripped)
    return [cell.replace('\\|', '|').strip() for cell in cells]


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
