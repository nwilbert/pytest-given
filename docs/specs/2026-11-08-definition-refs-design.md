# Definition Refs — Design Spec

✅ [spec/definition-refs](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#tag=spec/definition-refs) (2 ✅)

## Goal

Let a glossary definition reference other terms, so a reader of the Glossary tab can follow the
vocabulary from one term to the next. The author bolds the term's name:

```markdown
| Step | A unit of narration in one **Phase**. Steps nest and may carry **Attachments**. |
```

The report renders `Phase` and `Attachments` the way it renders a term ref in a step: a
kind-colored word with the term's definition on hover, which opens the term's card on click. A
bold span that names no term is flagged by a new lint rule, so a renamed term doesn't silently
leave stale references behind.

## Background

Definitions already render inline Markdown — bold, italic, code and line breaks — through
`render_definition`. Bold and italic are only styled, so a reader who meets a term's name in a
definition has to find its row by hand.

Bold is the reference markup because it is what the `GLOSSARY.md` format of Matt Pocock's
[skills](https://github.com/mattpocock/skills) uses (`A single tracked unit of work inside an
**Issue tracker**`), which `ParagraphGlossary` reads (see the
[glossary sections spec](proposed/2026-11-08-glossary-sections-design.md)). One rule then covers every
glossary, and italics stay free for emphasis and example words. The convention this design
introduces: **in a definition, a bold span is a reference.**

This repo's `GLOSSARY.md` writes references in italics today: 58 of the 76 italic spans inside
definitions name a term (its canonical name or S-form, in any case). Those 58 become bold. The
other 18 are example words (`*Guest*`, `*searches for*`, `*APIs*`), an adjective being defined
(`*Custom*`) and one sub-term (`*sentence handle*`), and they stay italic. Its term cells are bold
today (`| **Step** |`). The term column already says what the cell is, so they become plain, and
bold in a table means one thing: a reference.

The Markdown source keeps the bold as written. GitHub gives table rows no anchors, so a real link
in the source would need an `<a id>` in every term cell. The bold stays the authoring form, and the
links appear where the report renders definitions.

## The definition ref

A **definition ref** is a bold span (`**...**`, not `*...*`) in a glossary definition whose whole
text names a term of the same glossary:

- **The match is by derived id.** The span's text, put through `derived_id`, equals a term's id or
  the derived id of the term's S-form. Case is folded, so `**phase**` and `**Phase**` both name
  `Phase`, and `**term refs**` names `term ref`. A term's id is its name's derived id, and no two
  terms share one, so the match is never ambiguous between canonical names. When one term's S-form
  equals another term's canonical name, the canonical name wins.
- **The whole span, nothing less.** `**sentence handle**` doesn't name `Handle`. A possessive
  works as written, since the `'s` in `**Case**'s` sits outside the span.
- **A bold span holding a code span is no ref**, and is not flagged: it formats an identifier.
- **A term's own name in its own definition** resolves, so it is not flagged, but renders as plain
  bold: a link to the card the reader is on goes nowhere.

The same rule holds for a file glossary and for a glossary declared in code, since both store the
definition as the same inline-Markdown string:

```python
payment = g.work_object('Payment', 'Money transferred for a **booking**.')
```

Resolution happens at render time and in the lint, over the glossary the report carries. The JSON
report is unchanged: a definition stays its authored string, and `pytest-given report` re-renders
the refs from it. A term citation folds a definition into a document as written, bold included.

## Resolution in `model/`

`report/` and `lint/` both need the rule, and both may import only `model/` (and `markdown/`). So
the rule lives on the model:

- `Glossary.resolve_ref(text: str) -> GlossaryTerm | None` — the term a bold span's text names, per
  the matching rules above. Its S-form index is kept current by the constructor and `register`,
  the way `_by_id` is.
- `definition_ref_text(span: InlineSpan) -> str | None` — a bold span's text if it could be a
  ref (holding no code span).
- `definition_bold_spans(definition: str) -> Iterator[str]` — that text for each span of a
  definition, read with `markdown.read_spans`.

## Rendering

- **Glossary tab.** A definition ref renders as `_term_ref_span(term, term.id, display)`, where
  `display` is the span's text as authored, so a ref keeps its inflection (`Attachments`). It
  carries the kind class, `term-ref--link`, `has-term-tip` and `data-term-id`, so hovering shows
  the referenced term's definition.
- **Clicking a definition ref** opens the referenced term's card. The capture-phase click handler
  in `app.js` navigates from a `.term-ref--link` only, not from any `[data-term-id]`: the card's
  header and controls carry the term's id for Alpine. It stops propagation, so the card a
  definition ref sits in doesn't also expand or collapse. `goToTerm` already clears
  the Glossary filters that hide its target, so a reader who searched for `step` and clicks
  **Phase** lands on its card.
- **Term tooltip: unchanged.** The tooltip's `definition_html`, pre-rendered per term in
  `_app_data`, renders a definition ref as `<strong>`. The tooltip closes when the pointer leaves
  the word that opened it, so a link inside it can't be reached, and `app.js` assigns it as
  `innerHTML` on the invariant that it holds only attribute-free tags.
- **Not a ref.** An unresolved bold span and a self-reference render as `<strong>`, as today.

`render_definition` takes an optional callback, `render_ref`, which gets each span and returns
the HTML it renders as instead, or None. The callback asks `definition_ref_text` whether the span
could be a ref, so the renderer and the lint share one rule. Resolution and the term-ref markup
then live in `html_renderer.py`, and `inline_markdown.py` stays free of both. Without the callback, as for the tooltip, it renders every bold span as `<strong>`. The
Glossary tab's filter is made per render over the report's glossary, as the `narration` filter
is, and applied to the term rather than its definition text (`term | definition_md`), so it knows
which ref is a self-reference.

## The `unresolved-definition-ref` lint rule

| Rule | Default | Catches |
|---|---|---|
| `unresolved-definition-ref` | warn | A bold span in a glossary definition that names no term. |

- **One finding per term and bold text.** Subject: the term's id, as for `dead-term`, so a
  deliberate bold span is an ordinary `given_lint_ignore` entry
  (`unresolved-definition-ref: <term-id glob>`). Location: the term's source. Message:

  ```text
  definition of 'Handle' bolds 'sentence handle', which names no glossary term
  ```

- **Remedies in the catalog entry:**
  - Fix the name, if the term was renamed.
  - Put an example word in a code span or quotes.
  - Use italics for emphasis.
- **A glossary that bolds for emphasis gets findings on upgrade**, one per bold text. The remedy
  is italics. Bold term cells are not definitions and are never flagged.
- **A partial run can mis-flag a glossary declared in code.** Terms declared inside a test module
  exist only when that module is collected, so linting one file can flag a ref to a term another
  module declares. A file glossary is always complete. Lint gates run on the whole suite, so this
  is documented, not designed around.
- **`dead-term` is unchanged.** A term referenced only from another term's definition is still
  dead: the rule asks whether the tests use the term.

## This repo's glossary

- **Term cells** drop their bold: `| **Step** |` becomes `| Step |`.
- **The 58 italic refs** become bold.
- **The 18 other italics stay**, except `*sentence handle*` in **Pin**, which becomes "a
  sentence's **Handle**", since it means that term.
- **The bold spans already in definitions**, all in **Handle**: `**bare**` and `**called**` name
  surface forms rather than terms, so they become italics, as does `**sentence handle**`.
  ``**`.l`**`` and ``**`.s`**`` hold code spans and stay.

`GLOSSARY.md` gains the row for the new term:

| Term | Meaning |
|---|---|
| Definition ref | A bold span in a glossary definition that names a term of the same glossary, by its canonical name or **S-form** in any case. The report renders it as a **term ref**. |

## Implementation touch points

- `model/schema.py` — `Glossary.resolve_ref` and its S-form index; `definition_ref_text` and
  `definition_bold_spans` beside it, re-exported from `model/__init__.py`.
- `report/inline_markdown.py` — `render_definition` takes the optional `render_ref` callback.
- `report/html_renderer.py` — `_inline_md` becomes a `definition_md` filter made per render, whose
  callback resolves a span over the report's glossary, skips the term itself, and renders the rest
  with `_term_ref_span`. `report.html.j2` applies it to the term. `_app_data`'s `definition_html`
  passes no callback.
- `report/templates/app.js` — the click handler's narrower selector.
- `lint/base.py` — `UNRESOLVED_DEFINITION_REF`, default `warn`.
- `lint/runtime_rules.py` — `_unresolved_definition_ref_findings`, registered in `_RUNTIME_RULES`.
- `docs/site/guide/glossary.md` — the definition paragraph states the convention.
  `docs/site/configuration/narration-lint.md` — the rule table.
- Authoring skill `references/glossaries.md` — the convention, beside the line on formatting a
  definition, and plain term cells in place of the line that allows emphasized ones.
  `references/lint.md` — the catalog row with its remedies. Reviewing skill
  `references/hygiene.md` — a definition whose meaning rests on another term, with that term's
  first mention not bold, is a finding, the gap the lint can't see. Passing mentions of common
  terms such as *term* or *glossary* are not. Regenerate the `.claude/skills/` mirror with
  `uv run pytest-given skills install`.
- Examples: no example glossary references a term today. The hotel-booking glossary declared in
  code and `examples/file-glossary-booking/`'s `GLOSSARY.md` each gain a few refs, so both glossary
  kinds demonstrate the feature. The latter's `**how**` and `**when**` (*Cancellation Policy*) are
  emphasis and become italics.
- `GLOSSARY.md` — the edits above and the new row.
- `CHANGELOG.md` — two entries under Added: definition refs, and the `unresolved-definition-ref`
  lint rule.
- Regenerate `examples/` and `examples/self-report/`. Playwright-verify the Glossary tab (hover
  and click a definition ref, a self-reference, an unresolved bold span) and the tooltip.

## Test coverage

- `Glossary.resolve_ref` units: canonical name in each case; S-form; a multi-word term; no match;
  an S-form that collides with another term's canonical name; a term registered after the first
  lookup.
- `definition_bold_spans` units: italic skipped; a bold span holding a code span skipped; a
  possessive after the span.
- Renderer units on the data contract: which term ids a rendered definition references, and that a
  self-reference and an unresolved bold span reference none.
- Rule units: a resolving bold span (clean), an unresolved one (finding), an italic (clean), a
  self-reference (clean), a bold span holding a code span (clean), two definitions with the same
  unresolved text (one finding each).
- Integration: the finding prints under `--given-lint`, and an ignore entry suppresses it.
- Self-report, tagged `spec/definition-refs`: one scenario for the matching rule (case and S-form),
  one for the lint rule.
