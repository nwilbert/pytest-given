# Glossary Sections, Avoided Words and Paragraph Glossaries — Design Spec

## Goal

Three additions to the glossary, designed together because they share the file glossaries and the
Glossary tab, plus a rename they make necessary:

- **Glossary sections.** A term belongs to a named group: the heading it sits under in a
  `GLOSSARY.md`, or the section a code glossary declares it through. The Glossary tab groups terms
  by section.
- **Avoided words.** A term lists the rejected synonyms a writer should not use for it. The report
  shows them on the term's card, and a new lint rule, `avoided-term`, flags one in narration.
- **The paragraph format.** A new `ParagraphGlossary` reads the `GLOSSARY.md` format of Matt
  Pocock's [skills](https://github.com/mattpocock/skills) (its `domain-modeling` and `teach`
  skills), one paragraph per term, so a project that keeps its glossary that way loads it
  unchanged.
- **`FileGlossary` becomes `TableGlossary`.** With two file formats, each gets a class named for
  what it reads.

## Background

`FileGlossary` reads every GFM pipe table in a Markdown file into one flat term set. A heading
over a table is ignored, so this repo's own `GLOSSARY.md`, split into nine sections from *Core test
model* to *Collaboration*, renders as one list grouped by kind. Most of its terms are kindless,
since they never appear in a story, so the Glossary tab shows them under one *Uncategorized*
heading.

Pocock's format has no tables. Each term is a paragraph:

```markdown
# Ordering

Receives and tracks customer orders.

## Language

**Order**:
A customer's request for goods, placed in one checkout.
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request
```

Terms sit under `## Language` (`## Terms` in the `teach` skill) and may be grouped under
subheadings. Two further sections, `## Relationships` and `## Flagged ambiguities`, hold prose and
bullets, not terms. The `_Avoid_:` line is how the format records rejected synonyms. A repo with
several bounded contexts keeps one `GLOSSARY.md` per context, listed in a `GLOSSARY-MAP.md`.

## Non-goals

- **`## Relationships` and `## Flagged ambiguities`.** `ParagraphGlossary` skips both. Neither
  reaches the report.
- **Several glossaries per suite.** A file glossary reads one file, and a suite has one glossary,
  as today. `GLOSSARY-MAP.md` is not read. A repo with several contexts gives each its own suite
  and its own report.
- **Nested sections.** A section is one heading, never a path of headings.
- **A kind in the paragraph format.** The format has no place for one, so its terms are kindless
  until *kind inference* settles them.
- **Format detection.** The class names the format. A file in the other format fails with an error
  that names the other class.
- **A `FileGlossary` alias.** Alpha releases take breaking changes with a migration note, not
  compatibility shims.

## The model

`GlossaryTerm` gains two fields:

```python
@dataclass(frozen=True, kw_only=True)
class GlossaryTerm:
    id: TermId
    kind: TermKind | None
    canonical: str
    definition: str | None = None
    source: SourceLocation | None = None
    section: str | None = None
    avoid: tuple[str, ...] = ()
```

- **`section`** is the section's name as written, or `None` for a term outside every section.
  `Glossary` keeps no section list: sections are ordered by the first term that names each one, in
  `Glossary.terms` order, which is registration order for a code glossary and file order for a
  file glossary.
- **`avoid`** holds the avoided words in authored order. An entry may end in a parenthesized note,
  as in `ticket (use only when quoting external systems)`. The report shows the whole entry. The
  lint matches only the **avoided word**: the entry's text before the note, stripped.
- **One id space across sections.** Lookup stays by name alone (`g['Guest']`), and the same term in
  two sections is the duplicate-term error it is today.
- **An avoided word may not name a term** of the same glossary, by canonical name or *S-form* in
  any case. A glossary that avoids `Booking` while defining `Booking` contradicts itself, so
  loading raises, naming both terms. A code glossary checks at registration, against the terms
  registered so far and, for each later term, against the avoided words already recorded.

Both fields go into the JSON report through the reflective serializer, so `pytest-given report`
re-renders sections and avoided words from a saved run.

## Code glossaries

### Sections

`Glossary.section(name)` returns a `GlossarySection`, which declares terms the way the glossary
does. Every term it declares goes into the same glossary, with `section=name`:

```python
g = Glossary()

booking = g.section('Booking')
guest = booking.actor('Guest', 'A person who books a *room*.', avoid=['Customer', 'Client'])
room = booking.work_object('Room', 'A bookable unit of a hotel.')

payment = g.section('Payment')
refund = payment.activity('refund', 'Return the money paid for a cancelled booking.')

clerk = g.actor('Clerk', 'Staff at the front desk.')  # no section
```

