# Bare Strings in Activity Paths — Design Spec

## Goal

Allow a bare `str` at **any** position of an activity `path()`. Today a bare
string is accepted only at odd positions ≥ 3 (a connective like `'to'`);
position 0, position 1 (the verb), and every even node position require a
glossary handle. This relaxes that so the verb slot — and any slot — may be a
plain word.

A bare string is **label text with no glossary identity**: no id, no kind,
never registered in the glossary, never classified by inference. This is the
gap left when `draft.*` was deleted — there is currently no way to put a word
the team has *not* promoted to ubiquitous language onto an activity arrow
(e.g. a one-off `'receives'`). Drafts used to fill it; bare words fill it now,
without a second vocabulary model.

Paired with a **coverage-eligibility threshold**: any activity is
constructible, including an all-bare one, but an activity with fewer than **two
distinct glossary terms** does not participate in scenario-coverage matching —
it renders in a neutral "not coverage-tracked" state instead. The threshold
governs *coverage matching*, not authoring: it does not gate what you may write,
only where coverage carries enough signal to be meaningful.

This **supersedes** two grammar rules in the
[draft-unification spec](2026-06-27-glossary-draft-unification-design.md):

- *"Position 1 specifically must be a verb."*
- *"A bare `str` is **not** allowed at an even position."*

## Background

- **Grammar** (`capture/story.py::path`): a node/edge alternation — even
  positions (0, 2, …) are entity nodes, odd positions (1, 3, …) are edges. Odd
  length ≥ 3, starts on an actor, ends on a node. A bare `str` dispatches to
  `ActivityWord` via `_to_part`, but `path()` only *accepts* one at odd
  positions ≥ 3; positions 0, 1 and even positions raise.
- **`ActivityWord` already flows everywhere.** It is position-agnostic
  downstream: `serde` round-trips it; `coverage.identity_of_part` returns
  `None` for it (`coverage.py:61`); `aggregations` guards term collection with
  `isinstance(part, ActivityTermRef)` (`aggregations.py:220`); the renderer
  emits a muted `activity-word` span for any word (`renderer.py:310`). None of
  them assume a word only appears on an edge. So allowing bare words is confined
  to **grammar validation** — the model, serde, aggregations, and the
  per-part renderer need no change. (Coverage matching and the per-activity
  coverage chip do change, but for the eligibility threshold below, not because
  of where words appear.)
- **Coverage degenerate case.** `a_refs` builds an activity's identity set from
  its `ActivityTermRef` parts. An activity with an empty set falls into the
  `matches_any_step` branch (`coverage.py:126–132`) — "covered by every
  in-scope step," which is meaningless. Bare nodes make that case reachable in
  practice; the eligibility threshold below removes it (such activities are
  excluded from matching, not matched against everything).

## Design

### Grammar — words carry no role

- A bare `str` is accepted at **every** position and becomes an `ActivityWord`.
  It is **not** assigned a role: no actor/noun/verb requirement is imposed on a
  word. Imposing one would pretend a word is vocabulary and blur the line
  against kindless/undefined terms (see below).
- **Handle-kind guards remain — for handles only.** If you pass a *typed
  handle*, it must suit the slot, because a misplaced typed term is a real
  mistake worth catching:
  - **Position 0:** an actor-ish handle (`Actor` / `ActorInstance` /
    `DeferredTermHandle` / `DeferredTermInstance`). A `WorkObject` or `Verb`
    handle raises.
  - **Odd positions:** a verb-ish handle (`Verb` / `InflectedVerb` /
    `Deferred…`). An `Actor` / `WorkObject` handle raises.
  - **Even positions ≥ 2:** a node handle. A `Verb` / `InflectedVerb` handle
    raises.

  `DeferredTermHandle` (the kindless `g('foo')` / `g['foo']` / file-glossary
  handle) is valid at both node and edge positions, as today — only eagerly
  kind-typed handles are slot-checked.
- **Alternation shape is unchanged:** odd length ≥ 3, ends on a node position. A
  bare word may occupy the final position; the shape rule still rejects an
  even-length path (a dangling trailing edge). The shape is about
  graph-convertibility, not about any word's role.
- `_suggestion_for` drops its *"Wrap the noun as a glossary term"* branch (that
  advice is now wrong — a bare noun is allowed). Remaining messages fire only
  for wrong-kind handles and name the offending slot + handle kind.

### The distinction this preserves

Words are deliberately left unclassified so they stay distinct from the two
term states the draft-unification spec introduced:

| Kind of part | id? | in glossary? | classified? |
| --- | --- | --- | --- |
| **Bare word** (`'receives'`) | no | no | never — it is just text |
| **Kindless term** (`g('redeems')`) | yes | yes | by slot-position inference |
| **Undefined term** (`definition is None`) | yes | yes | kind yes, prose no |

A word never enters inference (it has no `term_id`), never appears in the
Glossary view, and renders as muted `activity-word` text — visually
distinguishable from a tracked term's pill.

### Coverage eligibility threshold

Authoring is **not** gated — any activity is constructible, including an
all-bare one. The threshold governs *coverage matching only*:

- **An activity is eligible for coverage only if it has ≥ 2 distinct glossary
  term refs** — i.e. ≥ 2 distinct `ActivityTermRef.term_id` values across all of
  its paths. ("distinct" guards the same-term-twice loophole.) An ineligible
  activity (0 or 1 distinct term) is **excluded from matching**: it never
  matches a step and never appears as covered.
- Eligibility is computed **eagerly** from the constructed parts — no glossary
  or kind inference needed (term refs carry their `term_id` already).
