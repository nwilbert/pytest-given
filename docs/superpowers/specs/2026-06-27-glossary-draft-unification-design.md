# Glossary Draft Unification — Design Spec

## Goal

Delete the `draft` concept. Today "unsettled vocabulary" is a separate
subsystem — `draft.actor/work_object/verb(...)` mint kind-typed `Draft*`
placeholders that become `ActivityPlaceholder` parts, are rejected in step
narrations, and are hard-excluded from coverage. This is a second, parallel
vocabulary model that exists only because drafts have no glossary identity.

Replace it with one model: an **ordinary glossary term that may lack a kind
and/or a definition**. "Draftness" stops meaning *"this vocabulary does not
exist yet"* (no id, excluded from coverage, dashed pill) and becomes *"this
term exists but is not yet classified and/or documented"* (real id, surfaced
and filterable in the report). One vocabulary model instead of two.

Two accessors carry the new ergonomics on the existing code-defined glossary
`g`:

1. **`g("foo")` — declare-or-get.** Mints a *kindless* term if new, returns the
   existing term if present (leaning on today's idempotent registration). This
   is the lightweight path that replaces `draft.*`: no kind. It takes an
   optional `definition` (`g("foo", definition=…)`) — kindless does not imply
   undefined.
2. **`g["foo"]` — get-only.** References a term named elsewhere; raises on an
   unknown name (with a did-you-mean hint), as a typo guard.

Term *kind* is then filled by the **existing** post-collection inference pass
(`resolve_glossary_kinds`) from story slot-positions — the exact mechanism the
[file-backed glossary](2026-06-18-file-backed-glossary-design.md) introduced,
now generalized from file-only terms to all terms.

This **supersedes** the draft design in the
[Domain Storytelling spec](2026-06-07-domain-storytelling-design.md) (`Draft*`
handles, `ActivityPlaceholder`, the `draft.*` factory, the narration rejection,
and the "drafts excluded from coverage" rule). It also supersedes two
out-of-scope lines in the
[file-backed glossary spec](2026-06-18-file-backed-glossary-design.md): "Changing
`draft.*`" and "Adding name-subscript access to the code-defined `Glossary`".

## Scope

In:

- **`g("foo")` declare-or-get** on the code-defined `Glossary` — mints a
  kindless term (`kind=None`) if new, else returns the existing term (idempotent,
  per `terms_match`). Accepts an optional `definition` keyword
  (`g("foo", definition=…)`, default `None`); the term is always kindless but
  may carry prose. Returns a deferred-kind handle usable inline in stories and
  t-strings.
- **`g["foo"]` get-only** on the code-defined `Glossary` — name-based,
  case-insensitive lookup returning the same deferred-kind handle; raises
  `PytestGivenError` with a did-you-mean hint on an unknown name. Replaces the
  current low-level `g[TermId] -> GlossaryTerm` subscript.
- **Deletion of the `draft` subsystem:** `capture/draft.py`,
  `DraftActor/DraftWorkObject/DraftVerb`, the `draft` factory, the
  `ActivityPlaceholder` model node, the `_to_part` draft branch, and the
  `_reject_draft_in_narration` block in `capture/template.py`.
- **Coverage:** remove the `a_refs`-returns-`None`-on-placeholder exclusion in
  `report/coverage.py`. Every activity now participates in matching, since all
  terms have ids.
- **Report:** make definition-less terms visually flagged and filterable
  (the *"No definition yet."* state already renders) alongside the existing kind
  filters; kindless terms already render in the *Uncategorized* bucket.
- **Story grammar formalized as a node/edge alternation:** even positions
  (0, 2, 4, …) are entity **nodes** (actors / work objects); odd positions
  (1, 3, 5, …) are **edges** — a verb handle or a bare-string connective. A path
  alternates node / edge / node …, has an **odd length ≥ 3**, starts with an
  actor, and ends on a node. This replaces the current "free-form beyond
  position 2" rule and makes a path directly convertible to a Domain
  Storytelling graph (nodes + labelled edges).
- **`definition` becomes `str | None`** (default `None`): models "undefined"
  as a first-class state parallel to `kind: … | None`, with boundary
  normalization (`''` / whitespace-only → `None`) so there is exactly one
  representation.
- **Migration** of the `hotel-booking` example and docs off `draft.*`.

Out:

- **An ambient/default glossary.** An explicit `g` is still required (decision
  A). `g("foo")` is the lightweight path *on that object*; there is no
  zero-setup global.
- **`g("foo")` creating on a file-backed glossary.** A `FileGlossary` is a
  closed vocabulary: both `g["foo"]` and `g("foo")` raise on an unknown name.
  In-code creation is code-glossary-only.
- **A kind supplied via `g("foo")`.** The call form is kindless by design (kind
  is left to inference); use `g.actor/work_object/verb("foo", definition=…)`
  when you want to *state* a kind in code. A definition, by contrast, *is*
  accepted on `g("foo")`.
- **A separate "promote me" / drafts worklist view.** Surfacing undefined
  terms reuses the existing Glossary view + a filter; no new tab.

## Background

- **Code glossary.** `src/pytest_given/capture/glossary.py` monkey-patches
  `actor` / `work_object` / `verb` onto the model `Glossary`; each mints an
  eager kind-typed handle (`Actor` / `WorkObject` / `Verb`). Registration
  (`_register_kind`) is already idempotent: re-registering a matching
  `(kind, canonical, definition)` returns the existing term; a conflicting one
  raises. The user-facing `g` *is* the raw model `Glossary`, whose
  `__getitem__` today is the low-level `TermId -> GlossaryTerm` index
  (`model/schema.py:161`).
- **File glossary.** `capture/file_glossary.py` already provides the target
  shape: a single **deferred-kind** `FileTermHandle` (one type for all kinds),
  name-based `g['Guest']` access that raises on unknown with a did-you-mean
  hint, and `kind=None` until resolved. Nothing in its body is file-specific —
  it is just `TermHandle` + `__call__` — so it generalizes by renaming (below).
- **Kind inference.** `capture/kind_resolution.py::resolve_glossary_kinds`
  already runs over the merged glossary for *every* registered glossary
  (`plugin.py:421`), inferring `None` kinds from activity slot-positions
  (0 → actor, 1 → verb, ≥2 → object; "leads a path at least once" wins → actor)
  and verifying declared kinds. Kindless terms (`kind=None`) are already a
  first-class model state and already render in the report's *Uncategorized* bucket
  (`selectattr('kind', 'none')`).
- **Drafts.** `capture/draft.py` mints `Draft*` placeholders → `_to_part`
  produces `ActivityPlaceholder(kind, text)` (no id). `coverage.py::a_refs`
  returns `None` for any activity containing one (hard coverage-exclusion).
  `template.py::_reject_draft_in_narration` blocks drafts in step narrations.

The asymmetry the file-glossary spec deliberately left in place — *"drafts stay
kind-typed; kind inference applies only to `FileGlossary` terms"* — is exactly
what this spec removes. Drafts were the only vocabulary without identity; once
every term has an id, the placeholder node, the narration rejection, and the
coverage special-case all lose their reason to exist.

## Design

### Accessor model

| Form | Meaning | Unknown name | Kind | Definition |
| --- | --- | --- | --- | --- |
| `g("foo", definition=…)` | declare-or-get | *creates* (code glossary) | inferred | optional (default `None`) |
| `g["foo"]` | get-only | *raises* (typo guard) | — | — |
| `g.actor/work_object/verb("foo", definition=…)` | explicit | creates | declared | optional |

- Both `g("foo")` and `g["foo"]` return a **deferred-kind handle** — the same
  handle type the file glossary already uses, generalized by renaming
  `FileTermHandle` → `DeferredTermHandle` (see *Deletions and model changes*).
  The plan unifies on one deferred handle rather than introducing a second.
- `g("foo")` is idempotent: a later `g.verb("foo")` or `g("foo")` for the same
  name returns/refines the same term (subject to the existing `terms_match`
  conflict rule).
- A term created via `g("foo")` and used only in scenario narration (never in a
  story slot) is never reached by inference and stays **kindless → *Uncategorized***.
  That is the intended replacement for "a draft verb referenced in a scenario".

### Handle and subscript integration

The user-facing `g` is the raw model `Glossary`, so two things change there:

- **`__getitem__` is repurposed** from `TermId -> GlossaryTerm` (low-level) to
  name-based `str -> <deferred handle>` that raises on unknown. Internal callers
  that index by `TermId` move to the explicit `Glossary.get(term_id)` /
  `_by_id` accessors (which already exist and are what coverage/aggregations
  use). `__call__` is added for declare-or-get.
- The deferred handle minted by `g("foo")` / `g["foo"]` must be **directly
  usable** in `path()` and t-strings. `_to_part` and `_try_term_ref` already
  accept `FileTermHandle` / `FileTermInstance` (renamed to `DeferredTermHandle` /
  `DeferredTermInstance`); the unified handle slots into the same match arms. The
  eager `Actor`/`WorkObject`/`Verb` handles minted by the explicit `g.actor(...)`
  API remain valid.

### Story grammar

A `path()` is a node/edge alternation so it maps directly onto a Domain
Storytelling graph:

- **Even positions (0, 2, 4, …) are entity nodes** — an actor or work-object
  handle. Position 0 is specifically an actor (the "leads a path" rule). A bare
  `str` is **not** allowed at an even position; vocabulary is always a handle
  (`g(...)`, `g[...]`, `g.actor(...)`, or an instance), never a bare string —
  auto-promoting bare strings would reintroduce the typo-safety hole and the
  draft-by-accident problem.
- **Odd positions (1, 3, 5, …) are edges** — either a verb handle (a labelled
  arrow) or a bare-string connective (`'to'`, `'into'`), which stays an
  `ActivityWord`. Position 1 specifically must be a verb (the leading
  actor → verb → noun triple); later odd positions may be either.

> **Superseded (2026-06-27):** these two rules are relaxed by
> [Bare Strings in Activity Paths](bare-strings-in-activity-paths-design.md) — a
> bare `str` is now accepted at any position (including the verb slot and node
> positions), and the two-term rule is a coverage-eligibility threshold rather
> than a construction constraint.

- A path **alternates** node / edge / node …, has an **odd length ≥ 3**, and
  ends on a node. A path that ends on an edge (even length, dangling arrow) is
  rejected. Multi-arrow activities continue to use multiple `path()` calls.

This replaces today's "free-form beyond position 2" rule (spec line 185 of the
Domain Storytelling design), which permitted additional verbs and nouns in any
order and so could not be turned into a node/edge graph.

