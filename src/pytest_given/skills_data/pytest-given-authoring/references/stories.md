# Authoring stories

A domain story models a flow as a sequence of activities — who does what with what — at the actor level, above individual scenarios. The report's Stories tab renders each story as a timeline with per-activity coverage computed from the scenarios that implement it. (For the method behind the feature, see [domain-storytelling.md](domain-storytelling.md).)

## What a story is

```python
from pytest_given import activity, path, story

book_a_group_trip = story('Book a Group Trip', [
    activity(organizer('Carol'), search('searches for'), room),
    activity(organizer('Carol'), select('selects'), room('Deluxe Suite')),
    activity(organizer('Carol'), submit('submits'), payment, 'for', booking),
])
```

- An activity reads left-to-right: **actor → verb → work object**, with optional connective words (`'for'`, `'to'`) between parts. Structurally it is a strict node/edge alternation of odd length ≥ 3: even positions are entity nodes (position 0 is the acting actor), odd positions are edges (a verb or a connective).
- **A bare word consumes a position.** Write a connective as one string in an edge slot (`'to the'`, `'with a'`); never insert a standalone article before a noun — it shifts the noun into a verb slot and construction fails.
- Handles come from the glossary; calling one supplies an instance or inflection — `organizer('Carol')`, `search('searches for')`.
- Any part may be a **bare string** instead of a glossary handle — but an activity needs at least two distinct glossary terms to be matched by narration; under-anchored activities render as "not coverage-tracked" unless a step pins them (below).
- `path(...)` branches an activity where alternate sequences run in parallel or share a prefix:

```python
activity(
    path(organizer('Carol'), add('adds'), guest('Alice'), 'to', booking),
    path(organizer('Carol'), add('adds'), guest('Bob'), 'to', booking),
),
```

**A branched activity is expensive to cover.** Coverage unions the term refs of *all* paths, so covering it takes one step referencing every term in every branch — past two near-identical branches that step stops being writable and the activity is effectively uncoverable. Branch with `path(...)` only for strands you accept as uncovered; otherwise split them into separate activities, or pin a covering step (below).

## Binding scenarios to a story

**A story reaches the report only through `@scenario(story=...)`.** Stories are discovered from the scenarios that bind them, so a defined-but-unbound story never appears however complete it is — an empty Stories tab means no scenario names it, not a broken definition.

```python
@scenario('Carol selects a suite', story=book_a_group_trip)
def test_select_suite(carol):
    with when(t'{organizer("Carol")} {select("selects")} a {room}'):
        ...
```

Coverage is matched **per step**: an activity is covered when a *single step's* term references include all of the activity's terms (an instance also counts for its canonical term) — references spread across several steps don't add up. The Stories tab shows a coverage chip per activity with the scenarios that touch it.

Two corollaries of "per step":

- **Only step narration counts.** Term refs in the `@scenario` name never contribute. A scenario titled with both actors stays uncovered until those refs also appear in a `given`/`when`/`then`.
- **Growing an activity's terms raises its coverage bar.** Adding a term — or narrowing one to an instance (`room` → `room('Deluxe Suite')`) — makes every covering step carry the new identity too, so editing a story can silently uncover a scenario that used to cover it (a pinned step is immune). Re-render the Stories tab after touching an activity.

A step can also **pin** an activity explicitly — `given(text, activity=3)`, taking the 1-based activity number in the story (or a sequence of numbers). A pin *replaces* narration matching for that step rather than adding to it: the step covers exactly the activities it names and no others, however well its text fits them. A pin is also the only thing that reaches an under-anchored activity: the two-term rule gates narration matching, not pins. Use a pin when the activity is phrased above the vocabulary the step narrates (e.g. a process-level activity implemented by a technical test), and keep it on the one step that genuinely demonstrates the activity.

**Activity numbers are positional, so inserting a row renumbers the pins after it.** `story(...)` assigns ids 1..N in list order, and a pin stores the number rather than the activity — insert in the middle and every `activity=N` past the insertion keeps its number while landing on a different activity, silently, with no error and no lint finding. Append where the flow allows it; otherwise number the new row explicitly (`activity(guest, 'cancels', booking, activity_id=12)` — auto-numbering skips ids already taken, so the two forms mix) and re-read the pins you would have shifted.

An uncovered activity is a signal, not an error — it marks vocabulary and behavior no test exercises yet.

## When a story earns its keep

Write a story for flows with distinguishable actors and hand-offs — a user and a system, two roles, a pipeline of responsibilities. Single-function units don't need one; scenarios alone are the right level there. A story that would read "the function is called with X" is a scenario wearing a costume.

## Authoring workflow

- **Keep activities at domain granularity** — what the actor does ("submits payment for the booking"), never what the code does ("calls `submit_payment()`"). If an activity only makes sense to someone reading the implementation, it's too fine.
- **Grow the glossary from the activities — but only with real vocabulary.** A slot gets a term when the word is domain language someone would look up; a word that is just sentence prose (generic verbs like *tells*, *reviews*) stays a bare string. Don't mint glossary rows to satisfy the grammar. With a file glossary and no kind column, term kinds are inferred from slot positions for free (see [glossaries.md](glossaries.md)); unclassified vocabulary can enter as `g('loyalty points')` and be triaged later.
- **Derive stories from Domain Storytelling sessions** where you can: transfer the sentences recorded with stakeholders into `activity(...)` rows, then write scenarios against them — see [domain-storytelling.md](domain-storytelling.md).
