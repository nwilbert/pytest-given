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

Paired with a **floor**: an activity must carry at least **two distinct
glossary terms**, so the entities anchoring it stay real vocabulary and
coverage stays meaningful.

This **supersedes** two grammar rules in the
[draft-unification spec](../2026-06-27-glossary-draft-unification-design.md):

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
  them assume a word only appears on an edge. So the change is confined to
  **validation** — the model, serde, coverage, aggregations and renderer need
  no structural change.
- **Coverage degenerate case.** `a_refs` builds an activity's identity set from
  its `ActivityTermRef` parts. An activity with an empty set falls into the
  `matches_any_step` branch (`coverage.py:126–132`) — "covered by every
  in-scope step," which is meaningless. Bare nodes make that case reachable in
  practice; the floor below removes it.

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

### Activity term floor

- **Every activity must contain at least two distinct glossary term refs** —
  i.e. ≥ 2 distinct `ActivityTermRef.term_id` values across all of the
  activity's paths. Enforced in `activity()`, raising `PytestGivenError` that
  names the activity's parts and the rule. ("distinct" guards the
  same-term-twice loophole.)
- Checkable **eagerly**: counting term refs needs no glossary and no kind
  inference — just inspect the constructed parts.
- **Rationale:** the entities anchoring an activity (the nodes of the DS graph)
  must be real vocabulary; only the verb/connective tissue may be bare. For a
  minimal `actor → verb → object`, that means actor and object are terms and the
  verb may be a word — exactly the `g['Guest'], 'receives', g['Confirmation']`
  case (2 terms). Threshold is **2**, not 3, because 3 would reject that very
  case (only longer paths could then carry a bare verb).

### Coverage consequence

- With ≥ 2 distinct term refs guaranteed per activity, `a_refs` is **never
  empty** for a validly constructed story. The `matches_any_step` branch
  (`coverage.py:126–132`) becomes unreachable; **replace it with an invariant
  `assert`** that `a_refs` is non-empty (per the project's assert-over-pragma
  rule), rather than leaving a dead branch.
- A **partially** bare activity matches normally on its term identities; the
  bare verb/connective simply does not participate in matching (as words never
  have).

## Error handling

- **Wrong-kind handle at a slot** → `PytestGivenError` naming the position and
  the handle kind. Bare strings never raise on role.
- **Activity with < 2 distinct term refs** → `PytestGivenError` naming the rule
  and the activity's parts.
- **Length / alternation violations** (even length, fewer than 3 parts) →
  unchanged `PytestGivenError`.

## Testing

- **Grammar (accept):** a bare `str` is accepted at positions 0, 1, 2, a later
  even position, and the final position — each dispatches to `ActivityWord`.
  The motivating `path(guest, 'receives', confirmation)` builds.
- **Grammar (reject, handles):** a `WorkObject`/`Verb` handle at position 0, an
  `Actor`/`WorkObject` handle at an odd position, a `Verb` handle at an even
  position — all still raise. (These replace the former "rejects bare string at
  position 0/1/2/even" tests, which now assert acceptance.)
- **Alternation:** even-length (dangling edge) and < 3 parts still raise.
- **Floor:** an activity with 2 distinct terms is accepted; 1 distinct term
  (including the same term twice) is rejected; a multi-path activity that
  aggregates 2 distinct terms across its paths is accepted; a fully-bare
  activity is rejected.
- **Coverage:** a partially-bare activity matches on its terms; existing
  coverage tests pass; the new `a_refs` non-empty assert never trips for a valid
  story.
- **Inference:** a verb *handle* at position 1 still infers `verb`; bare words
  never reach inference.

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
  work object (with optional connective words)"* gains a note that the verb and
  connectives may be bare strings, while the entity nodes must be glossary
  terms (≥ 2 per activity). Adjust any prose implying every path part is a term.
- **Supersede note:** add a pointer in the
  [draft-unification spec](../2026-06-27-glossary-draft-unification-design.md)
  marking its two grammar bullets as superseded by this spec, when this lands.
- Per the spec-lifecycle convention, `git mv` this file up to
  `docs/superpowers/specs/` in the commit that lands the implementation.

## Forward notes

- **Per-node-position floor.** The floor counts distinct term ids per activity.
  A future, finer rule (e.g. "position 0 and the final node must each be a
  term") could be considered, but the simple count suffices now.
- **Anonymous node rendering.** A bare node renders with the same muted
  `activity-word` styling as a bare connective, so the two are visually
  indistinguishable despite occupying node vs edge positions. A future
  "anonymous node pill" rendering could distinguish them; deferred (it adds
  renderer position-awareness + CSS + Playwright work for marginal v1 value).
- **`matches_any_step` removal.** If a future feature legitimately wants a
  term-less activity, the floor and the `a_refs` assert would be revisited
  together.
