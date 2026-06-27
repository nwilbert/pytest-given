# File-backed Glossary — Design Spec

## Goal

Let a project use its existing `GLOSSARY.md` (the canonical artifact at the
repo root) as a pytest-given glossary, instead of declaring terms in code with
`g.actor(...)` / `g.work_object(...)` / `g.verb(...)`. A new `FileGlossary`
parses a standard Markdown glossary — one or more pipe tables — into the same
glossary model the rest of the system already consumes.

Two things make this more than a parser:

1. **Kind classification is optional in the file.** A glossary table usually
   has a term column and a description column, but no actor / work-object /
   verb column. So term *kind* must be either read from an optional column or
   **inferred from how terms are used in Domain Stories** — actor in the first
   slot, verb in the second, work object in a later slot — with a
   post-collection resolution pass that reconciles all usages and flags
   contradictions.
2. **Terms are accessed by name.** `g['Guest']` (case-insensitive) returns a
   handle usable directly in t-strings and stories, with no intermediate
   variable required.

This supersedes the "external glossary file formats (Markdown)" out-of-scope
line in the [Domain Storytelling spec](../2026-06-07-domain-storytelling-design.md).

## Scope

In:

- `FileGlossary(path, *, term_column=0, description_column=1, kind_column=None)`
  — parses a Markdown file at construction, composing an inner `Glossary`.
- Name-based, case-insensitive subscript access `g['Guest']` returning a single
  deferred-kind `FileTermHandle`, usable inline in t-strings and stories.
- A built-in GFM pipe-table parser (no new dependency).
- Optional `kind_column` for explicit classification; otherwise kind is left
  unresolved and filled by inference.
- An optional-kind model change: `GlossaryTerm.kind` becomes
  `Literal['actor', 'object', 'verb'] | None`.
- A **post-collection kind-resolution pass** over assembled stories that infers
  undeclared kinds from activity-slot positions, verifies declared kinds
  against observed positions, and errors on contradiction/conflict.
- Migration of activity parts onto a single `ActivityTermRef` (retiring
  `ActivityEntity` / `ActivityTerm`), mirroring the existing `NarrationTermRef`
  kind-by-lookup pattern.
- Neutral (uncoloured) rendering of kindless terms, in both story and t-string
  pills.

Out:

- **Generating `GLOSSARY.md` from a code-defined glossary** (the reverse
  direction) — its own later spec. See *Forward notes*.
- **Heading-scoped / sectioned tables.** v1 merges all tables in the file into
  one term set. Per-section grouping (and a grouped HTML glossary view) is
  deferred; it pairs naturally with the export feature. See *Forward notes*.
- Multiple files / multiple Bounded Contexts per suite — one `FileGlossary`
  wraps one glossary, same as the existing one-glossary-per-suite assumption.
  Different BCs use different files (and remain subject to the existing
  single-glossary-per-story invariant).
- YAML / JSON glossary formats.
- Changing `draft.*` — drafts stay kind-typed (`draft.actor` / `draft.work_object`
  / `draft.verb`). Kind inference applies only to `FileGlossary` terms.
- Adding name-subscript access to the code-defined `Glossary` (its `g[TermId]`
  semantics are unchanged).

## Background

Today (`src/pytest_given/capture/glossary.py`) a `Glossary` is mutable storage;
`g.actor()` / `g.work_object()` / `g.verb()` mint kind-typed handles
(`Actor` / `WorkObject` / `Verb`) that carry the kind eagerly. Those handles go
into t-strings and into `path(...)`, which validates the actor → verb → noun
grammar **eagerly by handle type** (`story.py:_check_position`). Terms record a
`source: SourceLocation` from their construction site.

Two model facts make file-backed glossaries cheap:

- `NarrationTermRef` (`schema.py:43`) already resolves a t-string pill's kind
  via `glossary[term_id].kind` — pills don't bake in a kind, they look it up.
- The `_REGISTERED_GLOSSARIES` registry (`glossary.py`) lets the plugin find the
  glossary without a side-channel, and coverage/story rollups key off
  `Glossary` instances and handles' `.glossary` back-ref.

So if `FileGlossary` registers an inner `Glossary` and the resolution pass sets
term kinds on it, every downstream consumer — Glossary tab, coverage, pills —
works unchanged.

## Components

### `FileGlossary`

```python
from pytest_given import FileGlossary

g = FileGlossary('GLOSSARY.md')                       # defaults: col 0 term, col 1 description
g = FileGlossary('GLOSSARY.md', kind_column='Kind')   # explicit kinds from a header
```

