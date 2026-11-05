# Glossary

Canonical vocabulary for pytest-given. Use these terms in code, docs, commit messages, and conversation; flag inconsistencies in review.

This glossary covers pytest-given's own bounded context. The terminology a *user's* test suite adopts (the domain the user is testing — e.g., the coffee domain in `examples/coffeeshop/test_coffeeshop.py`) is a separate concern.

**Update rule:** rename or repurpose a term → update this file in the same commit.

## Core test model

| Term | Meaning |
|---|---|
| **Scenario** | A test that narrates the rule it demonstrates, marked with `@scenario`. Tests without the mark stay out of the report. |
| **Scenario title** | The statement of the rule a *Scenario* demonstrates. Not the test function's name, which the *Node ID* carries. |
| **Step** | A unit of narration in one *Phase*. Steps nest and may carry *Attachments*, but have no status or error of their own: a failure belongs to the *Scenario*, and to its *Case* in a *Parameter table*. |
| **Narration** | The human-readable text on a step or scenario title, which may mix plain text with values, placeholders and *term refs*. |
| **Phase** | The category of a step: `given`, `when`, or `then`. A step has exactly one phase. |
| **when_then** | One block that narrates a `when` action and its `then` outcome as two sibling steps. Used mainly to narrate an expected raise, so the action and its outcome stay distinct steps. |
| **Tag** | A free-form label on a scenario. A `/` nests it: `ticket/ABC-123` sits under `ticket`. |
| **Attachment** | A labeled piece of text or JSON bound to the step being narrated. |

## Parametrization

| Term | Meaning |
|---|---|
| **Parametrized scenario** | A *Scenario* whose test is parametrized, so it runs once per *Case*. pytest-given groups the results. |
| **Case** | One row of a parametrized scenario: its node ID, its parameter values, its status and any error. |
| **Case ID** | A *Case*'s pytest ID: its *Node ID*'s parametrize tail without the brackets (`touching-edges`), as the terminal prints it. *Custom* when it is more than its values' generated parts, as from `pytest.param(..., id=...)` or `ids=`. |
| **Parameter table** | The per-scenario table of cases and columns. A column is a `param` (a parametrize input), a `derived` (a narrated value that varies across cases) or an `attachment` (an attachment whose payload varies). |
| **Group** | Collapsing the cases of a parametrized scenario into one logical scenario carrying a *Parameter table*. Cases group when they share both the same name and the same *Node ID* without its parametrize tail — one test function; two same-named scenarios on different test functions stay separate. `@scenario(group_parametrized=False)` declines the merge, so each case lives on as its own scenario. |
| **Templatize** | Derive the grouped-template step text by comparing every comparable case: what all of them share stays inline, and anything that varies points at a parameter-table column. The baseline comes from the first passed case, and every other passed case must narrate that same template — a failed case too, over the steps it shares with the baseline. |

## Fixtures and recording

| Term | Meaning |
|---|---|
| **Step fixture** | A pytest fixture that narrates its setup as a `given` *Step*. A fixture cannot narrate `when` or `then`. |
| **Plain fixture** | A pytest fixture without a pytest-given decorator. It produces no step in the report unless a *Given annotation* on the test's parameter narrates it. |
| **Given annotation** | A `given(...)` in a test parameter's `Annotated[...]` type: `def test(room: Annotated[int, given('a room')])`. On a parametrize value or a *Plain fixture* it adds a childless `given` step; on a *Step fixture* it replaces the fixture's root label and its pins. Only `given` is allowed, and a `Template` in it may only hold a bare parametrize column. |
| **Fixture recording** | The steps and attachments a step fixture narrates during setup. A generator fixture's teardown records nothing — it refuses steps and attachments. |
| **Graft** | Attaching a fixture recording into the active scenario's step tree at the moment its host test starts. |

## Collector state

| Term | Meaning |
|---|---|
| **Collector** | What gathers a session's scenarios, fixture recordings and parameter info. |
| **Active scenario** | The scenario currently being recorded into. |
| **Node ID** | A pytest test identifier (e.g., `tests/test_x.py::test_y[a-b]`). |
| **Step stack** | The chain of currently-open steps. Opening a step adds it, and leaving its block removes it. |

