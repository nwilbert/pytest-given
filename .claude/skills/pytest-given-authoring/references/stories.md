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

- An activity reads left-to-right: **actor → verb → work object**, with optional connective words (`'for'`, `'to'`) between parts.
- Handles come from the glossary; calling one supplies an instance or inflection — `organizer('Carol')`, `search('searches for')`.
- Any part may be a **bare string** instead of a glossary handle — but an activity needs at least two distinct glossary terms to be coverage-tracked; under-anchored activities render as "not coverage-tracked".
- `path(...)` branches an activity where alternate sequences run in parallel or share a prefix:

```python
activity(
    path(organizer('Carol'), add('adds'), guest('Alice'), 'to', booking),
    path(organizer('Carol'), add('adds'), guest('Bob'), 'to', booking),
),
```

## Binding scenarios to a story

```python
@scenario('Carol selects a suite', story=book_a_group_trip)
def test_select_suite(carol):
    with when(t'{organizer("Carol")} {select("selects")} a {room}'):
        ...
```

Each step's term references are matched against the story's activities to compute coverage; the Stories tab shows a coverage chip per activity with the scenarios that touch it. A step can also bind to a specific activity explicitly: `given(text, activity=...)`.

An uncovered activity is a signal, not an error — it marks vocabulary and behaviour no test exercises yet.

## When a story earns its keep

Write a story for flows with distinguishable actors and hand-offs — a user and a system, two roles, a pipeline of responsibilities. Single-function units don't need one; scenarios alone are the right level there. A story that would read "the function is called with X" is a scenario wearing a costume.

## Authoring workflow

- **Keep activities at domain granularity** — what the actor does ("submits payment for the booking"), never what the code does ("calls `submit_payment()`"). If an activity only makes sense to someone reading the implementation, it's too fine.
- **Grow the glossary from the activities.** Every slot wants a term; with a file glossary and no kind column, kinds are inferred from slot positions for free (see [glossaries.md](glossaries.md)). Unclassified vocabulary can enter as `g('loyalty points')` and be triaged later.
- **Derive stories from Domain Storytelling sessions** where you can: transfer the sentences recorded with stakeholders into `activity(...)` rows, then write scenarios against them — see [domain-storytelling.md](domain-storytelling.md).
