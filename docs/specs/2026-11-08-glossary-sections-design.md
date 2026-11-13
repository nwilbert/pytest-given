# Glossary Sections, Avoided Words and Paragraph Glossaries — Design Spec

✅ [spec/glossary-sections](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#tag=spec/glossary-sections) (6 ✅)

## Goal

Three additions to the glossary, designed together because they share the file glossaries and the
Glossary tab, plus a rename they make necessary:

- **Glossary sections.** A term belongs to a named group: the heading it sits under in a
  `GLOSSARY.md`, or the section a code glossary declares it through. The Glossary tab groups terms
  by section and filters by them.
- **Avoided words.** A term lists the rejected synonyms a writer should not use for it. The report
  shows them on the term's card, and a new lint rule, `avoided-word`, flags one in narration.
- **The paragraph format.** A new `ParagraphGlossary` reads the `GLOSSARY.md` format of Matt
  Pocock's [skills](https://github.com/mattpocock/skills) (its `domain-modeling` and `teach`
  skills), one paragraph per term, so a project that keeps its glossary that way loads the file
  as it is.
- **`FileGlossary` becomes `TableGlossary`.** With two file formats, each gets a class named for
  what it reads.

## Background

`FileGlossary` reads every GFM pipe table in a Markdown file into one flat term set. A heading
over a table is ignored, so this repo's own `GLOSSARY.md`, split into eight sections from *Core
test model* to *Collaboration*, renders as one list grouped by kind. Most of its terms are kindless,
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
A request for payment sent to a customer after delivery, for one **Order**.
_Avoid_: Bill, payment request
```

Terms sit under `## Language` (`## Terms` in the `teach` skill) and may be grouped under
subheadings. Two further sections, `## Relationships` and `## Flagged ambiguities`, hold prose and
bullets, not terms. The `_Avoid_:` line is how the format records rejected synonyms. A definition
names another term in bold, the markup a *definition ref* uses (see the
[definition refs spec](2026-11-08-definition-refs-design.md)). A repo with
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
    definition: Definition | None = None
    source: SourceLocation | None = None
    section: str | None = None
    avoid: tuple[str, ...] = ()
```

- **`section`** is the section's name as written, or `None` for a term outside every section.
  `Glossary` keeps no section list: sections are ordered by the first term that names each one, in
  `Glossary.terms` order, which is registration order for a code glossary and file order for a
  file glossary.
- **`avoid`** holds the avoid entries in authored order, each an inline-Markdown string. An entry
  may end in a parenthesized note, as in `ticket (use only when quoting external systems)`. The
  report shows the whole entry. The lint matches only the **avoided word**: the entry's text before
  the note, with its inline markup unwrapped (as a term cell is) and stripped. An entry with no
  avoided word, such as a note alone, raises. An entry whose avoided word repeats an earlier one of
  the same term, as names compare (`name_key`), is dropped.
- **One id space across sections.** Lookup stays by name alone (`g['Guest']`). The same term in
  two sections is a conflict: two rows or registrations agree only when their section and avoided
  words agree too, so a repeat that today passes as identical raises once it names another
  section.
- **An avoided word may not name a term** of the same glossary. The two conflict when the word or
  its *S-form* spells the term's canonical name or S-form, in any case (their `name_keys`
  intersect), so nothing the lint flags is a term's own name. A glossary that avoids `Booking`
  while defining `Booking` or `Bookings` contradicts itself, so loading raises, naming the avoided
  word, the term that avoids it and the term it names.
- **Several terms may avoid the same word.** *Guest* and *Clerk* can both avoid `Customer`, and the
  lint then offers both, leaving the writer to pick the one the step means.
- A code glossary runs the check at registration, against the terms and avoided words registered
  so far.

Both fields go into the JSON report through the reflective serializer, and `serde`'s
`_glossary_term_from_dict` reads them back, so `pytest-given report` re-renders sections and
avoided words from a saved run.

## Code glossaries

### Sections

`Glossary.section(name)` returns a `GlossarySection`, which declares terms the way the glossary
does. Every term it declares goes into the same glossary, with `section=name`:

```python
g = Glossary()

booking = g.section('Booking')
guest = booking.actor('Guest', 'A person who books a **room**.', avoid=['Customer', 'Client'])
room = booking.work_object('Room', 'A bookable unit of a hotel.')