- **Rationale:** coverage is a derived, best-effort signal; it should assert a
  match only where there is enough vocabulary to make one meaningful. The
  entities anchoring an activity (the DS-graph nodes) are what coverage matches
  on, so two real anchors is the floor for a meaningful match. For a minimal
  `actor → verb → object`, that means actor and object are terms and the verb may
  be a word — exactly the `g['Guest'], 'receives', g['Confirmation']` case
  (2 terms). Threshold is **2**, not 3, because 3 would exclude that very case
  (only longer paths could then carry a bare verb). It is a *threshold*, not a
  constructor `raise`, so it never gates expression — you can sketch a story in
  bare words and watch coverage light up as you promote nodes to terms.

### Coverage and rendering consequence

- **`compute_coverage` skips ineligible activities** (those with < 2 distinct
  identities): they are neither added to `refs_by_activity` nor matched. The
  `matches_any_step` branch (`coverage.py:126–132`) — "empty refs → covered by
  every step" — is **removed**; an empty/under-anchored ref set now means
  *excluded*, not *matches everything*.
- **Ineligible activities render in a neutral "not coverage-tracked" state**,
  visually distinct from an uncovered (red `0/N`) chip — a muted dash (`—`) with
  the tooltip *"insufficient number of glossary terms for matching"*, so the
  reason is explicit. An eligible-but-uncovered activity keeps the existing
  `0/N` styling. The rollup (`ActivityCoverage` / `per_activity`) carries an
  eligibility flag so the template can branch; the template already reads
  `rollup.per_activity[activity.id]`, so every activity keeps an entry. This is
  template/CSS work and is **Playwright-verified** per the frontend rule.
- A **partially** bare but eligible activity matches normally on its term
  identities; the bare verb/connective simply does not participate (as words
  never have).

## Error handling

- **Wrong-kind handle at a slot** → `PytestGivenError` naming the position and
  the handle kind. Bare strings never raise on role.
- **Length / alternation violations** (even length, fewer than 3 parts) →
  unchanged `PytestGivenError`.
- **An under-anchored activity (< 2 distinct terms) does *not* raise** — it is
  constructible and simply ineligible for coverage (rendered "not
  coverage-tracked"). There is no construction-time term floor.

## Testing

- **Grammar (accept):** a bare `str` is accepted at positions 0, 1, 2, a later
  even position, and the final position — each dispatches to `ActivityWord`.
  The motivating `path(guest, 'receives', confirmation)` builds.
- **Grammar (reject, handles):** a `WorkObject`/`Verb` handle at position 0, an
  `Actor`/`WorkObject` handle at an odd position, a `Verb` handle at an even
  position — all still raise. (These replace the former "rejects bare string at
  position 0/1/2/even" tests, which now assert acceptance.)
- **Alternation:** even-length (dangling edge) and < 3 parts still raise.
- **Construction is never gated by term count:** an all-bare activity and a
  1-term activity both construct without error.
- **Coverage eligibility:** an activity with ≥ 2 distinct terms participates in
  matching; an activity with 0 or 1 distinct term (including the same term twice)
  is excluded — it never appears as covered and reports the ineligible state. A
  multi-path activity aggregating 2 distinct terms across its paths is eligible.
- **Coverage matching:** a partially-bare but eligible activity matches on its
  terms; existing coverage tests pass; an all-bare activity is no longer
  "covered by every step" (the `matches_any_step` behaviour is gone).
- **Inference:** a verb *handle* at position 1 still infers `verb`; bare words
  never reach inference.
- **Rendering (Playwright):** an ineligible activity shows the neutral "not
  coverage-tracked" dash with the *"insufficient number of glossary terms for
  matching"* tooltip, distinct from an uncovered `0/N` chip.

## Migration / docs

Pre-release: no compatibility shims.

- **Example** (`examples/file-glossary-booking/`): restore the second activity
  as `activity(g['Guest'], 'receives', g['Confirmation'])` — the original
  motivating case — and correct the module docstring (the slot-1 note and the
  `'receives'` note).
- **`GLOSSARY.md`:** broaden `ActivityWord` to *"a bare path word — a node label
  or an edge connective; carries no kind or id; never classified or listed in
  the glossary."* Updated in the same commit as the code (per its update rule).
- **`README.md`:** the line *"An activity reads left-to-right: actor → verb →
  work object (with optional connective words)"* gains a note that any part may
  be a bare string, but an activity needs ≥ 2 distinct glossary terms to be
  tracked for coverage. Adjust any prose implying every path part must be a term.
- **Supersede note:** add a pointer in the
  [draft-unification spec](2026-06-27-glossary-draft-unification-design.md)
  marking its two grammar bullets as superseded by this spec, when this lands.
- Per the spec-lifecycle convention, `git mv` this file up to
  `docs/specs/` in the commit that lands the implementation.

## Forward notes

- **Finer eligibility rule.** Eligibility counts distinct term ids per activity.
  A future, finer rule (e.g. "position 0 and the final node must each be a
  term") could be considered, but the simple count suffices now.
- **Anonymous node rendering.** A bare node renders with the same muted
  `activity-word` styling as a bare connective, so the two are visually
  indistinguishable despite occupying node vs edge positions. A future
  "anonymous node pill" rendering could distinguish them; deferred (it adds
  renderer position-awareness + CSS + Playwright work for marginal v1 value).
- **`matches_any_step` removal.** Excluding under-anchored activities replaces
  the old "empty refs → matches everything" behaviour. If a future feature wants
  a term-less activity to participate in coverage, the eligibility threshold and
  this exclusion would be revisited together.
