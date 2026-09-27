# Glossary

A glossary defines the terms of your domain: the words your team uses for the things and actions it deals with. These words should mean the same everywhere: in conversations with stakeholders, in code, in tests, and in guidance for AI agents. pytest-given lets your tests refer to glossary terms, which links them to the glossary. The report highlights each such word and shows the term's definition on hover, and a **Glossary** tab lists all terms.

Referring to glossary terms from your tests is optional: a glossary is useful on its own. It also pairs well with [Domain Storytelling](domain-storytelling.md): story sentences that use glossary terms can be matched against your tests, so the report shows which scenarios cover them.

!!! info "Ubiquitous Language"

    Domain-Driven Design calls this shared vocabulary the [ubiquitous language](https://martinfowler.com/bliki/UbiquitousLanguage.html): one set of terms that domain experts and developers use everywhere. A glossary writes it down, and tests that refer to its terms stay in that language.

## Declaring terms

Create a `Glossary` and declare each term with a definition:

```python
from pytest_given import Glossary

g = Glossary()
guest = g('Guest', definition='Person booking accommodation.')
room = g('Room', definition='A bookable hotel room.')
book = g('book', definition='Reserve a room for a stay.')
```

Each call returns a **handle**. If the term already exists, `g(...)` returns its handle. To only look up a term, use `g['Guest']`, which raises an error if the term doesn't exist.

## Term refs

A **term ref** is a glossary term used in a step or a scenario title. To create one, put a handle into a [t-string](step-text.md), like `t'a {guest} {book("books")} a {room}'`. The report shows each term ref as a highlighted word with the term's definition on hover.

A term ref has three forms. Use the simplest one that fits your sentence:

- **`{guest}`** shows the term as declared: *Guest*.
- **`{guest.low}`** shows the term in lowercase: *guest*. This is the usual form in the middle of a sentence.
- **`guest('Alice')`** shows any other text: a verb form (`book('books')`), a plural (`room('rooms')`), or a specific instance (`guest('Alice')`). Don't write `guest('Guest')` or `guest('guest')`; use `{guest}` or `{guest.low}` instead.

All three forms work on every handle, including handles you look up by name.

## File glossary

Instead of declaring terms in Python, you can keep your glossary in a Markdown file. People and AI agents can read and edit it without touching code, and your project may already have a `GLOSSARY.md`. Load the file with `FileGlossary`:

```python
from pathlib import Path
from pytest_given import FileGlossary

g = FileGlossary(Path(__file__).parent / 'GLOSSARY.md')
```

The file needs at least one Markdown table (a GFM pipe table). By default, the first column is the term and the second is its description. To use other columns, pass `term_column`, `description_column`, or `kind_column`. Each takes a column number (starting at 0) or a header name (case-insensitive):

```python
g = FileGlossary('GLOSSARY.md', term_column='Term', description_column='Meaning', kind_column='Kind')
```

Look up a term by name with `g['Guest']` (case-insensitive). The result is a handle like any other:

```python
with when(t'{g["Guest"]} {g["book"]("books")} a {g["Room"]}'):
    ...
```

A file glossary is a **closed vocabulary**: you add new terms only as rows in the file. Both `g['foo']` and `g('foo')` only look up a term, and raise an error if it doesn't exist.

## Kinds

A term can have a kind, which sets its color in the report. The kinds come from [Domain Storytelling](domain-storytelling.md): **actor**, **work object**, and **activity**. To declare a kind, use `g.actor(...)`, `g.work_object(...)`, or `g.activity(...)` instead of `g(...)`:

```python
guest = g.actor('Guest', definition='Person booking accommodation.')
room = g.work_object('Room', definition='A bookable hotel room.')
book = g.activity('book', definition='Reserve a room for a stay.')
```

In a file glossary, the kinds come from the column you pass as `kind_column`.

If you don't declare a kind, pytest-given [infers it](domain-storytelling.md#kind-inference) from the story sentences that use the term. A term that gets no kind either way is **kindless**. The report shows it in a neutral color and lists it under **Uncategorized** in the Glossary tab.

## Undefined terms

A term without a `definition=` is **undefined**. The Glossary tab marks it with an *Undefined* badge and can filter for these terms.

Every declared term appears in the report, whether a test uses it or not.

## Discovery

pytest-given finds your glossary in one of two ways:

1. Through a story: each `story(...)` remembers the glossary its terms come from.
2. Otherwise, by looking for a `Glossary` or `FileGlossary` object among the names defined in your `conftest.py` files.

So if you use a glossary without stories, import the glossary object itself into a `conftest.py`:

```python
# conftest.py
from tests.glossary import g  # noqa: F401 — plugin discovery
```

`import tests.glossary` does not work: it imports the module, not the glossary object. pytest-given then finds nothing, and the Glossary tab stays empty.

A test suite can have only one glossary. If your stories reach two different glossary objects, or your `conftest.py` files hold two, pytest-given raises `PytestGivenError`. A `conftest.py` glossary other than the one your stories use is ignored, so keep one glossary object and import it everywhere.

## Examples

The hotel-booking and file-glossary-booking [examples](../examples.md) show a glossary in use.