**Kind-inference slot mapping updates to match.** `kind_resolution._slot_for`
currently maps only position 1 → verb and everything ≥2 → noun; under the
alternation it becomes: position 0 → actor, **odd → verb**, even ≥2 → noun.
Connectives are `ActivityWord` (no `term_id`) and never reach inference, so any
*term* at an odd position is a verb.

### Coverage

`a_refs` drops its placeholder check and the early `None` return; an activity's
identity set is built from its `ActivityTermRef` parts as today. Every activity
is eligible for matching. The former "stays visibly uncovered" demonstration
(hotel-booking activity 7) is re-expressed as "stays visibly *undefined*" via
the report flag below — a term/activity can now legitimately be covered while
still lacking a definition.

### Definition as `str | None`

`GlossaryTerm.definition` becomes `str | None` (default `None`) so
"undefined" is a first-class state, parallel to `kind: … | None` for
"kindless". To keep exactly one representation, the value is **normalized at
the boundaries**: `_register_kind` and `FileGlossary._add_row` map an empty or
whitespace-only definition to `None` (a blank description cell, which parses to
`''` today, becomes `None`). The constructors flip their default —
`g.actor/work_object/verb(name, definition: str | None = None)` and likewise
`g(name, definition: str | None = None)` — `definition` is an ordinary
positional-or-keyword argument (not keyword-only) — all routed through the same
boundary normalization.

