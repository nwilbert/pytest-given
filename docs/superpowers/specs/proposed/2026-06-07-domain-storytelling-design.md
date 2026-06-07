# Domain Storytelling — Design Spec

## Goal

Turn the pytest-given HTML report into an executable artifact of Domain-Driven Design discovery. Add three pieces, each optional and independently useful:

1. A suite-wide **Ubiquitous Language glossary** — terms tagged as actor / object / verb, with definitions.
2. **Domain Stories** — sequence-numbered activity timelines that reference glossary terms.
3. **Scenario↔activity binding** — explicit on `@scenario(...)` / step `activity=`, or implicit from the glossary terms referenced in step narration.

The report grows a top-level tabbed navigation: **Scenarios** (today's view, unchanged), **Stories**, **Glossary**. Each tab is hidden when its data is empty. A suite using neither DS nor UL is unaffected.

## Scope

In:

- `Glossary` + `GlossaryTerm` (kinds: `actor` / `object` / `verb`) at suite level.
- `Story`, `Activity`, `ActivityPath`, and three `ActivityPart` variants (`ActivityEntity`, `ActivityTerm`, `ActivityWord`).
- New narration variant `NarrationTermRef` replacing the placeholder for entity / verb-term references in t-strings.
- Public API: `actor`, `work_object`, `verb`, `story`, `activity`, `path`; fixture-decorator forms of `actor` / `work_object`; scenario kwarg `story=` / `activities=`; step kwarg `activity=`.
- Implicit binding inference from step term-refs.
- Three-view report navigation; story timeline with per-row scenario badges and bidirectional anchors; glossary view grouped by kind.
- Pass/fail propagation onto activities, with count chip.
- Per-use inflection via call syntax (`dispense('dispenses')`, `cup('Cups')`).

Out:

- Example Mapping rule / example / question authoring (separate spec).
- egon.io file import or export (`.dst`, `.egn`, SVG, PNG).
- External glossary file formats (YAML / JSON / Markdown).
- Event Storming integration.
- Glossary synonyms, anchoring against non-narration text, external doc links from term entries.
- Pictogrammatic story rendering (egon.io-style); the data model leaves graph rendering open for a later spec.
- Custom `format_spec` semantics in t-strings — type detection is the only mechanism.
- A graph view of activities. The schema supports one via `ActivityPath` parts, but only the timeline view ships in v1.

## Background

pytest-given today captures each test as a `Scenario` with a tree of `Step`s and renders them as a flat collection of cards (`src/pytest_given/report/templates/report.html.j2`). Narration parts are one of:

- `NarrationLiteral` — plain text.
- `NarrationValue` — t-string interpolation whose name does not match a parametrize column; rendered bold.
- `NarrationPlaceholder` — t-string interpolation matching a parametrize column; rendered with one of six palette colours (`.param-color-0..5` in `styles.css`).

The dispatch lives in `_make_narration_filter` (`src/pytest_given/report/renderer.py`), discriminating by Python type via `match`/`case`.

Per AGENTS.md the project is pre-release; JSON schema changes are not hedged ([[project-prerelease-status]]).

Two TODOs in `TODO.md` motivate this spec:

- "Think about UL support (e.g., by connecting the report to a glossary)".
- "Provide an agent skill for work with pytest-given" — the spec deliberately leaves room for that follow-up.

## Approach

### Data model (`src/pytest_given/model/schema.py`)

NewType aliases (per AGENTS.md: `NewType` for domain ids, PEP 695 `type` only for plain aliases):

```python
TermId = NewType('TermId', str)
ActivityId = NewType('ActivityId', int)
StoryId = NewType('StoryId', str)
```

Glossary:

```python
@dataclass(frozen=True)
class GlossaryTerm:
    id: TermId
    kind: Literal['actor', 'object', 'verb']
    canonical: str
    definition: str

@dataclass(frozen=True)
class Glossary:
    terms: tuple[GlossaryTerm, ...]
```

Stories:

```python
class ActivityPart: ...

@dataclass(frozen=True)
class ActivityEntity(ActivityPart):
    kind: Literal['actor', 'object']
    entity_id: TermId
    display: str

@dataclass(frozen=True)
class ActivityTerm(ActivityPart):
    term_id: TermId          # kind == 'verb'
    display: str

@dataclass(frozen=True)
class ActivityWord(ActivityPart):
    text: str

@dataclass(frozen=True)
class ActivityPath:
    parts: tuple[ActivityPart, ...]

@dataclass(frozen=True)
class Activity:
    id: ActivityId
    paths: tuple[ActivityPath, ...]

@dataclass(frozen=True)
class Story:
    id: StoryId
    title: str
    activities: tuple[Activity, ...]
```

New narration part variant (replaces my earlier draft's `NarrationEntity`):

```python
@dataclass(frozen=True)
class NarrationTermRef(NarrationPart):
    kind: Literal['actor', 'object', 'verb']
    term_id: TermId
    display: str
    param_column: str | None = None   # set iff the interpolation matched a parametrize column
```

Additions on existing types:

- `ReportData.glossary: Glossary` (default: empty `Glossary(terms=())`).
- `ReportData.stories: tuple[Story, ...]` (default: `()`).
- `Scenario.story_id: StoryId | None = None`.
- `Scenario.activity_ids: tuple[ActivityId, ...] = ()` — explicit floor; `()` means *infer from steps*.
- `Step.activity_ids: tuple[ActivityId, ...] = ()` — explicit tighter binding (a step may cover one or more activities); `()` means *infer from this step's term-refs*.

### Authoring API (`src/pytest_given/__init__.py` exports; implementation in new modules)

Public surface:

| Name | Signature | Effect |
|---|---|---|
| `actor` | `(name: str, *, id: str \| None = None, definition: str = '') -> Actor` | Returns an `Actor`; registers a `GlossaryTerm(kind='actor')` |
| `work_object` | `(name: str, *, id: str \| None = None, definition: str = '') -> WorkObject` | Same, kind `'object'` |
| `verb` | `(canonical: str, *, id: str \| None = None, definition: str = '') -> Verb` | Same, kind `'verb'` |
| `@actor(...)` | Applied to a `@pytest.fixture`-decorated function | Wraps return value in entity proxy |
| `@work_object(...)` | Same | Same |
| `path` | `(*parts: Actor \| WorkObject \| Verb \| InflectedRef \| str) -> ActivityPath` | Validates grammar |
| `activity` | `(*parts_or_paths, id: int \| None = None) -> Activity` | Single-path (positional parts) or multi-path (positional `Path`s) |
| `story` | `(title: str, *, id: str \| None = None, activities: tuple[Activity, ...] = ()) -> Story` | Registers `Story` |
| `@scenario` | Existing decorator + `story=Story \| str \| None`, `activities=Sequence[int] = ()` | Scenario-level binding |
| `given` / `when` / `then` | Existing context-managers + kwarg `activity: int \| Sequence[int] \| None = None` | Step-level binding |

Id auto-derivation: lowercase `name` / `canonical`, replace runs of non-alphanumerics with `-`, strip leading/trailing `-`. `"Customer"` → `"customer"`; `"Order received"` → `"order-received"`. Explicit `id=` always wins.

Story id auto-derivation: same rule applied to `title`.

Activity sequence numbers: the `Story` constructor assigns `1..N` from positional order. An `Activity` constructed with explicit `id=N` (or a leading integer positional) keeps that id; the story validates uniqueness across activities and a strictly increasing order is preferred but not enforced (gaps are allowed for future inserts).

Inflection at use site: `Actor`, `WorkObject`, `Verb` are callable with a single string argument returning an `InflectedRef(term, display)`. Activities and t-strings both accept the bare term (canonical display) or the inflected form. No `forms` field on `GlossaryTerm`; observed displays are aggregated at render time.

Worked example:

```python
# domain.py
from pytest_given import actor, work_object, verb, story, activity

customer = actor('Customer', definition='Person buying coffee.')
machine  = actor('Machine',  definition='Automated coffee dispenser.')
cup      = work_object('Cup',    definition='Container for coffee.')
coin     = work_object('Coin',   definition='Unit of currency.')
beans    = work_object('Beans',  definition='Roasted coffee beans.')
coffee   = work_object('Coffee', definition='Brewed coffee in a cup.')
button   = work_object('Button', definition='Selection button.')

place    = verb('place',    definition='Set the cup under the dispenser.')
insert   = verb('insert',   definition='Drop a coin into the slot.')
press    = verb('press',    definition='Push a selection button.')
grind    = verb('grind',    definition='Mill beans into grounds.')
dispense = verb('dispense', definition='Deliver coffee from the spout.')

order_coffee = story('Order Coffee', activities=(
    activity(customer, place('places'),       cup),
    activity(customer, insert('inserts'),     coin),
    activity(customer, press('presses'),      button),
    activity(machine,  grind('grinds'),       beans),
    activity(machine,  dispense('dispenses'), coffee, 'into', cup),
))
```

```python
# tests/test_orders.py
from pytest_given import scenario, given, when, then
from domain import (order_coffee, customer, machine, cup, coin, coffee,
                    button, place, insert, press, dispense)

@scenario('Buy coffee', story=order_coffee)
def test_buy_coffee():
    with given(t'the {customer} has a {coin}'):
        ...
    with when(t'the {customer} {place('places')} the {cup}'):
        ...
    with when(t'the {customer} {insert('inserts')} the {coin}'):
        ...
    with when(t'the {customer} {press('presses')} the {button}'):
        ...
    with then(t'the {machine} {dispense('dispenses')} the {coffee} into the {cup}'):
        ...
```

No explicit `activity=` anywhere; scenario coverage is `{1, 2, 3, 5}` inferred from step term-refs.

### Registration model (`src/pytest_given/capture/registry.py`, new module)

Process-global registries — one for the Glossary, one for Stories — populated at module import time by the constructors. Snapshotted into `ReportData.glossary` / `ReportData.stories` at session start (existing `pytest_sessionfinish` flow). Both registries are mutable during collection and frozen for emission.

Conflict semantics:

- Re-registering the same term `id` is idempotent if all fields match exactly; raises `PytestGivenError` if any field differs.
- Cross-kind id collision (e.g. `actor('foo')` and `verb('foo')`) raises with a message naming both kinds and source-module hints.
- Re-registering a `Story` id raises unconditionally.

Test isolation: registries are cleared at session start before conftest collection, so pytest's own subprocess invocations and repeated test runs do not accumulate state.

### Capture (`src/pytest_given/capture/template.py`, `src/pytest_given/capture/decorators.py`)

`narration_from(...)` already dispatches `str` / `Template` / t-string into a `Narration`. Extend the t-string branch:

- For each interpolation, after current parametrize-name matching:
  - If the interpolation value `isinstance(value, Actor | WorkObject | Verb | InflectedRef)`: produce a `NarrationTermRef(kind=…, term_id=…, display=…, param_column=<col if matched else None>)`.
  - If the value is an `InflectedRef`: the display is the inflected form, term_id is the underlying term.
  - Else fall back to existing `NarrationValue` / `NarrationPlaceholder` paths.

Scenario binding capture (`src/pytest_given/plugin.py`, in `pytest_collection_modifyitems` or wherever `@scenario` metadata is read): read `story=` (may be a `Story`, its id string, or `None`) and `activities=` (validated as a tuple of ints, each present in the story's activity ids when explicit). Store in `Scenario.story_id` / `Scenario.activity_ids`.

Step binding capture (`given` / `when` / `then` context-manager entry): accept `activity: int | Sequence[int] | None`. Normalize to `tuple[ActivityId, ...]`. Store in `Step.activity_ids` (a single int becomes a 1-tuple; `None` leaves the field as `()`).

### Implicit binding (renderer-time, no schema cost)

Algorithm at render time, for any `Scenario` with `activity_ids == ()` whose `story_id` is set:

For each `Step` reachable from the scenario:
1. If `step.activity_ids != ()`: those are the step's covered activities (explicit override).
2. Else compute the step's term-ref set `S = {tr.term_id for tr in step.narration.parts if isinstance(tr, NarrationTermRef)}`.
3. For each activity `A` in the bound story: collect its term-ref set `A_refs` = union over all paths of `entity_id` / `term_id` from `ActivityEntity` and `ActivityTerm` (ignore `ActivityWord`). Activity `A` is covered by step iff `A_refs ⊆ S`.
4. Scenario coverage = union of all step coverages.

The subset rule transparently handles verb and entity matching: if `A` has a verb term, that term must appear in `S`; if `A` is verbless (only `ActivityWord` between entities), only the entities need to match. For multi-path activities the union across paths means the step must reference every term across every path — strict semantics for v1; per-path partial coverage is a follow-up.

Empty cases: scenario has no story → not on the Stories view at all. Scenario has story but no step covers any activity → renders under the story with zero activity coverage badges; activity rows render as gaps.

The algorithm runs in `src/pytest_given/report/coverage.py` (new module). It is pure (input: `Scenario`, `Story`; output: `dict[ActivityId, set[StepRef]]`). Renderer calls it once per (scenario, story) pair.

### Serde (`src/pytest_given/model/serde.py`)

Round-trip the new types. `ActivityPart` variants discriminate on a `kind` key, mirroring how `NarrationPart` already discriminates:

```json
{"type": "actor",  "entity_id": "customer", "display": "Customer"}
{"type": "object", "entity_id": "cup",      "display": "Cup"}
{"type": "verb",   "term_id":   "dispense", "display": "dispenses"}
{"type": "word",   "text":      "into"}
```

The `NarrationTermRef` follows the same pattern:

```json
{"type": "term-ref", "kind": "actor", "term_id": "customer",
 "display": "Customer", "param_column": null}
```

`ReportData` gains:

```json
{
  "glossary": {"terms": [...]},
  "stories":  [...],
  "scenarios": [...]
}
```

Existing fields unchanged.

### Renderer (`src/pytest_given/report/renderer.py`, templates, styles, app.js)

#### Three-view navigation

A top-level tab strip rendered in `report.html.j2`:

- Tab visibility (canonical): `Scenarios` always; `Stories` shown iff `len(stories) > 0`; `Glossary` shown iff `len(glossary.terms) > 0`. See *Optional support* below for the practical implication that any non-empty Stories implies a non-empty Glossary.
- Active tab tracked via `x-data` on the body with `view: 'scenarios' | 'stories' | 'glossary'`; URL hash carries `#view=stories&story=order-coffee` or similar.
- Sidebar contents bound to the active tab.

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

- Search box wrapping the input with the existing `.search-box` / `.search-box-icon` / `.search-box-clear` pattern (magnifying-glass left, clear-× right). Reuses existing styles directly.
- "Show kinds" section, styled with `.sidebar-section` / `.sidebar-label` tokens. Three kind-filter rows (Actors / Work Objects / Verbs), each: checkbox + colour swatch + label + count. Default all on; toggles hide whole kind groups.

Toolbar (top of main pane, mirrors the Scenarios header strip):

- Title `Glossary` (1.25rem, weight 600) with meta line `N terms · M actors · K work objects · L verbs`.
- Right-aligned `Collapse all references` / `Expand all references` button reusing `.collapse-all-btn` — minimal chrome, muted colour, accent on hover.

Term entries, grouped by kind:

- Kind section header (`.kind-header`): kind title in its colour, term count in muted small text.
- Each entry has a head row: chevron + term name pill + body column (definition + optional "Also used as" line).
- The chevron is the existing `.scenario-chevron` shape — 8×8 corner border, -45° → 45° on toggle, 0.15s ease — used here on per-term toggle.
- Term name as a pill in its kind colour (`.term-actor` / `.term-obj` for actor/object; `.term-verb` for verbs uses cyan text with dotted underline — matches the narration styling).
- Definition paragraph, regular weight, default text colour. Empty definitions render with a muted-italic "No definition yet." placeholder so gaps are visible without erroring.
- "Also used as: *forms*" — observed inflections auto-aggregated from every `display` value seen across `ActivityEntity` / `ActivityTerm` / `NarrationTermRef` instances; deduplicated, sorted by frequency, canonical excluded. Suppressed when the only observed form is canonical.

Refs block (collapsible, per-term):

- Container uses the same `grid-template-rows: 0fr ↔ 1fr` 200ms ease-out animation as `.scenario-body`. Per-term expansion state keyed by `term.id`.
- Content padding-left aligns the chips with the description column above (`18 + 14 + 180 + 14 = 226px` under the entry-head grid; spec values may be tuned to actual rendered widths).
- Two inline lines, each suppressed when empty:
  - **Stories:** chips of the form *Order Coffee · acts 1, 5* — one chip per story this term participates in.
  - **Scenarios:** chips of the form *Buy coffee · when, then* — one chip per scenario whose narration references the term.
- Labels use the same typography as `.entry-forms .label` (muted, regular weight, no transform). Chips are clickable; clicking jumps to the matching activity row in the Stories view or scenario card in the Scenarios view.

Visual hierarchy in an expanded entry: term pill (heaviest) > definition (regular text) > "Also used as" / "Stories" / "Scenarios" labels (all quieter, matching). The three "label : chip(s)" lines form a consistent family of metadata annotations under each definition.

#### Narration styling (`styles.css`)

Two CSS classes per kind. `NarrationTermRef`:

- `kind="actor"`: `.term-ref-actor` — `background:#fef3c7; color:#92400e; border:1px solid #fcd34d; border-radius:4px; padding:1px 6px; font-weight:500; cursor:pointer;`
- `kind="object"`: `.term-ref-object` — `background:#ccfbf1; color:#0f766e; border:1px solid #5eead4; border-radius:4px; padding:1px 6px; cursor:pointer;`
- `kind="verb"`: `.term-ref-verb` — `color:#0e7490; border-bottom:1px dotted #0e7490; cursor:pointer; font-weight:500;` (text-only, no background)

Combined case (param_column != None): adds a 2px border in the matching `.param-color-N` hue, replacing the kind border. Implemented as a small modifier class.

Pointer cursor on all three kinds — clicking jumps to the Glossary tab. The term's definition shows via a `title` attribute on the span for native tooltips; a richer hover affordance is a polish task for a later spec.

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

Existing scenario status palette (`--color-passed`, `--color-failed`, `--color-skipped`) reused. Count chip: small subscript-style block `m/n` next to the status colour.

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

Three independence guarantees, all governed by the same two emptiness checks:

- **No story, no terms** → only the Scenarios view; tab strip hidden (single-tab degenerate state matches today's report).
- **Glossary declared, no story** → Scenarios + Glossary tabs. Narration uses term refs for highlighting; the Glossary view stands alone.
- **Story declared** → Stories + Scenarios + Glossary tabs. The grammar invariant on `ActivityPath` (`Entity (Word+ Entity)+`) guarantees a declared story has at least two entities, each of which auto-registers a glossary term — so a non-empty Stories implies a non-empty Glossary.

Tab visibility rules:
- Scenarios: always visible.
- Stories: `len(ReportData.stories) > 0`.
- Glossary: `len(ReportData.glossary.terms) > 0`.

These are explicit guards in the Jinja tab strip; no further per-case logic.

## Components touched

- `src/pytest_given/model/schema.py` — all new dataclasses (`Glossary`, `GlossaryTerm`, `Story`, `Activity`, `ActivityPath`, `ActivityEntity`, `ActivityTerm`, `ActivityWord`, `NarrationTermRef`); NewType aliases; additions on `ReportData`, `Scenario`, `Step`.
- `src/pytest_given/model/serde.py` — encode/decode all new types, including the `kind`-discriminated `ActivityPart` and `NarrationTermRef` variants.
- `src/pytest_given/model/__init__.py` — re-export new types.
- `src/pytest_given/capture/registry.py` — new module; process-global Glossary + Stories registries with session-start clear and snapshot.
- `src/pytest_given/capture/glossary.py` — new module: `actor`, `work_object`, `verb` constructors; `Actor` / `WorkObject` / `Verb` / `InflectedRef` classes; fixture-decorator forms.
- `src/pytest_given/capture/story.py` — new module: `path`, `activity`, `story` constructors; grammar validation; multi-path support.
- `src/pytest_given/capture/template.py` — extend `narration_from` t-string branch to emit `NarrationTermRef` on entity / verb-term values.
- `src/pytest_given/capture/decorators.py` — accept `activity=` kwarg on `given` / `when` / `then`; normalize to `tuple[ActivityId, ...]`; record on `Step`.
- `src/pytest_given/plugin.py` — accept `story=` / `activities=` on `@scenario`; resolve `story` arg (Story or id); validate activity ids; snapshot registries at session start.
- `src/pytest_given/report/coverage.py` — new module: pure implicit-binding inference.
- `src/pytest_given/report/renderer.py` — extend `_make_narration_filter` to handle `NarrationTermRef`; pass glossary / stories / coverage maps to Jinja env.
- `src/pytest_given/report/templates/report.html.j2` — tab strip; three view containers; Stories view markup (sidebar list, story header, activity timeline, scenario cards section with badge strips); Glossary view markup (kind filters, term entries).
- `src/pytest_given/report/templates/styles.css` — entity pill classes; verb dotted-underline class; tab strip; story timeline rows; coverage chip; scenario badge strip; "Covers:" strip on scenario cards.
- `src/pytest_given/report/templates/app.js` — `view` state in Alpine root; hash sync; sync-highlight `hoveredActivity` / `hoveredScenario`.
- `src/pytest_given/__init__.py` — re-export `actor`, `work_object`, `verb`, `story`, `activity`, `path`.
- `README.md` and `GLOSSARY.md` — document the new authoring API and update the canonical-vocabulary list.
- `examples/test_examples.py` — add an "Order Coffee" story example exercising all three views; regenerate via `uv run nox -s examples`.

## Error handling

- **Term id conflict on mismatch.** `PytestGivenError` naming both sites (module / line) and the differing field(s).
- **Cross-kind id collision.** `PytestGivenError` naming both kinds.
- **Story id conflict.** `PytestGivenError` naming both story declarations.
- **Activity grammar violation.** `PytestGivenError` raised by `path(...)` (and the implicit single-path inside `activity(...)`); message names the offending position (e.g. "two adjacent entities at parts[2]:parts[3]") and the malformed activity's parts as repr.
- **Unknown story in `@scenario(story=...)`.** Resolved at collection time (`pytest_collection_modifyitems`); raises with the list of registered story ids.
- **Activity id not in story.** Same time; raises with the story's valid activity ids.
- **Step `activity=` outside scenario scope.** When scenario has explicit `activities=[...]`, the step's `activity_ids` must be a subset; raises with both sets in the message. When the scenario uses implicit binding (`activities=()`), the step's `activity_ids` is validated against the story's full activity-id set.
- **Inflection of an entity inside narration that's neither callable nor wrapped.** Type detection requires the interpolation value to be an `Actor` / `WorkObject` / `Verb` / `InflectedRef` instance; ordinary strings continue to render via `NarrationValue` / `NarrationPlaceholder`. No error; just no pill.

All errors are pytest-collection errors (raised before test execution), so authors see them during `pytest --collect-only` or at startup.

## Testing

### Unit

- `tests/unit/capture/test_glossary.py` (new):
  - `actor('Customer')` returns an `Actor` whose `.entity_id == 'customer'`; idempotent re-registration; conflict on mismatched definition raises.
  - `verb('dispense')` registers with kind `'verb'`; cross-kind id collision raises.
  - Id auto-derivation: `'Order received'` → `'order-received'`; explicit `id=` wins.
  - Inflection: `customer('Customers')` returns `InflectedRef(term=customer, display='Customers')`.
- `tests/unit/capture/test_story.py` (new):
  - `path(...)` grammar: rejects leading/trailing word, rejects two adjacent entities, accepts multi-word phrases between entities.
  - `activity(...)` accepts positional single-path; multi-path via `path(...)` calls; mixing raises.
  - `story(...)` auto-numbers activities in declaration order; explicit `id=` on an activity keeps it; uniqueness checked.
- `tests/unit/capture/test_template.py`:
  - T-string interpolation of `Actor` → `NarrationTermRef(kind='actor', ...)`.
  - T-string interpolation of `InflectedRef` → `NarrationTermRef` with the inflected display.
  - Interpolation matching a parametrize column AND carrying an entity value → `NarrationTermRef(..., param_column=<col>)`.
- `tests/unit/capture/test_registry.py` (new):
  - Session-start clear isolates terms across runs.
  - Snapshotting yields a frozen `Glossary` / `Story` tuple.
- `tests/unit/model/test_schema.py` / `test_serde.py`:
  - All new dataclasses round-trip through `report_to_dict` / `report_from_dict`.
  - `ActivityPart` variants discriminate correctly on a `type` key.
  - Empty `Glossary` and empty stories tuple round-trip.
- `tests/unit/report/test_coverage.py` (new):
  - Implicit binding: step references full set → covers activity; missing verb → does not cover; verbless activity matched by entities alone.
  - Multi-step scenario: scenario coverage is the union of step coverage.
  - Explicit step `activity_ids` overrides inference for that step but not others.
  - Multi-path activity: any one path's term-set may participate; satisfying *one* path suffices (refined: the activity counts as covered iff the union of its parts' refs is a subset of the step's refs).
- `tests/unit/report/test_renderer.py`:
  - The narration filter dispatches `NarrationTermRef` to the appropriate kind class; combined case adds the `param-color-N` modifier.
  - Tab visibility flags surface to the template context based on `ReportData.glossary` / `ReportData.stories` emptiness.
  - Coverage map structure (per scenario, per activity) reaches the template.

Per [[feedback-no-frontend-markup-tests]] these stay on the data-shape contract — no asserts on raw HTML / class strings.

### Integration

- `tests/integration/test_domain_storytelling.py` (new):
  - A small "Order Coffee" suite with glossary, story, and three scenarios runs cleanly; JSON output has populated `glossary`, `stories`, `scenario.story_id`, and per-step term-refs.
  - Scenario with `activities=()` and matching steps yields inferred scenario coverage equal to the set of activities its steps reference.
  - Scenario with explicit `activities=[1, 2]` plus a step bound to `activity=5` raises at collection.

### Visual (Playwright)

Per [[feedback-no-frontend-markup-tests]], Playwright is the only verification for renderer correctness.

- Regenerate `examples/report-data.json` and `examples/report.html` via `uv run nox -s examples` after extending `examples/test_examples.py` with an Order Coffee story.
- Open in Playwright and verify:
  - Three tabs present and switchable; URL hash updates.
  - Stories view: timeline rendering, status colours, scenario badge clicks anchor down to the matching card.
  - Bidirectional sync-highlight: hovering an activity row highlights matching scenarios; hovering a scenario card highlights matching activity rows.
  - Glossary view: kind filters toggle term groups; "Used in" links navigate cross-view.
  - Cursor on all entity refs is pointer; clicking jumps to the Glossary entry.
  - Activity 3 (no coverage in the example) renders with the gap state.
- Console messages clean after init.

### Coverage gate

100% per AGENTS.md; new modules exercised by the unit tests above. Per [[feedback-assert-over-pragma]], invariant guards use `assert`, not `# pragma: no cover`.

## Open follow-ups (not in scope, tracked here)

- Example Mapping integration: rule / question authoring atop the story↔scenario substrate.
- egon.io import: parse `.dst` JSON into a `Story`; emit `.dst` from a declared `Story`.
- External glossary file ingestion (YAML / Markdown).
- Glossary synonyms and external doc-link fields.
- Pictogrammatic activity rendering (graph view) — the data model is graph-ready (`ActivityPath` enforces `Entity (Word+ Entity)+`).
- Step's `activity_ids` ergonomics: a sentinel like `activity='all'` to cover the whole story explicitly.
- Agent skill for pytest-given authoring (existing TODO; likely benefits from this design's vocabulary).
