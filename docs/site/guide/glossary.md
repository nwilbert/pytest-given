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
book = g('book', definition='Reserve a **room** for a stay.')
```

A definition can use [bold, italic, code and line breaks](step-text.md#formatting). Bold marks a reference to another term: in the report, `**room**` shows the Room term's definition on hover and opens its entry in the Glossary tab when clicked. A bold word matches a term's name or its [S-form](#term-refs) in any case, so `**Rooms**` works too. Use italics for emphasis, because the lint flags a bold word that names no term ([`unresolved-definition-ref`](../configuration/narration-lint.md)).

Each call returns a **handle**. If the term already exists, `g(...)` returns its handle. To only look up a term, use `g['Guest']`, which raises an error if the term doesn't exist.

## Term refs

A **term ref** is a glossary term used in a step or a scenario title. To create one, put a handle into a [t-string](step-text.md), like `t'a {guest} {book.s} a {room}'`. The report shows each term ref as a highlighted word with the term's definition on hover.

A term ref has four forms. Use the simplest one that fits your sentence:

- **`{guest}`** shows the term as declared: *Guest*.
- **`{guest.l}`** shows the term in lowercase: *guest*. This is the usual form in the middle of a sentence. Only capitalized words are lowercased, so acronyms keep their case: `LLM Call` reads *LLM call*.
- **`{room.s}`** shows the term's **S-form**: the plural of a noun (*Rooms*), or the third person singular of a verb (`book.s` reads *books*). It adds -s to the last word, -es after s, x, z, ch or sh, and turns a consonant + y into -ies. Anything else, such as *people* or *checks in*, takes the called form.
- **`guest('Alice')`** shows any other text: an irregular form (`person('people')`), another verb form (`search('searches for')`), or a specific instance (`guest('Alice')`). Don't write `guest('Guest')`, `guest('guest')` or `room('rooms')`; use `{guest}`, `{guest.l}` or `{room.l.s}` instead. The Glossary tab lists every called form of a term under *Other forms*, whether it names an instance or is another form of the word.

`.l` and `.s` chain and also apply to the called form: `{room.l.s}` reads *rooms*, `{room('suite').s}` reads *suites*. All forms work on every handle, including handles you look up by name.

## Markdown glossary

Instead of declaring terms in Python, you can keep your glossary in a Markdown file. People and AI agents can read and edit it without touching code, and your project may already have a `GLOSSARY.md`. pytest-given reads two formats: terms in tables with `TableGlossary`, and term paragraphs with `ParagraphGlossary`. Loading a file with the wrong class raises an error that names the other one.

Look up a term by name with `g['Guest']` (case-insensitive). The result is a handle like any other:

```python
with when(t'{g["Guest"]} {g["book"].s} a {g["Room"]}'):
    ...
```

A Markdown glossary is a **closed vocabulary**: you add new terms only in the file. Both `g['foo']` and `g('foo')` only look up a term, and raise an error if it doesn't exist.

### Tables

`TableGlossary` reads the Markdown tables of a file:

```python
from pathlib import Path
from pytest_given import TableGlossary

g = TableGlossary(Path(__file__).parent / 'GLOSSARY.md')
```

The file needs at least one Markdown table (a GFM pipe table). pytest-given reads the tables a GFM renderer shows, including one in a blockquote or a list but not one in a code or HTML block, and a cell missing from a row reads as empty. Every table is read, except one whose header lacks a column you select by name. By default, the first column is the term and the second is its definition. To use other columns, pass `term_column`, `definition_column`, `kind_column` or `avoid_column`. Each takes a column number (starting at 0) or a header name (case-insensitive):

```python
g = TableGlossary(
    'GLOSSARY.md',
    term_column='Term',
    definition_column='Meaning',
    kind_column='Kind',
    avoid_column='Avoid',
)
```

A term or kind cell may be formatted: `**Guest**` reads as `Guest`. The definition keeps its [formatting](step-text.md#formatting). An avoid cell lists the term's [avoided words](#avoided-words), separated by commas. A comma inside parentheses doesn't separate them.

### Term paragraphs

`ParagraphGlossary` reads the `GLOSSARY.md` format of Matt Pocock's [skills](https://github.com/mattpocock/skills), where each term is a paragraph of its own, a **term paragraph**:

```markdown
# Ordering

Receives and tracks customer orders.

## Language

**Order**:
A customer's request for goods, placed in one checkout.
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery, for one **Order**.
_Avoid_: Bill, payment request

## Relationships

- An **Order** produces one **Invoice**.
```

```python
from pathlib import Path
from pytest_given import ParagraphGlossary

