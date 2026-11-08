# Definition Refs — Design Spec

## Goal

Let a glossary definition reference other terms, so a reader of the Glossary tab can follow the
vocabulary from one term to the next. The author italicizes the term's name, which is how this
repo's own `GLOSSARY.md` already writes references:

```markdown
| **Step** | A unit of narration in one *Phase*. Steps nest and may carry *Attachments*. |
```

The report renders `Phase` and `Attachments` the way it renders a term ref in a step: a
kind-colored word with the term's definition on hover, which opens the term's card on click. An
italic that names no term is flagged by a new lint rule, so a renamed term doesn't silently leave
stale references behind.

## Background

Definitions already render inline Markdown — bold, italic, code and line breaks — through
`render_definition`. An italic is only styled, so a reader who meets *Phase* in a definition has
to find its row by hand.

In this repo's `GLOSSARY.md`, 58 of the 76 italic spans inside definitions name a term (its
canonical name or S-form, in any case). The other 18 are example words (`*Guest*`, `*searches
for*`, `*APIs*`), an adjective being defined (`*Custom*`), and one sub-term (`*sentence handle*`).
Those 18 become code spans, bold or rewording, which is the convention this design introduces:
**in a definition, an italic is a reference.**

The Markdown source keeps the italic as written. GitHub gives table rows no anchors, so a real link
in the source would need an `<a id>` in every term cell. The italic stays the authoring form, and
the links appear where the report renders definitions.

## The definition ref

A **definition ref** is an italic span (`*...*`, not `**...**`) in a glossary definition whose
whole text names a term of the same glossary:

- **The match is by derived id.** The span's text, put through `derived_id`, equals a term's id or
  the derived id of the term's S-form. Case is folded, so `*phase*` and `*Phase*` both name
  `Phase`, and `*term refs*` names `term ref`. A term's id is its name's derived id, and no two
  terms share one, so the match is never ambiguous between canonical names. When one term's S-form
  equals another term's canonical name, the canonical name wins.
- **The whole span, nothing less.** `*sentence handle*` doesn't name `Handle`. A possessive works
  as written, since the `'s` in `*Case*'s` sits outside the span.
- **An italic holding a code span is no ref**, and is not flagged: it formats an identifier.
- **A term's own name in its own definition** resolves, so it is not flagged, but renders as plain
  italic: a link to the card the reader is on goes nowhere.

The same rule holds for a `FileGlossary` and for a glossary declared in code, since both store the
definition as the same inline-Markdown string:

```python
payment = g.work_object('Payment', 'Money transferred for a *booking*.')
```

Resolution happens at render time and in the lint, over the glossary the report carries. The JSON
report is unchanged: a definition stays its authored string, and `pytest-given report` re-renders
the refs from it. A term citation folds a definition into a document as written, italics
included.

## Resolution in `model/`

`report/` and `lint/` both need the rule, and both may import only `model/` (and `markdown/`). So
the rule lives on the model:

- `Glossary.resolve_ref(text: str) -> GlossaryTerm | None` — the term an italic's text names, per
  the matching rules above. Its S-form index is kept current by the constructor and `register`,
  the way `_by_id` is.
- `definition_italics(definition: str) -> Iterator[str]` — the text of each italic span a
  definition holds that could be a ref (not bold, holding no code span), read with
  `markdown.read_spans`.

## Rendering

- **Glossary tab.** A definition ref renders as `_term_ref_span(term, term.id, display)`, where
  `display` is the span's text as authored, so a ref keeps its inflection (`Attachments`). It
  carries the kind class, `term-ref--link`, `has-term-tip` and `data-term-id`, so hovering shows
  the referenced term's definition.
- **Clicking a definition ref** opens the referenced term's card. Two things in `app.js` stand in
  the way today:
  - The capture-phase click handler skips every `[data-term-id]` inside a `.entry`, because the
    card's own header carries one. It lets a `.term-ref--link` inside `.entry-def` through to
    `goToTerm`, and stops propagation, so the card it sits in doesn't also expand or collapse.
  - `goToTerm` scrolls to a card the Glossary search, kind filter or definition filter may hide. A
    reader who searched for `step` and clicks *Phase* would see nothing happen. `goToTerm` resets
    whichever of the three hides the target.
- **Term tooltip: unchanged.** `definition_html` renders a definition ref as `<em>`. The tooltip
  closes when the pointer leaves the word that opened it, so a link inside it can't be reached, and
  `app.js` assigns it as `innerHTML` on the invariant that it holds only attribute-free tags.
- **Not a ref.** An unresolved italic and a self-reference render as `<em>`, as today.