## Report

| Term | Meaning |
|---|---|
| **Report** | The output artifact: a JSON data file and optional self-contained HTML and Markdown renderings derived from it. The JSON is the source of truth. |
| **Renderer** | Converts a JSON report into a rendering — a self-contained HTML page or a Markdown document. |
| **Parameter coloring** | Each parametrize column gets a stable highlight color; placeholders and matching values share that color wherever they appear in step text and the parameter table. |
| **Value highlight** | A neutral highlight applied to t-string interpolation values that don't correspond to a parametrize column and are constant across every case (e.g., a computed expression like `price * 1.2`). One that varies becomes a `derived` column instead. |
| **Source link** | A link to a file and line: a scenario's test function, or the declaration of a *Story* or *Term*. |
| **Report link** | A Markdown link to a scenario, tag or story in the HTML *Report*. Without a glyph it is a plain one, which claims only that its target exists. |
| **Citation** | A *Report link* led by its target's status glyph, citing a scenario, tag or story from a Markdown document: `✅ [title](<report URL>#scenario=…)`. A tag or story citation adds a summary after it, `(5 ✅ · 2 🔵)`. A target the *Report* lacks reads `❓`. |
| **Narrated citation** | A *Citation* of a scenario written as a collapsible block, the citation as its summary and the scenario's Markdown narration as its body. |
| **Citation finding** | One problem `pytest-given citations check` reports on one *Report link*: its kind (`stale`, `missing`, `failed`, `mistyped`, …), the document location and a message. |
| **Theme** | The HTML report's colour scheme — `light`, `dark`, or `auto` (follow the viewer's system). |

## Narration lint

| Term | Meaning |
|---|---|
| **Narration lint** | The `--given-lint` pass that checks recorded scenarios against the *Lint rule* catalog. It enforces the structural subset of the narration conventions — it cannot check whether a *Step*'s text is semantically true. |
| **Lint rule** | One named check, carrying a surface and a default *Severity*. A `runtime` rule reads the recorded scenarios; an `ast` rule parses the step bodies' source. |
| **Lint finding** | One *Lint rule* firing on one subject: the rule id, the *Severity* it fired at, the subject, a *Source link* location and a message naming the offender. |
| **Severity** | A *Lint rule*'s level — `off`, `warn` or `error`. Only `error` fails the run, `warn` reports in the terminal summary, and an `off` rule is not evaluated at all. |

## Domain Storytelling

The Domain-Driven Design layer atop the core surface. All terms here are optional features: a test suite can use none, some, or all.

