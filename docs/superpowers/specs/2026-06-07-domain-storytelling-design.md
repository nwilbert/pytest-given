# Domain Storytelling — Design Spec

## Goal

Turn the pytest-given HTML report into an executable artifact of Domain-Driven Design discovery. Add three pieces, each optional and independently useful:

1. A suite-wide **Ubiquitous Language glossary** — terms tagged as actor / object / verb, with definitions.
2. **Domain Stories** — sequence-numbered activity timelines that reference glossary terms. The format follows [Domain Storytelling](https://domainstorytelling.org/quick-start-guide): actors / work objects / verbs as the three-kind vocabulary, sequence-numbered activities, and the same kind-driven rendering rules (actors consolidated across a diagram, work objects per-activity). v1 covers the core sentence grammar and timeline rendering; advanced DS constructs (Groups, Annotations) are out of scope — see below.
3. **Scenario↔activity binding** — explicit on `@scenario(...)` / step `activity=`, or implicit from the glossary terms referenced in step narration.

The report grows a top-level tabbed navigation: **Scenarios** (today's view, unchanged), **Stories**, **Glossary**. Each tab is hidden when its data is empty. A suite using neither DS nor UL is unaffected.

## Terminology mapping (DS ↔ this spec)

| Domain Storytelling | This spec | Notes |
|---|---|---|
| Actor | `actor` (glossary kind) | Person, organization, or IT system that acts. |
| Work object | `work_object` (glossary kind) | Document, information, or physical object acted upon. |
| Activity (numbered sentence) | `Activity` | A numbered row in the story; may contain multiple arrows. |
| Sequence number | `Activity.id` | The `1`, `2`, `3`… labelling activities. |
| Arrow label (verb) | `verb` (glossary kind), `ActivityTerm` | DS doesn't promote verbs to a first-class category — they're just labels on arrows. We make `verb` a glossary kind because DDD's ubiquitous language treats verbs (commands, domain events) as first-class vocabulary alongside nouns. This is an honest DDD enrichment over pure DS, not a deviation. |
| — (no DS analogue) | `ActivityPath` | Internal carrier for the arrow structure *within* one activity. A DS activity can contain multiple arrows (joining flows, parallel branches); each `ActivityPath` carries one linear sequence. Authors usually pass parts directly to `activity(...)` and we synthesize a single path; only multi-arrow shapes surface `path(...)`. |
| — (no DS analogue) | `ActivityEntity` | Internal grammar marker unifying actors and work objects in entity-position. Not user-facing. |
| Annotation | *out of scope (v1)* | Freeform notes on activities; data model can extend later. |
| Group | *out of scope (v1)* | Labelled wrappers around activity ranges; data model can extend later. |

In short: actors / work objects / activities / sequence numbers follow DS faithfully; verbs are a DDD-UL enrichment; paths and entities are internal carriers that authors rarely name directly.

## Scope

In:

- `Glossary` + `GlossaryTerm` (kinds: `actor` / `object` / `verb`), declared by the user as a single explicit `Glossary` instance (no module-import global registry, no name field).
- `Story`, `Activity`, `ActivityPath`, and `ActivityPart` variants (`ActivityEntity`, `ActivityTerm`, `ActivityWord`) — defined as a PEP 695 union to mirror `NarrationPart`.
- New narration variant `NarrationTermRef` for entity / verb-term references in t-strings (sits alongside the existing `NarrationPlaceholder`, which still handles parametrize-column interpolations).
- Public API: `Glossary` class with term-registration methods (`actor` / `work_object` / `verb`) and `story(...)`; module-level `activity` / `path` constructors; scenario kwarg `story=` / `activities=`; step kwarg `activity=`.
- Implicit binding inference from step term-refs.
- Three-view report navigation; story timeline with per-row scenario badges and bidirectional anchors; glossary view grouped by kind.
- Pass/fail propagation onto activities, with count chip.
- Per-use display via call syntax — verb inflections (`confirm('confirms')`) and noun instances (`room('Deluxe Suite')`). Inflections share identity with the canonical verb; instances carry distinct identity (see *Instances and inflections*).

Out:

- **Domain Storytelling Groups and Annotations** — DS lets modelers wrap activities in labelled Groups (subprocesses, parallel branches) and attach freeform Annotations to activities or sentences. v1 ships neither; the data model can be extended later without breaking the timeline view.
- Multiple `Glossary` instances per suite (one-per-Bounded-Context) — v1 assumes exactly one; the plugin raises on more. See follow-ups for the multi-BC extension.
- Example Mapping rule / example / question authoring (separate spec).
- egon.io file import or export (`.dst`, `.egn`, SVG, PNG).
- External glossary file formats (YAML / JSON / Markdown).
- Event Storming integration.
- Glossary synonyms, external doc links.
- Pictogrammatic / graph-view rendering of stories — only the timeline view ships in v1; the data model is graph-ready.
- Custom `format_spec` semantics in t-strings — type detection is the only mechanism.

## Background

pytest-given today captures each test as a `Scenario` with a tree of `Step`s and renders them as a flat collection of cards (`src/pytest_given/report/templates/report.html.j2`). Narration parts are one of:

- `NarrationLiteral` — plain text.
- `NarrationValue` — t-string interpolation whose name does not match a parametrize column; rendered bold.
- `NarrationPlaceholder` — t-string interpolation matching a parametrize column; rendered with one of six palette colours (`.param-color-0..5` in `styles.css`).

The dispatch lives in `_make_narration_filter` (`src/pytest_given/report/renderer.py`), discriminating by Python type via `match`/`case`.

Per AGENTS.md the project is pre-release; JSON schema changes are not hedged ([[project-prerelease-status]]). The motivating `TODO.md` items are "UL support" (this spec's main thrust) and "agent skill for pytest-given" (deferred — likely benefits from this design's vocabulary).

## Approach

### Data model (`src/pytest_given/model/schema.py`)

NewType aliases (per AGENTS.md: `NewType` for domain ids, PEP 695 `type` only for plain aliases):

```python
TermId = NewType('TermId', str)
ActivityId = NewType('ActivityId', int)
StoryId = NewType('StoryId', str)
```

Glossary term (frozen leaf — no `kind`-bearing dependents need it denormalized; the renderer resolves kind via the glossary):

```python
@dataclass(frozen=True, kw_only=True)
class GlossaryTerm:
    id: TermId
    kind: Literal['actor', 'object', 'verb']
    canonical: str
    definition: str
```

Glossary (mutable container — terms are added at user-module import time via methods; same instance is snapshotted onto `ReportData`):

```python
@dataclass
class Glossary:
    terms: list[GlossaryTerm] = field(default_factory=list)

    # term-registration methods (signatures in the API table below)
    def actor(self, name: str, *, definition: str = '') -> Actor: ...
    def work_object(self, name: str, *, definition: str = '') -> WorkObject: ...
    def verb(self, name: str, *, definition: str = '') -> Verb: ...
```

`Glossary` is a mutable container (matching the existing `Step` / `Scenario` / `ReportData` convention of mutable aggregate, frozen leaves). The user holds the instance; the plugin neither creates nor clears it. Each `Actor` / `WorkObject` / `Verb` returned by the methods carries a back-reference to its `Glossary` so a `Story` can later compute the set of glossaries it touches.

`Story` is intentionally *not* owned by `Glossary`. Domain Stories may span multiple Bounded Contexts in DDD (cross-context interactions, context maps), and the multi-glossary follow-up needs a story to reference terms from more than one `Glossary`. v1 enforces a single glossary per story, but the data model leaves the door open.

`GlossaryTerm.id` and `Story.id` are **internal** identifiers, auto-derived from `canonical` / `title` for serde anchoring and cross-references inside `ReportData`. They are not exposed as kwargs (see *Id auto-derivation*).

Story / activity / path:

```python
@dataclass(frozen=True, kw_only=True)
class ActivityEntity:
    """Part referencing a term whose kind is 'actor' or 'object'."""
    entity_id: TermId
    display: str

@dataclass(frozen=True, kw_only=True)
class ActivityTerm:
    """Part referencing a term whose kind is 'verb'."""
    term_id: TermId
    display: str

@dataclass(frozen=True, kw_only=True)
class ActivityWord:
    """Bare-string connective (preposition, article, etc.). Carries no kind."""
    text: str

@dataclass(frozen=True, kw_only=True)
class ActivityPlaceholder:
    """A draft (kind-tagged but not glossary-registered) entity or verb."""
    kind: Literal['actor', 'object', 'verb']
    text: str

type ActivityPart = ActivityEntity | ActivityTerm | ActivityWord | ActivityPlaceholder

@dataclass(frozen=True, kw_only=True)
class ActivityPath:
    parts: tuple[ActivityPart, ...]

@dataclass(frozen=True, kw_only=True)
class Activity:
    id: ActivityId
    paths: tuple[ActivityPath, ...]

@dataclass(frozen=True, kw_only=True)
class Story:
    id: StoryId
    title: str
    activities: tuple[Activity, ...]
```

`ActivityEntity` and `ActivityTerm` encode the structural role of a *typed* reference (entity-position vs verb-position) backed by a `GlossaryTerm`. `ActivityPlaceholder` is the analogous "drafted but not yet promoted" form — kind is known, glossary commitment is deferred. `ActivityWord` is reserved for connective text (prepositions, articles, conjunctions) that carries no kind by intent.

**Field-naming convention:** parts that reference something (have an `entity_id` / `term_id`) use `display` for their rendered form — capturing inflections / capitalizations that vary from the underlying term's `canonical`. Parts that are literal content (no reference) use `text`. So `ActivityEntity.display`, `ActivityTerm.display`, `NarrationTermRef.display` versus `ActivityWord.text`, `ActivityPlaceholder.text`. `Narration.text` (existing) is the joined top-level string and matches the literal-content side of the same convention.

`path(...)` constructs:
- `ActivityEntity` for any `Actor`/`WorkObject` argument, or for `ActorInstance`/`WorkObjectInstance` (returned by call syntax on an `Actor`/`WorkObject` — see *Instances* below).
- `ActivityTerm` for any `Verb` argument, or for `InflectedVerb` (returned by call syntax on a `Verb` — see *Inflections* below).
- `ActivityPlaceholder` for any value returned by `draft.actor(...)` / `draft.work_object(...)` / `draft.verb(...)`.
- `ActivityWord` for any bare-string argument.

The renderer reads kind from the glossary for typed references, and from the placeholder itself for drafts.

**Instances and inflections — the kind-driven split.** Call syntax on a noun (actor / work object) creates an *instance*; call syntax on a verb creates an *inflection*. Different identity semantics:

- `guest('Alice')` → `ActorInstance(actor=guest, display='Alice')`. The instance has a distinct identity from the canonical `guest`. Used when you need to distinguish "Guest Alice" from "Guest Bob" in the same story.
- `room('Deluxe Suite')` → `WorkObjectInstance(work_object=room, display='Deluxe Suite')`. Same — distinct identity.
- `confirm('confirms')` → `InflectedVerb(verb=confirm, display='confirms')`. *Same identity* as canonical `confirm` — inflection is purely morphological, the verb is one verb.

These three are intermediate value classes consumed by `path(...)` and `narration_from(...)`; they never appear in the persisted schema (which stores `ActivityEntity` / `ActivityTerm` / `NarrationTermRef` with `term_id` + `display`).

**Identity is derived from `display`, not stored.** Two rules:

- Entity refs (actor / work object): `display == term.canonical` means the canonical concept (identity = `(term_id, None)`); any other `display` means an instance (identity = `(term_id, id_derive(display))`).
- Verb refs: any `display` resolves to the same identity (`term_id`); display variation is purely cosmetic.

The renderer / coverage module looks up `glossary[term_id].kind` to choose the interpretation. No `instance_id` field on the parts — the canonical lookup is essentially free given the glossary is already in hand.

**Grammar.** Each `ActivityPath` enforces Domain Storytelling's canonical sentence shape — *subject → action → noun* — at its leading triple:

1. **Position 0: an actor** — `Actor` (typed), `ActorInstance`, or `DraftActor`. The subject of the sentence.
2. **Position 1: a verb** — `Verb` (typed), `InflectedVerb`, or `DraftVerb`. The action.
3. **Position 2: an anchored noun** — `Actor`, `ActorInstance`, `WorkObject`, `WorkObjectInstance`, `DraftActor`, or `DraftWorkObject`. The object of the action (DS allows it to be either another actor or a work object).

Beyond position 2 the path is free-form: any further parts (additional nouns, bare-string connectives like `'into'`, additional verbs) are accepted in any order. Multi-arrow activities use multiple `path(...)` calls.

The check is purely structural — `path(...)` discriminates by Python argument type, no glossary lookup needed. The iterative-authoring path stays open via `draft.*` for any noun or verb the team hasn't committed yet.

Typical authoring mistakes the rules catch, each with a targeted message:
- `activity(room, confirm('confirmed'), guest)` — work-object-initiated; rule 1 fails. Suggest active-voice rephrasing.
- `activity(guest, room)` — verbless; rule 2 fails. Prompt for the action.
- `activity(guest, submit('submits'), 'the payment')` — bare string in object position; rule 3 fails. Suggest `g.work_object('Payment')` or `draft.work_object('payment')`.

**Identity, consolidation, and the future graph view.** Typed references identify by `term_id`; drafts by `(kind, id_derive(text))` using the same normalization as glossary-term ids. The timeline view in v1 doesn't apply any consolidation (each activity is its own row), but DS's pictographic rules — actors drawn once, work objects drawn per activity — are a kind-driven policy the future graph view can apply directly: group `ActivityEntity` / `ActivityPlaceholder` instances by identity, consolidate when kind is `actor`, keep separate when kind is `object`. Coverage matching treats drafts differently from typed refs — see *Scenario ↔ story activity binding*.

New narration part variant:

```python
@dataclass(frozen=True, kw_only=True)
class NarrationTermRef:
    """Reference to a glossary term — kind resolved via glossary[term_id].kind."""
    term_id: TermId
    display: str
    param_column: str | None = None   # set iff the interpolation matched a parametrize column
```

`NarrationPart` is extended:

```python
type NarrationPart = NarrationLiteral | NarrationValue | NarrationPlaceholder | NarrationTermRef
```

Kind on `NarrationTermRef` is resolved at render time via `glossary[term_id].kind` (no denormalization).

**Drafts are story/activity-only.** They have no narration-side variant, and interpolating a draft into a step t-string raises at capture (see *Error handling* — "Draft interpolated in narration"). Drafts are about sketching the *story* before the glossary is settled; once the team is writing tests against an activity, the corresponding vocabulary must be promoted to the glossary first (or the step can use a plain string). See *Scenario ↔ story activity binding* for how drafts interact with coverage.

Additions on existing types:

- `ReportData.glossary: Glossary | None = None` — the single declared glossary, or `None` if the suite uses no glossary at all.
- `ReportData.stories: list[Story] = field(default_factory=list)` — stories referenced by any scenario, snapshotted at session-finish. Top-level (not nested under `glossary`) so a future multi-BC story can hold references into more than one `Glossary`.
- `Scenario.story_id: StoryId | None = None`.
- `Scenario.activity_ids: tuple[ActivityId, ...] = ()` — explicit cap (steps may not cover activities outside this set); `()` means *infer from steps*.
- `Step.activity_ids: tuple[ActivityId, ...] = ()` — explicit tighter binding (a step may cover one or more activities); `()` means *infer from this step's term-refs*.

#### Runtime lookup pattern

The schema stores ordered collections as lists (canonical, JSON-friendly), but lookups by id need to be O(1) for the renderer and coverage matching. Each container maintains a derived id→element index alongside its list, kept in sync by the container's own methods and rebuilt in `__post_init__` after deserialization. The index is excluded from `repr` and never serialized; it's purely an in-memory acceleration over the list.

| Container | Storage (serialized) | Index (in-memory) | Public lookup |
|---|---|---|---|
| `Glossary` | `terms: list[GlossaryTerm]` | `_by_id: dict[TermId, GlossaryTerm]` | `glossary[term_id]`, `glossary.get(term_id)` |
| `Story` | `activities: tuple[Activity, ...]` | `_by_id: dict[ActivityId, Activity]` | `story[activity_id]`, `story.get(activity_id)` |
| `ReportData` | `scenarios: list[Scenario]`, `stories: list[Story]` | `_scn_by_id`, `_story_by_id` | `report_data.scenario(node_id)`, `.story(story_id)` |

The Glossary's `actor` / `work_object` / `verb` methods (and `Story`'s activity insertion) write through to both the list and the dict atomically, so uniqueness conflicts are detected with an O(1) lookup before append. Renderer and coverage code never touch the lists directly — they go through `__getitem__` or `get`.

JSON shape is unaffected: only the lists are serialized. External consumers reading the JSON see the same flat structure as today.

### Authoring API (`src/pytest_given/__init__.py` exports; implementation in new modules)

Public surface:

| Name | Signature | Effect |
|---|---|---|
| `Glossary()` | `() -> Glossary` | Construct the glossary instance the user holds for the suite. |
| `Glossary.actor` | `(name: str, *, definition: str = '') -> Actor` | Registers a `GlossaryTerm(kind='actor')` on this glossary; returns the `Actor` handle. |
| `Glossary.work_object` | `(name: str, *, definition: str = '') -> WorkObject` | Same, kind `'object'`. |
| `Glossary.verb` | `(name: str, *, definition: str = '') -> Verb` | Same, kind `'verb'`. The verb's canonical form is the registered name; inflections are per-call via `verb('inflected')`. |
| `draft.actor` | `(text: str) -> DraftActor` | Module-level singleton method. Returns a kind-tagged placeholder; no glossary registration. |
| `draft.work_object` | `(text: str) -> DraftWorkObject` | Same, kind `'object'`. |
| `draft.verb` | `(text: str) -> DraftVerb` | Same, kind `'verb'`. |
| `story` | `(title: str, activities: Sequence[Activity] = ()) -> Story` | Module-level constructor. Activities are positional (no kwarg) — pass a list. Inspects activity parts to compute the set of glossaries referenced; in v1 the set must have size ≤ 1 (a story made entirely of drafts is legal — its glossary set is empty). Drafts don't contribute to this set. |
| `Actor.__call__` / `WorkObject.__call__` | `(display: str) -> ActorInstance` / `WorkObjectInstance` | Call syntax on a noun creates an *instance* — distinct identity from the canonical concept (e.g., `guest('Alice')` distinguishes from `guest`). |
| `Verb.__call__` | `(display: str) -> InflectedVerb` | Call syntax on a verb creates an *inflection* — same identity as canonical (e.g., `confirm('confirms')` is still the `confirm` verb in a different form). |
| `path` | `(*parts: Actor \| WorkObject \| Verb \| ActorInstance \| WorkObjectInstance \| InflectedVerb \| DraftActor \| DraftWorkObject \| DraftVerb \| str) -> ActivityPath` | Validates the DS sentence grammar: leading triple is *actor → verb → noun* (anchored, typed or draft). Beyond position 2 the path is free-form. Bare strings are reserved for connectives. The union covers *which kinds of arguments are accepted at all*; per-position constraints (e.g., no `Verb` in position 2) are enforced at runtime by `path(...)`, not in the type. See *Grammar* in the data model section. |
| `activity` | `(*parts_or_paths, id: int \| None = None) -> Activity` | Single-path (positional parts) or multi-path (positional `Path`s). Optional `id=` overrides the auto-assigned sequence number; see below. |
| `@scenario` | Existing decorator + `story: Story \| None = None, activities: Sequence[int] = ()` | Scenario-level binding. |
| `given` / `when` / `then` (context-manager form) | Existing context-managers + kwarg `activity: int \| Sequence[int] \| None = None` | Step-level binding. Narration accepts plain strings and t-strings with term/instance/inflection interpolation. Drafts (`DraftActor`/`DraftWorkObject`/`DraftVerb`) are not permitted in narrations — interpolating one raises at capture. |
| `@given` / `@when` / `@then` (fixture-decorator form) | Existing decorators stacked *under* `@pytest.fixture` (i.e., `@pytest.fixture` is the outer / topmost decorator — see `examples/test_coffeeshop.py` for the established convention) | Records the fixture's setup narration; **does not** change the fixture's return value. Accepts the same narration forms as the context-manager — t-strings interpolating `Actor` / `WorkObject` / `Verb` / `ActorInstance` / `WorkObjectInstance` / `InflectedVerb` produce `NarrationTermRef` parts that flow into the Glossary view's "Instances" / "Also used as" aggregation (with fixture provenance annotated). |

Note: no `id=` parameter is exposed on the *vocabulary* surface — `GlossaryTerm.id` and `Story.id` are internal and always derived from `name` / `title`. To get a specific id, pick the name that derives to it. `Activity.id` is different in nature (a user-visible sequence number rendered as the row number in the story timeline) and remains settable via `activity(..., id=N)`.

No dedicated fixture-decorator forms like `@actor` / `@work_object` are introduced. The fixture-to-term relationship is M:N for concepts (one fixture might yield instances of several actors; one actor might be produced by several fixtures), so attaching a term-as-concept to a fixture symbol is misleading. Where authors want to *document* that a fixture corresponds to a specific instance, they reach for the existing `@given` / `@when` / `@then` fixture-decorator forms with a t-string that interpolates the instance — e.g., `@given(t'our guest {guest("Alice")}')`. This keeps the fixture's return type unchanged and reuses already-familiar narration machinery.

#### Id auto-derivation

For both `GlossaryTerm.id` (from the registration `name`, stored as `canonical`) and `Story.id` (from `title`):

1. Lowercase the input.
2. Replace every maximal run of characters *not* in `[a-z0-9]` with a single ASCII hyphen `-`.
3. Strip leading and trailing `-`.
4. If the result is the empty string, raise `PytestGivenError` (e.g., a name of `"---"` or `"  "`).

Worked rule output:

| Input | Id |
|---|---|
| `"Guest"` | `"guest"` |
| `"Order received"` | `"order-received"` |
| `"  Work Object  "` | `"work-object"` |
| `"do_the_thing"` | `"do-the-thing"` (underscore is non-alphanumeric under `[a-z0-9]`) |
| `"Buy / sell"` | `"buy-sell"` |
| `"Guest #1"` | `"guest-1"` |
| `"café"` | `"caf"` (non-ASCII letters are treated as non-alphanumeric in v1; Unicode-aware folding is a follow-up) |
| `"---"` | *raises* |

The derivation is deterministic, so serialized reports remain stable across runs as long as canonical names don't change.

#### Activity sequence numbers

The `story(...)` constructor assigns `1..N` from positional order. An `Activity` constructed with explicit `id=N` keeps that number; the story validates uniqueness across activities, and a strictly increasing order is preferred but not enforced (gaps are allowed for future inserts).

**Stability note.** Activity ids double as cross-reference keys for `scenario.activity_ids` and `step.activity_ids`. Reordering or inserting unnumbered activities therefore shifts the numbers and breaks any code (test or report) that referenced them. Once a scenario or step binds explicitly to an activity, pin the activity's id with `activity(..., id=N)` so subsequent re-orderings don't silently re-target the binding. Implicit (term-ref) coverage is unaffected — it identifies activities by their term refs, not by id.

Call-site display variation, kind-driven: every `Actor`, `WorkObject`, and `Verb` is callable with a single string argument; the resulting type and identity depend on kind. `Actor`/`WorkObject` produce `ActorInstance` / `WorkObjectInstance` (distinct identity from canonical — used to disambiguate "Guest Alice" from "Guest Bob"). `Verb` produces `InflectedVerb` (same identity as canonical — used for "confirms" vs "confirm", "sends" vs "send"). Activities and t-strings both accept the bare term (canonical display) or the call-syntax form. No `forms` / `instances` fields on `GlossaryTerm`; observed displays are aggregated at render time and surfaced under each term in the Glossary view.

Worked example — *Online Hotel Booking* (same domain as `examples/test_hotel_booking.py`):

```python
# domain.py
from pytest_given import Glossary, story, activity, draft

g = Glossary()

guest          = g.actor('Guest',          definition='Person booking accommodation.')
booking_system = g.actor('Booking System', definition='Automated reservation system.')

room         = g.work_object('Room',         definition='A bookable hotel room.')
booking      = g.work_object('Booking',      definition='A reservation for a room.')
payment      = g.work_object('Payment',      definition='Money transferred for a booking.')
confirmation = g.work_object('Confirmation', definition='Notification of a successful booking.')

search  = g.verb('search',  definition='Look up available options.')
select  = g.verb('select',  definition='Choose one option from a set.')
submit  = g.verb('submit',  definition='Send to the system for processing.')
confirm = g.verb('confirm', definition='Finalize and acknowledge.')
send    = g.verb('send',    definition='Deliver to a recipient.')

# `loyalty bonus` and the `redeems` verb appear as drafts in activity 7 — the
# team hasn't decided yet whether they belong in the ubiquitous language.

book_a_shared_room = story('Book a Shared Room', [
    # 1. Canonical activity — any specific guest searching satisfies this.
    #    Scenarios that mention guest('Alice') or guest('Bob') will both cover
    #    this row via the canonical-fallback rule.
    activity(guest, search('searches for'), room),
    # 2. Actor instance + work-object instance: Alice selects the Deluxe Suite.
    activity(guest('Alice'), select('selects'),  room('Deluxe Suite')),
    # 3. Same actor instance; canonical work object.
    activity(guest('Alice'), submit('submits'),  payment),
    # 4. Confirmation references TWO distinct guest instances.
    activity(booking_system, confirm('confirms'), booking,
             'for', guest('Alice'), 'and', guest('Bob')),
    # 5. Send to Alice — distinct from the Bob version on the next line.
    activity(booking_system, send('sends'), confirmation, 'to', guest('Alice')),
    # 6. Identical activity shape, different guest instance → different identity.
    activity(booking_system, send('sends'), confirmation, 'to', guest('Bob')),
    # 7. Draft verb + draft work object — Alice redeems a loyalty bonus.
    activity(guest('Alice'), draft.verb('redeems'), draft.work_object('loyalty bonus')),
])
```

```python
# tests/test_booking.py
import pytest
from pytest_given import scenario, given, when, then
from domain import (book_a_shared_room, guest, booking_system, room, booking,
                    payment, confirmation, search, select, submit, confirm, send)

# Fixture-decorator form of `@given` — the fixture's return value is unchanged
# (still a plain User), but its `given` narration records the instance binding.
# The Glossary view will surface "Alice" and "Bob" as observed instances of
# Guest, annotated with the originating fixture name.

@pytest.fixture
@given(t'our guest {guest('Alice')}')
def alice():
    return User(name='Alice', email='alice@example.com')

@pytest.fixture
@given(t'our guest {guest('Bob')}')
def bob():
    return User(name='Bob', email='bob@example.com')

@scenario('Alice books a shared room with Bob', story=book_a_shared_room)
def test_book_shared(alice, bob):
    # `alice` and `bob` are plain User objects — use them as such in the body.
    # The fixture-level @given already records that they're the Alice/Bob
    # instances; the test starts directly with the booking actions.
    with when(t'{guest('Alice')} {search('searches for')} a {room}'):
        alice.search_rooms()
    with when(t'{guest('Alice')} {select('selects')} the {room('Deluxe Suite')}'):
        alice.select_room('Deluxe Suite')
    with when(t'{guest('Alice')} {submit('submits')} the {payment}'):
        alice.submit_payment(...)
    with then(t'the {booking_system} {confirm('confirms')} the {booking} for {guest('Alice')} and {guest('Bob')}'):
        ...
    with then(t'the {booking_system} {send('sends')} a {confirmation} to {guest('Alice')}'):
        ...
    with then(t'the {booking_system} {send('sends')} a {confirmation} to {guest('Bob')}'):
        ...
```

No explicit `activity=` anywhere; scenario coverage is `{1, 2, 3, 4, 5, 6}` — every typed activity gets covered. Activity 7 is the gap because both its verb (`redeems`) and its object (`loyalty bonus`) are drafts; draft-bearing activities are excluded from implicit coverage. See the worked walk-through below for the per-step `A_refs` / `S` derivation and the design payoffs the table makes concrete.

### Registration model (no global registry)

State lives entirely in user-held `Glossary` and `Story` objects — no plugin-managed runtime registry. The single carve-out is a process-scoped story-id duplicate-tracking dict (see below) that's populated at user-module import time as a fast-feedback authoring aid and cleared at every session start; it holds ids + source locations, not content. Repeated pytest subprocess invocations naturally re-execute the user's module top-level code.

Plugin-side discovery at session finish:

1. Walk collected `Scenario` instances; for each with `story_id` set, the `Story` is reachable through the captured `@scenario(story=...)` reference on `Scenario`.
2. Collect those stories into `ReportData.stories`.
3. From each story's parts, collect the set of referenced `Glossary` instances and union them across stories. v1 invariant on the union: size ≤ 1; if 2+ distinct glossaries are reached, raise with the offending story and its glossaries. Drafts don't contribute (per the `story(...)` construction rule), so an all-draft story contributes nothing here.
4. If the union from step 3 is empty (no stories at all, or only all-draft stories), fall back to **conftest discovery**: iterate `config.pluginmanager.get_plugins()`, filter to plugin modules whose `__file__` basename is `conftest.py`, and collect every module-level attribute that `isinstance(_, Glossary)`. This surfaces a glossary view for Glossary-only suites and all-draft-story suites alike. Zero matches → `ReportData.glossary = None`; one match → use it; 2+ distinct matches raise, message listing each conftest path and its glossary's term count.

   **Discovery is conftest-only on purpose.** A `Glossary` defined in a regular module (e.g., the `domain.py` of the worked example) is only discoverable via story-back-refs — if no story references it, it stays invisible. Glossary-only suites must therefore either define the `Glossary` directly in a `conftest.py`, or re-export it from one (`from .domain import g`). The user-facing rule, documented in `README.md` and `GLOSSARY.md`: *to get a Glossary tab without declaring any Story, put `g = Glossary()` (or an import that binds it) in a conftest.*
5. The resulting glossary (or `None`) is assigned to `ReportData.glossary`. Tab visibility (see *Optional support*) is computed from `ReportData.glossary` and `ReportData.stories`.

Conflict semantics, enforced inside `Glossary` methods:

- Re-registering the same term id is idempotent iff *all* fields (kind, canonical, definition) match; raises on any divergence.
- Cross-kind id collision within one glossary raises with both call sites.

Story-id duplicates are detected by the module-level `story(...)` constructor via the process-scoped duplicate-tracking dict introduced in the preamble — keyed by `StoryId`, value is the declaration site (file + line). Two stories whose titles derive to the same id raise with both sites in the message. The canonical store of stories remains `ReportData.stories` (populated at session finish from story-back-refs); the dict is purely for fast authoring feedback at import time.

### Capture (`src/pytest_given/capture/template.py`, `src/pytest_given/capture/decorators.py`)

`narration_from(...)` already dispatches `str` / `Template` / t-string into a `Narration`. Extend the t-string branch:

- For each interpolation, after current parametrize-name matching:
  - If the interpolation value is one of `Actor` / `WorkObject` / `Verb` / `ActorInstance` / `WorkObjectInstance` / `InflectedVerb`: produce `NarrationTermRef(term_id=…, display=…, param_column=<col if matched else None>)`. `display` is the canonical for bare terms, the instance display for `ActorInstance`/`WorkObjectInstance`, or the inflected form for `InflectedVerb`. `term_id` is the underlying term's id in every case.
  - If the interpolation value is a `DraftActor` / `DraftWorkObject` / `DraftVerb`: raise `PytestGivenError` — drafts are story-side only (see *Error handling*).
  - Else fall back to existing `NarrationValue` / `NarrationPlaceholder` paths.

Scenario binding capture (`src/pytest_given/plugin.py`, in `pytest_collection_modifyitems` or wherever `@scenario` metadata is read): read `story=` (a `Story` instance or `None`) and `activities=` (validated as a tuple of ints, each present in the story's activity ids when explicit). Store `Scenario.story_id = story.id` and `Scenario.activity_ids`. Also retain a session-scoped mapping from `StoryId → Story` so the discovery walk in the Registration model can recover the full `Story` objects without re-reaching into user code.

Step binding capture (`given` / `when` / `then` context-manager entry): accept `activity: int | Sequence[int] | None`. Normalize to `tuple[ActivityId, ...]`. Store in `Step.activity_ids` (a single int becomes a 1-tuple; `None` leaves the field as `()`).

### Scenario ↔ story activity binding

This section consolidates how a `Scenario` ends up associated with one or more `Activity` instances of its `Story`. There are two levels of binding (scenario→story, step→activities) and three sources (scenario-level explicit, step-level explicit, term-ref inference). The renderer needs a single `dict[ActivityId, set[StepRef]]` per scenario; everything below describes how that map is produced.

#### Inputs

After capture, each `Scenario` carries:

- `story_id: StoryId | None` — set iff `@scenario(story=…)` was provided.
- `activity_ids: tuple[ActivityId, ...]` — set iff `@scenario(activities=[…])` was provided; otherwise `()`.

Each `Step` carries:

- `activity_ids: tuple[ActivityId, ...]` — set iff `given(…, activity=…)` (or `when` / `then`) was provided; otherwise `()`.
- `narration.parts` — possibly containing `NarrationTermRef` instances, each with a `term_id`.

Each `Activity` of the bound `Story` has:

- a set of referenced **identities**, `A_refs`. An identity is computed per-part using *strict* matching (no canonical-fallback — that asymmetry lives only on the step side, see *Step → activity binding*):
  - `ActivityEntity` (actor or work object): identity is `(entity_id, instance_id_of(display))` where `instance_id_of` returns `None` when `display == glossary[entity_id].canonical` and `id_derive(display)` otherwise.
  - `ActivityTerm` (verb): identity is `(term_id, None)` regardless of display. Verb inflection is a 1:1 morphological variation — `confirm` and `confirm('confirms')` are the same verb in different forms, never distinct things — so no instance-style identity arises.
  - `ActivityWord` and `ActivityPlaceholder`: contribute nothing.

  **Drafts do not participate in coverage matching** — an activity must use glossary-typed references to be eligible for implicit coverage. Entity instances *do* participate, with their distinct identity: `guest('Alice')` and `guest('Bob')` are different identities, both different from canonical `guest`.

#### Scenario → story binding

A scenario is "on a story" iff `scenario.story_id is not None`. Scenarios without a story do not appear in the Stories view at all; they still appear (unchanged) in the Scenarios view. The `story=` kwarg takes the `Story` object directly (not its id string) so that user code keeps a live reference — the id is stored only for serde.

#### Step → activity binding

For each step, the set of activities it "covers" is computed by the following precedence:

1. **Explicit step binding.** If `step.activity_ids != ()`, those are the covered activities. No further inference.
2. **Term-ref inference.** Otherwise, compute the step's identity set `S` from each `NarrationTermRef` in the narration:
   - **Verb ref**: contributes `(term_id, None)`. Inflections (e.g., `confirm('confirms')` vs canonical `confirm`) are synonymous — same identity — because verb inflection is a 1:1 morphological variation, not a many-to-one relationship.
   - **Entity ref to the canonical** (`display == canonical`): contributes `(term_id, None)`.
   - **Entity ref to a specific instance** (`display != canonical`): contributes *both* `(term_id, instance_id_of(display))` *and* `(term_id, None)`.

   The dual contribution from instance refs is the **canonical-fallback rule**: a scenario saying "Alice does X" implicitly *also* says "some Guest does X", so it should cover a canonical activity `activity(guest, …)`. The reverse is asymmetric: a scenario saying "a Guest does X" doesn't claim Alice specifically, so it doesn't cover `activity(guest('Alice'), …)`.

   For each activity `A` in the bound story, `A` is covered by this step iff `A_refs ⊆ S` (`A_refs` itself uses strict identity — no expansion). A step with no term-refs and no explicit `activity=` covers nothing.

   Coverage cheat-sheet:

   | Story activity uses | Scenario step uses | Covers? |
   |---|---|---|
   | canonical (`guest`) | canonical (`guest`) | ✓ |
   | canonical (`guest`) | instance (`guest('Alice')`) | ✓ — instance adds the canonical identity to `S` |
   | instance (`guest('Alice')`) | instance (`guest('Alice')`) | ✓ |
   | instance (`guest('Alice')`) | instance (`guest('Bob')`) | ❌ — different instance identity |
   | instance (`guest('Alice')`) | canonical (`guest`) | ❌ — bare canonical doesn't claim a specific instance |
   | verb canonical (`confirm`) | verb inflection (`confirm('confirms')`) | ✓ — inflection is synonymous |
   | verb inflection (`confirm('confirms')`) | verb canonical (`confirm`) | ✓ — same direction, same identity |

The subset rule handles verb and entity matching uniformly: every `ActivityEntity` and `ActivityTerm` in the path contributes to `A_refs`, and all of them must appear in `S`. For multi-path activities `A_refs` is the union across paths, so a step must reference every term across every path — strict v1 semantics; per-path partial coverage is a follow-up.

**Drafts and bare strings in coverage.** `ActivityWord` (bare connective) contributes nothing to `A_refs`. `ActivityPlaceholder` (draft) is stronger: **an activity containing any draft is excluded from implicit (term-ref) coverage entirely** — the subset rule is not even evaluated. Only an explicit step `activity=N` binding can cover a draft-bearing activity. (Drafts can't appear in narrations at all — capture rejects them — so there's no step-side draft channel to reason about.) To bring a draft-bearing activity into implicit coverage, promote the draft to a glossary term; the activity's `A_refs` then includes the new term and matching resumes normally. The hard exclusion is the deliberate forcing function: missing vocabulary keeps the activity visibly uncovered until the team commits a name.

#### Scenario → activity coverage

The scenario's activity-coverage map is built from its steps:

- If `scenario.activity_ids != ()`: the scenario is *constrained* to that explicit set. Each step is still processed by the step-level rule above, but any step coverage falling outside `scenario.activity_ids` is an error caught at capture time (see *Error handling* — "Step `activity=` outside scenario scope"). The scenario as a whole "covers" `scenario.activity_ids`; the step-level map provides the per-step breakdown.
- Otherwise (`activity_ids == ()`): the scenario covers the union of all step coverages — *implicit inference*.

#### Worked walk-through

Using the "Book a Shared Room" example above (activities 1–7, no explicit `activity=` anywhere). `A_refs` uses *strict* identity (no canonical expansion — the canonical-fallback rule applies only at the step side):

| # | Activity (parts) | A_refs |
|---|---|---|
| 1 | `guest search('searches for') room` (canonical entities; verb inflection collapses to `(search, ∅)`) | `{(guest, ∅), (search, ∅), (room, ∅)}` |
| 2 | `guest('Alice') select room('Deluxe Suite')` | `{(guest, alice), (select, ∅), (room, deluxe-suite)}` |
| 3 | `guest('Alice') submit payment` | `{(guest, alice), (submit, ∅), (payment, ∅)}` |
| 4 | `booking-system confirm booking 'for' guest('Alice') 'and' guest('Bob')` | `{(booking-system, ∅), (confirm, ∅), (booking, ∅), (guest, alice), (guest, bob)}` |
| 5 | `booking-system send confirmation 'to' guest('Alice')` | `{(booking-system, ∅), (send, ∅), (confirmation, ∅), (guest, alice)}` |
| 6 | `booking-system send confirmation 'to' guest('Bob')` | `{(booking-system, ∅), (send, ∅), (confirmation, ∅), (guest, bob)}` |
| 7 | `guest('Alice') draft·redeems draft·loyalty-bonus` | *excluded — draft-bearing* |

Each step's `S` applies the **canonical-fallback rule**: every entity instance ref contributes both its specific identity *and* the canonical `(term_id, ∅)`. Verb refs contribute `(term_id, ∅)` always. (Fixture-level `@given` narrations also contribute term-refs to the report, but they don't participate in step→activity coverage — only the in-test `given` / `when` / `then` steps do.)

| Step | S (with canonical fallback) | Covers |
|---|---|---|
| `when {guest('Alice')} {searches for} a {room}` | `{(guest, alice), (guest, ∅), (search, ∅), (room, ∅)}` | **1** *(canonical activity, matched via fallback)* |
| `when {guest('Alice')} {selects} the {room('Deluxe Suite')}` | `{(guest, alice), (guest, ∅), (select, ∅), (room, deluxe-suite), (room, ∅)}` | **2** |
| `when {guest('Alice')} {submits} the {payment}` | `{(guest, alice), (guest, ∅), (submit, ∅), (payment, ∅)}` | **3** |
| `then the {booking-system} {confirms} the {booking} for {guest('Alice')} and {guest('Bob')}` | `{(booking-system, ∅), (confirm, ∅), (booking, ∅), (guest, alice), (guest, bob), (guest, ∅)}` | **4** |
| `then the {booking-system} {sends} a {confirmation} to {guest('Alice')}` | `{(booking-system, ∅), (send, ∅), (confirmation, ∅), (guest, alice), (guest, ∅)}` | **5** |
| `then the {booking-system} {sends} a {confirmation} to {guest('Bob')}` | `{(booking-system, ∅), (send, ∅), (confirmation, ∅), (guest, bob), (guest, ∅)}` | **6** |

Scenario coverage = union = `{1, 2, 3, 4, 5, 6}`. **Activity 7** (`Alice draft.redeems draft.loyalty-bonus`) is excluded from implicit coverage by the draft rule above and stays visibly uncovered. Once the team promotes `redeems` to `g.verb(...)` and `loyalty bonus` to `g.work_object(...)`, the activity rejoins normal matching — `A_refs` becomes `{(guest, alice), (redeem, ∅), (loyalty-bonus, ∅)}`, and the scenario needs a step that mentions all three to cover it.

**Two design payoffs the table makes concrete:**

- **Activity 1 (canonical) is covered by an instance step.** The search step mentions `guest('Alice')`; under canonical fallback, `S` includes both `(guest, alice)` *and* `(guest, ∅)`, so the canonical activity `A_refs = {(guest, ∅), …}` is satisfied. A scenario about Bob would cover row 1 the same way — canonical activities welcome any instance.
- **Activities 5 and 6 are not conflated.** Same booking_system, same `send`, same `confirmation` — they differ only by guest instance. The instance carries distinct identity, so each activity matches only its own step. The negative case is explicit: the Alice-step's `S` contains `(guest, alice)` and `(guest, ∅)` but *not* `(guest, bob)`, so it doesn't cover activity 6's `A_refs` (which requires `(guest, bob)`). Without instances the two activities would collapse to one identity and conflate.

#### Mechanics

The algorithm is implemented in `src/pytest_given/report/coverage.py` as a pure function:

```python
def compute_coverage(scenario: Scenario, story: Story) -> dict[ActivityId, set[StepRef]]: ...
```

The renderer calls it once per (scenario, story) pair. `StepRef` is a lightweight identifier (probably `tuple[NodeId, list[int]]` for the path through `Step.children`) so the renderer can build the per-activity scenario badges without re-walking trees.

Empty cases: scenario has no story → not on the Stories view at all. Scenario has a story but no step covers any activity → renders under the story with zero activity coverage badges; activity rows render as gaps.

### Serde (`src/pytest_given/model/serde.py`)

Round-trip the new types. `ActivityPart` variants discriminate on a `type` key, mirroring how `NarrationPart` already discriminates. The `type` reflects the structural variant (entity / term / word / placeholder), *not* the term's kind for typed references (which lives on `GlossaryTerm`):

```json
{"type": "entity",      "entity_id": "guest",   "display": "Guest"}
{"type": "entity",      "entity_id": "room",    "display": "Room"}
{"type": "term",        "term_id":   "confirm", "display": "confirms"}
{"type": "word",        "text":      "for"}
{"type": "placeholder", "kind":      "object",  "text": "loyalty bonus"}
{"type": "placeholder", "kind":      "verb",    "text": "redeems"}
```

Narration parts add only `term_ref`; drafts have no narration variant.

```json
{"type": "term_ref", "term_id": "guest", "display": "Guest", "param_column": null}
```

`GlossaryTerm` still carries `kind` (authoritative for typed references); `ActivityPlaceholder` carries its own `kind` directly since it has no glossary backing.

`ReportData` gains:

```json
{
  "glossary":  {"terms": [...]} | null,
  "stories":   [...],
  "scenarios": [...]
}
```

Existing fields unchanged.

### Renderer (`src/pytest_given/report/renderer.py`, templates, styles, app.js)

#### Three-view navigation

A top-level tab strip rendered in `report.html.j2`:

- Active tab tracked via `x-data` on the body with `view: 'scenarios' | 'stories' | 'glossary'`; URL hash carries `#view=stories&story=order-coffee` or similar.
- Sidebar contents bound to the active tab.
- Tab visibility rules: see *Optional support* below.

#### Scenarios view (unchanged structure)

Existing layout preserved. The only differences:
- Step narration may include `NarrationTermRef` parts — rendered with the new pill styles.
- Clicking an entity pill jumps to the Glossary tab, scrolled to and highlighting the matching term.

#### Stories view

Sidebar: list of `Story` entries, each showing title, "N activities · M scenarios", and a mini coverage bar (existing status palette).

Main pane:

- Story header: title, summary stats (covered / total activities, failing count, scenarios).
- Activity timeline: vertical list of activity rows.
  - Row layout: `[seq number] [parts] [coverage chip] [scenario badge strip]`.
  - Parts render in part order: `ActivityEntity` → pill (kind-coloured), `ActivityTerm` → cyan dotted-underline text, `ActivityWord` → plain dark-gray text.
  - Multi-path activities stack: each `ActivityPath` becomes its own line within the row body, sharing the same sequence number on the left.
  - Coverage chip: status colour (green pass / red fail / yellow mixed / gray no-coverage) + count chip `m/n passing`.
  - Scenario badge strip on the right: small clickable badges, each with status dot + scenario name. Click anchors to the matching scenario card below.
- Scenario cards section: same card markup as the Scenarios view, with a "Covers:" strip of numeric activity badges at the top, each anchored to the corresponding timeline row.

Bidirectional sync-highlight: Alpine `$watch` on a `hoveredActivity` / `hoveredScenario` ref pair adds a highlight class to the matching rows / cards.

#### Glossary view

Sidebar:

- Search box wrapping the input with the existing `.search-box` / `.search-box-icon` / `.search-box-clear` pattern (magnifying-glass left, clear-× right). Reuses existing styles directly. Filter is case-insensitive substring match against both `canonical` and `definition`; empty input shows everything. Filtering happens client-side; matched terms remain in their kind groups (kind headers are hidden when all their terms are filtered out).
- "Show kinds" section, styled with `.sidebar-section` / `.sidebar-label` tokens. Three kind-filter rows (Actors / Work Objects / Verbs), each: checkbox + colour swatch + label + count. Default all on; toggles hide whole kind groups. Search and kind filters compose with AND semantics.

Toolbar (top of main pane, mirrors the Scenarios header strip):

- Title `Glossary` (1.25rem, weight 600) with meta line `N terms · M actors · K work objects · L verbs`.
- Right-aligned `Collapse all references` / `Expand all references` button reusing `.collapse-all-btn` — minimal chrome, muted colour, accent on hover.

Term entries, grouped by kind:

- Kind section header (`.kind-header`): kind title in its colour, term count in muted small text.
- Each entry has a head row: chevron + term name pill + body column (definition + a muted summary line like *3 instances · used in 4 scenarios* — counts only, no chips here).
- The chevron is the existing `.scenario-chevron` shape — 8×8 corner border, -45° → 45° on toggle, 0.15s ease — used here on per-term toggle.
- Term name as a pill in its kind colour (`.term-actor` / `.term-obj` for actor/object; `.term-verb` for verbs uses cyan text with dotted underline — matches the narration styling).
- Definition paragraph, regular weight, default text colour. Empty definitions render with a muted-italic "No definition yet." placeholder so gaps are visible without erroring.

Refs block (collapsible, per-term) — the navigable detail behind the head-row counts:

- Container uses the same `grid-template-rows: 0fr ↔ 1fr` 200ms ease-out animation as `.scenario-body`. Per-term expansion state keyed by `term.id`.
- Content padding-left aligns the chips with the description column above (`18 + 14 + 180 + 14 = 226px` under the entry-head grid; spec values may be tuned to actual rendered widths).
- Up to four inline lines, each suppressed when empty (examples below are drawn from the worked example, with the relevant term annotated in parens):
  - **Stories:** chips of the form *Book a Shared Room · acts 1, 2* (for the `room` term — appearing only in the search and select activities) — one chip per story this term participates in.
  - **Scenarios:** chips of the form *Alice books a shared room · when, then* (for the `guest` term — referenced in both `when` and `then` steps) — one chip per scenario whose narration references the term.
  - **Instances** (actor / work-object terms only): chips of the form *Alice* · *Bob* (for the `guest` term) or *Deluxe Suite* (for the `room` term) — observed instance displays where `display != canonical`, aggregated from `ActivityEntity` / entity-referencing `NarrationTermRef` instances across both step narrations (in-test `given` / `when` / `then`) and fixture-level narrations (fixture-decorator `@given` / `@when` / `@then`). When an instance is first observed in a fixture's `@given`, the chip is annotated with the originating fixture name — e.g., *Alice (fixture: alice)* — so readers can navigate from the Glossary to the fixture definition. Deduped, sorted by frequency, frequency count on hover. Suppressed when only the canonical form is observed.
  - **Also used as** (verb terms only): chips of observed inflections aggregated from every `display` value seen across `ActivityTerm` / verb-referencing `NarrationTermRef` instances; deduped, sorted by frequency, canonical excluded. Suppressed when the only observed form is canonical.
- Labels use the same typography as `.entry-forms .label` (muted, regular weight, no transform). Chips are clickable; clicking jumps to the matching activity row in the Stories view or scenario card in the Scenarios view.

Visual hierarchy in an expanded entry: term pill (heaviest) > definition (regular text) > head-row summary line (quieter still) > refs-block labels "Stories" / "Scenarios" / "Instances" / "Also used as" (all the same quieter weight, forming one consistent family of navigable annotations).

#### Narration styling (`styles.css`)

`NarrationTermRef` is rendered with a single class chosen at template time by looking up the kind: `glossary[part.term_id].kind` (via the `Glossary.__getitem__` index — never the underlying list). The renderer exposes a small helper (Jinja test or filter, e.g. `term_kind(part)`) so the template stays terse.

- kind `actor` → `.term-ref-actor` — `background:#fef3c7; color:#92400e; border:1px solid #fcd34d; border-radius:4px; padding:1px 6px; font-weight:500; cursor:pointer;`
- kind `object` → `.term-ref-object` — `background:#ccfbf1; color:#0f766e; border:1px solid #5eead4; border-radius:4px; padding:1px 6px; cursor:pointer;`
- kind `verb` → `.term-ref-verb` — `color:#0e7490; border-bottom:1px dotted #0e7490; cursor:pointer; font-weight:500;` (text-only, no background)

Combined case (`param_column != None`): adds a 2px border in the matching `.param-color-N` hue, replacing the kind border. Implemented as a small modifier class.

Pointer cursor on all three kinds — clicking jumps to the Glossary tab. The term's definition shows via a `title` attribute on the span for native tooltips; a richer hover affordance is a polish task for a later spec.

#### Activity-timeline draft styling (`styles.css`)

`ActivityPlaceholder` parts in the Stories timeline use the kind-colour palette with a **draft cue**: a `1px dashed` border (instead of solid) for actors and objects, and a dashed underline (instead of dotted) for verbs. The text is italicized; the cursor is `default` (no Glossary entry to jump to); a `title` attribute reads "Draft — promote to glossary to lock in" so authors discover the migration path on hover.

- kind `actor` → `.term-ref-actor.is-draft`
- kind `object` → `.term-ref-object.is-draft`
- kind `verb` → `.term-ref-verb.is-draft`

The Glossary view does *not* list drafts (they have no glossary entry); a future enhancement may add a "Drafts" sidebar section as a parking lot for promotion candidates. Drafts can't appear in scenario narrations at all — capture rejects them at the t-string interpolation site — so the visual "promote me" cue is needed only in the story timeline.

#### Reused existing styles

The Glossary and Stories views reuse existing tokens and component classes wherever possible:

- `.search-box` / `.search-box-icon` / `.search-box-clear` — sidebar search input (Glossary).
- `.sidebar-section` / `.sidebar-label` — sidebar section headers ("Show kinds", etc.).
- `.collapse-all-btn` — Glossary toolbar's "Collapse all references" button.
- `.scenario-chevron` (and `.scenario-chevron-open` modifier) — per-term chevron in the Glossary; also activity-row expansion in Stories.
- `.scenario-body` (and `.expanded` modifier) grid-template-rows pattern — per-term refs collapsible; activity-row scenario lists.
- `.entry-forms .label` typography (muted, regular weight, no transform) — "Also used as", "Stories", "Scenarios" inline labels.

New classes (defined in `styles.css`):

- `.term-pill`, `.term-actor`, `.term-obj`, `.term-verb` — Glossary entry term names; same colours as the entity narration palette.
- `.kind-header`, `.kind-title`, `.kind-meta` — Glossary kind-group headers.
- `.entry`, `.entry-head`, `.entry-name`, `.entry-body`, `.entry-def`, `.entry-forms` — Glossary term entries.
- `.refs`, `.refs-inner`, `.refs-content`, `.refs-line` — refs collapsible region; the refs animation reuses the `.scenario-body` grid-rows transition.
- `.use-chip` — small clickable reference chip used in Glossary refs lines and Stories scenario badges.
- `.activity-row`, `.activity-num`, `.activity-cov`, `.activity-badges` — Stories timeline rows.
- `.story-sidebar`, `.story-head`, `.story-stats`, `.scn-act-strip` — Stories view structural classes.
- `.nav-tab`, `.nav-tab-active`, `.frame-nav` — three-view tab strip.

#### Coverage chip

Existing scenario status palette reused for the pass/fail/skip cases (`--color-passed`, `--color-failed`, `--color-skipped`). Activity coverage adds two new tokens defined alongside the existing ones in `styles.css`:

- `--color-mixed` — yellow, used when an activity has both passing and failing covering scenarios.
- `--color-uncovered` — neutral gray, used for activities no scenario covers (draft-bearing or otherwise gapped).

Count chip: small subscript-style block `m/n` next to the status colour.

#### Tab strip and view switching (`app.js`)

Existing Alpine setup gains:

- `view: 'scenarios' | 'stories' | 'glossary'` — active tab.
- `selectedStory: StoryId | null` — sidebar selection in the Stories view.
- `glossaryKindFilter: { actor: bool, object: bool, verb: bool }` — kind toggles in the Glossary view.
- `expandedTerms: Record<TermId, true>` — per-term refs expansion in the Glossary view.
- Computed `anyTermsExpanded` getter (parallel to existing `anyScenariosExpanded`) — drives the Collapse/Expand-all label.
- `toggleAllTerms()` method mirroring `toggleAllScenarios()` — adds/removes every term id from `expandedTerms` based on the current aggregate state.
- `hoveredActivity`, `hoveredScenario` — synced highlight state for the Stories view bidirectional anchors.

The three view containers (`#view-scenarios`, `#view-stories`, `#view-glossary`) are mounted in the same DOM and switched via `x-show`. URL hash deserialization on load; serialization on tab change and on inner state changes (story selection, glossary filters, expanded terms). Hash format: `#view=glossary&kinds=actor,object` etc.

### Optional support

Glossary and Stories are each independently optional; the three usage modes (no DS/UL → only Scenarios; Glossary only → Scenarios + Glossary; Story declared → all three) emerge from the tab visibility rules:

- Scenarios: always visible.
- Stories: `len(ReportData.stories) > 0`.
- Glossary: `ReportData.glossary is not None and len(ReportData.glossary.terms) > 0`.

When only one tab is visible, the tab strip itself is hidden — degenerate to today's single-view report.

## Components touched

- `src/pytest_given/model/schema.py` — new dataclasses and union types per the *Data model* section; additions on `ReportData`, `Scenario`, `Step`.
- `src/pytest_given/model/serde.py` — encode/decode for the new types; `type` discriminator for `ActivityPart` and `NarrationPart` variants.
- `src/pytest_given/model/__init__.py` — re-export new types.
- `src/pytest_given/capture/glossary.py` — `Glossary` class; `Actor`/`WorkObject`/`Verb` value classes (with glossary back-refs); call-syntax overloads producing `ActorInstance` / `WorkObjectInstance` (for nouns) and `InflectedVerb` (for verbs); id auto-derivation; conflict enforcement.
- `src/pytest_given/capture/draft.py` — `draft` singleton, `DraftActor`/`DraftWorkObject`/`DraftVerb` value classes (kind+text, no glossary back-ref).
- `src/pytest_given/capture/story.py` — `path`, `activity`, `story` constructors; grammar validation; multi-path; per-process story-id uniqueness set.
- `src/pytest_given/capture/template.py` — extend `narration_from` t-string branch to emit `NarrationTermRef`.
- `src/pytest_given/capture/decorators.py` — `activity=` kwarg on `given`/`when`/`then`.
- `src/pytest_given/plugin.py` — `story=` / `activities=` on `@scenario`; session-finish discovery walk populating `ReportData.stories` and `ReportData.glossary`.
- `src/pytest_given/report/coverage.py` — pure implicit-binding inference (`compute_coverage`).
- `src/pytest_given/report/renderer.py` — handle `NarrationTermRef` via glossary lookup; pass glossary / stories / coverage maps and a `term_kind(part)` Jinja helper.
- `src/pytest_given/report/templates/report.html.j2` — tab strip; Scenarios / Stories / Glossary view markup.
- `src/pytest_given/report/templates/styles.css` — entity/verb/draft styling; tab strip; timeline rows; coverage chip; scenario badge strip.
- `src/pytest_given/report/templates/app.js` — `view` state; hash sync; sync-highlight.
- `src/pytest_given/__init__.py` — re-export `Glossary`, `draft`, `story`, `activity`, `path`.
- `README.md`, `GLOSSARY.md` — document the new authoring API.
- `examples/test_examples.py` → renamed to `examples/test_coffeeshop.py` — preserves today's showcase of the basic pytest-given features (no DS/UL content; the rename keeps the file's purpose explicit now that a second example exists).
- `examples/test_hotel_booking.py` — **new** example showcasing the DDD/DS features end-to-end: the *Online Hotel Booking* domain from the worked example above (actors `Guest`, `Booking System`; work objects `Room`, `Booking`, `Payment`, `Confirmation`; verbs `search`, `select`, `submit`, `confirm`, `send`), the `book_a_shared_room` story connecting them, and a couple of scenarios bound to it (covering both implicit term-ref inference and explicit `activity=`). Includes the `draft.verb('redeems')` + `draft.work_object('loyalty bonus')` activity to demonstrate iterative-authoring. Deliberately narrow — doesn't repeat parametrize / fixture / failure showcases that already live in `test_coffeeshop.py`.
- **One report per example file.** Each example produces its own JSON + HTML pair:
  - `examples/coffeeshop.html` + `examples/coffeeshop-data.json` (from `test_coffeeshop.py`)
  - `examples/hotel-booking.html` + `examples/hotel-booking-data.json` (from `test_hotel_booking.py`)

  These replace the current single-output `examples/report.html` / `examples/report-data.json`.
