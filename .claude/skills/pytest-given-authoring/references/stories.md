# Authoring stories

A domain story models a flow as a sequence of sentences: who does what with what. It works at the actor level, above individual scenarios. The report's Stories tab shows each story as a timeline, with coverage for each sentence computed from the scenarios that implement it. (For the method behind the feature, see [domain-storytelling.md](domain-storytelling.md).)

## What a story is

```python
from pytest_given import clause, sentence, story

book_a_group_trip = story('Book a Group Trip', [
    sentence(organizer('Carol'), 'searches for', room),
    sentence(organizer('Carol'), 'submits', payment, 'for', booking),
    sentence(booking_system, confirm.s, booking, name='confirm'),
])
```

- A sentence reads from left to right: **actor → activity → work object**, with optional connective words (`'for'`, `'to'`) between the parts. Each clause alternates strictly between entities and the words that link them, so it has an odd number of parts, at least three. Even positions hold entities, and position 0 is the actor who acts. Odd positions are the verb slots: an activity or a connective.
- **A bare word takes up a position.** Write a connective as one string in a verb slot (`'to the'`, `'with a'`). Never put a separate article before a noun, because that pushes the noun into a verb slot.
- Handles come from the glossary. Calling a handle supplies an instance or an inflection: `organizer('Carol')`, or `confirm.s`, which reads *confirms*.
- Any part may be a **bare string** instead of a glossary handle. That is the right choice for a verb that is just sentence prose (*searches for*, *submits*; see [Authoring workflow](#authoring-workflow)). But narration can only match a sentence with at least two different glossary terms. A sentence with fewer shows as "not coverage-tracked", unless a step pins it (see below).
- Some sentences have several arrow chains under one number: an actor handing a work object to two recipients, or two actors working side by side. Such a sentence takes one `clause(...)` per chain:

```python
sentence(
    clause(organizer('Carol'), 'adds', guest('Alice'), 'to', booking),
    clause(organizer('Carol'), 'adds', guest('Bob'), 'to', booking),
),
```

**A sentence with several clauses is hard to cover.** Coverage combines the term refs of *all* its clauses, so covering it takes one step that references every term in every clause. Such a step quickly becomes impossible to write. Use several clauses only for chains you accept as uncovered. Otherwise, split them into separate sentences, or pin a covering step (see below).

## Binding scenarios to a story

**Every declared story appears in the report**, covered or not. `@scenario(stories=...)` names the stories whose sentences the scenario's steps are matched against:

```python
@scenario('Carol selects a suite', stories=book_a_group_trip)
def test_select_suite(carol):
    with when(t'{organizer("Carol")} selects the {room("Deluxe Suite")}'):
        ...
```

Name a story in `stories=` only when a step can match or pin one of its sentences; a scenario that covers nothing in it is still listed under the story. Coverage is matched **step by step**: a sentence is covered when *one step's* term refs include all of the sentence's terms. Term refs spread over several steps don't add up. The Stories tab shows a coverage chip for each sentence, with the scenarios that touch it. The JSON report has the same result under `coverage[]` (see below).

What this means when you write:

- **Only step narration counts.** Term refs in the `@scenario` name never count. A scenario whose title names both actors stays uncovered until the same term refs appear in a `given`, `when` or `then`.
- **Only the term counts, not its wording.** `room`, `room.l.s` and `room('Deluxe Suite')` are the same term ref, and so are `select` and `select.s`. The instance in the step above is narration, not a condition. To matching, two sentences that differ only by instance are the same sentence. Give one of them a term the other lacks, or pin (see below).
- **Two sentences are covered together when one's terms are a subset of the other's.** The test is "sentence terms ⊆ step terms". So a step that covers `organizer · adds · guest · booking` also covers an `organizer · adds · guest` sentence, whatever that sentence meant. Narration can never tell the two apart. When two sentences turn out nested like this, you have three options: give the narrower one a term the wider one lacks (a different activity usually works), merge them, or accept the shared chip. A pin on the covering step also separates them, because it reaches only the sentences it names.
- **Adding a term to a sentence makes it harder to cover.** Every covering step then has to carry that term too. So editing a story can silently uncover a scenario that used to cover it. A pinned step is not affected.

**Check coverage after you change a sentence or a covering step.** Read it from the JSON report instead of working out the rule yourself:

```bash
pytest <selection> --given-json=report.json
# tracked sentences no scenario covers, as story#sentence
jq -r '.coverage[] | select(.tracked and .scenario_ids == [])
       | .story_id + "#" + (.sentence_id|tostring)' report.json
```

`coverage[]` holds `{story_id, sentence_id, tracked, scenario_ids}` for each sentence, computed by the same code as the Stories tab. `tracked: false` is the "not coverage-tracked" chip. The full shape is in the navigating skill's `references/report-json.md`.

A step can also **pin** sentences: `given(text, pins=book_a_group_trip['confirm'])` takes a sentence handle or a list of them. A pin *replaces* narration matching for that step. The step covers exactly the sentences the pin names, in any story. `pins=[]` turns matching off for a step. Only a pin can cover a sentence with fewer than two terms. Pin when the sentence is phrased at a higher level than the vocabulary the step narrates, such as a process-level sentence implemented by a technical test. Pin it on the one step that demonstrates it. `@scenario(pins=...)` pins the whole scenario: none of its steps is matched by narration, and the steps' own pins are added. `@scenario(pins=[])` keeps only the steps' pins.

**Pin by name, not by number.** Sentence numbers are positions. Inserting a sentence renumbers every sentence after it, and `the_story[5]` then silently points at a different sentence. Name each sentence you pin (`sentence(..., name='confirm')`) and pin `the_story['confirm']`.

An uncovered sentence is a signal, not an error. It marks vocabulary and behavior that no test exercises yet.

## When a story is worth writing

Write a story for flows with distinct actors and hand-offs: a user and a system, two roles, a pipeline of responsibilities. Single-function units don't need one; scenarios alone are the right level there. A story that would read "the function is called with X" is really a scenario.

## Authoring workflow

- **Keep sentences at the level of the domain.** Write what the actor does ("submits payment for the booking"), never what the code does ("calls `submit_payment()`"). If a sentence only makes sense to someone reading the implementation, it is too detailed.
- **Grow the glossary from the sentences, but only with real vocabulary.** A slot gets a term when the word is domain language someone would look up. A word that is just sentence prose, like the generic verbs *tells* and *reviews*, stays a bare string. Don't add glossary rows just to satisfy the grammar. With a file glossary and no kind column, term kinds are inferred from slot positions for free (see [glossaries.md](glossaries.md)). Vocabulary nobody has classified yet can enter as `g('loyalty points')` and be sorted out later.
