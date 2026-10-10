# Authoring glossaries

A glossary declares the ubiquitous language your tests speak: actors, work objects and activities, each with a definition. Steps, stories and scenario titles reference terms through handles. Each reference renders as a kind-colored word with the definition as a tooltip, and it feeds the report's Glossary tab, which can filter scenarios by term.

## Two ways to declare a glossary

**`FileGlossary` over a Markdown file is the recommended default.** Humans and agents read the same `GLOSSARY.md`, and the tests load it directly:

```python
from pathlib import Path
from pytest_given import FileGlossary

g = FileGlossary(Path(__file__).parent / 'GLOSSARY.md')
```

The file needs at least one GFM pipe table. By default, the first column holds the term and the second its description. Each override takes a 0-based index or a header name (case-insensitive):

```python
g = FileGlossary('GLOSSARY.md', term_column='Term', description_column='Meaning', kind_column='Kind')
```

The kind column takes `actor`, `work object` (or `object`), or `activity`.

**A code-defined `Glossary`** declares terms where the tests live:

```python
from pytest_given import Glossary

g = Glossary()
guest = g.actor('Guest', definition='Person booking accommodation.')
room = g.work_object('Room', definition='A bookable hotel room.')
book = g.activity('book', definition='Reserve a room for a stay.')
```

Either way, **give the language a public home.** Define the glossary, and the stories once there are some, in one dedicated module with a public name, such as `tests/ubiquitous_language.py`. That module *is* the suite's ubiquitous language, not a private helper, so don't prefix its name with an underscore. Test modules import their handles from it. A glossary without stories is fine: you get the Glossary tab without writing any stories.

**The plugin finds the glossary in one of two ways.** First, it reads the glossary from any `story(...)` that references it. A story records its glossary when it is built, so a suite with bound stories needs no further wiring. Otherwise, the plugin scans the attributes of `conftest.py` modules for a `Glossary` or `FileGlossary` instance. So a suite without stories has to bind the instance *by name*:

```python
# conftest.py
from tests.ubiquitous_language import g  # noqa: F401 — plugin discovery
```

`import tests.ubiquitous_language` binds a module, not a glossary. The scan then finds nothing, and the Glossary tab is empty. Binding the glossary by name is a good habit even with stories: it costs one line, and it keeps working after a later refactor removes the last story.

**One glossary per suite.** Stories that reach two different `Glossary` instances raise `PytestGivenError`, and so do two glossaries in conftests. But once the stories reach one glossary, a different glossary in a conftest is silently ignored. Keep one instance and import it everywhere.

## Using terms in narration

Look up a handle by name, like `g['Room']` (case-insensitive), or use the variables a code-defined glossary returned. Both work in t-string steps, `@scenario(...)` titles and story sentences:

```python
with when(t'a {g["Guest"].l} {g["book"].s} a {g["Room"].l}'):
    ...
```

Every handle offers the same four forms, whether you captured it (`guest = g.actor(...)`) or looked it up (`g['Guest']`). Pick the simplest form that gives the word you need:

- **Bare handle:** `g['Room']` renders the term's canonical text. Use it whenever the word appears unchanged. Writing `g['Room']('Room')` adds nothing.
- **`.l`:** `g['Attachment'].l` (or `guest.l`) renders the canonical text in lowercase, the usual form in the middle of a sentence. Acronyms keep their case (`LLM Call` becomes *LLM call*). Prefer it to `g['Attachment']('attachment')`.
- **`.s`:** the S-form. `room.s` renders *Rooms* and `book.s` renders *books*. It chains with `.l` (`room.l.s` renders *rooms*). Prefer it to `room('rooms')`. It only adds -s, -es or -ies to the last word; anything else (*people*, *checks in*) needs the called form.
- **Called:** `g['search']('searches for')` supplies any *other* wording: an irregular plural (`person('people')`), another inflection, or a concrete instance (`organizer('Carol')`). `.l` and `.s` work on it too.

## Naming terms

- **Term names are natural language, not class names.** Name the concept the way a person would say it (`File glossary`, `Clause part`), and spell out the implementing class (`FileGlossary`, `ClausePart`) in the definition. A one-word term may match its class name only when the class name is already the natural word. A multi-word CamelCase name never is.
- **Renaming or removing a term is a code change, not just a doc edit.** A term's slug is its lookup key: the name in lowercase, with every non-alphanumeric character replaced by `-`. So `File glossary` and `FileGlossary` are *different* keys, and a rename breaks every `g['Old name']` reference. Search for the old name, update the references, and re-render the reports. Rename the implementation too: if the code keeps the old name, you create exactly the language drift the vocabulary rule forbids (see [scenarios.md](scenarios.md)). Adding a term is always safe.

## Kinds

Each term is an actor, an activity or a work object. A term gets its kind in one of three ways:

1. **Explicitly:** `g.actor(...)`, `g.activity(...)` or `g.work_object(...)`, or a `kind_column` in the glossary file.
2. **Inferred from stories:** a term with no declared kind takes its kind from its positions in clauses. Position 0 makes it an actor, odd positions (the verb slots) an activity, and even positions from 2 on a work object. A term seen both as an actor and in a noun slot becomes an actor, because an actor can receive a hand-off. A term seen in a verb slot *and* in any other slot raises an error; add a kind column to settle it. A term used only in steps stays kindless (grey).
   **A declared kind is never overridden:** putting a term in a slot its kind doesn't allow raises an error at `sentence(...)`. `kind_column` is opt-in: a column headed "Kind" is ignored unless you pass `kind_column=`.
3. **Deliberately deferred:** `g('foo')` declares a term the team hasn't classified yet. It goes into the *Uncategorized* group and shows an *Undefined* badge until someone writes a definition. Treat this as a place to sort terms later, not a place to leave them. This works only for code-defined glossaries. A `FileGlossary` is a **closed vocabulary**: `g('foo')` and `g['foo']` both only look up, and raise on an unknown name. To add vocabulary, add a row to the file.

## Keeping the glossary honest

- **Don't dilute the glossary.** A term deserves its row when the team really uses the word: someone would look it up, and its meaning is specific to the domain. Never add a term just to get more term refs or to satisfy the lint. A generic word stays a bare string. When a row doesn't deserve its place, delete it instead of inventing a reference to it.
- **Watch the size. A glossary is read as a whole, never in samples.** Reading every term in one pass is how you notice a near-duplicate before you add it. A glossary too long to read comfortably in one sitting probably covers more than one bounded context. Raise that with the user as a design question: one glossary per context means splitting the suite too.
- **A definition that states behavior is part of the spec.** A row that says "must be unique" or "produces no step" makes a claim. Back it with a scenario, and update the row when the behavior changes.
- **A term that nothing references is normal.** A glossary documents the domain, not the suite's coverage, which is why `dead-term` is off by default. If you turn it on, treat a finding as a reason to look at the term. If an undecorated test already shows its behavior, decorate that test. If a step uses the term as plain text, add the term ref.