- `noxfile.py` — the `examples` session runs pytest twice (once per example file), regenerating both report pairs above. The current single-invocation form is replaced; factor the shared pytest args into a helper if it stays readable.

## Error handling

- **Term id conflict on mismatch.** Raised by the `Glossary` method when re-registration with the same derived id has divergent fields. Message names both call sites (module / line) and the differing field(s).
- **Cross-kind id collision within a glossary.** Same site, same call; message names both kinds.
- **Empty derived id.** Raised by `Glossary.actor` / `work_object` / `verb` and module-level `story(...)` when the auto-derivation rule yields the empty string.
- **Story id conflict.** Raised by module-level `story(...)` when two stories derive to the same id; message names both declaration sites.
- **Story spans multiple glossaries (v1).** Raised by `story(...)` at construction when its parts reference more than one distinct `Glossary` instance; message lists the offending glossaries.
- **Activity grammar violation.** Raised by `path(...)` (and the implicit single-path inside `activity(...)`) when any of the three leading-triple rules fails:
  - Position 0 is not an actor → message names the offending first-part type and suggests active-voice rephrasing (e.g., for `activity(room, confirm, guest)`: "did you mean `activity(guest, confirm, room)`?").
  - Position 1 is not a verb → message indicates the activity has a subject but no action.
  - Position 2 is not an anchored noun (actor or work object, typed or draft) → message suggests promoting the bare string to `g.work_object(...)` / `g.actor(...)` or wrapping it with `draft.*`.
  - Path has fewer than 3 parts → message indicates the activity is incomplete.

  Each variant includes the malformed activity's parts as repr.