payment = g.section('Payment')
refund = payment.activity('refund', 'Return the money paid for a cancelled **booking**.')

clerk = g.actor('Clerk', 'Staff at the front desk.')  # no section
```

- `GlossarySection` has `actor`, `work_object`, `activity` and the call form, with the glossary's
  signatures. It has no lookup: `g['Guest']` reads a term back whatever its section.
- `g.section('Booking')` called twice, in one module or two, returns sections that declare into the
  same group. Section names are compared as written, so `Booking` and `booking` are two sections.
- The name is stripped, and an empty one raises.
- `GlossarySection` is exported from `pytest_given` for type annotations.

### Avoided words

`actor`, `work_object`, `activity` and the call form take `avoid: Sequence[str] = ()`, on the
glossary and on a section. Each entry is stripped, an empty entry raises, and the field stores a
tuple.

A repeated registration stays idempotent only when it is *exactly* repeated, which now includes the
section and the avoided words: declaring `Guest` in section `Booking` and again in section `Staff`
raises. The conflict message lists both fields beside kind, canonical and definition.

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
  rows (id derivation, kind parsing, duplicate check) and runs the avoided-word checks. A subclass
  only supplies its reader. Both are closed vocabularies: the call form looks up and never creates,
  as `FileGlossary`'s does today.
- **Discovery is unchanged.** It recognizes the model's `Glossary` base, which both classes extend.
- **The wrong class** fails with an error naming the other one. `TableGlossary` on a file with no
  table but with term paragraphs adds "for `**Term**:` paragraphs, use `ParagraphGlossary`".
  `ParagraphGlossary` on a file with no term paragraph but with a table adds "for a glossary in
  tables, use `TableGlossary`".

### Sections in both formats

A term's section is the text of the nearest heading above its table or term paragraph, at any
level, read as plain text with its inline markup unwrapped (as a term cell is), and without an ATX
heading's closing hashes. Only a heading at the top level of the document counts. One inside a
list item or a blockquote is prose, and a table inside one, which `TableGlossary` reads as today,
takes the nearest top-level heading above it. Two exceptions name no section:

- **The title.** A file's only level-1 heading names the file, not a section. In this repo's
  `GLOSSARY.md`, `# Glossary` is the title and `## Core test model` is a section. A file with
  several level-1 headings has no title, and each of them is a section.
- **`Language` and `Terms`**, in any case, in `ParagraphGlossary` only. They hold the terms rather
  than group them.

A term with no qualifying heading above it has no section. Two headings with the same text form one
section.

`markdown/blocks.py` reports headings today only as text runs past their hashes. Both readers need
each heading's level and text, and `ParagraphGlossary` each paragraph as a run, in document order
and with whether the block sits at the top level, so `markdown/` gains a block walk that yields
headings, paragraphs and tables that way.

### `TableGlossary`

Today's `FileGlossary`, renamed, plus:

- **`avoid_column`** selects a column the way `kind_column` does, by index or header name, and is
  `None` by default. Its cell is split on commas outside parentheses, each entry stripped, empty
  entries dropped. A table addressed by the other columns but lacking the avoid column raises, as a
  missing kind column does. `_addresses_another_table` counts it among the named columns.
- **Sections** from the headings, as above.

### `ParagraphGlossary`

A **term line** is a line of a top-level paragraph that starts with a bold span followed directly
by a colon: `**Order**:`. The bold text, unwrapped, is the term. A **term paragraph** runs from a
term line to the next term line or the end of the paragraph. A term is usually a paragraph of its
own, and two terms written with no blank line between them, which Markdown reads as one paragraph,
are still two terms.

The rest of the term paragraph, up to an avoid line, is the definition. It may start on the term
line after the colon or on the next line, and a term with no text there has no definition. A
definition spanning several lines folds its soft line breaks into spaces, as GitHub renders them. A
`<br>` stays a break, and a hard break, written as a backslash or two spaces at the end of a line,
is stored as `<br>`, since the report renders only that and a newline as breaks.

- **The avoid line** is a line of the term paragraph that starts with an italic `Avoid` and a colon
  (`_Avoid_:` or `*Avoid*:`, case-insensitive). The rest of the term paragraph, its line breaks
  read as spaces, is split like an avoid cell, so a wrapped list runs on.