g = ParagraphGlossary(Path(__file__).parent / 'GLOSSARY.md')
```

- **A term paragraph starts with a term line:** a line that opens with the term's name in bold, followed directly by a colon, as in `**Order**:`. In `**Order:**` the colon sits inside the bold, so the line is no term line. The term paragraph ends at the next term line or at the end of the paragraph, so two terms with no blank line between them are still two terms.
- **The definition** is the rest of the term paragraph. It starts on the term line after the colon or on the next line. Its line breaks become spaces, as GitHub shows them. A `<br>`, or a backslash or two spaces at the end of a line, is a line break.
- **An avoid line** starts with `_Avoid_:` or `*Avoid*:` and lists the term's [avoided words](#avoided-words), separated by commas. A list too long for one line can wrap onto the term paragraph's next lines.
- **Everything else is prose**, which pytest-given ignores: the title, the description under it, any text before a paragraph's first term line, lists and blockquotes. A heading reading `Relationships` or `Flagged ambiguities` starts a part that is ignored too, up to the next heading of the same or a higher level.

The format has no place for a kind, so a term in it gets its kind from [kind inference](domain-storytelling.md#kind-inference) or stays kindless.

## Kinds

A term can have a kind, which sets its color in the report. The kinds come from [Domain Storytelling](domain-storytelling.md): **actor**, **work object**, and **activity**. To declare a kind, use `g.actor(...)`, `g.work_object(...)`, or `g.activity(...)` instead of `g(...)`:

```python
guest = g.actor('Guest', definition='Person booking accommodation.')
room = g.work_object('Room', definition='A bookable hotel room.')
book = g.activity('book', definition='Reserve a room for a stay.')
```

In a `TableGlossary`, the kinds come from the column you pass as `kind_column`.

If you don't declare a kind, pytest-given [infers it](domain-storytelling.md#kind-inference) from the story sentences that use the term. A term that gets no kind either way is **kindless**. The report shows it in a neutral color and lists it under **Uncategorized** when the Glossary tab groups terms by kind.

## Undefined terms

A term without a `definition=` is **undefined**. The Glossary tab marks it with an *Undefined* badge and can filter for these terms.

Every declared term appears in the report, whether a test uses it or not.

## Glossary sections

A **glossary section** is a named group of terms. The Glossary tab of the [HTML report](../html-report.md#stories-and-glossary) groups terms by section and filters by them.

In code, declare terms through `g.section(name)`. A section has the glossary's `actor`, `work_object`, `activity` and call form, and puts each term it declares into the glossary with that section:

```python
booking = g.section('Booking')
guest = booking.actor('Guest', definition='Person booking accommodation.')
room = booking.work_object('Room', definition='A bookable hotel room.')

payment = g.section('Payment')
refund = payment.activity('refund', definition='Return the money a **guest** paid for a cancelled stay.')

clerk = g.actor('Clerk', definition='Staff at the front desk.')  # no section
```

Look up a term on the glossary, whatever its section: `g['Guest']`. Calling `g.section('Booking')` again, in the same module or another, adds to the same section. Section names are compared as written, so `Booking` and `booking` are two sections.

In a Markdown glossary, a term's section is the nearest heading above its table or term paragraph, at any level, with its formatting removed. A heading inside a list or a blockquote doesn't count. Two kinds of heading name no section:

- **The title:** a file's only level-1 heading. A file with several level-1 headings has no title, and each of them names a section.
- **`Language` and `Terms`** in a `ParagraphGlossary`, in any case. They hold the terms rather than group them.

A term above every qualifying heading has no section. Two headings with the same text name one section.

A term belongs to one section. Declaring a term again in another section raises an error, and so does the same term in two sections of a file, even in two identical rows.

## Avoided words

An **avoided word** is a synonym of a term that the team has decided not to use. List a term's avoided words with `avoid=`, on the glossary or on a section:

```python
guest = g.actor('Guest', definition='Person booking accommodation.', avoid=['Customer', 'Client'])
```

A `TableGlossary` reads them from its `avoid_column`, a `ParagraphGlossary` from a term's avoid line. The term's card in the Glossary tab shows them when expanded, and the Glossary search finds the term by them. The [`avoided-word`](../configuration/narration-lint.md) lint rule flags an avoided word used in a step, a scenario title or a story sentence.

- **An entry may end with a note** in parentheses, as in `Reservation (in partner APIs only)`. The card shows the whole entry, and the lint matches only the text before the note. An entry that is only a note raises an error.
- **An entry shows its [formatting](step-text.md#formatting)** on the card, but a bold word in it links no term.
- **An entry is dropped** when its avoided word repeats an earlier entry's of the same term, in any case and with a hyphen or a space between its words, even if the notes differ.
- **An avoided word may not name a term** of the same glossary, by its name or its [S-form](#term-refs), in any case. A glossary that avoids `Booking` while it defines `Booking` or `Bookings` raises an error.
- **Several terms may avoid the same word.** The lint then names each of them, and you pick the one the step means.

## Discovery

pytest-given finds your glossary in one of two ways:

1. Through a story: each `story(...)` remembers the glossary its terms come from.
2. Otherwise, by looking for a `Glossary`, `TableGlossary` or `ParagraphGlossary` object among the names defined in your `conftest.py` files.

So if you use a glossary without stories, import the glossary object itself into a `conftest.py`:

```python
# conftest.py
from tests.glossary import g  # noqa: F401 — plugin discovery
```

`import tests.glossary` does not work: it imports the module, not the glossary object. pytest-given then finds nothing, and the Glossary tab stays empty.

A test suite can have only one glossary. If your stories reach two different glossary objects, or your `conftest.py` files hold two, pytest-given raises `PytestGivenError`. A `conftest.py` glossary other than the one your stories use is ignored, so keep one glossary object and import it everywhere.

## Examples

The hotel-booking, file-glossary-booking and paragraph-glossary [examples](../examples.md) show a glossary in use. All three have glossary sections and avoided words.