- **Empty draft text.** Raised by `draft.actor(...)` / `draft.work_object(...)` / `draft.verb(...)` when the supplied text is empty or whitespace-only. Drafts are required to display *something*; an empty draft would render as a styled blank.
- **`@scenario(story=...)` not a `Story`.** Raised at collection (`pytest_collection_modifyitems`); message shows the offending type.
- **Activity id not in story.** Same time; raises with the story's valid activity ids.
- **Step `activity=` outside scenario scope.** When the scenario has explicit `activities=[...]`, the step's `activity_ids` must be a subset; raises with both sets in the message. When the scenario uses implicit binding (`activities=()`), the step's `activity_ids` is validated against the story's full activity-id set.
- **Multiple `Glossary` instances reached at session finish.** Raised by the plugin; message lists each glossary's id-set and the stories that pulled it in.
- **Term-like value inside narration that's neither typed nor wrapped.** Type detection requires the interpolation value to be an `Actor` / `WorkObject` / `Verb` / `ActorInstance` / `WorkObjectInstance` / `InflectedVerb` instance; ordinary strings continue to render via `NarrationValue` / `NarrationPlaceholder`. No error; just no pill.
- **Draft interpolated in narration.** Raised by `narration_from(...)` (the t-string capture path) when an interpolation value is a `DraftActor` / `DraftWorkObject` / `DraftVerb`. Message names the draft's text and kind and suggests either promoting it to a glossary term (with the corresponding `g.actor(...)` / `g.work_object(...)` / `g.verb(...)` snippet) or replacing the interpolation with a plain string.