- `GlossarySection` has `actor`, `work_object`, `activity` and the call form, with the glossary's
  signatures. It has no lookup: `g['Guest']` reads a term back whatever its section.
- `g.section('Booking')` called twice, in one module or two, returns sections that declare into the
  same group. Section names are compared as written.
- A name that is empty or whitespace only raises.
- `GlossarySection` is exported from `pytest_given` for type annotations.

### Avoided words

`actor`, `work_object`, `activity` and the call form take `avoid: Sequence[str] = ()`, on the
glossary and on a section. Each entry is stripped, an empty entry raises, and the field stores a
tuple.

A repeated registration stays idempotent only when it is *exactly* repeated, which now includes the
section and the avoided words: declaring `Guest` in section `Booking` and again in section `Staff`
raises.

## File glossaries

A **file glossary** is a glossary loaded from a Markdown file, in one of two formats, each with its
own class:

```python
TableGlossary(
    path,
    *,
    term_column: ColumnSpec = 0,
    definition_column: ColumnSpec = 1,
    kind_column: ColumnSpec | None = None,
    avoid_column: ColumnSpec | None = None,
)

ParagraphGlossary(path)
```

- **Shared base.** Both subclass a private `_MarkdownFileGlossary(LookupGlossary)` in
  `capture/file_glossary.py`, which reads the file, wraps reader errors with the path, registers the
  rows (id derivation, kind parsing, duplicate check) and runs the avoided-word check. A subclass
  only supplies its reader. Both are closed vocabularies: the call form looks up and never creates,
  as `FileGlossary`'s does today.
- **Discovery is unchanged.** It recognizes the model's `Glossary` base, which both classes extend.
- **The wrong class** fails with an error naming the other one. `TableGlossary` on a file with no
  table but with term paragraphs adds "for `**Term**:` paragraphs, use `ParagraphGlossary`".
  `ParagraphGlossary` on a file with no term paragraph but with a table adds "for a glossary in
  tables, use `TableGlossary`".

### Sections in both formats

A term's section is the text of the nearest heading above its table or term paragraph, at any
level, read as plain text with its inline markup unwrapped (as a term cell is). Two exceptions name
no section:

- **The title.** When the file's first heading is a level-1 heading, it names the file, not a
  section. In this repo's `GLOSSARY.md`, `# Glossary` is the title and `## Core test model` is a
  section.
- **`Language` and `Terms`**, in `ParagraphGlossary` only. They hold the terms rather than group
  them.

A term with no qualifying heading above it has no section. Two headings with the same text form one
section.

`markdown/blocks.py` reports headings today only as text runs past their hashes. Both readers need
each heading's level and text, and `ParagraphGlossary` each paragraph as a run, in document order,
so `markdown/` gains a block walk that yields headings, paragraphs and tables in order.

### `TableGlossary`

Today's `FileGlossary`, renamed, plus:

- **`avoid_column`** selects a column the way `kind_column` does, by index or header name, and is
  `None` by default. Its cell is split on commas outside parentheses, each entry stripped, empty
  entries dropped. A table addressed by the other columns but lacking the avoid column raises, as a
  missing kind column does. `_addresses_another_table` counts it among the named columns.
- **Sections** from the headings, as above.

### `ParagraphGlossary`

A **term paragraph** is a paragraph whose first line starts with a bold span followed directly by a
colon: `**Order**:`. The bold text, unwrapped, is the term. The rest of the paragraph, up to an
avoid line, is the definition. It may start on the first line after the colon or on the next line,
and a definition spanning several lines keeps its line breaks, which `normalize_definition` and the
renderer treat as in a table cell.

- **The avoid line** is a line of the paragraph that starts with an italic `Avoid` and a colon
  (`_Avoid_:` or `*Avoid*:`, case-insensitive). The rest of the line is split like an avoid cell.
  Lines after it are ignored.
- **Skipped sections.** A heading reading `Relationships` or `Flagged ambiguities`
  (case-insensitive) starts a stretch the reader skips, up to the next heading of the same or a
  higher level.
- **Everything else is prose.** The title, the description under it, and any paragraph that is not
  a term paragraph are ignored, so `**Update rule:** rename…`, whose colon sits inside the bold, is
  not a term paragraph.
- A file with no term paragraph raises, naming the expected form.

## The Glossary tab