Touchpoints: `serde` read becomes `d.get('definition')` and write omits the key
(or emits `null`); `terms_match` (`None == None`) and the template's
`{% if term.definition %}` keep working unchanged; the Glossary search filter
(`report.html.j2:469`) concatenates `term.definition`, so it must guard with
`(term.definition or '')` to avoid a `None`-concatenation error. The report's
"undefined" test is `definition is None`.

### Report

- **Undefined flag.** Terms whose `definition is None` get a visible marker
  in the Glossary view (the *"No definition yet."* placeholder already renders;
  promote it from a faint hint to a deliberate badge).
- **Filter.** Add an "undefined" toggle next to the existing kind filters so
  a reader can isolate the terms that still need prose. Kindless terms continue
  to appear in the existing *Uncategorized* group; no new tab or view.
- **Rename the kindless bucket label** from *Other* to *Uncategorized* (the
  visible group heading, the filter row, and the summary count at
  `report.html.j2:428/444/453`). The internal `kindless` filter key / CSS
  (`glossaryKindFilter.kindless`, `kind-swatch-kindless`) is unchanged.
- **Orthogonal flags.** A term can be both kindless and undefined, so the two
  read as independent signals: it sits in the *Uncategorized* group *and* carries
  an undefined badge — not one or the other.
- All report changes are template/CSS/`app.js` and are verified with Playwright
  (the data-shaped contract — aggregations / kindless bucket — keeps its Python
  tests).

### Deletions and model changes

- Remove `capture/draft.py` and its test, `DraftActor/DraftWorkObject/
  DraftVerb`, and the `draft` export from the package surface.
- Remove `ActivityPlaceholder` from the model, its `_to_part` branch, its
  renderer arm (the `is-draft` pill path), and its serialization. `is-draft`
  CSS is retired. `NarrationPlaceholder` (the `{name:spec}` parameter token) is
  unrelated and stays.
- Remove `_reject_draft_in_narration`. A vocabulary handle in a t-string is
  always a real term ref now.