All errors except the construction-time ones above are pytest-collection or session-finish errors (raised before / immediately after test execution); construction-time errors fire at module-import time, so authors see them during `pytest --collect-only` or at startup.

## Testing

### Unit

- `tests/unit/capture/test_glossary.py` (new):
  - `Glossary().actor('Guest')` returns an `Actor` whose underlying term has `id == 'guest'` and `kind == 'actor'`; the actor carries a back-ref to its glossary.
  - Idempotent re-registration (same args) returns an equivalent handle; conflict on mismatched definition raises.
  - Cross-kind id collision within a single glossary raises (`g.actor('Foo')` + `g.verb('foo')`).
  - Id auto-derivation: `'Order received'` → `'order-received'`; underscores collapse; non-ASCII letters strip; empty derived id raises.
  - Call syntax on a noun: `guest('Alice')` returns `ActorInstance(actor=guest, display='Alice')`; `room('Deluxe Suite')` returns `WorkObjectInstance(work_object=room, display='Deluxe Suite')`. Identity is derived from display ≠ canonical.
  - Call syntax on a verb: `confirm('confirms')` returns `InflectedVerb(verb=confirm, display='confirms')`. Identity stays `term_id` regardless of display.
- `tests/unit/capture/test_story.py` (new):
  - `path(...)` leading-triple grammar — position 0 must be an actor; a `WorkObject` / `Verb` / `DraftWorkObject` / `DraftVerb` / bare string in position 0 raises.
  - `path(...)` position 1 must be a verb (`Verb`, `InflectedVerb`, or `DraftVerb`); an `Actor` / `WorkObject` / bare string in position 1 raises.
  - `path(...)` position 2 must be an anchored noun (`Actor` / `WorkObject` / `ActorInstance` / `WorkObjectInstance` / `DraftActor` / `DraftWorkObject`); a bare string or `Verb` in position 2 raises.
  - `path(...)` paths with fewer than 3 parts raise.
  - `path(...)` accepts free-form parts beyond position 2: a 5-part `(actor, verb, work_object, 'into', work_object)` path validates cleanly.
  - `path(...)` part dispatch: `Actor`/`WorkObject`/`ActorInstance`/`WorkObjectInstance` → `ActivityEntity`; `Verb`/`InflectedVerb` → `ActivityTerm`; `DraftActor`/`DraftWorkObject`/`DraftVerb` → `ActivityPlaceholder`; bare `str` → `ActivityWord`.
  - `activity(...)` accepts positional single-path; multi-path via `path(...)` calls; mixing raises.
  - `story(...)` auto-numbers activities in declaration order; explicit `id=` on an activity keeps it; uniqueness checked.
  - `story(...)` across two distinct `Glossary` instances raises (v1 invariant). Drafts do not contribute to the glossary-set check.
  - Story-id duplicate detection raises on second declaration of the same title.
