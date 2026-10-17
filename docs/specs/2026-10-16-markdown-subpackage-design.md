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

- `model/text.py` holds `read_spans`, `located_spans` and the span types (`PlainSpan`, `CodeSpan`,
  `EmphasisSpan`, `InlineSpan`): the reader of the inline subset titles, steps and definitions are
  written in. It sits in the leaf because `model/narration.py` calls it — `read_narration`, which
  capture, grouping and report all go through, and `spanned_part`, which refuses a span around a
  value, placeholder or term ref.
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
from the package. Every other package may import it; the direction among them stays as it is.

```
markdown/                  the leaf — reading Markdown: block structure, tables, inline spans
model/                     schema, serde, errors, shared text rules
capture/  lint/  report/   each on model/ only, never on each other
grouping/                  on model/ + capture/
citations/                 on model/ + report/
plugin/   cli/             the entry points
```

The name shadows no import: the package imports itself relatively, and markdown-it-py's module is
`markdown_it`. (The docs toolchain's Python-Markdown, `markdown`, is never imported by `src/`.)

### What moves in

**Block structure** — from `citations/markdown_links.py`: the configured parser, the wrapped block
rules that record each line's text column, `_source_lines`, and the walk that yields each
paragraph's, heading's and table cell's text with its source offsets (today `_inline_runs` and
`_Run`). `table_cell_spans` comes with it.

```python
type Span = tuple[int, int]

@dataclass(frozen=True)
class SourceLine:
    start: int                # source offset of `content`
    content: str              # the line, or the part of it past a container prefix
    end: int                  # where the source line ends, before its line break

@dataclass(frozen=True)
class TextRun:
    line: int                 # 1-based, the source's, of the run's first line
    lines: tuple[SourceLine, ...]
    in_table_row: bool = False

    @cached_property
    def text(self) -> str: ...            # the lines joined by `\n`
    @cached_property
    def offsets(self) -> list[int]: ...   # where each character sits, one more for the end

    def span(self, start: int, end: int) -> Span: ...
    def line_at(self, index: int) -> int: ...
    def slice(self, start: int, end: int) -> TextRun: ...   # still placed in the source

def text_runs(source: str) -> Iterator[TextRun]: ...
```

`text_runs` yields every run, in document order: whether one could hold a link (`](` in it) is
the link scanner's question, so that filter stays in citations. A run's `line_at` replaces the
scanner's bisect over line starts: a run's lines are consecutive source lines. `offsets` is built
on first use, since most runs hold no link. A `MarkdownLink` holds its trailing text as a slice of
its run, so placing a summary in it is the run's `span`, not a copy of the run's offsets.

**Tables** — one reader, built on the same parse as the runs:

```python
@dataclass(frozen=True)
class TableCell:
    start: int          # source offset; a cell GFM supplies to a short row is empty, at its end
    text: str           # as written, container prefix left out

    @property
    def end(self) -> int: ...

    @property
    def content(self) -> str:
        """What a renderer reads: stripped, `\\|` as `|`, NUL as U+FFFD."""

@dataclass(frozen=True)
class TableRow:
    line: int                        # 1-based, the source's
    cells: tuple[TableCell, ...]     # exactly as many as the header, as GFM fits a row

    @property
    def contents(self) -> list[str]: ...

@dataclass(frozen=True)
class Table:
    header: TableRow
    rows: tuple[TableRow, ...]

def tables(source: str) -> list[Table]: ...
```

`capture/markdown_glossary.py` keeps its column resolution and row checks and reads `tables()`
instead of walking tokens; its parser goes. `text_runs` yields each table cell as a run, read off
the same `Table`, in document order with paragraphs and headings as now; a cell GFM supplies to a
short row is an empty run, which holds no link.

**Inline reading** — `read_spans`, `located_spans` and the span types from `model/text.py`;
`ASCII_PUNCTUATION`, `code_span_at`, `plain_link_text` and `fold_whitespace` from
`report/link_text.py`; `LINE_BREAK`, CommonMark's line endings, which the block reader splits
the source at and the renderers fold, from `report/text.py`'s `NEWLINE`.

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
`tests/unit/model/test_text.py`, the `table_cell_spans` tests from
`tests/unit/citations/test_markdown_links.py`, and the `plain_link_text` tests from
`tests/unit/report/test_link_text.py` that read hand-written text. The round trip — written by
`link_text`, read back by `plain_link_text` — stays in `report`, with `link_text`. The link
scanner's tests stay in citations, the block cases among them: they state where a link is found,
and `tables()` gains tests of its own. The oracle test and `test_template.py` import the moved
names from `markdown`. The scenarios in
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
- `markdown/` imports nothing from the rest of the package (`grep -rn "from \.\." src/pytest_given/markdown`
  finds nothing).