- **Skipped sections.** A heading reading `Relationships` or `Flagged ambiguities`
  (case-insensitive) starts a stretch the reader skips, up to the next heading of the same or a
  higher level.
- **Everything else is prose.** The title, the description under it, any text before a paragraph's
  first term line, and every list item and blockquote are ignored.
  `**Order:** a customer's request`, whose colon sits inside the bold, is no term line.
- A file with no term line raises, naming the expected form.

A file in this format can still draw lint findings once loaded. Pocock's own `GLOSSARY.md` bolds
one word for emphasis (`The **decision** qualifier`), which `unresolved-definition-ref` flags. A
definition renders in the same inline subset as any other, so underscore emphasis such as
`_only_` shows as written.

## The Glossary tab

### Grouping

- **Sections count from two.** A glossary is *sectioned* when its terms name at least two sections.
  Terms with no section don't count as one, and every spelling of `Other` counts as the same one. A
  glossary with a single section, such as a table glossary under one `## Terms` heading, shows no
  section anywhere in the tab, as if it had none. The terms keep their `section` in the model and
  the JSON report.
- **Section is the default grouping.** Section headers appear in section order, and each card
  keeps its kind color.
- **Other is the last group.** A section named `Other`, in any case, always comes last, and the
  terms with no section join it. Sections that spell the name differently, such as `Other` and
  `other`, merge into it under the first one's spelling. When no section has that name, **Other**
  appears only for terms with no section.
- **The Kind grouping** is today's view.
- **The switch** appears only when the glossary is sectioned *and* has at least one term with a
  kind. It is a segmented control at the top of the Glossary sidebar, labelled *Group by*,
  with *Section* and *Kind*, styled like the definition filter.
- **Each grouping brings its own filter**, shown below the switch:
  - *Kind* shows today's kind checkboxes.
  - *Section* shows a list of the sections in section order, **Other** last when it appears, each
    with its report-wide term count, as a kind checkbox shows. Clicking a row selects or
    deselects it, and a selected row is highlighted the way a selected term is under *Browse by:
    Terms*. With no row selected, every section shows. With some selected, the tab shows the terms
    of any selected section.
- **Switching to the Kind grouping clears the section selection**, so the selection and the URL
  always agree. The kind checkboxes, which the URL never carries, don't apply in the Section
  grouping and keep their state for the next switch.
- **Without the switch:** a sectioned glossary with no kinds groups by section and shows the
  section list. An unsectioned one with kinds groups by kind, as today. One with neither shows the
  flat list, as today, with no section headers, no section list and no kind checkboxes.
- **The search and the definition filter apply in both groupings.** A section header hides when
  none of its terms is visible, and "No terms match this filter" covers both groupings.
- **The section selection is in the URL**, one `section=` parameter per selected section, written
  on every tab, as `tag=` carries the tag filters. **Other** is always `section=Other`, whatever
  spelling its header shows, and selects the terms with no section too. A link carrying `section=`
  shows the Glossary in the Section grouping with those sections selected. It opens the Glossary
  tab only when it also carries `view=glossary`. A URL without `section=` clears the selection and
  leaves the grouping as it is. A name the report no longer has is dropped and named in the
  stale-link snackbar, as for a tag. The grouping itself is not in the URL, as the kind checkboxes
  are not, so a switch adds a history entry only when it clears a selection.
- **Each section header carries a link button**, the plain link icon a term row shows when the
  report has no public URL. It copies `view=glossary&section=<name>`, with the name URL-encoded so
  a heading such as `Q&A` survives, the link that selects that section alone. A section is no
  citation target, so there is no copy menu, and `citations check` treats a section link in a
  document as an ordinary link.
- The URL's `term=` link opens the term's card in whichever grouping is showing. When the target is
  hidden, `goToTerm`'s `_resetTermFilters` clears the section selection along with the search and
  the other filters it clears today.
- **The tab's header summary is unchanged** in both groupings: the term count and the kind
  tallies.