`render_definition` takes an optional glossary and a callback that renders one resolved ref, so
`inline_markdown.py` stays free of the term-ref markup, which lives in `html_renderer.py`. Without
them, as for the tooltip, it renders every italic as `<em>`.

## The `unresolved-definition-ref` lint rule

| Rule | Default | Catches |
|---|---|---|
| `unresolved-definition-ref` | warn | An italic in a glossary definition that names no term. |

- **One finding per term and italic text.** Subject: the term's id, as for `dead-term`, so a
  deliberate italic is an ordinary `given_lint_ignore` entry
  (`unresolved-definition-ref: <term-id glob>`). Location: the term's source. Message:

  ```text
  definition of 'Pin' italicizes 'sentence handle', which names no glossary term
  ```

- **Remedies in the catalog entry:**
  - Fix the name, if the term was renamed.
  - Put an example word in a code span or quotes.
  - Use bold for stress.
- **A partial run can mis-flag a glossary declared in code.** Terms declared inside a test module
  exist only when that module is collected, so linting one file can flag a ref to a term another
  module declares. A `FileGlossary` is always complete. Lint gates run on the whole suite, so this
  is documented, not designed around.
- **`dead-term` is unchanged.** A term referenced only from another term's definition is still
  dead: the rule asks whether the tests use the term.

## This repo's glossary

The 18 italics that name no term change:

- Example words become code spans: `*Guest*`, `*Room*`, `*Booking*` (Actor, Work Object,
  Instance), `*book*`, `*confirm*`, `*search*`, `*searches for*` (Activity, Inflection),
  `*rooms*`, `*books*`, `*APIs*`, `*people*`, `*checks in*` (S-form, Handle).
- `*Custom*` in **Case ID** is an adjective the row defines, so it becomes `**Custom**`.
- `*sentence handle*` in **Pin** becomes "a sentence's *Handle*".

`GLOSSARY.md` gains the row for the new term:

| Term | Meaning |
|---|---|
| **Definition ref** | An italic in a glossary definition that names a term of the same glossary, by its canonical name or *S-form* in any case. The report renders it as a *term ref*. |

## Implementation touch points

- `model/schema.py` — `Glossary.resolve_ref` and its S-form index; `definition_italics` beside it,
  re-exported from `model/__init__.py`.
- `report/inline_markdown.py` — `render_definition` takes the optional glossary and ref callback.
- `report/html_renderer.py` — the `_inline_md` filter passes the report's glossary and a callback
  over `_term_ref_span`. `definition_html` passes neither.
- `report/templates/app.js` — the click handler's `.entry` exemption and `goToTerm`'s filter
  reset.
- `lint/base.py` — `UNRESOLVED_DEFINITION_REF`, default `warn`.
- `lint/runtime_rules.py` — `_unresolved_definition_ref_findings`, registered in `_RUNTIME_RULES`.
- `docs/site/guide/glossary.md` — the definition paragraph states the convention.
  `docs/site/configuration/narration-lint.md` — the rule table.
- Authoring skill `references/glossaries.md` — the convention, beside the line on formatting a
  definition. `references/lint.md` — the catalog row with its remedies. Reviewing skill
  `references/hygiene.md` — a definition that names another term without italics is a finding,
  the gap the lint can't see. Regenerate the `.claude/skills/` mirror with
  `uv run pytest-given skills install`.
- Examples: no example glossary italicizes anything today. The hotel-booking glossary declared in
  code and `examples/file-glossary-booking/`'s `GLOSSARY.md` each gain a few refs, so both glossary
  kinds demonstrate the feature.
- `GLOSSARY.md` — the 18 edits and the new row.
- `CHANGELOG.md` — two entries under Added: definition refs, and the `unresolved-definition-ref`
  lint rule.
- Regenerate `examples/` and `examples/self-report/`. Playwright-verify the Glossary tab (hover
  and click a definition ref, a self-reference, an unresolved italic) and the tooltip.

## Test coverage

- `Glossary.resolve_ref` units: canonical name in each case; S-form; a multi-word term; no match;
  an S-form that collides with another term's canonical name; a term registered after the first
  lookup.
- `definition_italics` units: bold skipped; an italic holding a code span skipped; a possessive
  after the span.
- Renderer units on the data contract: which term ids a rendered definition references, and that a
  self-reference and an unresolved italic reference none.
- Rule units: a resolving italic (clean), an unresolved one (finding), a self-reference (clean), an
  italic holding a code span (clean), two definitions with the same unresolved text (one finding
  each).
- Integration: the finding prints under `--given-lint`, and an ignore entry suppresses it.
- Self-report, tagged `spec/definition-refs`: one scenario for the matching rule (case and S-form),
  one for the lint rule.
