# Inline Markdown in Glossary Term Descriptions — Design Spec

## Goal

Render a small set of inline Markdown in glossary term **descriptions** so prose
reads the way it was authored:

- `**bold**` and `__bold__` → `<strong>`
- `*italic*` → `<em>`
- `` `code` `` → `<code>`
- a hard line break — a literal `<br>` (`<br/>`, `<br />`) **or** a `\n` in the
  source string → `<br>`

The emphasis set is the exact four-pattern set the existing
`capture/markdown_glossary.py` `_EMPHASIS` regex already recognises (and *strips*
from term/kind cells). A description authored as `A **VIP** guest who books a
Room` currently shows the markers literally; after this change `**VIP**` renders
bold.

Line breaks need both a literal-`<br>` form and a `\n` form because the two
description sources have asymmetric newline capability: a code-glossary string
(`g.actor('Guest', 'line one\nline two')`) carries a real `\n`, but a
`FileGlossary` description cell is a single physical GFM table row that
*structurally cannot* hold a newline — its portable break is a literal `<br>`
(the GFM in-cell convention). Supporting both means each source has a natural
authoring path and they render identically.

Out of scope: links, lists, and any block-level Markdown (they need a different,
block-aware render path). Single-underscore italic (`_italic_`) is intentionally
**not** supported, mirroring `_EMPHASIS`, so identifiers like `work_object` in a
description are never mangled. Narration step text is untouched.

## Background

A term description lives in `GlossaryTerm.definition` (a `str | None`), populated
from two sources that share the same field:

- code glossary — `g.actor('Guest', 'A **VIP** guest')`
- `FileGlossary` — a Markdown table's description column (kept raw;
  `markdown_glossary.py` strips emphasis from term/kind cells but not the
  description cell)

The description is rendered in **two** places, both of which currently show
Markdown markers literally:

1. **Glossary-tab entry** (`report.html.j2`, the `.entry-def` block) —
   `{{ term.definition if term.definition else '' }}`, Jinja-autoescaped.
2. **Hover tooltip** on every term pill across the report — `renderer.py`
   `_term_pill` emits `data-term-def="{escape(tooltip_def)}"`; `app.js`
   `_initTermTooltip` sets `defEl.textContent = pill.dataset.termDef`.

The description also currently feeds a **third** consumer, the glossary
**search-match string** (`report.html.j2` entry `x-show`):
`(term.canonical + ' ' + (term.definition or '')) | lower`, matched against
`glossarySearch`. This design removes the description from that match target
(and hardens the target itself) — see *Glossary search hardening* below.

## Approach

A single pure render-time function converts inline Markdown to safe HTML for the
two description consumers. The glossary search is reworked separately so the
description no longer feeds it and its match key can no longer break the page.

### `report/inline_markdown.py` (new)

```python
def render_inline_markdown(text: str) -> str:
    """Escape `text` for HTML, then render **bold** / __bold__ / *italic* /
    `code` as <strong>/<em>/<code> and hard breaks (<br> or \\n) as <br>.
    Returns a safe HTML string."""
```

- HTML-escape the whole string first (`markupsafe.escape` / `html.escape`), so
  `<`, `>`, `&` in a description are always literal and code-span content is
  escaped.
- Normalise hard breaks next: re-admit an author's escaped `&lt;br&gt;` /
  `&lt;br/&gt;` / `&lt;br /&gt;` (case-insensitive) as a real `<br>`, and turn
  any literal newline (`\r\n`, `\r`, `\n`) into `<br>`. `<br>` is the only HTML
  tag re-admitted from the escaped text; everything else stays escaped.
- Then one left-to-right `re.sub` over a combined alternation with the **code
  span first** — `` `(.+?)` `` | `\*\*(.+?)\*\*` | `__(.+?)__` | `\*(.+?)\*` —
  so `` `a*b` `` renders as code without italicising its interior. A single
  non-overlapping pass (not the stabilise-loop `_strip_emphasis` uses); nested
  bold-in-code / bold+italic combinations are out of scope. (Break normalisation
  runs before emphasis; the two are orthogonal — `.+?` never spans the `<br>`
  boundary because no literal newlines remain.)