`build_glossary_view` returns both groupings. The cards render once, in the default grouping:
the Section grouping in a sectioned glossary, the Kind grouping or the flat list otherwise, as
today. In a sectioned glossary with kinds, the Kind grouping renders a slot per term, which borrows
its card as a Stories-view slot borrows a scenario card (`fillStoryCards`): the first time the Kind
grouping shows, each slot is filled with a clone of the term's card, its ids and `aria-controls`
prefixed `kind-` through the same preparation `_prepareClone` gives a scenario clone. The page
thus carries each card once, the default view needs no cloning on load, and no id appears twice.
A clone keeps the original's `data-term-id`, so expanded cards, keyed by term id in Alpine state,
stay expanded across a switch. `goToTerm` scrolls to `kind-term-<id>` while the Kind grouping of
a sectioned glossary shows. The per-group visible counts, keyed by kind today, are keyed by group
so that both groupings use them.

### Avoided words on the card

A card whose term avoids words shows them in its expanded panel, as `Avoid: Customer, Client`, each
entry as written, note included, rendered by `definition_html`. An entry is a string, not a
stored definition, so its bold renders as plain bold, never as a definition ref. The Glossary
search matches avoided words, so a reader searching `customer` finds *Guest*. The term tooltip in
narration is unchanged.

### Term citations

A defining term citation folds in the definition as today. Avoided words and the section are not
folded in.

## The `avoided-word` lint rule

| Rule | Default | Catches |
|---|---|---|
| `avoided-word` | warn | An avoided word in the plain text of a step, a scenario title or a story sentence. |

- **What it scans:** the plain-text pieces of each scenario's title and step narrations, per
  grouped scenario, and the bare clause words of each story sentence. Bold and italic text is
  scanned without its markers. Bare clause words that follow one another in a clause are read as
  one text, joined by a space. Term refs, values, placeholders and code spans are skipped, so a
  term ref never trips it, except that both phrases of a Boolean phrase spec are scanned. Glossary definitions are not scanned, since a definition may name a
  rejected word on purpose.
- **How it matches:** case-insensitive, on whole words, the avoided word as written or its
  *S-form*. `Customer` is caught in "the customers pay" and not in "customerId". A multi-word
  avoided word matches across any run of whitespace and hyphens, so `payment request` is caught
  when a line break splits it, and `check-in desk` in "check in desk".
- **One finding per scenario or story and avoided word**, for the word's first use, the title read
  before the steps. Subject: the scenario's node ID or the story's id, so an intentional use is a
  `given_lint_ignore` entry like any finding on that subject. An entry silences every avoided word
  in its scenario or story. Location: the scenario's source when its title uses the word, otherwise
  the first step that uses it, or the story's source. Message, naming the avoided word as the
  glossary writes it:

  ```text
  step text uses 'Customer', which the glossary avoids in favour of 'Guest'
  ```

  or `scenario title uses …` and `story sentence uses …`. When several terms avoid the word, the
  message names each, in glossary order: `… in favour of 'Guest' or 'Clerk'`.
- **Catalog remedies:** use a term ref to the preferred term (the fitting one, when the message
  names several), or reword. If the word is right after all, remove it from the term's avoided
  words.
- **No glossary, no findings**, as for the other term rules.

## Glossary of this repo

`GLOSSARY.md` stays in the table format and gains sections from its existing headings, so the
self-report's Glossary tab groups by its eight sections, with the switch, since story terms carry
kinds. In its *Domain Storytelling* section the *File glossary* and *Term* rows change, and three
rows join them:

| Term | Meaning |
|---|---|
| File glossary | A glossary loaded from a Markdown file: a `TableGlossary` from GFM pipe tables, or a `ParagraphGlossary` from **term paragraphs**. |
| Term paragraph | A term in a `ParagraphGlossary`, written as one paragraph: `**Term**:`, its definition, and an optional `_Avoid_:` line, the format of Matt Pocock's skills. |
| Glossary section | A named group of terms: the heading a **file glossary** term sits under, or the `g.section(...)` a code glossary declares it through. The Glossary tab groups and filters by it. |
| Avoided word | A rejected synonym a **term** lists, which the `avoided-word` lint rule flags in narration. An avoid entry may add a parenthesized note, which the report shows and the lint ignores. |
| Term | A glossary entry: an **Actor**, **Work Object**, **Activity**, or **kindless** term. Each carries an id (slug), a canonical name, a kind unless kindless, an optional definition, an optional **glossary section** and any **avoided words**. |

