# Authoring stories

A domain story models a flow as a sequence of sentences — who does what with what — at the actor level, above individual scenarios. The report's Stories tab renders each story as a timeline with per-sentence coverage computed from the scenarios that implement it. (For the method behind the feature, see [domain-storytelling.md](domain-storytelling.md).)

## What a story is

```python
from pytest_given import clause, sentence, story

book_a_group_trip = story('Book a Group Trip', [
    sentence(organizer('Carol'), 'searches for', room),
    sentence(organizer('Carol'), 'submits', payment, 'for', booking),
    sentence(booking_system, confirm('confirms'), booking, name='confirm'),
])
```

- A sentence reads left-to-right: **actor → activity → work object**, with optional connective words (`'for'`, `'to'`) between parts. Structurally each clause is a strict node/edge alternation of odd length ≥ 3: even positions are entity nodes (position 0 is the acting actor), odd positions are edges (an activity or a connective) — the verb slots.
- **A bare word consumes a position.** Write a connective as one string in an edge slot (`'to the'`, `'with a'`); never insert a standalone article before a noun — it shifts the noun into a verb slot and construction fails.
- Handles come from the glossary; calling one supplies an instance or inflection — `organizer('Carol')`, `confirm('confirms')`.
- Any part may be a **bare string** instead of a glossary handle — the right place for a verb that is just sentence prose (*searches for*, *submits*; see [Authoring workflow](#authoring-workflow)). But a sentence needs at least two distinct glossary terms to be matched by narration; under-anchored sentences render as "not coverage-tracked" unless a step pins them (below).
- A sentence with several arrow chains under one number — an actor handing a work object to two recipients, two actors working side by side — takes one `clause(...)` per chain:

```python
sentence(
    clause(organizer('Carol'), 'adds', guest('Alice'), 'to', booking),
    clause(organizer('Carol'), 'adds', guest('Bob'), 'to', booking),
),
```

**A multi-clause sentence is expensive to cover.** Coverage unions the term refs of *all* clauses, so covering it takes one step referencing every term in every clause, which quickly stops being a step anyone can write. Use several clauses only for chains you accept as uncovered; otherwise split them into separate sentences, or pin a covering step (below).

## Binding scenarios to a story

**Every declared story reaches the report**, covered or not. `@scenario(stories=...)` names the stories a scenario's steps are narration-matched against:

```python
@scenario('Carol selects a suite', stories=book_a_group_trip)
def test_select_suite(carol):
    with when(t'{organizer("Carol")} selects the {room("Deluxe Suite")}'):
        ...
```

Name a story in `stories=` only when a step can match or pin one of its sentences: a scenario that covers none of it still lists under the story. Coverage is matched **per step**: a sentence is covered when a *single step's* term refs include all of the sentence's terms — refs spread across several steps don't add up. The Stories tab shows a coverage chip per sentence with the scenarios that touch it; the JSON report carries the same result under `coverage[]` (below).

What the rule means when you write:

- **Only step narration counts.** Term refs in the `@scenario` name never contribute. A scenario titled with both actors stays uncovered until those refs also appear in a `given`/`when`/`then`.
- **Only the term counts, not its surface form.** `room`, `room.low` and `room('Deluxe Suite')` are one ref, as are `select` and `select('selects')` — the instance in the step above is narration, not a constraint. Two sentences differing only by instance are one to matching: give them a distinguishing term, or pin (below).
- **Two sentences cover together when one's terms are a subset of the other's.** The test is `sentence terms ⊆ step terms`, so a step covering `organizer · adds · guest · booking` also covers an `organizer · adds · guest` sentence, whatever that row meant — the two are never distinguishable by narration. When two rows come out nested, give the narrower one a term the wider lacks (a distinct activity usually does it), merge them, or accept the shared chip; a pin on the covering step reaches only the sentences it names, so it separates them too.
- **Growing a sentence's terms raises its coverage bar.** Adding a term makes every covering step carry it too, so editing a story can silently uncover a scenario that used to cover it (a pinned step is immune).

**Verify coverage after touching a sentence or a covering step** — from the JSON report, not by re-deriving the rule:

```bash
pytest <selection> --given-json=report.json
# tracked sentences no scenario covers, as story#sentence
jq -r '.coverage[] | select(.tracked and .scenario_ids == [])
       | .story_id + "#" + (.sentence_id|tostring)' report.json
```

`coverage[]` holds `{story_id, sentence_id, tracked, scenario_ids}` per sentence, computed by the same code as the Stories tab; `tracked: false` is the "not coverage-tracked" chip. The full shape is in the navigating skill's `references/report-json.md`.

A step can also **pin** a sentence explicitly — `given(text, pins=book_a_group_trip['confirm'])`, taking a sentence handle (or a list of them). A pin *replaces* narration matching for that step rather than adding to it: the step covers exactly the sentences it names, in any story, however well its text fits others; `pins=[]` opts a step out of matching without pinning anything. A pin is also the only thing that reaches an under-anchored sentence: the two-term rule gates narration matching, not pins. Use a pin when the sentence is phrased above the vocabulary the step narrates (e.g. a process-level sentence implemented by a technical test), and keep it on the one step that genuinely demonstrates the sentence. `@scenario(pins=...)` pins the whole scenario: it covers those sentences plus its steps' pins, and none of its steps is narration-matched; `@scenario(pins=[])` keeps only the steps' pins.

**Pin by name, not by number.** Sentence numbers are positions, so inserting a row renumbers every row after it, and `the_story[5]` silently lands on a different sentence. Name a sentence you pin (`sentence(..., name='confirm')`) and pin `the_story['confirm']`.

An uncovered sentence is a signal, not an error — it marks vocabulary and behavior no test exercises yet.

## When a story earns its keep

Write a story for flows with distinguishable actors and hand-offs — a user and a system, two roles, a pipeline of responsibilities. Single-function units don't need one; scenarios alone are the right level there. A story that would read "the function is called with X" is a scenario wearing a costume.

## Authoring workflow

- **Keep sentences at domain granularity** — what the actor does ("submits payment for the booking"), never what the code does ("calls `submit_payment()`"). If a sentence only makes sense to someone reading the implementation, it's too fine.
- **Grow the glossary from the sentences — but only with real vocabulary.** A slot gets a term when the word is domain language someone would look up; a word that is just sentence prose (generic verbs like *tells*, *reviews*) stays a bare string. Don't mint glossary rows to satisfy the grammar. With a file glossary and no kind column, term kinds are inferred from slot positions for free (see [glossaries.md](glossaries.md)); unclassified vocabulary can enter as `g('loyalty points')` and be triaged later.
- **Derive stories from Domain Storytelling sessions** where you can: transfer the sentences recorded with stakeholders into `sentence(...)` rows, then write scenarios against them — see [domain-storytelling.md](domain-storytelling.md).
