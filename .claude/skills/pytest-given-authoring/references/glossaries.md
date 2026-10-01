# Authoring glossaries

A glossary declares the ubiquitous language your tests speak: actors, work objects, and activities, each with a definition. Steps, stories, and scenario titles reference terms through handles; every reference renders as a kind-colored word with the definition as tooltip and feeds the report's Glossary tab (with per-term scenario filtering).

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

The kind column takes `actor`, `work object` (or `object`), or `activity`.

**Code-defined `Glossary`** — declare terms where the tests live:

```python
from pytest_given import Glossary

g = Glossary()
guest = g.actor('Guest', definition='Person booking accommodation.')
room = g.work_object('Room', definition='A bookable hotel room.')
book = g.activity('book', definition='Reserve a room for a stay.')
```

Either way, **give the language a public home**: define the glossary — and the stories, once there are some — in one dedicated, publicly named module, e.g. `tests/ubiquitous_language.py`. The module *is* the suite's ubiquitous language, not a private helper — don't underscore-prefix it; test modules import their handles from it. Glossary-only mode is fine — you get the Glossary tab without writing any stories.

**Discovery** works one of two ways. The plugin first reads the glossary off any `story(...)` that references it — a story records its glossary at construction, so a suite with bound stories needs no further wiring. Failing that, it scans `conftest.py` module attributes for a `Glossary`/`FileGlossary` instance. A suite with no stories therefore has to bind the instance *by name*:

```python
# conftest.py
from tests.ubiquitous_language import g  # noqa: F401 — plugin discovery
```

`import tests.ubiquitous_language` binds a module, not a glossary: the scan finds nothing and the Glossary tab renders empty. Binding it anyway is the safe habit — it costs one line and survives a later refactor that drops the last story.

**One glossary per suite.** Stories reaching two distinct `Glossary` instances raise `PytestGivenError`, and so do two in conftests; but once the stories reach one, a different conftest glossary is silently ignored — keep one instance and import it everywhere.

## Using terms in narration

Look up handles by name — `g['Room']` (case-insensitive) — or use the captured variables from a code-defined glossary. Both work in t-string steps, `@scenario(...)` titles, and story sentences:

```python
with when(t'a {g["Guest"].low} {g["book"]("books")} a {g["Room"].low}'):
    ...
```

Pick the lightest surface form for the word you need — the same three forms on every handle, captured (`guest = g.actor(...)`) or looked up (`g['Guest']`):

- **Bare handle** — `g['Room']` renders the term's canonical text. Use it whenever the word appears as-is — restating it as `g['Room']('Room')` is redundant noise.
- **`.low`** — `g['Attachment'].low` (or `guest.low`) renders the canonical lowercased, the usual mid-sentence form. Prefer it over the equivalent `g['Attachment']('attachment')`.
- **Called** — `g['book']('books')` supplies any *other* surface: an activity inflection, a plural (`g['Term']('terms')`), or a concrete instance (`organizer('Carol')`).

## Naming terms

- **Term names are natural language, not class names.** Name the concept a human would say (`File glossary`, `Clause part`) and spell the implementing class (`FileGlossary`, `ClausePart`) inside the definition. A one-word term may coincide with its class only when the class is already the natural word — multi-word CamelCase never is.
- **Renaming or removing a term is a code change, not just a doc edit.** A term's slug (lowercased, non-alphanumeric → `-`) is the lookup key, so `File glossary` and `FileGlossary` are *different* keys and a rename breaks every `g['Old name']` reference. Grep for the old name, update the references, re-render the reports — and carry the rename into the implementation naming: leaving the old name in the code creates exactly the language drift the vocabulary rule forbids (see [scenarios.md](scenarios.md)). Adding a term is always safe.

## Kinds

Terms are actors, activities, or work objects. Three ways a term gets its kind:

1. **Explicit** — `g.actor(...)` / `g.activity(...)` / `g.work_object(...)`, or a `kind_column` in the glossary file.
2. **Inferred from stories** — a term with no declared kind takes one from its clause slot positions: position 0 → actor, odd positions (the verb slots) → activity, even positions ≥ 2 → work object. A term seen in both actor and noun slots resolves to actor (an actor can be the target of a hand-off); a term seen in a verb slot *and* any other slot raises — add a kind column to disambiguate. A term used only in steps stays kindless (neutral wash).
   **A declared kind is never overridden:** putting the term in a slot its kind forbids raises at `sentence(...)`. `kind_column` is opt-in: a column headed "Kind" is ignored unless you pass `kind_column=`.
3. **Deliberately deferred** — `g('foo')` declares a term the team hasn't classified yet: it lands in the *Uncategorized* bucket and shows an *Undefined* badge until a definition arrives. Use it as a triage bucket, not a resting place. Code-defined glossaries only: a `FileGlossary` is a **closed vocabulary** — `g('foo')` and `g['foo']` both merely look up and raise on unknown names; new vocabulary is added as a row in the file.

## Keeping the glossary honest

- **Don't dilute the glossary.** A term earns its row by being vocabulary the team speaks: something someone would look up, with a meaning specific to the domain. Never add terms to render more term refs or to satisfy the lint; a generic word stays a bare string. When a row doesn't earn its place, delete it rather than manufacture a reference to it.
- **Watch the size — a glossary is read whole, never sampled.** Reading every term in one pass is how a near-duplicate gets caught before it is coined. A glossary that outgrows one comfortable reading speaks for more than one bounded context: raise it with the user as a design question, since one glossary per context means splitting the suite too.
- **A definition that asserts behavior is a spec sentence.** A row saying "must be unique" or "produces no step" makes a claim: back it with a scenario, and update the row when the behavior changes.
- **A term nothing references is normal.** A glossary documents the domain, not the suite's coverage, which is why `dead-term` is off by default. Where you opt in, read a finding as a prompt to look at the term: if an undecorated test already demonstrates its behavior, decorate that test; if a step says the term as plain text, add the term ref.
