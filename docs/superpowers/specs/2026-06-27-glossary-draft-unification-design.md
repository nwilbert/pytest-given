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
   is the lightweight path that replaces `draft.*`: no kind, no definition.
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
  kindless term (`kind=None`, `definition=''`) if new, else returns the existing
  term (idempotent, per `terms_match`). Returns a deferred-kind handle usable
  inline in stories and t-strings.
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
  filters; kindless terms already render in the *Other* bucket.
- **Tail-grammar tightening:** a single `path()` carries at most one verb (the
  position-1 arrow); additional verbs in the tail are no longer accepted.
  Multi-arrow activities use multiple `path()` calls, as today. This keeps
  position-inference unambiguous and aligns with Domain Storytelling's
  one-verb-per-arrow model.
- **Migration** of the `hotel-booking` example and docs off `draft.*`.

Out:

- **An ambient/default glossary.** An explicit `g` is still required (decision
  A). `g("foo")` is the lightweight path *on that object*; there is no
  zero-setup global.
- **`g("foo")` creating on a file-backed glossary.** A `FileGlossary` is a
  closed vocabulary: both `g["foo"]` and `g("foo")` raise on an unknown name.
  In-code creation is code-glossary-only.
- **Definitions supplied via `g("foo")`.** The call form is kindless and
  definition-less by design; use `g.actor/work_object/verb("foo",
  definition=…)` when you want to state a kind and/or prose in code.
- **A separate "promote me" / drafts worklist view.** Surfacing undocumented
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
  hint, and `kind=None` until resolved.
- **Kind inference.** `capture/kind_resolution.py::resolve_glossary_kinds`
  already runs over the merged glossary for *every* registered glossary
  (`plugin.py:421`), inferring `None` kinds from activity slot-positions
  (0 → actor, 1 → verb, ≥2 → object; "leads a path at least once" wins → actor)
  and verifying declared kinds. Kindless terms (`kind=None`) are already a
  first-class model state and already render in the report's *Other* bucket
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
| `g("foo")` | declare-or-get | *creates* (code glossary) | inferred | `''` |
| `g["foo"]` | get-only | *raises* (typo guard) | — | — |
| `g.actor/work_object/verb("foo", definition=…)` | explicit | creates | declared | optional |

- Both `g("foo")` and `g["foo"]` return a **deferred-kind handle** — the same
  handle type the file glossary already uses. The plan unifies on one deferred
  handle rather than introducing a second.
- `g("foo")` is idempotent: a later `g.verb("foo")` or `g("foo")` for the same
  name returns/refines the same term (subject to the existing `terms_match`
  conflict rule).
- A term created via `g("foo")` and used only in scenario narration (never in a
  story slot) is never reached by inference and stays **kindless → *Other***.
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
  accept `FileTermHandle` / `FileTermInstance`; the unified handle slots into
  the same match arms. The eager `Actor`/`WorkObject`/`Verb` handles minted by
  the explicit `g.actor(...)` API remain valid.

### Story grammar

`path()` keeps the leading-triple rule (actor → verb → noun). The tail tightens:
nodes (actors / work objects) and bare-string connectives only — **no second
verb** in a single path. A bare `str` in any position remains an `ActivityWord`
connective (unchanged); it is never auto-promoted to a term (that would
reintroduce the typo-safety hole and the draft-by-accident problem). Vocabulary
in a path is always a handle (`g(...)`, `g[...]`, `g.actor(...)`, or an
instance), never a bare string.

### Coverage

`a_refs` drops its placeholder check and the early `None` return; an activity's
identity set is built from its `ActivityTermRef` parts as today. Every activity
is eligible for matching. The former "stays visibly uncovered" demonstration
(hotel-booking activity 7) is re-expressed as "stays visibly *undocumented*" via
the report flag below — a term/activity can now legitimately be covered while
still lacking a definition.

### Report

- **Undocumented flag.** Terms with an empty `definition` get a visible marker
  in the Glossary view (the *"No definition yet."* placeholder already renders;
  promote it from a faint hint to a deliberate badge).
- **Filter.** Add an "undocumented" toggle next to the existing kind filters so
  a reader can isolate the terms that still need prose. Kindless terms continue
  to appear in the existing *Other* group; no new tab or view.
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

## Error handling

- **`g["foo"]` unknown name** (code or file glossary) → `PytestGivenError` with
  a `difflib` did-you-mean hint, matching today's `FileGlossary.__getitem__`.
- **`g("foo")` on a file-backed glossary, unknown name** → same raise; the file
  is authoritative, so the call form does not create.
- **Kind conflict** (a term used in incompatible slots, or declared kind vs
  observed position) → unchanged `resolve_glossary_kinds` errors.
- **Registration conflict** (same name, conflicting kind/definition) →
  unchanged `_register_kind` / `terms_match` error.
- **Second verb in a single `path()`** → `PytestGivenError` from the tightened
  grammar check, suggesting a separate `path(...)` call.

## Testing

- **Accessors:** `g("foo")` creates-then-reuses (idempotent); `g["foo"]` raises
  with hint on unknown; `g("foo")` on a `FileGlossary` raises; a handle from
  either form is usable in `path()` and a t-string.
- **Inference:** a `g("foo")` term used at a verb slot resolves to verb; used
  only in a scenario stays kindless; the actor-leads-a-path rule still holds via
  existing `kind_resolution` tests.
- **Coverage:** an activity built entirely from `g(...)` terms is now matchable;
  the former placeholder-exclusion test is removed/replaced.
- **Grammar:** a two-verb single `path()` raises; a tail of nodes + connectives
  validates.
- **Report:** Playwright — undocumented badge shows for definition-less terms,
  the undocumented filter isolates them, kindless terms appear in *Other*.

## Migration

Pre-release: no compatibility shims (per project policy). Rewrite the
`hotel-booking` example to drop `draft.*` — activity 7's `draft.verb('redeems')`
/ `draft.work_object('loyalty points')` become `g('redeems')` / `g('loyalty
points')` (kindless until inferred), demonstrating the new undocumented state.
Update `GLOSSARY.md`/`README` references and any prose in the two prior specs
that describes drafts as current behavior.

## Forward notes

- **`g("foo")` definitions / kinds.** If a future need arises to attach a
  definition or kind at the call site without the typed methods, `g("foo",
  definition=…, kind=…)` is a natural extension; left out of v1 to keep the call
  form unambiguously "lightweight kindless".
- **Promote-to-file workflow.** With drafts gone, "promote" becomes "add a
  definition (and let the kind infer)". A future export feature could surface
  undocumented terms as a checklist for writing them into `GLOSSARY.md`.
