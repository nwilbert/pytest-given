# Domain Storytelling

Three optional pillars layer **Domain-Driven Design** on top of the core surface. Adopt any one independently — or all three for a full vocabulary-and-story workflow. The HTML report adds a tabbed view: **Scenarios** (always present), **Stories**, and **Glossary** (each only shown when populated).

**1. Ubiquitous-language `Glossary`** — declare the actors, work objects, and verbs your tests speak about:

```python
from pytest_given import Glossary

g = Glossary()
guest = g.actor('Guest', definition='Person booking accommodation.')
room = g.work_object('Room', definition='A bookable hotel room.')
book = g.verb('book', definition='Reserve a room for a stay.')
```

Use the captured handles directly in t-strings — `t'a {guest} {book("books")} a {room}'`. Each interpolation becomes a washed, kind-colored word in the rendered step, with the term's definition as a tooltip. Glossary terms feed the Glossary tab.

Reference a term with the lightest surface form that fits the sentence — the same three forms on every handle (captured or looked up):

- **Bare** — `{guest}` renders the term's canonical text. Use it whenever the word appears as-is; restating it as `guest('Guest')` is redundant.
- **`.low`** — `{guest.low}` renders the canonical lowercased, the common mid-sentence form, instead of the equivalent `guest('guest')`.
- **Callable override** — `guest('Alice')` supplies any other surface: a verb inflection (`book('books')`), a plural (`room('rooms')`), or a concrete instance.

**Loading a Markdown glossary file instead** — if your project already keeps a `GLOSSARY.md`, point `FileGlossary` at it rather than declaring terms in code:

```python
from pathlib import Path
from pytest_given import FileGlossary

g = FileGlossary(Path(__file__).parent / 'GLOSSARY.md')
```

The file must contain at least one GFM pipe table. By default the first column is the term and the second is the description; override with `term_column`, `description_column`, and `kind_column` (each accepts a 0-based index or a header name, case-insensitive):

```python
g = FileGlossary('GLOSSARY.md', term_column='Term', description_column='Meaning', kind_column='Kind')
```

Access terms by name — `g['Guest']` (case-insensitive). A `FileGlossary` is a **closed vocabulary**: unlike a code-defined `Glossary`, both `g['foo']` and `g('foo')` only look up, and both raise on an unknown name — new vocabulary is added as a row in the file. The returned handle is usable inline everywhere a code-defined handle is:

```python
# In a story activity:
activity(g['Guest'], g['book']('books'), g['Room'])

# In a t-string step:
with when(t'{g["Guest"]} {g["book"]("books")} a {g["Room"]}'):
    ...
```

**Kinds** — a term's kind is either declared (`g.actor(...)` / `g.work_object(...)` / `g.verb(...)`, or a `kind_column`) or **inferred from story activity-slot positions** at session finish: position 0 → actor, odd positions → verb, even positions ≥ 2 → work object. A declared kind is never silently overridden — it is checked against its slot when `activity(...)` is constructed, so misplacing it raises `PytestGivenError` naming the term and its kind. Inference then handles only the undeclared terms, and raises at session finish if one turns up in a verb slot and an actor or noun slot; add a `kind_column` to disambiguate.

**Kindless and undefined terms** — a term no story activity references stays kindless; on a code-defined glossary `g('foo')` declares one the team hasn't classified yet (`g['foo']` only looks up, and raises if unknown), showing an *Undefined* badge until `definition=` is supplied. Every declared term reaches the report, referenced or not; kindless ones render under a neutral wash and collect under **Uncategorized** in the Glossary tab.

**Discovery** — the plugin finds the glossary in one of two ways: off any `story(...)` that references it (a story records its glossary at construction), or, failing that, by scanning `conftest.py` module attributes for a `Glossary` / `FileGlossary` instance. A suite with no stories — glossary-only mode — therefore has to bind the instance **by name** in a `conftest.py`:

```python
# conftest.py
from tests.ubiquitous_language import g  # noqa: F401 — plugin discovery
```

`import tests.ubiquitous_language` binds a module, not a glossary, so the scan finds nothing and the Glossary tab renders empty. Note that a suite supports **one glossary**: two distinct instances reaching the report raise `PytestGivenError`.

**2. Domain Stories** — model a flow as a sequence of `activity(...)` rows tied together by `story(...)`:

```python
from pytest_given import activity, story

book_a_group_trip = story('Book a Group Trip', [
    activity(organizer('Carol'), 'searches for', room),
    activity(organizer('Carol'), 'selects', room('Deluxe Suite')),
])
```

An activity reads left-to-right: actor → verb → work object (with optional connective words). Any part may be a bare string instead of a glossary handle — generic verbs like *searches for* belong there; only vocabulary with a domain-specific meaning earns a glossary row — but an activity needs at least two distinct glossary terms to be matched by narration; under-anchored activities render as "not coverage-tracked" unless a step pins them explicitly.

`path(...)` gives one activity **parallel branches** — alternate sentences that happen together, one per branch:

```python
activity(
    path(organizer('Carol'), 'adds', guest('Alice'), 'to', trip),
    path(organizer('Carol'), 'adds', guest('Bob'), 'to', trip),
)
```

A path alternates node / edge / node …, so it has an odd length ≥ 3 and ends on an entity. Covering a multi-path activity takes a step referencing every term across all of its paths.

**3. Scenario ↔ activity binding** — link a scenario (and individual steps) to the story it implements:

```python
@scenario('Carol selects a suite', story=book_a_group_trip)
def test_select_suite(carol):
    with when(t'{organizer("Carol")} selects the {room("Deluxe Suite")}'):
        ...
```

Each step's term references are matched against the story's activities to compute coverage. The Stories tab shows the timeline with a coverage chip per activity and the scenarios that touch it; selecting an activity offers *Open in Scenarios*, which filters the Scenarios view down to those scenarios. A step can also bind explicitly with `given(text, activity=...)`, naming an activity by its 1-based position in the story; pass `activity(..., activity_id=N)` to fix a row's number so inserting a row later doesn't renumber the pins after it. `@scenario(..., activities=[2, 3])` requires `story=` and narrows the scenario to those activity ids, so it can cover no others. The JSON report carries the same per-activity result under a top-level `coverage` key, so a terminal or an agent can read it without re-deriving the rule.

The [domain-storytelling](https://github.com/nwilbert/pytest-given/blob/main/docs/specs/2026-06-07-domain-storytelling-design.md) and [file-backed glossary](https://github.com/nwilbert/pytest-given/blob/main/docs/specs/2026-06-18-file-backed-glossary-design.md) design specs carry the full surface; the [examples](../examples.md) show it end to end.