- `tests/unit/capture/test_draft.py` (new):
  - `draft.actor('Concierge')` returns a `DraftActor` with `kind='actor'`, `text='Concierge'`.
  - Empty/whitespace draft text raises.
  - Two `draft.actor('Concierge')` calls produce equal-valued instances (data equality, not necessarily identity).
  - `str(draft.actor('Concierge')) == 'Concierge'` — drafts stringify to their text for `repr` / debug use. T-string interpolation rejects them at capture, separately covered in `test_template.py`.
- `tests/unit/capture/test_template.py`:
  - T-string interpolation of `Actor` → `NarrationTermRef(term_id='guest', display='Guest', param_column=None)` — no `kind` field on the part.
  - T-string interpolation of `ActorInstance` / `WorkObjectInstance` → `NarrationTermRef` with the instance display, `term_id` of the underlying term.
  - T-string interpolation of `InflectedVerb` → `NarrationTermRef` with the inflected display, `term_id` of the verb.
  - Interpolation matching a parametrize column AND carrying an entity value → `NarrationTermRef(..., param_column=<col>)`.
  - T-string interpolation of a `DraftActor` / `DraftWorkObject` / `DraftVerb` raises `PytestGivenError` — drafts are not permitted in narrations.
- `tests/unit/model/test_schema.py` / `test_serde.py`:
  - All new dataclasses round-trip through `report_to_dict` / `report_from_dict`.
  - `ActivityPart` variants discriminate correctly on a structural `type` key (`entity` / `term` / `word`); kind is not on the part.
  - `NarrationTermRef` round-trips without a `kind` field.
  - `ReportData.glossary == None` and `ReportData.stories == []` round-trip.
