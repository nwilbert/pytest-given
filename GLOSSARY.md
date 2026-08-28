# Glossary

Canonical vocabulary for pytest-given. Use these terms in code, docs, commit messages, and conversation; flag inconsistencies in review.

This glossary covers pytest-given's own bounded context. The terminology a *user's* test suite adopts (the domain the user is testing — e.g., the coffee domain in `examples/coffeeshop/test_coffeeshop.py`) is a separate concern.

**Update rule:** rename or repurpose a term → update this file in the same commit.

## Core test model

| Term | Meaning |
|---|---|
| **Scenario** | A test function decorated with `@scenario(...)`. Not every pytest test is a scenario — undecorated tests are tolerated but not collected. |
| **Step** | A unit of narration: a `with given(...)` / `when(...)` / `then(...)` block, or the root recording from a step fixture. Steps nest. Each carries a phase, narration, attachments, and children — but no status and no error of its own: a failure is recorded on the *Scenario*, and per *Case* on the *Parameter table*, which is where both renderers read it. |
| **Narration** | The human-readable text on a step or scenario name. Modeled as a `Narration` dataclass bundling a flat rendered `text: str` with a `parts: list[NarrationPart]` (empty for plain-string authoring; populated when the source was a t-string or `pytest_given.Template`, with `NarrationLiteral` / `NarrationValue` / `NarrationPlaceholder` / `NarrationTermRef` pieces). The structured form lets the templatizer and renderer treat parametrize-bound values specially without regex tricks. |
| **Phase** | The category of a step: `given`, `when`, or `then`. A step has exactly one phase. |
| **when_then** | A step-authoring helper that emits a `when` action and its `then` outcome as two sibling steps from a single `with` block. Used mainly to narrate an expected raise (`with when_then('the action', 'the error is raised'), pytest.raises(...)`), so the action and its outcome stay distinct steps. |
| **Tag** | Free-form string label attached via `@scenario(name, tags=[...])`. Used by the report's filter UI. |
| **Attachment** | A labeled blob (text or JSON) bound to the currently-active step via `attach(label, content)`. |

## Parametrization

| Term | Meaning |
|---|---|
| **Parametrized scenario** | A `@scenario`-decorated test that also carries `@pytest.mark.parametrize(...)`. Produces multiple scenario records during a run; pytest-given groups them. |
| **Case** | One row of a parametrized scenario — a single tuple of parameter values, its status, and any error. |
| **Parameter table** | The per-scenario grouping of typed columns + cases. A column is a `param` (a `@pytest.mark.parametrize` input), a `derived` (a narrated value that varies across cases) or an `attachment` (an attachment whose payload varies). Appears in the report below the grouped-template steps. |
| **Group** | Collapsing the N scenario records of a parametrized scenario into one logical scenario carrying a *Parameter table*. Cases group when they share the same *Node ID* without its parametrize tail — one test function — and the same name; two same-named scenarios on different test functions stay separate. `@scenario(group_parametrized=False)` declines the merge, so each case lives on as its own scenario. |
| **Templatize** | Derive the grouped-template step text by comparing every comparable case: what all of them share stays inline, and anything that varies becomes a `{name}` placeholder or attachment badge pointing at a parameter-table column. The baseline tree comes from the first passed case, and every other passed case must narrate that same template. |

## Fixtures and recording

| Term | Meaning |
|---|---|
| **Step fixture** | A pytest fixture whose function is wrapped with `@given(text)`. Only `@given` is allowed on fixtures; `@when` / `@then` are rejected. |
| **Plain fixture** | A pytest fixture without a pytest-given decorator. Used by tests but produces no step in the report. |
| **Fixture recording** | A captured subtree of steps + attachments produced while a step fixture is being set up (and, for generator fixtures, torn down). Stored keyed by fixture-instance identity. |
| **Graft** | Attaching a fixture recording into the active scenario's step tree at the moment its host test starts. |

## Collector state

| Term | Meaning |
|---|---|
| **Collector** | The module-level singleton that accumulates scenarios, fixture recordings, and parameter info during a pytest session. Reset at the start of each session. |
| **Active scenario** | The scenario currently being recorded into; tracked by node ID. |
| **Node ID** | A pytest test identifier (e.g., `tests/test_x.py::test_y[a-b]`). Used as a key throughout the collector. |
| **Step stack** | The chain of currently-open steps; entered by `with given(...)`, popped on exit. Mirrored inside a fixture recording while a fixture body is running. |

## Report

| Term | Meaning |
|---|---|
| **Report** | The output artifact: a JSON data file and optional self-contained HTML and Markdown renderings derived from it. The JSON is the source of truth. |
| **Renderer** | Converts a JSON report into a rendering — a self-contained HTML page or a Markdown document. |
| **Parameter coloring** | Each parametrize column gets a stable highlight color; placeholders and matching values share that color wherever they appear in step text and the parameter table. |
| **Value highlight** | A neutral highlight applied to t-string interpolation values that don't correspond to a parametrize column and are constant across every case (e.g., a computed expression like `price * 1.2`). One that varies becomes a `derived` column instead. |
| **Source link** | A clickable file:line anchor on a scenario card, a story panel, or an expanded glossary term card. Resolved from the `given_source_link` config (preset name like `vscode` / `github`, or a raw URL template). Captured as a `SourceLocation` (POSIX relpath + 1-indexed line) — from `pytest.Item.location` for a scenario, from the declaration site for a *Story* or *Term*. Disabled by default. |

