# Sentences and Clauses — Design Spec

## Goal

Name the Domain Storytelling layer with Domain Storytelling's own terms:

| Domain Storytelling | today | after |
|---|---|---|
| actor | kind `actor`, `g.actor()` | unchanged |
| work object | kind `object`, `g.work_object()` | unchanged |
| activity | kind `verb`, `g.verb()` | kind `activity`, `g.activity()` |
| sentence | `Activity`, `activity()` | `Sentence`, `sentence()` |
| — | `ActivityPath`, `path()` | `Clause`, `clause()` |

```python
book_a_room = story('Book a room', [
    sentence(guest, 'searches for', room),
    sentence(
        clause(organizer('Carol'), 'adds', guest('Alice'), 'to', booking),
        clause(organizer('Carol'), 'adds', guest('Bob'), 'to', booking),
    ),
])
```

This is a rename only; no behavior changes. The [pins spec](2026-09-21-pins-design.md)
builds on it, and both ship in one release so users migrate once.

## Background

The [Domain Storytelling quick-start guide](https://domainstorytelling.org/quick-start-guide)
defines the terms:

- "The actors' activities are shown as arrows and labeled with verbs." An activity is "the
  predicate of a sentence".
- "Activities connect actors and work objects to form sentences." The sequence number belongs to
  the sentence: "the sentences can be brought into an order by numbering them".

Its "Possible sentence structures" figure shows sentences with several arrows under one number:

- **4**: A hands over w to B and C. One activity arrow fans out to two recipients.
- **5**: A collaborates on w, and B collaborates on w. Two activity arrows, both numbered 5.

So our `Activity` is their sentence and our `verb` kind their activity. Our path is a linear walk
through one sentence's arrows, which Domain Storytelling doesn't name: sentence 4 is one activity
but two paths, since a path is linear and repeats the shared `A hands over w`. "Path" is also the
most overloaded word in code, where it reads as a file path first.

Two current texts contradict the source: the glossary's *Path* row ("a branching segment inside a
story … share a prefix"), and the guide's "alternate sentences" for the paths of one activity.

## Design

### The renames

Public API (`pytest_given`):

- `activity()` → `sentence()`
- `path()` → `clause()`
- `Glossary.verb()` → `Glossary.activity()`

Model (`model/schema.py`):

- `Activity` → `Sentence`, `ActivityId` → `SentenceId`
- `Story.activities` → `Story.sentences`, `Activity.paths` → `Sentence.clauses`
- `ActivityPath` → `Clause`, `ActivityPart` → `ClausePart`, `ActivityTermRef` → `ClauseTermRef`,
  `ActivityWord` → `ClauseWord`
- `TermKind` `'verb'` → `'activity'`

Private names follow the public ones (`_PinnedActivity`, `_activity_path_from_dict`, …). No old
name survives outside the pin surface and the grammar words below.

**Left to the pins spec.** The pin surface keeps its names here, since the pins spec replaces it and
nothing should be renamed twice: `activity_id=`, step `activity=`, `@scenario(activities=)`, and
`activity_ids` on scenarios and steps.

**Kept.** Grammar words that describe positions or forms, not the kind:

- The slots stay *actor*, *verb* and *noun*. "Verb slot" names a grammatical position, and Domain
  Storytelling says activities are verbs, so an activity term sits in a verb slot.
- *Inflection* stays: a surface form of an activity term.

### Report

JSON:

- `stories[].activities[]` → `stories[].sentences[]`, each `{id, clauses: [{parts}]}`.
- `glossary.terms[].kind`: `"verb"` → `"activity"`.
- `coverage[].activity_id` → `sentence_id`.

Serde reads only the new names. `pytest-given report` on a report saved before this change fails
on its first `verb` term, since the kind is validated. That's acceptable in alpha, and the
changelog says to regenerate.

HTML:

- The chip `Activity 3: …` becomes `Sentence 3: …`.
- The hash parameter `#activity-filter=` becomes `#sentence-filter=`. An old shared link opens
  unfiltered.
- The Glossary view's *Verbs* group becomes *Activities*.
- CSS: `term-verb`, `term-ref-verb`, `kind-swatch-verb` and the `--term-verb-*` tokens become
  `activity`.
- App data: `scenario_activities` → `scenario_sentences`, `activity_labels` → `sentence_labels`.

Verified by Playwright only.

### File glossary and lint

- The file-glossary kind column takes `activity` where it took `verb`. `verb` is rejected with the
  existing message listing the accepted values.
- The `dead-term` message's "no story activity" becomes "no story sentence". No rule id changes.

### Glossary

`GLOSSARY.md` is also the dogfood file glossary, so `pg['Activity']` in
`tests/ubiquitous_language.py` follows the row rename.

The Domain Storytelling section's intro gains one line: terms follow Domain Storytelling's own,
where actors and work objects connected by activities form sentences.

New and rewritten rows:

- **Sentence** (was *Activity*): One numbered row in a story, what Domain Storytelling calls a
  sentence: an actor, an activity and its work objects, plus connective words. Constructed by
  `sentence(...)`. Usually one clause, built implicitly; several when the sentence has several
  arrows under one number.
- **Activity** (was *Verb*): A glossary term for what an actor does (e.g., *book*, *confirm*), which
  Domain Storytelling draws as an arrow labelled with a verb. Activities accept inflections: calling
  `book('books')` records *books* as a surface form of the canonical *book*.
- **Clause** (was *Path*): One linear walk through a sentence's arrows, a node/edge alternation
  starting actor → verb → noun, constructed by `clause(...)`. A sentence with several arrow chains
  under one number, such as an actor handing a work object to two recipients, takes one clause per
  chain. Domain Storytelling names no such unit.
- **Clause part** (was *Activity Part*): unchanged apart from "bare clause word" for "bare path
  word".

Rows that change a word:

- *Glossary*: `.activity(...)` in place of `.verb(...)`.
- *File glossary*, *Slot*: "clause" in place of "activity path".
- *Term*: "an Actor, Work Object, Activity, or kindless term".
- *Handle*: "an inflection on an *Activity*".
- *Term ref*: `ClauseTermRef` inside a clause.
- *Inflection*: "a surface form of an Activity term".
- *Story*: "a sequence of sentences", `story('Title', [sentence(...), ...])`.
- *Kind inference*, *Kindless*: "story sentences", "never in a sentence".
- *Scenario↔activity binding* becomes *Scenario↔sentence binding*, and *Coverage* says "sentence".
  The pins spec rewrites both.

### Docs and skills

- Site guide:
  - `domain-storytelling.md`: the vocabulary, the mapping to Domain Storytelling with a link to the
    quick-start guide, and "one clause per arrow chain" in place of "alternate sentences".
  - `scenarios.md`, `parametrized.md`, `index.md`, `examples.md`, `narration-lint.md`: the new
    names.
- `README.md`: the new names.
- Authoring skill: `SKILL.md`, `api.md`, `domain-storytelling.md`, `glossaries.md` (the kind column
  value), `scenarios.md`, `stories.md`.
- Navigating skill: `report-json.md`, its field list and `jq` examples.
- Reviewing skill: `SKILL.md`, `story-coverage.md`.
- Regenerate the `.claude/skills/` mirror with `uv run pytest-given skills install`.

Specs under `docs/specs/` outside `proposed/` stay as written, since they record decisions in the
vocabulary of their time.

### Self-report and examples

- `tests/ubiquitous_language.py`: `sentence(...)`, `pg['Sentence']`. The sentence "developer
  captures story as activity" now reads "as sentence".
- `hotel-booking` and `file-glossary-booking` move to the new names.
- `hotel-booking` gains a sentence whose clauses start at different actors, the quick-start
  figure's sentence 5. No test or example has that shape today.
- Tests follow mechanically, including scenario titles that name the old terms. One new scenario:
  a sentence whose clauses start at different actors builds and is covered.
- Regenerate the example and self-report outputs.

### Changelog

Each break gets a `**Breaking.**` entry with its migration:

- `activity()` is now `sentence()`, `path()` is now `clause()`, and `Glossary.verb()` is now
  `Glossary.activity()`: rename the calls and imports.
- A file glossary's kind column says `activity` where it said `verb`.
- In the JSON report, `stories[].activities[]` is now `stories[].sentences[]` with `clauses` in
  place of `paths`, the term kind `"verb"` is now `"activity"`, and `coverage[].activity_id` is now
  `sentence_id`. Regenerate saved reports: `pytest-given report` rejects a `verb` kind.
- The report's `#activity-filter=` link parameter is now `#sentence-filter=`.

The pin arguments get their entries from the pins spec.

## Considered and rejected

- **Keep `Activity` for the numbered row.** The quick-start guide puts the number on the activity
  arrow, so "activity 3" reads naturally. But it leaves the verb kind without its Domain
  Storytelling name, and it is wrong exactly for multi-arrow sentences like 5.
- **Rename the row only, keep `verb`.** The term kinds would still not match Domain Storytelling's
  building blocks (actors, work objects, activities).
- **Other names for the path:**
  - *branch*: git, and a single-clause sentence doesn't branch.
  - *chain*: method chaining.
  - *route*: web routing.
  - *walk*: graph theory and `os.walk`.
  - *strand*: says nothing.

  *Clause* fits the grammar the vocabulary already uses: a clause is a subject plus a predicate,
  which is exactly what `clause()` enforces.
- **Subject / predicate / object slots.** The actor and noun slots map onto the kinds inference
  assigns, and grammar names would add a layer between them.
- **`verb` as a file-glossary kind alias.** The kind column is ubiquitous language, with one name
  per kind. The existing aliases are spellings of one word (`work object`, `work_object`), not
  synonyms.
- **Kind `object` → `work_object`.** The method is already `g.work_object()` and the file glossary
  accepts `work object`. Only the stored literal differs, which no author types, so it doesn't
  justify a JSON break.

## Forward notes

- **Story diagrams** (unmerged branch) rebase onto the new names: the arrow number comes from
  `int(sentence.id)`, and the arrows from `sentence.clauses`.
