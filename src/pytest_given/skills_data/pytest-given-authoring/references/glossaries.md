# Authoring glossaries

A glossary declares the ubiquitous language your tests speak: actors, work objects, and verbs, each with a definition. Steps and stories reference terms through handles; every reference renders as a kind-coloured pill with the definition as tooltip and feeds the report's Glossary tab (with per-term scenario filtering).

## Two ways to declare a glossary

**`FileGlossary` over a Markdown file — the recommended default.** One `GLOSSARY.md` both humans and agents read, loaded live by the tests:

```python
from pathlib import Path
from pytest_given import FileGlossary

g = FileGlossary(Path(__file__).parent / 'GLOSSARY.md')
```

The file needs at least one GFM pipe table. By default the first column is the term and the second its description; override with `term_column`, `description_column`, and `kind_column` (0-based index or case-insensitive header name):

```python
g = FileGlossary('GLOSSARY.md', kind_column='Kind')
g = FileGlossary('GLOSSARY.md', term_column='Term', description_column='Meaning')
```

**Code-defined `Glossary`** — declare terms where the tests live:

```python
from pytest_given import Glossary

g = Glossary()
guest = g.actor('Guest', definition='Person booking accommodation.')
room = g.work_object('Room', definition='A bookable hotel room.')
search = g.verb('search', definition='Look up available options.')
```

Either way, put the glossary in a `conftest.py` so the plugin discovers it. Glossary-only mode is fine — you get the Glossary tab without writing any stories.

## Using terms in narration

Look up handles by name — `g['Room']` (case-insensitive) — or use the captured variables from a code-defined glossary. Both work in t-string steps and in story activities; the callable form supplies the inflection an activity or sentence needs:

```python
with when(t'a {g["Guest"]} {g["book"]("books")} a {g["Room"]}'):
    ...
```

## Naming terms

- **Term names are natural language, not class names.** Name the concept a human would say (`File glossary`, `Activity Part`) and spell the implementing class (`FileGlossary`, `ActivityPart`) inside the definition. A one-word term may coincide with its class only when the class is already the natural word — multi-word CamelCase never is.
- **Renaming or removing a term is a code change, not just a doc edit.** A term's slug (lowercased, non-alphanumeric → `-`) is the lookup key, so `File glossary` and `FileGlossary` are *different* keys and a rename breaks every `g['Old name']` reference. Grep for the old name, update the references, re-render the reports. Adding a term is always safe.

## Kinds

Terms are actors, verbs, or work objects. Three ways a term gets its kind:

1. **Explicit** — `g.actor(...)` / `g.verb(...)` / `g.work_object(...)`, or a `kind_column` in the glossary file.
2. **Inferred from stories** — when a file glossary has no kind column, kinds are inferred from story activity-slot positions (slot 0 → actor, slot 1 → verb, slot ≥ 2 → work object). A term used only in steps stays kindless (neutral pill).
3. **Deliberately deferred** — `g('foo')` declares a term the team hasn't classified yet: it lands in the *Uncategorized* bucket and shows an *Undefined* badge until a definition arrives. Use it as a triage bucket, not a resting place.

## Keeping the glossary honest

- **Tags never duplicate terms** — filter a feature area via its term, and keep tags for what the glossary can't carry (behaviour, mechanism). The `tag-shadows-term` lint rule enforces this.
- **Every file term appears in the report**, even one no step or story references. On suites whose glossary should be fully exercised, opt into the `dead-term` lint rule to flag unreferenced terms.