- **Rename the deferred handle to a kind-neutral name.** `FileTermHandle` →
  `DeferredTermHandle` and `FileTermInstance` → `DeferredTermInstance`, moved to
  `capture/glossary.py` next to `TermHandle` (the shared base) so neither code
  nor file glossary owns it. `FileGlossary` imports and mints the renamed class
  instead of defining its own; the code glossary's `__call__` / `__getitem__`
  mint the same type. Nothing in the body changes — it is purely a name + home
  move, plus updating `_to_part` / `_try_term_ref` match arms and any imports.

## Error handling

- **`g["foo"]` unknown name** (code or file glossary) → `PytestGivenError` with
  a `difflib` did-you-mean hint, matching today's `FileGlossary.__getitem__`.
- **`g("foo")` on a file-backed glossary, unknown name** → same raise; the file
  is authoritative, so the call form does not create.
- **Kind conflict** (a term used in incompatible slots, or declared kind vs
  observed position) → unchanged `resolve_glossary_kinds` errors.
- **Registration conflict** (same name, conflicting kind/definition) →
  unchanged `_register_kind` / `terms_match` error.
- **Grammar violations** → `PytestGivenError`: a bare string or verb at an even
  (node) position; a non-verb-non-connective at an odd (edge) position; a path
  ending on an edge (even length / dangling arrow). Messages name the offending
  position and suggest the fix (wrap as a handle, or split into another
  `path(...)`).

## Testing

- **Accessors:** `g("foo")` creates-then-reuses (idempotent); `g["foo"]` raises
  with hint on unknown; `g("foo")` on a `FileGlossary` raises; a handle from
  either form is usable in `path()` and a t-string.
- **Inference:** a `g("foo")` term used at a verb slot resolves to verb; used
  only in a scenario stays kindless; the actor-leads-a-path rule still holds via
  existing `kind_resolution` tests.
- **Coverage:** an activity built entirely from `g(...)` terms is now matchable;
  the former placeholder-exclusion test is removed/replaced.
- **Grammar:** node/edge alternation validates (`actor verb object 'to' actor`,
  `actor verb object verb object`); a bare string or verb at an even position
  raises; an even-length path (dangling edge) raises; `_slot_for` maps an
  odd-position verb to the verb slot.
- **Definition:** empty / whitespace-only definitions normalize to `None` from
  both the typed constructors and a blank `FileGlossary` cell; serde round-trips
  `None`.
- **Report:** Playwright — undefined badge shows when `definition is None`,
  the undefined filter isolates those terms, kindless terms appear in *Uncategorized*.

## Migration

Pre-release: no compatibility shims (per project policy). Rewrite the
`hotel-booking` example to drop `draft.*` — activity 7's `draft.verb('redeems')`
/ `draft.work_object('loyalty points')` become `g('redeems')` / `g('loyalty
points')` (kindless until inferred), demonstrating the new undefined state.
Update `README` references and any prose in the two prior specs that describes
drafts as current behavior.

### `GLOSSARY.md` updates

The project glossary (`GLOSSARY.md`, *Domain Storytelling* section) is updated in
the same commit as the code (per its update rule):

- **Remove `Draft`.** The placeholder vocabulary concept is gone.
- **Remove the `ActivityPlaceholder` variant from `ActivityPart`** — it becomes a
  three-variant union (`ActivityEntity` / `ActivityTerm` / `ActivityWord`).
- **Replace `FileTermHandle`** with **`DeferredTermHandle`**: the deferred-kind
  handle returned by *both* the code glossary (`g('foo')` declare-or-get,
  `g['foo']` get-only) and a `FileGlossary` (`g['Guest']`). Kind is `None` until
  the post-collection resolution pass runs.
- **Amend `Glossary` (capitalized)** to list the two accessor forms — `g('foo')`
  (declare-or-get a kindless term, optional `definition=`) and `g['foo']`
  (get-only, raises on an unknown name) — alongside the typed
  `.actor/.work_object/.verb` methods.
- **Amend `Term`** so the definition is "an optional definition (`str | None`,
  `None` when undefined)".
- **Add `Kindless`** — a term with `kind=None` (no actor/object/verb classification
  yet); inferred from story slot positions, and shown in the report's
  *Uncategorized* bucket when inference leaves it unset.
- **Add `Undefined`** — a term with `definition is None` (no prose yet);
  surfaced by a badge and a filter in the Glossary view. Orthogonal to *kindless*.
- **Add `Uncategorized`** (report term) — the Glossary-view bucket for kindless
  terms; renamed from the former *Other*.

## Forward notes

- **`g("foo")` kind at the call site.** `g("foo")` already takes `definition`;
  if a future need arises to also state a kind without the typed methods,
  `g("foo", kind=…)` is a natural extension, left out of v1 so the call form
  stays unambiguously "lightweight kindless".
- **Promote-to-file workflow.** With drafts gone, "promote" becomes "add a
  definition (and let the kind infer)". A future export feature could surface
  undefined terms as a checklist for writing them into `GLOSSARY.md`.