- `tests/unit/report/test_coverage.py` (new):
  - Implicit binding: step references full set → covers activity; missing verb or missing entity → does not cover.
  - Draft exclusion: activity containing any `ActivityPlaceholder` is excluded from implicit coverage; only explicit step `activity=N` brings it in.
  - Multi-step scenario: scenario coverage is the union of step coverage.
  - Explicit step `activity_ids` overrides inference for that step but not others.
  - Multi-path activity: any one path's term-set may participate; satisfying *one* path suffices (refined: the activity counts as covered iff the union of its parts' refs is a subset of the step's refs).
  - Drafts hard-exclude from implicit coverage: an activity containing any `ActivityPlaceholder` is excluded from term-ref inference entirely, regardless of how many of its typed terms a step mentions. Explicit step `activity=N` is the only way to cover it.
  - Promoting a draft to a glossary term changes the coverage outcome: the activity rejoins implicit coverage with the promoted term added to `A_refs`, and steps must mention every term in `A_refs` to keep coverage.
- `tests/unit/report/test_renderer.py`:
  - The narration filter resolves `NarrationTermRef` to the matching CSS class via glossary lookup (`actor`/`object`/`verb`); combined case adds the `param-color-N` modifier.
  - Tab visibility flags surface to the template context based on `ReportData.glossary` being `None`-or-empty / `ReportData.stories` emptiness.
  - Coverage map structure (per scenario, per activity) reaches the template.