- **Composition, not subclassing.** `FileGlossary` owns an inner `Glossary`.
  At construction it parses the file, registers each row as a `GlossaryTerm`
  (kind from `kind_column` if present, else `None`), and registers the inner
  glossary into `_REGISTERED_GLOSSARIES`. The path used to discover "the"
  glossary (conftest-declared, glossary-only mode) is unchanged.
- **`g[name]` access** is case-insensitive. The name is run through the existing
  `id_derive` (which lowercases + slugs), so `g['Guest']`, `g['guest']`, and
  `g['GUEST']` resolve to the same term. Returns a single `FileTermHandle`
  (memoized per term id, so repeated subscripts are identical objects). Unknown
  name → `PytestGivenError` listing close matches.
- **Inline use.** `g['Guest']` is an expression returning a handle, usable
  directly in story activities (`activity(g['Guest'], g['searches'], g['Room'])`)
  and t-string step text
  (`t'{g["Guest"]} {g["searches"]("searches for")} a {g["Room"]}'`). No
  intermediate variable required.

### `FileTermHandle`

> **Superseded:** `FileTermHandle` is renamed `DeferredTermHandle` in [2026-06-27-glossary-draft-unification-design.md](2026-06-27-glossary-draft-unification-design.md).

One handle type for all file terms, regardless of kind (kind is deferred).

- Carries the `GlossaryTerm` and a back-ref to the inner `Glossary` (same shape
  as the existing `_TermHandle`), so `.id`, `.canonical`, `.glossary` work.
- Callable for per-use display: `g['Room']('Deluxe Suite')` (instance display)
  and `g['search']('searches for')` (verb inflection) both just set a display
  string — since kind is unknown, one call form covers both. Returns a
  display-bearing instance analogous to today's `ActorInstance` /
  `WorkObjectInstance` / `InflectedVerb`, but kind-agnostic.
- In `path(...)`, a `FileTermHandle` (and its display-instance) is **exempt from
  eager grammar validation** — position is informative, not constraining. It
  emits an `ActivityTermRef`. The resolution pass does the checking instead.
- In t-strings, it produces a `NarrationTermRef` exactly as code-defined handles
  do.

### Markdown parsing