### Grouping

- **Section is the default grouping.** Section headers appear in section order. Terms with no
  section come last, under **Other**, which appears only when some terms have a section and some
  don't. Each card keeps its kind color.
- **The Kind grouping** is today's view.
- **The switch** appears only when the glossary has at least one section *and* at least one term
  with a kind. It is a segmented control in the Glossary sidebar, labelled *Group by*, with
  *Section* and *Kind*, styled like the definition filter.
- **Without the switch:** a glossary with sections but no kinds groups by section. One with kinds but
  no sections groups by kind, as today. One with neither shows the flat list, as today.
- **Filters apply in both groupings.** The kind checkboxes, the definition filter and the search
  hide terms inside section groups too, and a section header hides when none of its terms is
  visible. "No terms match this filter" covers both groupings.
- The chosen grouping is not persisted. The URL's `term=` link opens the term's card in whichever
  grouping is showing.

`build_glossary_view` returns both groupings, so the template renders the section groups and the
kind groups and `app.js` shows one. The per-group visible counts, keyed by kind today, are keyed by
group so that both groupings use them.

### Avoided words on the card

A card whose term avoids words shows them under the definition, as `Avoid: Customer, Client`, each
entry as written, note included. The Glossary search matches avoided words, so a reader searching
`customer` finds *Guest*. The term tooltip in narration is unchanged.

### Term citations

A defining term citation folds in the definition as today. Avoided words and the section are not
folded in.

## The `avoided-term` lint rule

| Rule | Default | Catches |
|---|---|---|
| `avoided-term` | warn | An avoided word in the plain text of a step or a scenario title. |

- **What it scans:** the plain-text pieces of each scenario's title and step narrations, per
  grouped scenario. Term refs, values, placeholders and code spans are skipped, so a term ref never
  trips it. Glossary definitions are not scanned, since a definition may name a rejected word on
  purpose.
- **How it matches:** case-insensitive, on whole words, the avoided word as written or its
  *S-form*. `Customer` is caught in "the customers pay" and not in "customerId".
- **One finding per scenario and avoided word.** Subject: the scenario's node ID, so an intentional
  use is a `given_lint_ignore` entry like any scenario-subject finding. Location: the first step
  that uses the word, or the scenario's source for its title. Message:

  ```text
  step text uses 'Customer', which the glossary avoids in favour of 'Guest'
  ```

  or `scenario title uses …` for a title.
- **Catalog remedies:** use a term ref to the preferred term, or reword. If the word is right after
  all, remove it from the term's avoided words.
- **No glossary, no findings**, as for the other term rules.

## Glossary of this repo

`GLOSSARY.md` stays in the table format and gains sections from its existing headings, so the
self-report's Glossary tab groups by its nine sections, with the switch, since story terms carry
kinds. Its rows change:

| Term | Meaning |
|---|---|
| **File glossary** | A glossary loaded from a Markdown file: a `TableGlossary` from GFM pipe tables, or a `ParagraphGlossary` from *term paragraphs*. |
| **Term paragraph** | A term in a `ParagraphGlossary`, written as one paragraph: `**Term**:`, its definition, and an optional `_Avoid_:` line, the format of Matt Pocock's skills. |
| **Glossary section** | A named group of terms: the heading a *file glossary* term sits under, or the `g.section(...)` a code glossary declares it through. The Glossary tab groups by it. |
| **Avoided word** | A rejected synonym a *term* lists, which the `avoided-term` lint rule flags in narration. |
| **Term** | A glossary entry: an Actor, Work Object, Activity, or kindless term. Each carries an id (slug), a canonical name, a kind unless kindless, an optional definition, an optional *glossary section* and any *avoided words*. |

## The rename

`FileGlossary` becomes `TableGlossary` everywhere: the class, its module's docstring, the exports,
`tests/ubiquitous_language.py`, the tests that construct one, the file-glossary example, `noxfile.py`
and `pyproject.toml` where they name it, AGENTS.md, the site, and the three bundled skills. The
module stays `capture/file_glossary.py`, since it holds both classes, and the example stays
`examples/file-glossary-booking/`, since *file glossary* still names both. Committed specs under
`docs/specs/` keep the old name, as a record of their time.

## Implementation touch points

- `markdown/blocks.py` — the block walk with heading levels and paragraphs, re-exported from
  `markdown/__init__.py`.
- `model/schema.py` — `GlossaryTerm.section` and `avoid`. A helper `avoided_word(entry)` that
  strips the note, beside the term model, since `capture/` and `lint/` both need it.
