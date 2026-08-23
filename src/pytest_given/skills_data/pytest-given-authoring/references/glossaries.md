# Authoring glossaries

A glossary declares the ubiquitous language your tests speak: actors, work objects, and verbs, each with a definition. Steps, stories, and scenario titles reference terms through handles; every reference renders as a kind-colored word with the definition as tooltip and feeds the report's Glossary tab (with per-term scenario filtering).

## Two ways to declare a glossary

**`FileGlossary` over a Markdown file — the recommended default.** One `GLOSSARY.md` both humans and agents read, loaded live by the tests:

```python
from pathlib import Path
from pytest_given import FileGlossary

g = FileGlossary(Path(__file__).parent / 'GLOSSARY.md')
```

The file needs at least one GFM pipe table. By default the first column is the term and the second its description; each override takes a 0-based index or case-insensitive header name:

```python
g = FileGlossary('GLOSSARY.md', term_column='Term', description_column='Meaning', kind_column='Kind')
```

**Code-defined `Glossary`** — declare terms where the tests live:

```python
from pytest_given import Glossary

g = Glossary()
guest = g.actor('Guest', definition='Person booking accommodation.')
room = g.work_object('Room', definition='A bookable hotel room.')
search = g.verb('search', definition='Look up available options.')
```

Either way, **give the language a public home**: define the glossary — and the stories, once there are some — in one dedicated, publicly named module, e.g. `tests/ubiquitous_language.py`. The module *is* the suite's ubiquitous language, not a private helper — don't underscore-prefix it; test modules import their handles from it. Glossary-only mode is fine — you get the Glossary tab without writing any stories.

**Discovery** works one of two ways. The plugin first reads the glossary off any `story(...)` that references it — a story records its glossary at construction, so a suite with bound stories needs no further wiring. Failing that, it scans `conftest.py` module attributes for a `Glossary`/`FileGlossary` instance. A suite with no stories therefore has to bind the instance *by name*:

```python
# conftest.py
from tests.ubiquitous_language import g  # noqa: F401 — plugin discovery
```

`import tests.ubiquitous_language` binds a module, not a glossary: the scan finds nothing and the Glossary tab renders empty. Binding it anyway is the safe habit — it costs one line and survives a later refactor that drops the last story.

**One glossary per suite.** Two distinct `Glossary` instances reaching the report — via stories or via conftests — raise `PytestGivenError`. Splitting vocabulary across bounded contexts means splitting the test suite too.

## Using terms in narration

Look up handles by name — `g['Room']` (case-insensitive) — or use the captured variables from a code-defined glossary. Both work in t-string steps, `@scenario(...)` titles, and story activities:

```python
with when(t'a {g["Guest"]} {g["book"]("books")} a {g["Room"]}'):
    ...
```

Pick the lightest surface form for the word you need — the same three forms on every handle, captured (`guest = g.actor(...)`) or looked up (`g['Guest']`):

- **Bare handle** — `g['Room']` renders the term's canonical text. Use it whenever the word appears as-is — restating it as `g['Room']('Room')` is redundant noise.
- **`.low`** — `g['Attachment'].low` (or `guest.low`) renders the canonical lowercased, the usual mid-sentence form. Prefer it over the equivalent `g['Attachment']('attachment')`.
- **Callable override** — `g['book']('books')` supplies any *other* surface: a verb inflection, a plural (`g['Term']('terms')`), or a concrete instance (`organizer('Carol')`).

## Naming terms

- **Term names are natural language, not class names.** Name the concept a human would say (`File glossary`, `Activity Part`) and spell the implementing class (`FileGlossary`, `ActivityPart`) inside the definition. A one-word term may coincide with its class only when the class is already the natural word — multi-word CamelCase never is.
- **Renaming or removing a term is a code change, not just a doc edit.** A term's slug (lowercased, non-alphanumeric → `-`) is the lookup key, so `File glossary` and `FileGlossary` are *different* keys and a rename breaks every `g['Old name']` reference. Grep for the old name, update the references, re-render the reports — and carry the rename into the implementation naming: leaving the old name in the code creates exactly the language drift the vocabulary rule forbids (see [scenarios.md](scenarios.md)). Adding a term is always safe.

## Kinds

Terms are actors, verbs, or work objects. Three ways a term gets its kind:

1. **Explicit** — `g.actor(...)` / `g.verb(...)` / `g.work_object(...)`, or a `kind_column` in the glossary file.
2. **Inferred from stories** — a term with no declared kind takes one from its story activity-slot positions: position 0 → actor, odd positions → verb, even positions ≥ 2 → work object. A term seen in both actor and noun slots resolves to actor (an actor can be the target of a hand-off); a term seen in a verb slot *and* any other slot raises — add a kind column to disambiguate. A term used only in steps stays kindless (neutral wash).
   **A declared kind is checked against those same positions, never overridden** — whether it came from a typed handle (`g.work_object(...)`) or a `kind_column` row, putting the term in a slot its kind forbids raises `PytestGivenError` at `activity(...)` construction, naming the term and its declared kind. Inference then handles only the undeclared terms. So an explicit kind settles ambiguity but does not license a mismatch. Note `kind_column` is opt-in: a column headed "Kind" is ignored unless you pass `kind_column=`, and those terms fall back to slot inference.
3. **Deliberately deferred** — `g('foo')` declares a term the team hasn't classified yet: it lands in the *Uncategorized* bucket and shows an *Undefined* badge until a definition arrives. Use it as a triage bucket, not a resting place. Code-defined glossaries only: a `FileGlossary` is a **closed vocabulary** — `g('foo')` and `g['foo']` both merely look up and raise on unknown names; new vocabulary is added as a row in the file.

## Keeping the glossary honest

- **Don't dilute the glossary — keep it sharp.** A term earns its row by being vocabulary the team actually speaks: something someone would look up, with a meaning specific to the domain. Never add terms to make activities render more term refs or to improve lint metrics; a generic word in an activity is better left a bare string, and the honest fix for a dead term is as often deleting it as manufacturing a reference.
- **Watch the size — a glossary is read whole, never sampled.** Authors and reviewers absorb every term in one pass; that is how a near-duplicate term gets caught before it is coined. A glossary that outgrows one comfortable reading is speaking for more than one bounded context: alert the user rather than start reading it piecemeal. The structural fix is one glossary per context — but a suite supports only one glossary, so that means splitting the suite as well; raise it as a design question, not a mechanical edit.
- **Tags never duplicate terms** — filter a feature area via its term, and keep tags for what the glossary can't carry (behavior, mechanism). The `tag-shadows-term` lint rule enforces this.
- **Every file term appears in the report**, even one no step or story references. On suites whose glossary should be fully exercised, opt into the `dead-term` lint rule to flag unreferenced terms.