## Domain Storytelling

The Domain-Driven Design layer atop the core surface. All terms here are optional features: a test suite can use none, some, or all.

| Term | Meaning |
|---|---|
| **Glossary** | The Ubiquitous-Language concept — the shared vocabulary a domain speaks in — and the class that realizes it: `Glossary()`, with `.actor(...)`, `.work_object(...)`, `.verb(...)` registration methods and `g('foo')` (declare-or-get a kindless term, optional `definition=`) / `g['foo']` (get-only, raises on unknown) accessor forms. |
| **File glossary** | A glossary loaded from a Markdown file, via the `FileGlossary(path)` class. It parses all GFM pipe tables in the file into the same inner `Glossary` model; terms are accessed by name (`g['Guest']`, case-insensitive). *Kind inference* fills in term kinds post-collection from activity *slot* positions when no explicit `kind_column` is configured. |
| **Deferred term** | A term handed over before its kind is settled — the `DeferredTermHandle` returned by the code glossary (`g('foo')` declare-or-get, `g['foo']` get-only) and by every *file glossary* lookup (`g['Guest']`). It subclasses the plain `TermHandle` that the typed registrations (`g.actor(...)` and friends) return, and adds no behavior — it marks only that the kind was left open. The deferral is in the handing over, not the term: a row with an explicit `kind_column` arrives through the same handle already kinded, while the rest stay `None` until *kind inference* runs. |
| **Term** | A registered glossary entry: an Actor, Work Object, Verb, or kindless term. Each carries an id (slug), a canonical name, a kind (`None` when kindless), and an optional definition (`str | None`, `None` when undefined). |
| **Actor** | A glossary term for a participant in the domain (e.g., *Guest*). Carries the actor kind color: a wash in narration, a pill in the Glossary view. |
| **Work Object** | A glossary term for a thing acted on (e.g., *Room*, *Booking*). Carries the work-object kind color: a wash in narration, a pill in the Glossary view. |
| **Verb** | A glossary term for an action (e.g., *book*, *confirm*). Verbs accept inflections — calling `book('books')` records *books* as a surface form of the canonical *book*. |
| **Term ref** | An occurrence of a term inside narration. Modeled as `NarrationTermRef` in step text and as `ActivityTermRef` inside activity prose. |
| **Instance** | A named refinement of an Actor or Work Object (e.g., `guest('Alice')` is an instance of the *Guest* actor). Instances aggregate in the Glossary tab's refs block. |
| **Inflection** | A surface form of a Verb other than its canonical name (e.g., *searches for* as an inflection of *search*). Reported under "Also used as:" in the Glossary. |
| **Story** | A named flow modeled as a sequence of activities. Constructed by `story('Title', [activity(...), ...])`. Stories are first-class report tabs and the unit of coverage. |
| **Activity** | One row in a story — typically `actor + verb + work_object` plus optional connective words. Constructed by `activity(...)`. |
| **Activity Part** | The two-variant union making up an activity's prose (`ActivityPart` = `ActivityTermRef | ActivityWord`): `ActivityTermRef` (a reference to a glossary term — actor, work object, or verb; kind resolved via the glossary) and `ActivityWord` (a bare path word — a node label or an edge connective; carries no kind or id, is never classified by inference, and never appears in the glossary — distinct from a kindless/undefined term, which has an id and is tracked). |
| **Path** | A branching segment inside a story — `path(...)` lets alternate activity sequences share a prefix. |
| **Slot** | A position role in an activity path, from its node/edge alternation: position 0 is the actor slot, odd positions are verb slots, and even positions ≥ 2 are noun slots. Slots drive both path validation and *kind inference*. |
| **Scenario↔activity binding** | The link between a scenario (or step) and one or more story activities. Carried by `@scenario(story=, activities=)` and the `activity=` kwarg on `given`/`when`/`then`. |
| **Coverage** | The "did this scenario touch that activity" relation. Computed by the *A_refs ⊆ S* rule: an activity is covered when its set of term references (as identities, with a canonical fallback) is a subset of a single step's term-reference identities — matching is per step, not against the union across steps. A step can also cover an activity explicitly via the `activity=` pin, regardless of its narration or its term count. |
| **Kind inference** | The post-collection pass (`infer_glossary_kinds`) that assigns each undeclared term a kind from the *slot* positions it occupies across all story activities; declared kinds are verified against observed positions instead. A term used in incompatible slots (or conflicting with its declared kind) raises. A term never referenced by any activity stays *kindless*. |
| **Kindless** | A term with `kind=None` — left unset when *kind inference* finds no story *slot* to infer from (a term used only in t-string steps, never in an activity). Shown in the report's *Uncategorized* bucket. |
| **Undefined** | A term with `definition is None`; surfaced by a badge and filter in the Glossary view. Orthogonal to *kindless*. |

## Collaboration

The people and machines collaborating on a pytest-given test suite — the cast of the project's own domain story (defined in `tests/ubiquitous_language.py`).

| Term | Meaning |
|---|---|
| **Developer** | Person who writes the application code and — together with the *Agent* — the scenarios; curates the glossary with the *Domain Expert*. |
| **Domain Expert** | Person who owns the domain knowledge and the ubiquitous language; source of domain stories and reviewer of scenarios and reports. A stakeholder in the broad sense. |
| **Agent** | AI coding agent that authors and maintains scenarios alongside the *Developer*, guided by the pytest-given skills. |
