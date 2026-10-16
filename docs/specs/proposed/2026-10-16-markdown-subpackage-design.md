# A `markdown/` Subpackage for Reading Markdown — Design Spec

## Goal

Read Markdown in one place. Every rule for how pytest-given reads Markdown — which lines are a
table and what its cells hold, where a paragraph's text sits in the source, what a backslash
escapes, where a code span ends, which spans a title is made of — lives in a new `markdown/`
subpackage, the leaf below `model/`. `FileGlossary` and `pytest-given citations` read a document's
tables through the same reader, so they cannot disagree about what a table is.

## Background

The rules for reading Markdown are spread over four packages, each placed by what could import it
rather than by what it is:

- `model/text.py` holds `read_spans` and the span types (`PlainSpan`, `CodeSpan`, `EmphasisSpan`,
  `InlineSpan`): the reader of the inline subset titles, steps and definitions are written in.
  It sits in the leaf because `model/narration.py`'s `read_narration` calls it, and capture,
  grouping and report all go through `read_narration`.
- `report/link_text.py` holds `ASCII_PUNCTUATION`, `code_span_at`, `plain_link_text` and
  `fold_whitespace`. `report` itself uses them only inside `plain_link_text`, and only `citations`
  calls that: they sit in `report` because `citations` may import it.
- `capture/markdown_glossary.py` builds a markdown-it parser and walks its table tokens for a
  glossary file's rows.
- `citations/markdown_links.py` builds a second markdown-it parser, its block rules wrapped to
  record where each line of text starts, and re-splits table rows with `table_cell_spans` to place
  each cell in the source.

The two parsers are configured alike by convention only (the CommonMark preset, the table rule,
`maxNesting` raised to 100, the inline rule off), and the two table walks read cells differently:
the glossary takes markdown-it's cell content, citations the cell's span in the source.

## Design

### Package and dependency direction

`src/pytest_given/markdown/` imports the standard library and markdown-it-py, and nothing else
from the package. `model/` imports it; so may every package above `model/`.

```
markdown/                  the leaf — reading Markdown: block structure, tables, inline spans
model/                     on markdown/ — schema, serde, errors, shared text rules
capture/  lint/  report/   each on model/ and markdown/, never on each other
grouping/                  on model/ + capture/ (and markdown/)
citations/                 on model/ + report/ (and markdown/)
plugin/   cli/             the entry points
```

The name shadows no import: the package imports itself relatively, and markdown-it-py's module is
`markdown_it`. (The docs toolchain's Python-Markdown, `markdown`, is never imported by `src/`.)

### What moves in

**Block structure** — from `citations/markdown_links.py`: the configured parser, the wrapped block
rules that record each line's text column, `_source_lines`, and the walk that yields each
paragraph's, heading's and table cell's text with its source offsets (today `_inline_runs` and
`_Run`). `table_cell_spans` comes with it.

**Tables** — one reader, built on the same parse as the runs:

```python
@dataclass(frozen=True)
class TableCell:
    start: int          # source offset; a cell GFM supplies to a short row is empty, start == end
    end: int
    text: str           # as written, container prefix left out

    @property
    def content(self) -> str:
        """What a renderer reads: stripped, `\\|` as `|`."""

@dataclass(frozen=True)
class TableRow:
    line: int                        # 1-based, the source's
    cells: tuple[TableCell, ...]     # exactly as many as the header, as GFM fits a row

@dataclass(frozen=True)
class Table:
    header: TableRow
    rows: tuple[TableRow, ...]

def tables(source: str) -> list[Table]: ...
```

`capture/markdown_glossary.py` keeps its column resolution and row checks and reads `tables()`
instead of walking tokens; its parser goes. Citations reads table cells from the same walk, in
document order with paragraphs and headings as now.

**Inline reading** — `read_spans` and the span types from `model/text.py`; `ASCII_PUNCTUATION`,
`code_span_at`, `plain_link_text` and `fold_whitespace` from `report/link_text.py`.

### What stays

- **Link scanning** stays in `citations/markdown_links.py`: `MarkdownLink`, its glyph and trailing
  summary, and the inline link reader are what a citation is, read off the runs `markdown/` yields.
- **Writing and rendering** stay in `report/`: `markdown_writer.py`, `inline_markdown.py`, and
  `link_text()` itself, which writes a citation's link text.
- **`model/text.py`** keeps `s_form`, `plural`, `derived_id` and `id_derive`; its docstring loses
  the `read_spans` paragraph.

### Imports and re-exports

Packages import the span types and readers from `markdown` directly (`from ..markdown import
read_spans`); `model` and `report` stop exporting the names that moved, so each has one home. The
module that imports `markdown_it` declares it in `__lazy_modules__`, so on Python 3.15 importing
`markdown/` — which `model/` now does at plugin load — still loads no markdown-it until a document
is parsed.

### Tests

Plain tests follow their code into `tests/unit/markdown/`: the `read_spans` tests from
`tests/unit/model/test_text.py`, the block and table tests from
`tests/unit/citations/test_markdown_links.py`. The scenarios in
`tests/unit/capture/test_markdown_glossary.py` stay where they are, unchanged: they state what a
`FileGlossary` user sees, which the move must not change, so they are its check — and no
scenario's node ID moves. `tests/unit/test_project_glossary.py` counts a row's written cells with `markdown.table_cell_spans`
rather than markdown-it's internal `escapedSplit`.

### Documentation

AGENTS.md's Architecture section gains `markdown/` in the diagram and the dependency direction.
Nothing user-facing changes, so neither the CHANGELOG nor the site nor the bundled skills do.

## Non-goals

- **Changing what is read.** Every report, glossary and citation result stays byte-for-byte what it
  is on `main`.
- **markdown-it's departures from CommonMark.** markdown-it reads two nested-container cases
  differently from CommonMark (an indented line after a lazy blockquote line, and an indented fence
  opener inside a nested blockquote), and it stops reading past `maxNesting` without a word.
  `markdown/` is where a fix for either would go, as would restoring a check of the block reader
  against an independent CommonMark implementation; neither is part of this move.
- **Reading `read_spans`' subset with markdown-it.** The inline subset deliberately differs from
  CommonMark (underscores never format, emphasis holds only plain text and code), so it stays
  hand-written.
- **Column-precise glossary errors.** The table reader carries each cell's span, which would let a
  glossary error name its column; the errors keep naming the line.

## Verification

- `uv run nox` passes at 100% coverage, and `uv run nox -s compat` passes on the oldest
  supported markdown-it-py.
- `tests/integration/test_lazy_imports.py` passes on Python 3.15.
- `uv run nox -s self_report examples` leaves every `.md` unchanged.
- `markdown/` imports nothing from the rest of the package (`grep -rn "from \.\.\(model\|capture\|report\|citations\)" src/pytest_given/markdown`
  finds nothing).
