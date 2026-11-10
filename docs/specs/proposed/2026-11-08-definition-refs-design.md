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
`markdown.definition_html`. Bold and italic are only styled, so a reader who meets a term's name
in a definition has to find its row by hand.

Bold is the reference markup because it is what the `GLOSSARY.md` format of Matt Pocock's
[skills](https://github.com/mattpocock/skills) uses (`A single tracked unit of work inside an
**Issue tracker**`), which `ParagraphGlossary` reads (see the
[glossary sections spec](2026-11-08-glossary-sections-design.md)). One rule then covers every
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

- **The match is by name, in any case.** The span's text equals a term's canonical name or its
  S-form, compared lowercased with each run of whitespace and hyphens folded to one space. So
  `**phase**` and `**Phase**` both name `Phase`, `**term refs**` names `term ref`, and
  `**parameter-table**` in a compound modifier names `Parameter table`. An all-caps name has two
  S-forms, since only a lowercase ending takes -es or -ies: `**SMSs**` and `**smses**` both name
  `SMS`. No two terms share a lowercased name, so the match is never ambiguous between canonical
  names. When one term's S-form equals another term's canonical name, the canonical name wins.
- **The whole span, nothing more or less.** `**sentence handle**` doesn't name `Handle`, and
  `**Note:**` doesn't name `Note`. A possessive works as written, since the `'s` in `**Case**'s`
  sits outside the span.
- **A bold span holding a code span is no ref**, and is not flagged: it formats an identifier.
- **A term's own name in its own definition** resolves, so it is not flagged, but renders as plain
  bold: a link to the card the reader is on goes nowhere.

The same rule holds for a file glossary and for a glossary declared in code, since both take the
definition as the same inline-Markdown string:

```python
payment = g.work_object('Payment', 'Money transferred for a **booking**.')
```

## The stored definition

A definition is resolved once, at session finish, and stored resolved, the way a step's narration
is. In the JSON report, a defined term's `definition` is an object:

```json
"definition": {
  "text": "Reserve a **Room** for a given stay.",
  "parts": [
    {"value": "Reserve a "},
    {"term_id": "room", "display": "Room", "expression": ""},
    {"value": " for a given stay."}
  ]
}
```

- **`text` is the definition as authored**, bold included. A term citation folds it into a
  document, and the Markdown report and the term tooltip render it.
- **A definition ref is a term ref part**, the part a step's narration uses, with an empty
  `expression`. Its `display` is the span's text, so a ref keeps its inflection (`Attachments`).
- **Everything else stays Markdown in literal parts**, an unresolved bold span included. A ref is
  written `**display**` in `text`, so joining the parts that way gives `text`. A part's text, below,
  means that: a literal's value, or a ref's `**display**`.
- **A self-reference is stored as a ref.** It names the term. That it renders unlinked is the
  renderer's choice.
- **A definition without refs** has one literal part. An undefined term's `definition` is `null`.

The parts give every reader of the JSON report the term ids without the matching rules.
`pytest-given report` re-renders a saved run without resolving anything. `jq` finds the terms a
definition names with `.definition.parts[] | select(.term_id)`, as it does for a step.

In the model, `GlossaryTerm.definition` is a `Definition | None`:

- `Definition(text: str, parts: tuple[DefinitionPart, ...])`. Its `__post_init__` asserts that
  the parts' text joins to `text`.
- `type DefinitionPart = NarrationLiteral | NarrationTermRef`.

It is a type of its own, not a `Narration`. A narration's `text` joins its parts with each ref as
its `display`, while a definition's `text` keeps the bold around each ref.

## Resolution

A glossary declared in code is complete only at session finish. A term's definition can reference
a term declared after it, in the same module or in another. So declaring a term resolves nothing.
A definition read from `GLOSSARY.md` or passed to `g.work_object` starts out as one literal part.

- **`resolve_definition_refs(glossary: Glossary) -> Glossary`**, in `capture/`, runs at session
  finish right after `infer_glossary_kinds`, over the complete glossary. It returns the glossary
  with every definition's refs resolved. It reads each definition's spans, with the characters
  each one covers, with `markdown.located_spans`, asks `definition_ref_text` whether a span could be a ref, and asks
  `Glossary.resolve_ref` which term the span names.
- **The lint and the renderer read the parts.** Neither resolves a name again.

The matching rules live in `model/`:

- `Glossary.resolve_ref(text: str) -> GlossaryTerm | None` — the term a bold span's text names, per
  the matching rules above. Its name index is kept current by the constructor and `register`,
  the way `_by_id` is.

The rest sits in `model/text.py`, beside `s_form`:

- `name_key(text: str) -> str` and `name_keys(name: str) -> set[str]` — the comparison above, and
  every key that spells a name. The Glossary tab's test for a term ref reading as the term's own
  name uses the same two.
- `definition_ref_text(span: InlineSpan) -> str | None` — a bold span's text if it could be a
  ref (holding no code span).
- `definition_bold_spans(text: str, *, before: str = '', after: str = '') -> Iterator[str]` — that
  text for each span of a literal part, read with `markdown.read_spans`. `before` and `after` are
  the text of the parts on either side.

## Rendering

- **Glossary tab.** A ref part renders through `_render_term_ref`, as a step's term ref does:
  its target looked up by `term_id`, and its `display` as plain text if the glossary holds no such
  term. It carries the kind class, `term-ref--link`, `has-term-tip` and `data-term-id`, so hovering
  shows the referenced term's definition. A literal part renders through `definition_html`, with
  the text of the parts on either side as context, so a span's edges read as they do in the whole
  definition.
- **Clicking a definition ref** opens the referenced term's card. The capture-phase click handler
  in `app.js` navigates from a `.term-ref--link` only, not from any `[data-term-id]`: the card's
  header and controls carry the term's id for Alpine. It stops propagation, so the card a
  definition ref sits in doesn't also expand or collapse. `goToTerm` already clears
  the Glossary filters that hide its target, so a reader who searched for `step` and clicks
  **Phase** lands on its card.
- **Term tooltip: unchanged.** `_app_data` embeds a term's `definition` as its `text`, so
  `app.js` reads the same string as before, and pre-renders the tooltip's `definition_html` field
  from it with `markdown.definition_html`, so a definition ref shows as `<strong>`. The tooltip
  closes when the pointer leaves the word that opened it, so a link inside it can't be reached,
  and `app.js` assigns it as `innerHTML` on the invariant that it holds only attribute-free
  tags.
- **Not a ref.** An unresolved bold span renders as `<strong>`, from its literal part. A
  self-reference, a ref part whose `term_id` is the term's own, renders as `<strong>` too.

The Glossary tab's filter is made per render over the report's glossary, as the `narration` filter
is, and applied to the term rather than its definition (`term | definition_md`), so it knows which
ref is a self-reference. `markdown/` knows nothing of refs: `definition_html` renders one literal
stretch, and the filter joins the parts.

## The `unresolved-definition-ref` lint rule

| Rule | Default | Catches |
|---|---|---|
| `unresolved-definition-ref` | warn | A bold span in a glossary definition that names no term. |

- **Read from the stored parts.** A bold span left in a literal part is unresolved:
  `definition_bold_spans` over each literal part, with the text of the parts on either side as
  context.
  The rule needs no lookup of its own.
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

- `model/schema.py` — `Definition`, `DefinitionPart`, `GlossaryTerm.definition: Definition | None`,
  and `Glossary.resolve_ref` with its name index.
- `model/serde.py` — a definition's parts are read with `_narration_part_from_dict`, and a part
  other than a literal or a term ref is refused as a malformed report.
- `model/text.py` — `name_key`, `name_keys`, `definition_ref_text` and `definition_bold_spans`,
  re-exported from `model/__init__.py`.
- `capture/` — `resolve_definition_refs` beside `infer_glossary_kinds`. In `glossary.py`,
  `normalize_definition` returns a definition of one literal part, for both glossary kinds, and the
  term conflict error prints the definitions' `text`.
- `plugin/session.py` — runs `resolve_definition_refs` right after `infer_glossary_kinds`.
- `markdown/rendering.py` — `definition_html` takes `before` and `after`, the text around a
  stretch, in place of `render_ref`.
- `report/html_renderer.py` — the `definition_md` filter renders a term's parts: a ref with
  `_render_term_ref`, a self-reference and a literal with `definition_html`. `report.html.j2`
  applies it to the term. `_app_data` embeds `definition.text` and renders `definition_html` from
  it.
- `report/md_renderer.py`, `report/glossary_view.py` and the term citations read
  `definition.text`.
- `report/templates/app.js` — the click handler's narrower selector.
- `lint/catalog.py` — `UNRESOLVED_DEFINITION_REF`, default `warn`.
- `lint/runtime_rules.py` — `_unresolved_definition_ref_findings`, registered in `_RUNTIME_RULES`,
  reading the literal parts.
- `docs/site/guide/glossary.md` — the definition paragraph states the convention.
  `docs/site/configuration/narration-lint.md` — the rule table.
- Authoring skill `references/glossaries.md` — the convention, beside the line on formatting a
  definition, and plain term cells in place of the line that allows emphasized ones.
  `references/lint.md` — the catalog row with its remedies. Reviewing skill
  `references/hygiene.md` — a definition whose meaning rests on another term, with that term's
  first mention not bold, is a finding, the gap the lint can't see. Passing mentions of common
  terms such as *term* or *glossary* are not. Navigating skill `references/report-json.md` — a
  term's `definition` object, and a `jq` line for the terms a definition names. Regenerate the
  `.claude/skills/` mirror with `uv run pytest-given skills install`.
- Examples: the hotel-booking glossary declared in code and `examples/file-glossary-booking/`'s
  `GLOSSARY.md` each carry a few refs, so both glossary kinds demonstrate the feature.
- `GLOSSARY.md` — the edits above and the new row.
- `CHANGELOG.md` — two entries under Added: definition refs, and the `unresolved-definition-ref`
  lint rule. One **Breaking** entry under Changed: a term's `definition` in the JSON report is an
  object, and `definition.text` holds the string it used to be.
- Regenerate `examples/` and `examples/self-report/`. Playwright-verify the Glossary tab (hover
  and click a definition ref, a self-reference, an unresolved bold span) and the tooltip.

## Test coverage

- `Glossary.resolve_ref` units: canonical name in each case; S-form; both S-forms of an all-caps
  name; a multi-word term; no match, punctuation around the name included; an S-form that
  collides with another term's canonical name; a term registered after the first lookup.
- `definition_bold_spans` units: italic skipped; a bold span holding a code span skipped; a
  possessive after the span; a span's edge read against the neighbouring text.
- `resolve_definition_refs` units: a ref becomes a term ref part whose `display` is the span's
  text; an unresolved bold span and a bold code span stay in literal parts; a self-reference is
  stored as a ref; a ref to a term registered after the referencing term resolves; joining the
  parts, each ref as `**display**`, gives `text`.
- Serde: a definition with ref parts round-trips, an undefined term's stays `null`, and a value
  part in a definition is refused.
- Renderer units on the data contract: which term ids a definition rendered from its parts
  references, and that a self-reference, an unresolved bold span and a ref to a term the glossary
  lacks reference none.
- Rule units: a resolved ref (clean), a bold span left in a literal part (finding), two definitions
  with the same unresolved text (one finding each). The units above cover which spans count and
  what resolves.
- Integration: the finding prints under `--given-lint`, and an ignore entry suppresses it.
  `pytest-given report` renders the refs of a saved JSON report.
- Self-report, tagged `spec/definition-refs`: one scenario for the matching rule (case and S-form),
  one for the stored parts, one for the lint rule.
