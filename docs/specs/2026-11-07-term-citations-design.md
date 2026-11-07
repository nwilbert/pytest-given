# Term Citations — Design Spec

✅ [spec/term-citations](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#tag=spec/term-citations) (8 ✅)

## Goal

Let a Markdown document cite a glossary term as it cites a tag, so that:

1. A document that leans on a term links it, and `pytest-given citations check` reports the link
   when the term leaves the report.
2. The citation states how the scenarios that use the term fare, kept current by
   `pytest-given citations update`.
3. A document can fold the term's definition under the citation, the report's wording in place,
   and a reviewer sees a changed definition in the document's diff.

## Background

A [citation](2026-10-07-citations-design.md) names a scenario, a tag or a story. A term has a
deep link, `#view=glossary&term=<id>`, but `check` reads none: a plain one is an ordinary link that
goes dead without a finding, and one with a glyph is `mistyped`.

The Glossary view already lists each term's scenarios: `build_term_crossrefs` walks every scenario's
title and steps for term refs. That list is what a tag's prefix match is to a tag, so a term gets a
rollup with no new notion of coverage.

## The term citation

```markdown
🔵 [Guest](https://example.org/report.html#view=glossary&term=guest) (5 ✅ · 2 🔵)
```

- **Fragment** — `view=glossary&term=<term id>`, the fragment the report's Glossary view already
  opens, in either parameter order. A bare `#term=<id>` opens the same term, so it names the term
  too, and `update` leaves it as written. A bare `#story=<id>` opens no story, so it stays an
  ordinary link.
- **Glyph and summary** — a tag's rollup over the scenarios the Glossary view lists for the term:
  every scenario with a term ref to it in its title or steps. `❌` if any failed, and a `failed`
  finding with it, else `🔵`, `✅`, `🟠`.
- **Link text** — the term's canonical name, literal as a tag's or story's title is.
- **No scenarios** — a term no scenario references reads `🟠 […](…) (no scenarios)`, as a story does.
  A reference from a story's sentence alone does not count: a summary counts scenarios.
- **Not in the report** — a term the glossary lacks reads `❓`, with the `missing` finding and the
  summary removed. A rename changes a term's id, so a renamed term is not in the report. `update`
  does not repoint it, as it does not repoint a tag or story. The finding suggests the closest term
  ids and canonical names.

A term's summary counts every scenario that mentions the term, however much the scenario is about
it. An everyday term's citation therefore goes stale with most new scenarios, and a failure
anywhere near the term marks it `❌`. This is accepted, and the docs steer authors to a plain report
link for such a term.

A plain link with no glyph, `[our guests](…#view=glossary&term=guest)`, is a plain report link: its
text is the author's and it claims only that the term exists, so a dead one is a `missing` finding.

`check --list` prints a term link as `✅ term guest`. `--covering` keeps a term citation or a plain
term link when the term's scenarios include the named one.

## The defining citation

```markdown
<details markdown="1">
<summary>🔵 <a href="https://example.org/report.html#view=glossary&term=guest">Guest</a> (5 ✅ · 2 🔵)</summary>

Someone staying at the hotel.

</details>
```

A **defining citation** is a term citation written as a `<details>` block: the citation in its
`<summary>`, the term's definition in its body. Its block follows a
[narrated citation](2026-10-17-narrated-citations-design.md)'s rules — the opening tag and
`markdown="1"`, the blank lines, the containers it is read in, an `update` that owns the body and
compares it character for character, a body nothing reads a link from — with these differences:

- **Summary** — the rollup follows `</a>` inside `<summary>`, separated by one space. `check` reads
  it by the same pattern as a one-line citation's and reports it `missing summary` or
  `stale summary`, both of which `update` fixes.
- **Body** — a blank line, the definition as one line of Markdown that shows what the report's
  Glossary view shows, a blank line. The report reads a definition's code and emphasis spans and
  shows everything else literally, so the line keeps those spans and escapes the rest with
  `literal_markdown`, a marker that would open a block at the line's start included, as the
  Markdown report's quoted text does. An author's `<br>` or a newline becomes `<br>`, as the Markdown
  report writes a line break in a table cell. A link or HTML tag in a definition therefore stays
  literal text in the document, and on a CommonMark renderer no definition can close the block
  early. Python-Markdown knows no `\<`, `\&`, `\~` or `\$` and reads tags before escapes, so on such
  a site a definition holding one of those characters shows the backslash and one holding
  `</details>` ends the block, as a narrated citation's step text does.
- **Undefined term** — the expected body is empty. A fresh block is current, with no finding. A
  block with text in its body gets a `stale` finding (`stale definition`), and `update` empties it:
  the body is the citation's whatever it holds, so an author's own words go outside the block and a
  definition removed from the glossary leaves the document too.
- **Not in the report** — the glyph becomes `❓`, the summary goes, and the author's body stays, as
  in a narrated citation of a scenario the report lacks.

| `<details>` citation of | Finding |
|---|---|
| A scenario | as today; a summary after `</a>` is `stray-summary` |
| A term | as above |
| A tag or story | `stray-narration`, as today |

Any other text after `</a>` stays `mistyped`.

## Copying from the report

The anchor link on each Glossary term row becomes the copy button a scenario card has:

| Entry | Shown |
|---|---|
| Copy link | always |
| Copy citation | with a report URL |
| Copy defining citation | with a report URL, for a term with a definition |

**Copy defining citation** copies the block with its glyph, `href`, link text and summary filled in
and its body empty for `update` to fill, as **Copy narrated citation** does. The entry uses the
narrated entry's icon, with its own tooltip. The citation data gains a `term` map beside `tag` and
`story`, holding each glossary term's row, and the templates a row fills gain a summary slot and a
`defining` form.

## Interaction with HTML citations

The proposed [HTML citations](proposed/2026-10-29-html-citations-design.md) design lands independently.
Whichever lands second carries the other through: an HTML term citation reads as an HTML tag
citation, and an HTML defining citation's body is the definition through the report's inline
Markdown rendering. Its menus gain the term row's HTML entries.

## Where the code goes

- `report/citation_index.py` — `TargetKind` gains `'term'`, `report_fragment` its fragment.
  `CitationIndex` gains `terms`, built on first use as `tags` and `stories` are, from a term-to-scenarios
  map its caller passes as it passes the story scenarios, since the HTML renderer has already walked
  them for the Glossary view. `citation`, `counted` and a `definition` method answer for it. A
  `Citation`'s HTML link text handles a literal title, escaped, which a scenario's narrated form never
  needed.
- `report/md_renderer.py` — `definition_body_md(term)`, the body as above, beside
  `narration_body_md`, reading spans with `read_spans` as `render_definition` does.
- `report/html_renderer.py`, `templates/`, `app.js` — the `term` citation data and the term row's
  copy button; the copy menu's defining entry.
- `citations/targets.py` — `parse_fragment`, `TargetResolver.resolve` and `suggestions` for a term;
  `shown_title` for a literal title in HTML.
- `citations/details.py`, renamed from `narrated.py` for its wider job as `NarratedCitation` becomes
  `DetailsCitation` — the shape reads an optional summary after `</a>`, with its span, by the pattern
  `check.py` reads a one-line citation's with, now shared in `targets.py`. A `mistyped` reason looks
  past a summary, so it names what is actually wrong with the block.
- `citations/check.py` — `_DetailsCheck`, renamed from `_NarratedCheck`, checks a summary and a term's
  body, and stops treating a scenario as the only kind that owns one. The `mistyped` message reads
  "names no scenario, tag, story or term". The `failed` message for a term reads
  `a scenario using cited term fails: Guest`, since a term itself cannot fail.

## Documentation

- `GLOSSARY.md` — **Citation** and **Report link** name terms; a **Defining citation** row beside
  **Narrated citation**.
- `docs/site/guide/citations.md` — the opening paragraphs, the kinds table, the glyph and summary
  rules, the fragment table, the `--covering` paragraph and a *Defining citations* section, with a
  live term citation and a live defining citation of the self-report's **Defining citation** term,
  which few scenarios will ever use. *Keeping the check accurate* adds: use a plain report link for
  an everyday term, whose citation changes with most new scenarios.
- `docs/site/html-report.md` — the copy button on a Glossary term row.
- `README.md`, `docs/site/index.md` and `docs/site/ai-agents.md` — terms among what a document can
  cite.
- The `pytest-given-citing` skill and its `references/repair.md` — the description, the glyph list,
  the term fragment in the triage row and the writing rules, the defining block, the broad-term
  warning, and that a renamed term is repaired by hand. The reviewing skill's citation step reads a
  defining citation's body as the meaning a document claims.
- `docs/specs/2026-10-07-citations-design.md` loses its out-of-scope entry on citing a term, and
  `docs/specs/2026-10-16-citations-list-design.md` its two examples of a term link as not a report
  link.
- `CHANGELOG.md`:
  - under Added: `citations check` and `update` read `#view=glossary&term=<id>` or `#term=<id>` as a
    citation of a term, with a tag's glyph and summary;
  - under Added: a term citation written as a `<details markdown="1">` block carries the term's
    definition, which `citations update` writes and `citations check` holds to the report;
  - under Changed: a plain report link to a glossary term is now checked, so a dead one fails
    `citations check`.

## Test coverage

- `tests/unit/report/` — a term's citation: rollup, literal title in both forms, no scenarios, a
  story reference not counted. A definition's body: spans kept; a link, an HTML tag and a line
  starting `</details>` or `- ` literal; a newline and `<br>` as `<br>`.
- `tests/unit/citations/` — reading the summary in a `<details>` block; every finding above; a
  current term citation silent; `--list` and `--covering`; a report with no glossary; a CRLF body and
  a body under a list item's indent.
- `tests/integration/test_cli_citations.py` — `update` fills a defining citation, `check` exits 1 on
  a stale one.
- Self-report scenarios tagged `spec/term-citations`, one per rule:
  - A term citation rolls up the scenarios that reference the term.
  - A term no scenario references reads as having no scenarios.
  - A failed scenario holding a term ref fails the citation of its term.
  - A term missing from the report is a finding, for a citation and a plain report link alike.
  - `citations update` writes a defining citation's body from the term's definition.
  - An undefined term's defining citation has an empty body, and `citations update` empties one
    that holds text.
  - A defining citation's body shows the definition as the report shows it.
  - `--covering` keeps a term citation that counts the scenario.
- Playwright: the copy menu on a Glossary term row with and without a report URL; a copied defining
  citation passes `check` after `update`.

## Verification

- `uv run nox` passes at 100% coverage. `uv run nox -s self_report examples` changes each `.md` by
  the new scenarios only.
- A defining citation renders on GitHub (its Markdown API) and in `uv run nox -s docs_build`, where
  the guide page's live example shows it.

## Out of scope

- **Repointing a renamed term.** Its id and canonical name change together, so nothing written in
  the citation identifies the new one.
- **Narrowing what counts**, such as counting only scenarios tagged with or titled by the term. Every
  reference counts, matching the list the citation's link opens.
- **Counting stories in the summary.**
- **Copying a filled body.** `update` fills it, one workflow for both `<details>` forms.