- A small built-in GFM pipe-table parser (no new dependency). It recognises
  pipe tables (`| a | b |` with a `| --- | --- |` separator row), handles
  escaped `\|`, and **skips fenced code blocks** so `|` inside ```` ``` ````
  fences is not mistaken for a table.
- **All** pipe tables in the file contribute rows; rows are merged into one
  term set. Tables need not share a column layout beyond the columns the config
  selects.
- Column selection: `term_column` / `description_column` / `kind_column` each
  accept **a header name (str, case-insensitive) or a 0-based index (int)**.
  Defaults: term = column 0, description = column 1, kind = none.
- `kind_column` cell values map case-insensitively: `actor` → `actor`;
  `work object` / `work_object` / `object` → `object`; `verb` → `verb`; empty
  cell → unresolved (`None`). An unrecognised non-empty value is an error.
- Each term's `source` is `SourceLocation(file=<md path>, line=<row line>)`, so
  source-link anchors jump into `GLOSSARY.md` at the right row.
- Duplicate term id across rows: identical (kind, canonical, definition) is
  idempotent; any conflict is an error (mirrors `_register_kind`).
- A term cell that derives an empty id (no alphanumerics) is an error (reuses
  `id_derive`'s guard).

### Kind model + resolution pass

- `GlossaryTerm.kind` becomes `Literal['actor', 'object', 'verb'] | None`.
  `None` = unresolved / kindless.
- The resolution pass runs **once, post-collection, before serialization**, in
  the plugin's report assembly (where stories and glossaries are already
  gathered). For every term referenced by an `ActivityTermRef` it collects the
  set of activity-slot positions the term appears in across all stories, then:
  - **slot roles:** position 0 is the actor slot (requires actor); position 1
    is the verb slot (requires verb); position ≥ 2 is a noun slot (accepts
    actor *or* work object).
  - **conflict takes precedence over inference.** The verb slot is exclusive: a
    term seen at a verb slot *and* at any non-verb slot has no consistent kind
    → `PytestGivenError` naming the conflicting stories/sites.
  - **undeclared term, otherwise:** seen at a verb slot → `verb`; else seen at
    an actor slot (position 0) anywhere → `actor`; else seen only at noun slots
    → `object`; else (never used in a story) → stays `None` (kindless). I.e. *a
    noun-slot term is provisionally a work object, but an actor-slot appearance
    anywhere makes it an actor.*
  - **declared term** (from `kind_column`): the declared kind is kept, but every
    slot it appears in must be **compatible** with it — actor slot ⇒ actor,
    verb slot ⇒ verb, noun slot ⇒ actor or object. Any incompatible appearance
    (e.g. a declared verb in the actor or a noun slot; a declared object in the
    actor or verb slot; a declared actor in the verb slot) is an error.
- The resolved kind is written onto the inner glossary's `GlossaryTerm`s and
  baked into the serialized JSON. The renderer stays a pure lookup
  (`glossary[term_id].kind`).
- Note: a single self-consistent-but-grammatically-wrong story (e.g. noun in
  the actor slot, used nowhere else) is *not* caught by inference — that is the
  inherent limit of auto-mode and the reason `kind_column` exists. Documented,
  not guarded.

### Activity-part migration

Retire `ActivityEntity` and `ActivityTerm`; introduce one
`ActivityTermRef{term_id: TermId, display: str}`, mirroring `NarrationTermRef`.
Kind is resolved by lookup at render time, never stored on the part.

- `story.py:_to_part`: `Actor` / `WorkObject` / `Verb` and their instances, and
  `FileTermHandle` and its instance, all map to `ActivityTermRef`. `Draft*` →
  `ActivityPlaceholder` (unchanged). `str` → `ActivityWord` (unchanged).
- `path()` grammar validation (`_check_position`) still applies to the
  kind-typed code handles and drafts; `FileTermHandle` is exempt.
- `serde.py`: the `ActivityPart` discrimination collapses to three variants —
  `ActivityTermRef` (has `term_id`), `ActivityPlaceholder` (has `kind` + `text`),
  `ActivityWord` (has `text`).
- `renderer.py` / `coverage.py` / `aggregations.py`: anywhere that matched
  `ActivityEntity` / `ActivityTerm` now matches `ActivityTermRef` and reads kind
  via the glossary. Coverage's term-matching (step term-refs ↔ activity
  term-refs) compares `term_id`s, which both variants already carried — so the
  matching logic simplifies rather than changes behaviour.

### Rendering

- `kind = None` → a neutral, uncoloured pill (no actor / object / verb styling),
  for both story `ActivityTermRef`s and t-string `NarrationTermRef`s. A new
  neutral CSS class alongside the existing kind colours.
- Per AGENTS.md, kindless-pill rendering is verified in Playwright on
  regenerated `examples/`, not pinned in Python tests.

## Errors

All `PytestGivenError` with actionable messages:

- File not found / unreadable.
- No parseable pipe table in the file.
- Named column not found in a table; or a table with too few columns for the
  configured indices.
- Unrecognised `kind_column` value.
- Empty-id term cell.
- Duplicate term with conflicting definition/kind.
- Declared kind contradicted by observed slot positions.
- Inference conflict (term used in incompatible slots).
- Unknown name in `g[name]` (with close-match suggestions).

## Testing

- **Parser (pure functions):** term/description/kind extraction; multiple
  tables merged; column-by-name vs by-index; default columns; escaped `\|`;
  fenced-code-block skipping; missing column; unrecognised kind value.
- **Resolution pass (pure function over assembled stories):** each inference
  branch (verb / actor-anywhere / noun→object / never-used→kindless);
  declared-vs-observed contradiction; cross-story conflict; declared kinds
  verified and passed through.
- **`FileGlossary` API:** case-insensitive lookup; memoized handle identity;
  inline use in `activity(...)` and t-strings; unknown-name error; source
  locations point into the file.
- **Integration:** a realistic `GLOSSARY.md`-shaped fixture + a story + a
  scenario; assert on the data-shaped contract (resolved kinds, term ids,
  coverage) — not on markup.
- **Migration regression:** existing story/coverage/serde tests updated to the
  `ActivityTermRef` shape; round-trip serde for the collapsed `ActivityPart`
  union.
- Run `uv run nox -s examples` to regenerate `examples/` and Playwright-verify
  neutral kindless pills; commit regenerated JSON.

## Forward notes (out of scope, recorded for later)

- **`GLOSSARY.md` export** from a code-defined glossary (reverse direction). At
  that point it's natural to emit one table per glossary **section**, which in
  turn motivates:
- **Sectioned glossaries** — heading-scoped tables on input, surfaced as grouped
  sections in the HTML Glossary view. v1 deliberately flattens; this is the
  upgrade path.