- Unmatched or unpaired markers (`a * b`, a lone `` ` ``) are left literal.
- Lives in `report/` because rendering is a report concern; per the subpackage
  rule `report/` depends only on `model/` and cannot import
  `capture/markdown_glossary.py`. The small regex overlap is the correct
  tradeoff, not a reason to break the boundary.

### Consumer wiring

1. **Glossary entry** — register a Jinja filter `inline_md` that returns
   `Markup(render_inline_markdown(text))`; change the `.entry-def` output to
   `{{ term.definition | inline_md }}` (empty/None → empty string, badge
   behaviour unchanged).
2. **Tooltip** — in `_term_pill`, run the definition through
   `render_inline_markdown` and attribute-escape the result into
   `data-term-def` (`escape(render_inline_markdown(tooltip_def))`). In `app.js`,
   change the tooltip def from `textContent` to `innerHTML`. This round-trips
   cleanly: attribute-escaped `&lt;strong&gt;…&lt;/strong&gt;` →
   `dataset.termDef` → `innerHTML`. Content is generated from trusted test
   source, so `innerHTML` carries no XSS concern; the escaping is for
   correctness (a literal `<` in a description).

### Glossary search hardening

The entry `x-show` (`report.html.j2:489`) currently inlines the lowercased match
key **into JavaScript source** as a single-quoted string literal:
`'{{ (term.canonical + ' ' + (term.definition or '')) | lower }}'.includes(...)`.
Any character that can't sit inside a `'…'` literal — an apostrophe, a newline,
a backslash, a Unicode line separator — breaks the Alpine expression and
silently kills that entry's filtering. Adding `<br>`/`\n` line breaks to
descriptions makes the newline case reachable, but the apostrophe case is a
pre-existing latent hazard independent of this feature.

Two coupled changes fix it at the root:

- **Move the key out of JS source into a `data-search` attribute.** Emit
  `data-search="{{ … | lower }}"` on the entry `div` (Jinja autoescapes the
  attribute value — quotes, `<`, `&`, newlines all handled) and change the
  `x-show` string clause to `$el.dataset.search.includes(glossarySearch.toLowerCase())`.
  Nothing runtime-derived is inlined into the expression any more, so the whole
  JS-literal injection class is gone — for term **names** as well as
  descriptions. The definition-filter clause is unchanged: it bakes in a
  compile-time boolean (`{{ 'true' if term.definition is none else 'false' }}`),
  not a string, so it was never at risk.
- **Search on the term name only.** The match key becomes `term.canonical | lower`
  — the description is dropped from search. The box is labelled "Search terms…"
  and filters the term *list*; full-text search over descriptions (always
  visible in each entry) is left to the browser's native find. This also means
  the line-break work has **no** interaction with search at all — the earlier
  `\n`-collapse step is no longer needed.

### CSS

`<strong>` / `<em>` use browser defaults. Add minimal monospace styling for
`.entry-def code` and `.term-tip-def code` consistent with the report's existing
inline-code look.

## Testing

- **Unit tests** on `render_inline_markdown` (pure logic, not markup-pinning):
  HTML-escaping of `<` / `&`; each of the four emphasis patterns; code-span-wins-
  over-italic (`` `a*b` ``); unmatched/lone markers left literal; empty string;
  `\n` → `<br>`; `<br>` / `<br/>` / `<br />` passthrough; a non-`br` tag stays
  escaped (`<script>` → `&lt;script&gt;`, not re-admitted).
- **No markup-pinning Python tests** on the renderer or template, per AGENTS.md.
- **Playwright-verify** the rendered entry and a pill tooltip in a regenerated
  example (console clean after init; emphasis renders; `<` shows literally); and
  the glossary search — typing a term name filters the list, and a description
  with a newline/apostrophe no longer throws a console error or breaks filtering.
- Regenerate `examples/` (`nox -s examples`) and `self_report`
  (`nox -s self_report`); commit only reports whose content actually changed.

## Example touch

Add inline Markdown to one description in a `FileGlossary` example so the feature
is visible in the committed HTML — e.g. bold a key word, wrap a type name in
`` `code` ``, and add a `<br>` break in one term's description. The regenerated
example HTML then demonstrates the rendered emphasis and break.
