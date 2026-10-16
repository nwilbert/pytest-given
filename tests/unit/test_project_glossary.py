"""The project's own GLOSSARY.md, whose tables a `FileGlossary` reads the way
GFM does: a row wider than its header lost its tail to an unescaped `|`."""

from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.rules_block.table import escapedSplit

_GLOSSARY = Path(__file__).parents[2] / 'GLOSSARY.md'


def test_every_glossary_row_is_as_wide_as_its_header() -> None:
    text = _GLOSSARY.read_text(encoding='utf-8')
    # Not `splitlines`, which also breaks where markdown-it does not.
    lines = text.split('\n')
    in_header = False
    width = 0
    misfits = []
    for token in MarkdownIt('commonmark').enable('table').parse(text):
        if token.type == 'thead_open':
            in_header = True
        elif token.type == 'tr_open':
            assert token.map is not None
            cells = _written_cells(lines[token.map[0]])
            if in_header:
                in_header, width = False, cells
            elif cells != width:
                misfits.append(
                    f'line {token.map[0] + 1}: {cells} cells, header has {width}'
                )
    assert misfits == []


def _written_cells(row: str) -> int:
    # markdown-it fits every row's tokens to its header, so the row is split
    # again the way its table rule splits one.
    cells = escapedSplit(row.strip())
    return len(cells) - (cells[0] == '') - (len(cells) > 1 and cells[-1] == '')
