# Glossary

A glossary lists the domain terms your tests use: the **ubiquitous language** of Domain-Driven Design. When step text mentions a glossary term, the report highlights the word and shows the term's definition on hover. The report also gets a **Glossary** tab that lists all terms.

You can use a glossary on its own. [Domain Storytelling](domain-storytelling.md) builds on it: its stories are made of glossary terms.

## Declaring terms

Create a `Glossary` and declare each term with a definition:

```python
from pytest_given import Glossary

g = Glossary()
guest = g('Guest', definition='Person booking accommodation.')
room = g('Room', definition='A bookable hotel room.')
book = g('book', definition='Reserve a room for a stay.')
```

Each call returns a **handle**. If the term already exists, `g(...)` returns it. To only look up a term, use `g['Guest']`, which raises an error if the term doesn't exist.

Put handles into t-string step text, like `t'a {guest} {book("books")} a {room}'`. Each handle becomes a **term ref**: a highlighted word in the rendered step.

## Term refs

A term ref has three forms. Use the simplest one that fits your sentence:

- **`{guest}`** shows the term as declared: *Guest*.
- **`{guest.low}`** shows the term in lowercase: *guest*. This is the usual form in the middle of a sentence.
- **`guest('Alice')`** shows any other text: a verb form (`book('books')`), a plural (`room('rooms')`), or a specific instance (`guest('Alice')`). Don't write `guest('Guest')` or `guest('guest')`; use `{guest}` or `{guest.low}` instead.

All three forms work on every handle, including handles you look up by name.

## File glossary

If your project already has a `GLOSSARY.md`, load it with `FileGlossary` instead of declaring terms in code:

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

A file glossary is a **closed vocabulary**: new terms can only be added as rows in the file. Both `g['foo']` and `g('foo')` just look up a term, and raise an error if it doesn't exist.

## Kinds

A term can have a kind, which sets its color. The kinds come from [Domain Storytelling](domain-storytelling.md): **actor**, **work object**, and **activity**. To declare a kind, use `g.actor(...)`, `g.work_object(...)`, or `g.activity(...)` instead of `g(...)`:

```python
guest = g.actor('Guest', definition='Person booking accommodation.')
room = g.work_object('Room', definition='A bookable hotel room.')
book = g.activity('book', definition='Reserve a room for a stay.')
```

In a file glossary, add a `kind_column`.

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
from tests.ubiquitous_language import g  # noqa: F401 — plugin discovery
```

`import tests.ubiquitous_language` does not work: it imports the module, not the glossary object. pytest-given then finds nothing, and the Glossary tab stays empty.

A test suite can have only one glossary. If two different glossary objects reach the report, pytest-given raises `PytestGivenError`.

## Examples

The hotel-booking and file-glossary-booking [examples](../examples.md) show a glossary in use.
