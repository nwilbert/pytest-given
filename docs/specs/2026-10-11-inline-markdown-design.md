# Inline Markdown in Titles, Steps and Definitions — Design Spec

✅ [spec/inline-markdown](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#tag=spec/inline-markdown) (2 ✅)

## Goal

Render bold, italic and code the same way wherever an author's prose shows up: scenario titles
and step text gain it in the HTML report, glossary definitions keep it, and the Markdown report
and citations write exactly the spans the HTML renders. Every other text shows literally in every
output. The rules follow CommonMark for the forms authors actually write, and give up on its
corner cases.

This spec is implemented before [Case Ids in Parameter
Tables](proposed/2026-10-10-parameter-table-case-ids-design.md), whose id column is written through the
Markdown writer below.

## Background

Glossary definitions render `**bold**`, `__bold__`, `*italic*`, `` `code` `` and `<br>` in the
HTML report (`report/inline_markdown.py`). Everywhere else the HTML escapes the text, so a title
`Books a **suite**` shows its asterisks. The Markdown report writes most text verbatim, so a
Markdown viewer shows that title bold, and a `*` or `<` in a tag, a skip reason or an error
message turns into formatting there too. A citation keeps the markers (`report/link_text.py`).

The shared pattern (`EMPHASIS` in `model/text.py`) also formats more than authors of Python tests
mean: `2 * 3 * 4` italicizes `3`, `__init__` turns bold, and a code span inside bold
(`` **`.l`** ``, as `GLOSSARY.md` writes it) shows its backticks.

## Supported Markdown

The table below is the user-facing summary; it moves into the documentation when this lands.

| Text | Bold, italic, code | Newline | `<br>` | Where it shows |
|---|---|---|---|---|
| Scenario title | rendered | space | literal | HTML, Markdown, citations |
| Step text | rendered | space | literal | HTML, Markdown |
| Glossary term definition | rendered | line break | line break | HTML: Glossary tab, term ref tooltip |
| `FileGlossary` term and kind cells | removed: `**Guest**` reads as `Guest` | | literal | wherever the term shows |
| Everything else | literal | | literal | |

*Rendered* means `**bold**` as bold, `*italic*` as italic and `` `code` `` as code; underscores
never format. *Literal* means the characters show as written in every output, the Markdown report
included. *Everything else* is the report title, term names and term refs, interpolated values,
case ids, story titles and clauses, tags, skip and xfail reasons, parameter column names and
values, attachments and error messages.

Titles and steps never break a line: a newline reads as a space, so `'act one\nact two'` reads
`act one act two`. The rest keeps its current layout. The Markdown report holds no stories and no
glossary, which is why definitions show only in the HTML.

## Span rules

One reader decides what a span is, and every output follows it:

- **Code span:** a backtick, at least one character, the next backtick. Its contents are verbatim.
- **Bold and italic:** `**x**` and `*x*`. The opening marker is followed by a non-space and the
  closing marker preceded by one, so `2 * 3 * 4` stays literal.
- **Underscores never format**, so `__init__`, `_private_` and `snake_case` read as written.
- **One level:** bold and italic may contain code spans and nothing else; spans never overlap, and
  the first one to close wins.
- **Everything else is literal**, unmatched markers and backslashes included. There is no escape
  syntax; a code span is how to show a marker.

## Pieces

A scenario title or a step is a sequence of pieces: plain text, term refs, interpolated values and
placeholders. Spans are read within one plain-text piece and never across another piece. In
`t'**{guest} books**'` neither `**` closes, so both stay literal in every output. Interpolated
values and term refs are never read for Markdown: a value `'*'` is an asterisk.

A per-case scenario's case id suffix is generated from values, so `_suffixed`
(`grouping/percase.py`) appends it as a value piece between bracket literals, like the placeholder
values a per-case title already fills in. Its `expression` is empty, since no source wrote it, so
the lint's expression checks pass over it. `test_split[a*b*c]` shows its asterisks, highlighted as
a value. A plain-string title gets parts too, so title and suffix are never read as one string.

## Outputs

- **HTML** (`report/inline_markdown.py`): renders the reader's spans as `<strong>`, `<em>` and
  `<code>`, escaping everything else. The narration filter renders each plain-text piece this way,
  and so does the parts-less path for a plain-string title or step. Definitions additionally turn
  `<br>` and newlines into breaks. Everything else is escaped as it is today.
- **Markdown** (`report/link_text.py`): one writer backslash-escapes every character CommonMark or
  GFM give inline meaning — the set `link_text` already escapes (``\ [ ] * ~ ` < & | $``) and a
  non-intraword `_` — so a Markdown viewer shows exactly what the HTML shows: an author's `<br>`
  or `[text](url)` stays text. The Markdown report and citations write every text through it; only
  the plain-text pieces of titles and steps keep the reader's spans, with their markers, and a
  scenario's title is written piece by piece. Code spans and fenced blocks the report writes itself
  stay verbatim. A title's or step's newlines fold to spaces; elsewhere the report's
  newline-to-`<br>` folding runs after the escaping. Reading a citation back is unchanged.
- **`FileGlossary`** (`capture/markdown_glossary.py`): unwraps the reader's spans in term and kind
  cells, as before.

## Attachments

Text and JSON attachments are data, not prose: their content shows literally in both reports, as
it already does. The HTML escapes it inside a `<pre>`; the Markdown report puts it in a code span,
or, when it holds a newline or a backtick or is long, in a fenced block whose fence outruns any
backtick run inside. Only the label changes: the Markdown report escapes it like any other text.

## Implementation touch points

- `model/text.py` — the reader replaces `EMPHASIS`: one regex alternation with the flanking
  lookarounds, plus a code-span pass over bold and italic contents.
- `report/inline_markdown.py` — renders the reader's spans; breaks only for definitions.
- `report/html_renderer.py` — plain-text pieces and parts-less narrations through it.
- `report/link_text.py` — the writer: spans for a title's or step's plain-text pieces, escaped
  whole for every other text; its own code-span and nesting logic for emphasis goes, and
  `plain_link_text` keeps its own for reading documents back.
- `report/md_renderer.py` — every text through the writer: the heading, titles and steps piece by
  piece, tags, skip and xfail reasons, column names, case keys, cells, attachment labels and error
  lines; `_narration_md` folds newlines to spaces.
- `report/citation_index.py`, `citations/check.py` — a scenario citation carries the title's
  pieces, so `link_text` writes each one on its own; story titles and tags are escaped whole.
- `grouping/percase.py` — the suffix as a value piece.
- `capture/markdown_glossary.py` — unwraps through the reader.
- `report/templates/` — no change; the per-case value highlight and rendered spans are
  Playwright-verified per AGENTS.md.
- Docs: the [table](#supported-markdown) and the span rules in a "Formatting" section of
  `docs/site/guide/step-text.md`, linked from `docs/site/guide/glossary.md`; the authoring skill's
  `references/scenarios.md` and `references/glossaries.md` in step; the navigating skill's
  `references/report-json.md` for the per-case suffix's value part.
- Self-report: decorate the tests that best state "a title's emphasis renders the same in every
  output" and "a span crossed by a term ref stays literal".
- `CHANGELOG.md`:
  - Added: scenario titles and step text render bold, italic and code in the HTML report.
  - Changed: glossary definitions render code inside bold and no longer italicize between spaced
    asterisks; the Markdown report shows every text but a title's or step's formatting literally,
    and a newline in a title or step as a space; a per-case title's case id is highlighted as a
    value.
  - **Breaking.** Glossary definitions no longer render `__bold__`, and `FileGlossary` no longer
    unwraps it in term and kind cells; write `**bold**`.
- Regenerate `examples/` (one coffeeshop title and step with emphasis) and `examples/self-report/`.

## Test coverage

- Reader, table-driven: each span form, flanking spaces, underscores literal, code inside bold,
  unmatched markers, backslashes literal.
- HTML rendering of a piece and of a definition (breaks in one, not the other), at the level of
  the existing `_inline_md` tests.
- Markdown writer: spans kept, stray markers escaped, intraword `_` untouched, `<br>`, `&amp;` and
  `[text](url)` escaped. The Markdown report for a span crossed by a term ref, a value holding `*`, a tag and an
  error message holding markers, a multiline step, which reads as one line, and a multiline
  parameter value, which still breaks.
- Citations: a scenario title with emphasis and one with a crossed span, written and read back; a
  story title and a tag with `*` in them; a per-case title whose id holds `*`.
- Per-case grouping: the suffix is a value piece, for a plain-string and a t-string title.
- `FileGlossary`: a `` **`Scenario`** `` cell unwraps.

## Out of scope

- **Other Markdown:** links, strikethrough, underscore emphasis, deeper nesting, backslash escapes.
- **Bare URLs:** a GFM viewer links `https://…` in the Markdown report, where the HTML shows text;
  the link reads as the same text.
- **A Markdown attachment type**, whose content would render a limited set of Markdown; text and
  JSON attachments stay literal.
- **Search:** the HTML search box matches the raw text, markers included; a query rarely contains
  them.