- `capture/glossary.py` — `Glossary.section`, `GlossarySection`, the `avoid` parameter, the exact-
  repeat check extended to both fields, the avoided-word-names-a-term check.
- `capture/markdown_glossary.py` — sections and `avoid_column` in the table reader, and the
  paragraph reader.
- `capture/file_glossary.py` — `_MarkdownFileGlossary`, `TableGlossary` with `avoid_column`,
  `ParagraphGlossary`, and the wrong-class hints.
- `__init__.py` and `capture/__init__.py` — export `TableGlossary`, `ParagraphGlossary` and
  `GlossarySection`, no longer `FileGlossary`.
- `report/glossary_view.py` — section groups beside kind groups, the switch's visibility, avoided
  words on `TermEntry`.
- `report/templates/report.html.j2`, `app.js`, `styles.css` — the switch, section groups, the
  group-keyed visible counts, the avoid line, avoided words in the search text.
- `lint/base.py` — `AVOIDED_TERM`, default `warn`. `lint/runtime_rules.py` —
  `_avoided_term_findings`, registered in `_RUNTIME_RULES`.
- Docs: `docs/site/guide/glossary.md` (the *File glossary* section covers both classes, sections in
  code and in files, `avoid`), `docs/site/html-report.md` (the grouping switch),
  `docs/site/configuration/narration-lint.md` (the rule table).
- Authoring skill: `references/api.md` (`section`, `avoid`, both file glossary classes),
  `references/glossaries.md` (sections, avoided words, the paragraph format), `references/lint.md`
  (the catalog row). Reviewing skill `references/hygiene.md`: a term with well-known synonyms the
  narration drifts into, and no avoided words, is a finding. Regenerate the `.claude/skills/` mirror
  with `uv run pytest-given skills install`.
- Examples:
  - `examples/hotel-booking/` declares its terms through two or three sections, with a few avoided
    words, so the code glossary demonstrates both and its report shows the switch.
  - `examples/file-glossary-booking/GLOSSARY.md` gains headings and an Avoid column.
  - A new `examples/paragraph-glossary/`: a small suite over a `GLOSSARY.md` in the paragraph
    format, with subheadings, avoided words and a `## Relationships` section the reader skips. It
    joins the `examples` session and the site's examples page.
- `GLOSSARY.md` — the rows above.
- `CHANGELOG.md`:
  - Under Changed, a **Breaking.** entry: `FileGlossary` is renamed `TableGlossary`, and the
    migration is the rename in the import and the constructor call.
  - Under Added, one entry each: glossary sections, avoided words, `ParagraphGlossary`, and the
    `avoided-term` lint rule.
- Regenerate `examples/` and `examples/self-report/`. Playwright-verify the Glossary tab in both
  groupings: the switch, filters and search in each, a `term=` link, the avoid line, a report with
  sections only and one with kinds only (no switch).

## Test coverage

- Block walk units: heading levels and text, paragraphs in order, tables in between.
- Section units, both classes: the nearest heading, the title exception, `Language` and `Terms`
  in `ParagraphGlossary`, a term above every heading, two headings with the same text.
- `TableGlossary` units: `avoid_column` by name and index, commas inside parentheses, a missing
  avoid column raising, the hint on a file of term paragraphs.
- `ParagraphGlossary` units: definition on the first line and on the next, a multi-line
  definition, the avoid line in both italic forms, skipped sections ending at the next heading of
  their level, a bold-with-colon-inside paragraph ignored, no term paragraph raising, the hint on a
  file of tables.
- Code glossary units: a section's terms carry it, `g.section` twice merges, an empty name raises,
  an inexact repeat across sections or avoided words raises, an avoided word naming a term raises in
  both registration orders.
- `build_glossary_view` units on the data contract: section order, the Other group's presence, the
  switch's visibility for each combination of sections and kinds.
- Rule units: an avoided word in plain text (finding), in a term ref (clean), in a code span
  (clean), its S-form (finding), inside a longer word (clean), a note ignored, one finding per
  scenario and word, a scenario title.
- Integration: the finding prints under `--given-lint`, an ignore entry suppresses it, discovery
  finds a `ParagraphGlossary` in a conftest, and a saved JSON report re-renders with sections and
  avoided words.
- Self-report, tagged `spec/glossary-sections`: one scenario each for a file glossary's sections,
  a code glossary's sections, the paragraph format, avoided words reaching the report, and the
  `avoided-term` rule.
