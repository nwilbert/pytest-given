# HTML Citations — Design Spec

## Goal

Let an HTML document cite scenarios, tags and stories the way a Markdown document does, so that:

1. An agent writing an HTML page — a pull request walkthrough, a design review, architecture
   documentation — can back its claims with citations that `pytest-given citations check` holds to
   the report and `pytest-given citations update` keeps current.
2. A person editing such a page by hand copies a citation from the report, as they do for Markdown.

Both one-line and narrated citations are supported, and so are plain report links.

## Background

A [citation](../2026-10-07-citations-design.md) is a status glyph and a link into the HTML report.
A [narrated citation](../2026-10-17-narrated-citations-design.md) is one written as a `<details>`
block, the scenario's narration in its body. Both are read from Markdown documents only:
`markdown_documents` searches directories for `*.md`, and `markdown_links.py` and `narrated.py` read
Markdown source.

The `<summary>` of a Markdown narrated citation is already an HTML citation —
`✅ <a href="…">title</a>`, its link text from `html_link_text` in `report/link_text.py`. HTML citations generalize
that line to a whole HTML document.

## Intent

Agents increasingly produce HTML rather than Markdown for documents meant to be read: it lays out
diagrams, tables and folded detail better, and it publishes as a page. Those documents make claims
about the system's behavior just as a Markdown spec does, and the claims rot the same way. HTML
citations give them the same guarantee.

## Goals, non-goals, anti-goals

**Goals**

- `check` and `update` read `.html` and `.htm` documents, with the same findings, rewrites and exit
  codes as for Markdown. `--list`, `--covering`, `--report`, `--report-url` and `--report-path`
  work unchanged.
- The report's copy menu offers HTML variants of every citation entry.
- The `pytest-given-citing` skill teaches an agent to write HTML citations.

**Non-goals**

- Keeping generated HTML current. `update` makes sense only for an HTML document people or agents
  maintain directly. For one written by a generator or template, the next regeneration overwrites
  what `update` wrote. That is accepted. `check` still works on such output: a finding there means
  the generator's source needs the fix.
- Styling. A narrated citation's body carries no classes and no CSS. Its layout is the browser's
  default for the elements it uses. The report link is there for anyone who wants the report's
  view.
- HTML citations inside Markdown documents, or Markdown citations inside HTML documents. A
  document's format follows its file suffix.

**Anti-goals**

- `update` reformatting the document. It rewrites the glyph, the `href` value, the link text, the
  summary and a narrated citation's body, and leaves every other byte as written. A page that
  changes outside those spans after `update` is a bug.