Per [[feedback-no-frontend-markup-tests]] these stay on the data-shape contract — no asserts on raw HTML / class strings.

### Integration

- `tests/integration/test_domain_storytelling.py` (new):
  - A small DDD/DS suite (using the same Online Hotel Booking domain as the example file, or a focused subset) with glossary, story, and three scenarios runs cleanly; JSON output has populated `glossary`, `stories`, `scenario.story_id`, and per-step term-refs.
  - Scenario with `activities=()` and matching steps yields inferred scenario coverage equal to the set of activities its steps reference.
  - Scenario with explicit `activities=[1, 2]` plus a step bound to `activity=5` raises at collection.

### Visual (Playwright)

Per [[feedback-no-frontend-markup-tests]], Playwright is the only verification for renderer correctness.

- Regenerate both reports via `uv run nox -s examples` after the rename to `examples/test_coffeeshop.py` and the addition of `examples/test_hotel_booking.py`. The session produces two pairs: `examples/coffeeshop.{html,-data.json}` (basic-feature showcase, no DS/UL tabs visible — sanity check that the optional features stay optional) and `examples/hotel-booking.{html,-data.json}` (Online Hotel Booking — the DDD/DS demo). The Playwright assertions below target the hotel-booking report.
- Open in Playwright and verify:
  - Three tabs present and switchable; URL hash updates.
  - Stories view: timeline rendering, status colours, scenario badge clicks anchor down to the matching card.
  - Bidirectional sync-highlight: hovering an activity row highlights matching scenarios; hovering a scenario card highlights matching activity rows.
  - Glossary view: kind filters toggle term groups; "Used in" links navigate cross-view.
  - Cursor on all entity refs is pointer; clicking jumps to the Glossary entry.
  - At least one activity in the hotel-booking story is uncovered (the draft-bearing one — e.g., the `loyalty bonus` activity) and renders with the gap state; draft parts render with the dashed `is-draft` styling.
