# Inline Markdown in Glossary Term Descriptions — Design Spec

## Goal

Render a small set of inline Markdown in glossary term **descriptions** so prose
reads the way it was authored:

- `**bold**` and `__bold__` → `<strong>`
- `*italic*` → `<em>`
- `` `code` `` → `<code>`

This is the exact four-pattern set the existing `capture/markdown_glossary.py`
`_EMPHASIS` regex already recognises (and *strips* from term/kind cells). A
description authored as `A **VIP** guest who books a Room` currently shows the
markers literally; after this change `**VIP**` renders bold.

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

The description is rendered in **three** places, all of which currently show
Markdown markers literally:

1. **Glossary-tab entry** (`report.html.j2`, the `.entry-def` block) —
   `{{ term.definition if term.definition else '' }}`, Jinja-autoescaped.
2. **Hover tooltip** on every term pill across the report — `renderer.py`
   `_term_pill` emits `data-term-def="{escape(tooltip_def)}"`; `app.js`
   `_initTermTooltip` sets `defEl.textContent = pill.dataset.termDef`.
3. **Search-match string** (`report.html.j2` entry `x-show`) —
   `(term.canonical + ' ' + (term.definition or '')) | lower`, matched against
   `glossarySearch`.

## Approach

A single pure render-time function converts inline Markdown to safe HTML;
consumers 1 and 2 render that HTML, consumer 3 keeps the raw plain text.

### `report/inline_markdown.py` (new)

```python
def render_inline_markdown(text: str) -> str:
    """Escape `text` for HTML, then render **bold** / __bold__ / *italic* /
    `code` as <strong>/<em>/<code>. Returns a safe HTML string."""
```

- HTML-escape the whole string first (`markupsafe.escape` / `html.escape`), so
  `<`, `>`, `&` in a description are always literal and code-span content is
  escaped.
- Then one left-to-right `re.sub` over a combined alternation with the **code
  span first** — `` `(.+?)` `` | `\*\*(.+?)\*\*` | `__(.+?)__` | `\*(.+?)\*` —
  so `` `a*b` `` renders as code without italicising its interior. A single
  non-overlapping pass (not the stabilise-loop `_strip_emphasis` uses); nested
  bold-in-code / bold+italic combinations are out of scope.
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
3. **Search** — unchanged. The raw description text stays the match target, so
   searching `VIP` still hits `A **VIP** guest`.

### CSS

`<strong>` / `<em>` use browser defaults. Add minimal monospace styling for
`.entry-def code` and `.term-tip-def code` consistent with the report's existing
inline-code look.

## Testing

- **Unit tests** on `render_inline_markdown` (pure logic, not markup-pinning):
  HTML-escaping of `<` / `&`; each of the four patterns; code-span-wins-over-
  italic (`` `a*b` ``); unmatched/lone markers left literal; empty string.
- **No markup-pinning Python tests** on the renderer or template, per AGENTS.md.
- **Playwright-verify** the rendered entry and a pill tooltip in a regenerated
  example (console clean after init; emphasis renders; `<` shows literally).
- Regenerate `examples/` (`nox -s examples`) and `self_report`
  (`nox -s self_report`); commit only reports whose content actually changed.

## Example touch

Add inline Markdown to one description in a `FileGlossary` example so the feature
is visible in the committed HTML — e.g. bold a key word and wrap a type name in
`` `code` `` in one term's description. The regenerated example HTML then
demonstrates the rendered emphasis.