## The rename

`FileGlossary` becomes `TableGlossary` everywhere: the class, its module's docstring, the exports,
`tests/ubiquitous_language.py`, `tests/conftest.py`, the tests that construct one, the
file-glossary example, `noxfile.py` and `pyproject.toml` where they name it, AGENTS.md, the site
(`guide/glossary.md`, `guide/step-text.md`, `examples.md`, `ai-agents.md`), the three bundled
skills. The module stays `capture/file_glossary.py`,
since it holds both classes, and the example stays `examples/file-glossary-booking/`, since *file
glossary* still names both. Implemented specs under `docs/specs/` and past CHANGELOG entries keep
the old name, as a record of their time.

## Implementation touch points

- `markdown/blocks.py` — the block walk with heading levels, paragraphs and whether a block sits
  at the top level, re-exported from `markdown/__init__.py`.
- `model/schema.py` — `GlossaryTerm.section` and `avoid`. A helper `avoided_word(entry)` that
  strips the note and unwraps the markup, beside the term model, since `capture/` and `lint/` both
  need it.
- `model/serde.py` — `_glossary_term_from_dict` reads both fields.
- `capture/glossary.py` — `Glossary.section`, `GlossarySection`, the `avoid` parameter, the exact-
  repeat check and its message extended to both fields, the two avoided-word checks.
- `capture/markdown_glossary.py` — sections and `avoid_column` in the table reader, and the
  paragraph reader.
- `capture/file_glossary.py` — `_MarkdownFileGlossary`, `TableGlossary` with `avoid_column`,
  `ParagraphGlossary`, and the wrong-class hints.
- `__init__.py` and `capture/__init__.py` — export `TableGlossary`, `ParagraphGlossary` and
  `GlossarySection`, no longer `FileGlossary`.
- `report/glossary_view.py` — section groups beside kind groups, the switch's visibility, the
  section list with its counts, avoided words on `TermEntry`.
- `report/templates/report.html.j2`, `app.js`, `styles.css` — the switch, the section list and its
  OR selection, cleared on a switch to Kind, the `section=` parameters in `_writeHash` and the hash
  reader, the header link
  buttons, the Kind grouping's card slots in a sectioned glossary and their filling (sharing
  `_prepareClone` with the Stories view), `goToTerm`'s target in that grouping, the group-keyed
  visible counts, the avoid line, avoided words in the search text and in `_termCounts`, the
  section selection in `_resetTermFilters`.
- `report/html_renderer.py` — the avoid line rendered through `definition_html`.
- `lint/catalog.py` — `AVOIDED_WORD`, default `warn`. `lint/runtime_rules.py` —
  `_avoided_word_findings`, registered in `_RUNTIME_RULES`.