- Console messages clean after init.

### Coverage gate

100% per AGENTS.md; new modules exercised by the unit tests above. Per [[feedback-assert-over-pragma]], invariant guards use `assert`, not `# pragma: no cover`.

## Open follow-ups (not in scope, tracked here)

- **Multiple `Glossary` instances per suite (one per Bounded Context).** Adds: a `Glossary(name=...)` field for disambiguation; a glossary selector in the Glossary view (shown only when `len(glossaries) > 1`); context-grouping in the Stories sidebar; stories that span multiple BCs (cross-context interactions, context maps); `ReportData.glossaries: list[Glossary]` instead of the single `glossary` field. The v1 data model deliberately keeps `Story` independent of any particular `Glossary` to leave this path open.
- Example Mapping integration: rule / question authoring atop the story↔scenario substrate.
- egon.io import: parse `.dst` JSON into a `Story`; emit `.dst` from a declared `Story`.
- External glossary file ingestion (YAML / Markdown).
- Glossary synonyms and external doc-link fields.
- Pictogrammatic activity rendering (graph view) — the data model is graph-ready and supports the kind-driven consolidation rule from Domain Storytelling (actors consolidated, work objects per-activity).
- Domain Storytelling Groups (labelled wrappers around activity ranges — subprocesses, parallel branches) and Annotations (freeform notes attached to activities or sentences). Both extend the schema additively; the timeline view can grow group-row headers and an annotation gutter without disturbing existing rendering.
- Step's `activity_ids` ergonomics: a sentinel like `activity='all'` to cover the whole story explicitly.
- Unicode-aware id auto-derivation (NFKD fold for non-ASCII letters) — v1 strips them.
- Agent skill for pytest-given authoring (existing TODO; likely benefits from this design's vocabulary).