- Status that goes stale silently. The glyph is the only status `update` keeps current, so
  styling that encodes status elsewhere is not supported (see [The citation](#the-citation)).

## The citation

```html
✅ <a href="https://example.org/report.html#scenario=tests/test_x.py::test_y">A renamed <code>test</code> keeps its citation</a>
✅ <a href="https://example.org/report.html#tag=spec/citations">spec/citations</a> (10 ✅)
```

The same parts as a Markdown citation, written as HTML:

- **Glyph**: bare text before the `<a>`, across any whitespace. As in Markdown, the glyph itself
  starts its text or follows whitespace or `(`, so a question mark ending a sentence is never read
  as one. Text starts after any tag, so `<li>✅ <a …>` is a citation. Not wrapped in an element: in
  `<span class="ok">✅</span>` the glyph becomes ❌ when the scenario fails while the class still
  says `ok`. A page that needs a status hook gets one only once pytest-given owns it, such as a
  `data-given-status` attribute `update` keeps current. That is future work, not part of this
  design.
- **Link**: an `<a>` whose `href` is a [report link](../../site/guide/citations.md#writing-it-by-hand).
  Any other attributes (`class`, `id`, `target`, …) are the author's, and `update` keeps them.
- **Link text**: a scenario's title as `html_link_text` renders it, a tag's or story's title
  escaped.
- **Summary**: for a tag or story, the text right after `</a>`, up to the next tag, as in Markdown.

`update` writes the `href` with `&` escaped as `&amp;`, as a story fragment needs. `check` reads
the `href`, the link text and the summary as parsed, entity references resolved, so `&#39;` and
`'` are the same link text.

A hand-written citation is `? <a href="…"></a>`, which `update` fills in. An `<a>` into the report
with no glyph is a plain report link: only its fragment is kept current, as in Markdown.

## The narrated citation

```html
<details>
<summary>✅ <a href="https://example.org/report.html#scenario=tests/test_x.py::test_y">A renamed <code>test</code> keeps its citation</a></summary>
<ol>
<li><strong>given</strong> a <i>citation</i> of <code>test_y</code></li>
<li><strong>when</strong> the test is renamed
  <ol>
  <li>📎 diff:
<pre><code>-def test_y():
+def test_z():</code></pre>
  </li>
  <li><strong>when</strong> its module is reloaded</li>
  </ol>
</li>
<li><strong>then</strong> <code>citations update</code> repoints it</li>
</ol>
</details>
```

- **`<details>` and `<summary>`**: any attributes, such as `open`, are kept. `markdown="1"` is
  neither added nor required. Unlike in Markdown, there are no blank-line or own-line rules: the
  `<summary>` is the first element child of the `<details>`, wherever it sits in the source.
- **Body**: everything between `</summary>` and the matching `</details>`. `update` replaces it
  whole. It mirrors the Markdown body element for element:
  - Steps form an `<ol>`, since their order is part of what they say. Each step is an `<li>`
    starting with its keyword in `<strong>`, on every step, as in Markdown. A step's attachments
    and then its children form a nested `<ol>` inside its `<li>`, the order the Markdown body
    lists them in.
  - Step text is rendered as `html_link_text` renders a title, except that a term ref becomes
    `<i>display</i>`. `<i>` is the HTML element for a technical term, and it reads as one with no
    CSS.
  - An attachment is an `<li>` reading `📎 label — <code>…</code>` when it fits inline, as the
    Markdown body decides, else `📎 label:` followed by `<pre><code>…</code></pre>`. A promoted
    attachment reads `📎 label — <em>see parameter table</em>`.
  - A grouped scenario's parameter table follows the steps as a `<table>` with a `<thead>` and a
    `<tbody>`, with the same columns as the Markdown table. Cells too big to inline follow the
    table as `<pre><code>` blocks, keyed as in Markdown.
- Only a scenario can be narrated. A narrated citation of a tag or story is a finding, as in
  Markdown. So is a `<details>` holding a citation in its `<summary>` that never closes: `update`
  cannot tell where its body ends.

### Writing and comparing the body

`update` writes the body as the example shows: `<ol>`, `</ol>` and each `<li>` on lines of their
own, an `<li>` at its `<ol>`'s indent, and a nested `<ol>` two spaces past its `<li>`'s. A `<pre>`
starts its own line at the margin, and its content is written as is, since indenting it would
change it. Every other line is prefixed with the `<details>` line's leading whitespace. Line
breaks follow the document's first one, as in Markdown.

`check` compares the body as parsed, not as written: the sequence of tags, attributes and text,
entity references resolved, text that is only whitespace dropped, and every other run of
whitespace collapsed to one space. Inside `<pre>` whitespace is compared exactly. This misses a
space removed or added between two inline elements, as in `<i>a</i> <code>b</code>`, which is
accepted: it never causes a finding, and the next rewrite of the body restores it. A formatter that reindents the body or rewraps its lines
therefore causes no finding, and `update` rewrites a body only when its content differs, so
reformatting alone never triggers a rewrite. Markdown bodies stay compared character for
character: there, indentation is structure, and a nested step reindented to two spaces renders
flat on a Python-Markdown site.

## Reading HTML

`HTMLParser` from the standard library, with `convert_charrefs=False` so text positions stay exact
past entity references. It never raises on malformed HTML, which matters for agent-written pages.
`getpos()` and `get_starttag_text()` give each tag's source span. That is all `update` needs to
rewrite only the spans listed under [Anti-goals](#goals-non-goals-anti-goals). lxml, html5lib and
BeautifulSoup give no reliable column offsets, and they would add a dependency.

Content of `<script>`, `<style>` and `<template>` elements, and of comments, is ignored: a report
URL inside a script's JSON is not a citation.

## Finding documents

A directory argument is searched for `*.md`, `*.html` and `*.htm`. `markdown_documents` becomes
`documents`, and the CLI help says so.

The search skips an HTML report. `report.html.j2` gains `<meta name="generator" content="pytest-given">`,
and a document whose `<head>` carries it is skipped without being read to the end. This matters in
this repository too: `docs/site/examples/` holds staged copies of the example reports, under the
`docs/site/` the `citations` sessions pass.

### Excluding documents

`check` and `update` take `--exclude GLOB`, repeatable. It drops from a directory search every
document whose path, relative to the working directory and written with `/`, matches the glob by
`PurePath.full_match`, so `**` spans directories. `--exclude '**/*.html'` keeps the commands on
Markdown, and `--exclude 'docs/build/**'` skips a generated folder. A document named on the command
line is always read, as with ruff's `--exclude`: naming it is the stronger statement. The search
now reading HTML can surface new findings on upgrade, and the CHANGELOG entry says so and points to
`--exclude`.

## The copy menu

Every copy menu that offers a citation gains its HTML variant as a separate entry, next to the
Markdown one:

| Menu | Markdown entries | Added HTML entries |
|---|---|---|
| Scenario card | Copy MD citation, Copy narrated MD citation | Copy HTML citation, Copy narrated HTML citation |
| Story header, Tags sidebar row | Copy MD citation | Copy HTML citation |

The existing entries are renamed **Copy MD citation** and **Copy narrated MD citation**, so
neither format reads as the default, and the pair lines up with the HTML entries. Each entry's
tooltip spells the format out, as the citation entry's already says "Markdown". The narrated HTML
entry copies an empty body for `update` to fill, as the Markdown one does. The HTML entries get
their own icon, distinct from the Markdown mark the citation entries use. Which icon is the
builder's call.

`scenario_citation_templates` gains the two HTML forms. A scenario's `scenario_row` already
carries the HTML title they need. Like every template change, the menu is Playwright-verified.

## Where the code goes

- `report/`: `narration_body_html(scenario)` next to `narration_body_md`, and
  `CitationIndex.narration_html(target)`. The HTML copy templates go in `citation_index.py`.
- `citations/html_links.py`: the HTML reader, the counterpart of `markdown_links.py` and
  `narrated.py` together. `check.py` gains an HTML check for each of the two existing
  `_LinkCheck` subclasses, or one check that dispatches on the link's kind, whichever reads
  better.
- No new dependency.

## Documentation

- `docs/site/guide/citations.md`: an HTML section covering both citation kinds, what is tolerated,
  the generated-HTML caveat, and the new copy entries.
- `docs/site/cli.md`: the document search and `--exclude`.
- The `pytest-given-citing` skill: how an agent writes an HTML citation, with `?` and an empty
  link for `update` to fill.
- `CHANGELOG.md`: **Added** entries for HTML documents and for `--exclude`, and **Changed** entries
  for the renamed copy menu entries and for directory searches now reading HTML.
- Self-report: scenarios tagged `spec/html-citations`, one per rule — HTML citations checked and
  updated, a narrated body written as HTML, extra attributes kept, script content ignored, a report
  skipped by the directory search, an `--exclude` glob dropping a searched document but not a
  named one.
