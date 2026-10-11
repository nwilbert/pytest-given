"""The project's own GLOSSARY.md, whose tables a `FileGlossary` reads the way
GFM does: a row wider than its header lost its tail to an unescaped `|`."""

from pathlib import Path

from pytest_given.model import table_cell_spans

_GLOSSARY = Path(__file__).parents[2] / 'GLOSSARY.md'


def test_every_glossary_row_is_as_wide_as_its_header() -> None:
    lines = _GLOSSARY.read_text(encoding='utf-8').splitlines()
    width = 0
    misfits = []
    for number, line in enumerate(lines, start=1):
        if not line.startswith('|'):
            continue
        cells = len(table_cell_spans(line))
        if number < len(lines) and set(lines[number]) <= set('|-: '):
            width = cells
        elif cells != width:
            misfits.append(f'line {number}: {cells} cells, header has {width}')
    assert misfits == []