Terms follow [Domain Storytelling](https://domainstorytelling.org/quick-start-guide)'s own, where actors and work objects connected by activities form sentences.

| Term | Meaning |
|---|---|
| **Glossary** | The shared vocabulary a domain speaks in: its Ubiquitous Language. |
| **File glossary** | A glossary loaded from the GFM pipe tables of a Markdown file. |
| **Deferred term** | A term handed over before its kind is settled: what `g('foo')` and `g['foo']` on a code glossary return, and a *file glossary* lookup of a row with no declared kind. *Kind inference* settles it later. |
| **Term** | A glossary entry: an Actor, Work Object, Activity, or kindless term. Each carries an id (slug), a canonical name, a kind unless kindless, and an optional definition. |
| **Handle** | What a glossary hands back for a *term*, the same from every accessor (`g.actor(...)`, `g('foo')`, `g['Guest']`, a captured `guest = ...`). It is what steps, scenario titles and sentences interpolate, in one of four surface forms: **bare** (`room` — the canonical display), **`.l`** (`room.l` — capitalized words lowercased, acronyms kept), **`.s`** (`room.s` — the *S-form*), or **called** (`room('Deluxe Suite')` — an *instance* on an Actor or Work Object, an inflection on an *Activity*). `.l` and `.s` also apply to a called form and chain (`room.l.s` reads *rooms*). Each form renders as a *term ref*. A story hands out a **sentence handle** the same way: `book_a_room['cancel']` by name or `book_a_room[3]` by number, which `pins=` takes. |
| **S-form** | A term's name with the regular English -s ending, from the `.s` handle form: the plural of an Actor or Work Object (*rooms*), the third person singular of an Activity (*books*). It adds -s to the last word, -es after s, x, z, ch or sh, and turns a consonant + y into -ies, but an acronym takes a plain -s (*APIs*); anything else, such as *people* or *checks in*, needs the called form. An S-form reference, in any case, is a reference to the term itself — not an *instance* or an *inflection*. |
| **Actor** | A glossary term for a participant in the domain (e.g., *Guest*). |
| **Work Object** | A glossary term for a thing acted on (e.g., *Room*, *Booking*). |
| **Activity** | A glossary term for what an actor does (e.g., *book*, *confirm*), which Domain Storytelling draws as an arrow labelled with a verb. Activities accept inflections: calling `search('searches for')` records *searches for* as a surface form of the canonical *search*. |
| **Term ref** | An occurrence of a term inside narration or a clause. |
| **Instance** | A named refinement of an Actor or Work Object (e.g., `guest('Alice')` is an instance of the *Guest* actor). |
| **Inflection** | A surface form of an Activity term other than its canonical name or *S-form* (e.g., *searches for* as an inflection of *search*). |
| **Story** | A named flow modeled as a sequence of sentences. Stories are the unit of coverage. |
| **Sentence** | What Domain Storytelling calls a sentence: an actor, an activity and its work objects, plus connective words. One row in a story, numbered by its position and optionally named, a name that stays put when rows are inserted. Usually one clause; several when the sentence has several arrows under one number. |
| **Clause part** | A piece of a clause's prose: a *term ref*, or a bare clause word. A bare clause word — a node label or edge connective — carries no kind or id, is never classified by inference, and never reaches the glossary. That last is what separates it from a kindless term, which has an id and is tracked. |
| **Clause** | One linear walk through a sentence's arrows, a node/edge alternation starting actor → verb → noun. A sentence with several arrow chains under one number, such as an actor handing a work object to two recipients, takes one clause per chain. Domain Storytelling names no such unit. |
| **Slot** | A position role in a clause, from its node/edge alternation: position 0 is the actor slot, odd positions are verb slots, and even positions ≥ 2 are noun slots. |
| **Scenario↔sentence binding** | The link between a scenario (or step) and story sentences. `@scenario(stories=...)` names the stories a scenario is narration-matched against; a *pin* (`pins=` on `@scenario` or on `given`/`when`/`then`) binds sentences explicitly, in any story, whether `stories=` names it or not. |
| **Pin** | What a *sentence handle* passed to `pins=` is recorded as, the way a term handle in narration is recorded as a *term ref*: a reference to a story and a sentence number. A pin binds explicitly and replaces narration matching — a step pin for that step, a scenario pin (`@scenario(pins=...)`) for every step of the scenario, which then covers its own pins plus its steps'. `pins=[]` pins nothing but still opts out of narration matching. A pin reaches under-anchored sentences too. |
| **Coverage** | The "did this scenario touch that sentence" relation. A sentence is covered when the set of terms it references is a subset of the terms a single step references — matching is per step, not against the union across steps, and on terms, not surface forms: an *instance* or *inflection* counts as its term. A *pin* covers its sentences directly instead, regardless of narration or term count. |
| **Kind inference** | The pass that assigns each undeclared term a kind from the *slot* positions it occupies across all story sentences; declared kinds are verified against observed positions instead. A term used in incompatible slots (or conflicting with its declared kind) raises. A term never referenced by any sentence stays *kindless*. |
| **Kindless** | A term with no kind, because *kind inference* finds no story *slot* to infer from (a term used only in t-string steps, never in a sentence). |
| **Undefined** | A term with no definition. Orthogonal to *kindless*. |

## Collaboration

The people and machines collaborating on a pytest-given test suite — the cast of the project's own domain story (defined in `tests/ubiquitous_language.py`).

| Term | Meaning |
|---|---|
| **Developer** | Person who writes the application code and — together with the *Agent* — the scenarios; curates the glossary with the *Domain Expert*. |
| **Domain Expert** | Person who owns the domain knowledge and the ubiquitous language; source of domain stories and reviewer of scenarios and reports. A stakeholder in the broad sense. |
| **Agent** | AI coding agent that authors and maintains scenarios alongside the *Developer*, guided by the pytest-given skills. |
