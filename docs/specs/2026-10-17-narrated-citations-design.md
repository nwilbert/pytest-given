# Narrated Citations — Design Spec

✅ [spec/narrated-citations](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#tag=spec/narrated-citations) (10 ✅)

## Goal

Let a citation of a scenario carry the scenario's narration, folded under it, so that:

1. A reader of a Markdown document — a spec, a README, a guide page — sees what the cited scenario
   does where it is cited, without leaving the document for the report.
2. A reviewer sees the cited behavior change in the document's diff.

`pytest-given citations update` writes the narration from the JSON report, and
`pytest-given citations check` holds it to the report character for character.

## Background

A [citation](2026-10-07-citations-design.md) states a scenario's title and status. What the
scenario does — its steps and parameter table — is one click away, in the HTML report. On GitHub
that click leaves the document, and a pull request's diff never shows it: a test whose steps
change while its title and status stay leaves every citation of it as it was.

The Markdown report already writes each scenario's narration as Markdown, and a document is
Markdown. HTML's `<details>` element folds content under a one-line `<summary>`, and GitHub, other
CommonMark renderers and Python-Markdown sites all render it.

This design builds on the [`markdown/` subpackage](2026-10-16-markdown-subpackage-design.md),
which lands first: the block reading it adds to is the one that design moves out of `citations/`.

## The narrated citation

```markdown
<details markdown="1">
<summary>✅ <a href="https://example.org/report.html#scenario=tests/test_x.py::test_y">A renamed <code>test</code> keeps its citation</a></summary>

- **given** a «citation» of `test_y`
- **when** the test is renamed
- **then** `citations update` repoints it

</details>
```

A **narrated citation** is a citation of a scenario written as a `<details>` block: the citation in
its `<summary>`, the scenario's narration in its body. Writing the block is the opt-in; a one-line
citation stays one line. Only a scenario can be narrated — a tag's or a story's narration would be
every scenario under it.

### Its parts

- **Opening tag** — `<details markdown="1">`, alone on its line; other attributes, such as `open`
  to show the narration unfolded, are the author's. Python-Markdown's `md_in_html`
  (the docs site's), kramdown and PHP Markdown Extra read a block's content as Markdown only with
  `markdown="1"`. CommonMark renderers — GitHub, markdown-it — read the body as Markdown anyway,
  since an HTML block ends at the first blank line, and GitHub drops the attribute.
- **Summary** — `<summary>`, the glyph, a space, an `<a href="…">` holding the link text, and
  `</summary>`, alone on the next line. The citation is HTML, not a Markdown link: inside an HTML
  block a renderer reads no Markdown, so `[title](url)` there shows its brackets; set apart by blank
  lines it becomes a paragraph, which GitHub lays out on its own line below the disclosure
  triangle. In HTML the triangle, glyph and link sit on one line, like any disclosure.
- **Body** — a blank line, the narration, a blank line.
- **Closing tag** — `</details>`, alone on its line.

The summary's parts are a scenario citation's, written as HTML:

- **Glyph** — the scenario's status, as a one-line citation's; `❓` for a target not in the report.
- **`href`** — the report link, its fragment `scenario=<node ID>`, in double quotes and read with
  its character references resolved, as any attribute value is. The report location rules are a
  one-line citation's: an absolute URL under `given_report_url`, or a relative one resolving to
  `--report-path`. A docs build rewrites a relative `href` exactly as it rewrites a Markdown link's
  destination (Zensical prefixes both with `../` for its directory URLs), so a relative link stays
  right in both forms.
- **Link text** — the scenario title as the HTML report's inline Markdown renders it: escaped, its
  spans as `<strong>`, `<em>` and `<code>`, a term ref as its plain display text. Written and
  expected are compared as the text they render to — tags dropped, character references resolved,
  whitespace folded — so a hand-written title without `<code>` stays current. Repointing a renamed
  test by its title compares the same text.
- **No summary** — a scenario citation takes none.

### Where it is read

Anywhere markdown-it reads an HTML block, at any container depth: in a list item or a blockquote
too, where GitHub renders it. Python-Markdown reads `md_in_html` blocks only at the top level of a
document — inside a list item it wraps the block in a paragraph and shows its tags — so the docs say
to keep a narrated citation at the top level on a Python-Markdown site.

An HTML block is a narrated citation when it holds a `<details>` tag, then a `<summary>` holding a
glyph and an `<a href>` that names the report, and nothing else; whitespace between them, a line
break included, is read as one space. Its body runs to the next HTML block in the same container
— the document, or the same list item or blockquote — that starts with `</details>`; a
`</details>` inside a fenced block in the body is code, not a closing tag, and a `<details>` block
before it leaves the first unclosed. A block that also holds its `</details>`, on a line of its own — no blank line after
`</summary>` — has an empty body; a `</details>` on the `</summary>` line is `mistyped`. Nothing in a scenario's body is read, neither a link nor a narrated citation nested in a list item: the body is the citation's, rewritten whole. A narrated citation of a tag or story, or of a scenario the report lacks, keeps the author's body, so its links are read.

A `<details>` block whose summary holds a glyph and a link into the report in any other shape — an
`<a>` with attributes besides `href`, an `href` not in double quotes, text after `</a>` or on the
`</details>` line, HTML after `</summary>` or a held `</details>` with no blank line between — or
that no `</details>` in its container closes is a `mistyped` finding. So is such a `<details>`
line inside a larger HTML block, with no blank line above it, read as a block of its own, and a
citing `<summary>` cut off from its `<details>` by a blank line or a list item's or blockquote's
edge, so a narrated citation never goes unchecked unseen. Any other `<details>` block is the author's and is left
alone.

## What the body holds

What the Markdown report writes for the scenario below its source anchor line:

- the steps, with term refs in `«»` and attachments as the Markdown report writes them;
- for a grouped scenario, the parameter table and the attachment blocks below it.

It leaves out:

- **the heading** — the summary replaces it;
- **the subtitle line** — the source anchor, with the tags and any skip or xfail reason beside it:
  its line number would change the document on every edit above the test;
- **errors** — a scenario's error block and a failed or xfailed case's block below the table. A failing
  citation is already a `failed` finding, and error text — paths, addresses — differs between runs.

One rendering serves both, so a narrated citation reads exactly as the scenario's section of
`--given-md` does, and the docs can say so.

### Nested steps

The Markdown report indents every line it hangs under a list item — a nested step, an attachment
line under a step, a fenced block under a note below the parameter table — by four spaces per
level. Python-Markdown — and so Zensical and MkDocs — reads a nested list only at four spaces,
and at two flattens it into its parent; CommonMark renderers read both. Four spaces render the same
narration on GitHub, in an agent's view of `--given-md` and on a docs site. A fenced attachment
under a nested step is checked to render in place with both markdown-it and the docs site's
Python-Markdown extensions.

## `update` and `check`

A narrated citation is checked as a one-line scenario citation is — glyph, link text, fragment,
repointing a renamed test by its title, `missing`, `failed` — plus its body and its opening tag:

| Finding | Kind | `update` |
|---|---|---|
| The body differs from the report's narration of the scenario | `stale` (`stale narration`) | writes the narration |
| The opening tag lacks `markdown="1"` | `stale` (`stale opening tag`) | adds it, keeping the other attributes |
| The citation names a tag or story | `stray-narration` | leaves it |
| The target is not in the report | `missing` | sets the glyph to `❓`, leaves the body |

- **Character for character** — the body is compared with the narration exactly, its line breaks
  normalized: a document checked out with CRLF line endings is not stale for them. `update` writes
  the narration with the line break the document's first line uses, and each line under the
  continuation prefix of the opening tag's line (a list item's indent, a blockquote's `> `), a
  blank line under that prefix with its trailing whitespace dropped (`>` in a blockquote, where an
  empty line would end it). The body is compared with those prefixes left out.
- **The stale-narration detail** names the first line that differs, written and expected, rather
  than a diff: the fix is always `update`, and the document's own diff shows the change once it ran.
- **An empty body** — a block copied from the report — is stale narration like any other, so `check`
  flags a fresh paste until `update` fills it.
- **A failed scenario** keeps its narration current: its body is rewritten as for any status, and
  its `failed` finding stays.
- **A tag or story** in a narrated citation is a finding `update` cannot fix: it would have to drop
  the author's body or keep a block with nothing to narrate. Nothing else of the block is checked.
- **A Markdown formatter** rewrites a narrated body — Prettier pads table columns, a list-indent
  rule set to two spaces reindents nested steps — and `check` then reports it stale. A document
  with narrated citations has its formatter skip them, such as with Prettier's
  `<!-- prettier-ignore-start -->` and `<!-- prettier-ignore-end -->` around each block.

`check --list` lists a narrated citation like a one-line scenario citation, and `--covering` keeps
it by the same rule, as the [listing design](2026-10-16-citations-list-design.md) sets out.

## Copying from the report

The report's copy buttons merge into one **copy button** on each scenario card, story header and
Tags sidebar row, opening a small menu:

| Entry | On | Shown |
|---|---|---|
| Copy link | scenario cards, story headers | always — the slug link the copy-link button copies today |
| Copy citation | scenario cards, story headers, tag rows | with a report URL |
| Copy narrated citation | scenario cards | with a report URL |

Where only one entry applies — a tag row, or any card of a report without a URL — the button copies
it directly, without a menu, as the buttons do today.

**Copy narrated citation** copies the block with its glyph, `href` and link text filled in and its
body empty:

```markdown
<details markdown="1">
<summary>✅ <a href="https://example.org/report.html#scenario=tests/test_x.py::test_y">A renamed <code>test</code> keeps its citation</a></summary>

</details>
```

`citations update` fills the body. The HTML report carries no narration — a body per scenario
would grow the report by its whole narration a second time — and writes a scenario's citations
from templates: each copied form once per page, as literal text around named slots, and per
scenario only its row — glyph, fragment, Markdown title, and HTML title where it differs. Rendered
whole per scenario, the one-line and narrated forms would repeat the fragment, the glyph and the
block's tags thousands of times.

The menu's look is the builder's, held to the report's tokens and verified in Playwright: it opens
on click or Enter, closes on Escape, on a click outside and after a copy, and keeps the copied
flash the buttons show today.

## Implementation touch points

- `markdown/` — the block walk yields HTML blocks too: each block's source lines, its container
  and its first line's continuation prefix.
- `citations/` — a reader of narrated citations over those HTML blocks, beside `markdown_links.py`'s
  link reader, giving the same parts a `MarkdownLink` gives — glyph, link text, `href`, each with
  its source span — plus the opening tag's and the body's spans; `check.py` checks them with the
  existing `_LinkCheck` rules and the findings above, `FindingKind` gaining `stray-narration`.
- `report/md_renderer.py` — the narration body as its own function, which `render_md` builds a
  scenario's section around; four-space nesting.
- `report/citation_index.py` — `Citation` gains the link text as HTML, through `inline_markdown.py`'s
  span rendering, and a scenario's row; the scenario citation templates, built by the same code as
  `markdown_halves`.
- `report/html_renderer.py`, `templates/`, `app.js` — the templates and rows in the citation data;
  the copy menu replacing the copy-link and citation buttons.
- `GLOSSARY.md` — a **Narrated citation** row beside **Citation**.

## Documentation

- `docs/site/guide/citations.md` — a *Narrated citations* section: the block, what its body holds,
  copying and filling one, keeping it at the top level on a Python-Markdown site, keeping a
  formatter off it (under *Keeping the check accurate*); a live narrated
  citation of a self-report scenario next to the page's live citations. The copy-button paragraph
  describes the menu.
- The `pytest-given-citing` skill — writing a narrated citation, the `stale narration` and
  `stray-narration` findings. The reviewing skill's citation step reads a narrated citation's body
  as the behavior a document claims.
- `CHANGELOG.md`:
  - under Added: a scenario citation written as a `<details markdown="1">` block carries the
    scenario's narration, which `citations update` writes and `citations check` holds to the
    report;
  - under Changed: the Markdown report indents nested steps and attachments by four spaces;
  - the report's copy buttons merging into a menu goes into the release's single visual-polish
    bullet.

## Test coverage

- `tests/unit/markdown/` — HTML blocks in the walk, with container and continuation prefix, in a
  list item and a blockquote.
- `tests/unit/citations/` — reading a narrated citation: its parts and spans; whitespace and a
  line break between the tags; a block holding its own `</details>`; a `</details>` in a fenced
  body block; an unclosed block; an author's `<details>` left alone. Checking one: each finding in
  the table, a current one silent, a title with a code span current, CRLF line endings, a body under
  a list item's indent and a blockquote's `> `;
  listed by `check --list` and kept by `--covering` as a one-line citation is.
- `tests/unit/report/` — the body leaves out heading, anchor and errors; four-space nesting.
- `tests/integration/test_cli_citations.py` — `update` fills an empty body, `check` exits 1 on a
  stale one.
- Self-report scenarios tagged `spec/narrated-citations`, one per rule:
  - `citations update` writes a narrated citation's body from the report.
  - `citations check` reports a narrated citation whose body differs from the report.
  - A narrated citation's body is the scenario's Markdown narration without heading, anchor line or
    errors.
  - A narrated citation of a tag or story is a finding `update` leaves.
  - The Markdown report nests steps by four spaces.
- Playwright: the copy menu on a scenario card, a story header and a tag row, with and without a
  report URL; the copied block pasted into a document passes `check` after `update`.

## Verification

- `uv run nox` passes at 100% coverage; `uv run nox -s self_report examples` changes each `.md` only
  by the four-space nesting and the new scenarios.
- A narrated citation with nested steps and a fenced attachment renders the same tree on GitHub
  (its Markdown API) and in `uv run nox -s docs_build`, where the guide page's live example shows it.
- `uv run nox -s docs_build` passes, and `citations check` over `docs/` is clean.

## Out of scope

- **Narrating a tag or story.** Its narration is every scenario under it.
- **Copying a filled body.** The report would carry every scenario's narration twice.
- **An HTML form of a one-line citation or a plain report link.** `<a href>` elsewhere in HTML is not
  read.
- **Choosing what the body holds per citation** (steps only, no attachments). One narration, the
  Markdown report's, is what keeps `check` exact and the form explainable in one sentence.