- Docs: `docs/site/guide/glossary.md` (the *File glossary* section covers both classes, sections in
  code and in files, `avoid`), `docs/site/html-report.md` (the grouping switch and the section
  list), `docs/site/configuration/narration-lint.md` (the rule table),
  `docs/site/guide/step-text.md` (the Formatting table: a section heading and a paragraph term name
  lose their markup as a term cell does, and an avoid entry renders its bold, italic and code on
  the term's card).
- Authoring skill: `references/api.md` (`section`, `avoid`, both file glossary classes),
  `references/glossaries.md` (sections, avoided words, the paragraph format), `references/lint.md`
  (the catalog row). Reviewing skill `references/hygiene.md`: a term with well-known synonyms the
  narration drifts into, and no avoided words, is a finding. Navigating skill: a term's `section`
  and `avoid` among the fields a `jq` query over the JSON report reads. Citing skill: a section
  link is an ordinary link, never a citation. Regenerate the `.claude/skills/` mirror with
  `uv run pytest-given skills install`.
- Examples:
  - `examples/hotel-booking/` declares its terms through two or three sections, with a few avoided
    words, so the code glossary demonstrates both and its report shows the switch.
  - `examples/file-glossary-booking/GLOSSARY.md` gains headings and an Avoid column.
  - A new `examples/paragraph-glossary/`: a small suite over a `GLOSSARY.md` in the paragraph
    format, with subheadings, avoided words and a `## Relationships` section the reader skips. It
    joins `_EXAMPLES` in `noxfile.py`, which regenerates it, holds citations to it and stages its
    report for the site, and the example lists in `README.md`, `docs/site/index.md` and
    `docs/site/examples.md`.
- `GLOSSARY.md` — the rows above.
- `CHANGELOG.md`:
  - Under Changed, a **Breaking.** entry: `FileGlossary` is renamed `TableGlossary`, and the
    migration is the rename in the import and the constructor call.
  - Under Changed, a second **Breaking.** entry: a term repeated under two headings of a file
    glossary raises, identical rows included, and the migration is to keep one of them.
  - Under Added, one entry each: glossary sections, avoided words, `ParagraphGlossary`, and the
    `avoided-word` lint rule.
- Regenerate `examples/` and `examples/self-report/`. Playwright-verify the Glossary tab in both
  groupings: the switch, the section list (one, several and no sections selected), a copied
  section link opened in a new tab, `section=Other`, a section name that needs URL-encoding, a
  `section=` link naming a removed section, back and forward across selections, a switch to Kind
  clearing the selection and the URL and back restoring both, the kind checkboxes, the search and
  the definition filter in each, a search matching an avoided word, a `term=` link to a term
  outside the selected sections, a definition ref clicked inside a card in the Kind grouping, a
  card left expanded across a switch, the avoid line, and a report with sections only, one with
  kinds only and one with a single section (no switch in each).

## Test coverage

- Block walk units: heading levels and text, paragraphs in order, tables in between, a closed ATX
  heading and a setext heading, a heading and a paragraph inside a list item and a blockquote
  reported as not at the top level.
- Section units, both classes: the nearest heading, the title exception, a file with two level-1
  headings, `Language` and `Terms` in `ParagraphGlossary` in any case, a term above every heading,
  two headings with the same text, a heading inside a blockquote ignored.
- `TableGlossary` units: `avoid_column` by name and index, commas inside parentheses, a missing
  avoid column raising, an avoided word naming a term raising, a note-only avoid entry raising, a
  repeated avoided word kept once, the hint on a file of term paragraphs, an exact repeat in
  another section raising.
- `ParagraphGlossary` units: definition on the term line and on the next, a term with no
  definition, a multi-line definition folded into one line, a `<br>` kept, a backslash and a
  two-space hard break stored as `<br>`, the avoid line in both italic forms, an avoid note holding
  a comma and a bold term, lines after the avoid line ignored, two terms with no blank line between
  them, prose before a paragraph's first term line ignored, a term line in a list item ignored, a
  term with parentheses in its name (`**RPE (Rate of Perceived Exertion)**:`), subheadings beside
  `## Terms` rather than under it, skipped sections ending at the next heading of their level and
  spanning a deeper one, a bold-with-colon-inside line ignored, no term line raising, the hint on a
  file of tables.
- Code glossary units: a section's terms carry it, `g.section` twice merges, a name is stripped, an
  empty name raises, an inexact repeat across sections or avoided words raises, an avoided word
  naming a term raises in both registration orders, by the word's S-form and by the term's.
- Avoided-word units: the note stripped, markup unwrapped, a note alone raising.
- `build_glossary_view` units on the data contract: section order, the Other group's presence, the
  section list's counts, an authored **Other** section merged with the terms that have none and
  last without any, two spellings of `Other` merged and counted as one section, a single section
  shown as none, the switch's visibility for each combination of sectioned and
  kinds.
- Rule units: an avoided word in plain text (finding), in another case (finding), in bold
  (finding), in a term ref (clean), in a code span (clean), its S-form (finding), inside a longer
  word (clean), a multi-word one split by a line break (finding), a note ignored, one finding per
  scenario and word, a scenario title, a word in the title and a step (one finding, on the title),
  a story sentence, bare clause words joined (finding), a word two terms avoid (both named).
- Integration: the finding prints under `--given-lint`, an ignore entry suppresses it, discovery
  finds a `ParagraphGlossary` in a conftest, and a saved JSON report re-renders with sections and
  avoided words.
- Self-report, tagged `spec/glossary-sections`: one scenario each for a file glossary's sections,
  a code glossary's sections, the paragraph format, avoided words reaching the report, and the
  `avoided-word` rule.
