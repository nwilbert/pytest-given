# Named Activities and Scenario Claims — Design Spec

## Goal

Let an activity carry an optional, stable name, so a pin survives a story being edited:

```python
activity(guest, 'cancels', booking, name='cancel')
...
with when(t'{guest} cancels the {booking}', activity='cancel'):
```

Alongside it, tighten what a scenario-level pin means: `@scenario(activities=[...])` becomes a
*claim* — the scenario covers exactly those activities — rather than a cap on what narration
matching may find.

## Background

`ActivityId` is `NewType('ActivityId', int)`. `story()` numbers unnumbered rows 1..N in list order,
and `activity(..., activity_id=12)` pins an explicit number (0 is the unset sentinel). The number
is both the display (timeline bubble, `Activity 3: …` chip, `story#3` in jq) and the handle (`given(...,
activity=3)`, `@scenario(activities=[2, 3])`, `coverage[].activity_id`, `steps[].activity_ids`).

Numbers are positional, so inserting a row silently re-targets every pin after it — documented as a
trap in the authoring skill, with explicit numbering as the workaround. A name is the better fix: it
says what the pin means, and it cannot shift.

Scenario-level `activities=` is today an intersection: narration matching still runs on unpinned
steps, and anything it finds outside the listed ids is dropped (`report/coverage.py`). It neither
guarantees the listed ids are covered nor stops matching. That is hard to explain and hard to
review; the reviewing skill already paraphrases it as "scoped to those activities and can cover no
others", which is only half of it.

## Design

### Number and name

An activity has two fields where it had one:

- `id: ActivityId` — unchanged in type (an int) and in every place the report references an
  activity, but now always the row's 1-based position in the story, assigned by `story()` from list
  order and never settable. Always contiguous, which is what a Domain Storytelling diagram numbers
  its arrows with.
- `name: ActivityName | None` — optional, given as `activity(*parts, name: str | None = None)`;
  `None` for a row that is not named, which is every existing story. `ActivityName` is a
  `NewType('ActivityName', str)` beside `ActivityId`, `TermId` and `StoryId` in `model/schema.py`, so
  a name and a bare step string can never be confused in a signature. Non-empty (whitespace-only
  rejected) and unique within its story (`story()` raises on a duplicate name as it does on a
  duplicate id today). Nothing else is restricted, as for a tag or an attachment label: the name is
  a label and a lookup key at capture time, never a report key, an HTML id or a hash parameter, so
  it needs no slug alphabet. Error messages and the timeline tag quote names (`'cancel'`) and leave
  numbers bare, so even a name like `'3'` never reads as row 3.

Explicit int numbering (`activity_id=12`) goes away, and with it the 0 sentinel and the
skip-taken-numbers rule in `_assign_sequence_numbers`. Its one job — keeping pins stable when a row
is inserted mid-story — is what the name does better.

### Pins

`activity=` on a step and `activities=` on `@scenario` accept `int | str | Sequence[int | str]`: an
int names a row by number, a str by name, and a sequence may mix them. A bare str is a single name
(today it is rejected as a would-be sequence). `bool` is still excluded from the int branch.

Pins resolve to numbers where the story is in hand, at the same two sites that validate them today:
`_validate_story_binding` at decoration time for the scenario form, `_check_step_activity_scope`
at capture time for the step form. A number not in the story or a name no activity carries raises
there, listing the story's rows as `number` / `'name'` pairs. After resolution `Scenario.activity_ids`
and `Step.activity_ids` hold ids (numbers) only, so `coverage.py`, `story_view.py` and the frontend
never see a name.

A scenario binds to exactly one story via `story=`, and both pin forms require it: `activities=`
without `story=` keeps raising at decoration time, a step pin in a scenario without a story at
capture time. Inferring "the only story in scope" was considered and rejected — it needs a scope
that does not exist, and a second story anywhere would break claims that never mentioned it.

### Claim, not cap

| `@scenario(activities=)` | step `activity=` | coverage |
|---|---|---|
| absent | absent | narration matching on every step |
| absent | on some steps | pinned steps contribute their ids; the rest are matched |
| present | absent | exactly the claimed ids |
| present | present | error at capture time |

A claim skips narration matching for the scenario entirely and, like a step pin, reaches
under-anchored activities. A step pin inside a claiming scenario is rejected by
`_check_step_activity_scope` when the step runs — the two forms would be either redundant or
contradictory, so a scenario is visibly one or the other. `compute_coverage` returns the claim
early, still intersected with the story's ids: a report replayed through `pytest-given report`
is deserialized unvalidated, and a stale claim must not render a `Covers:` chip at a row that no
longer exists. The scope intersection over matched steps and the "outside scenario scope" error go
away.

### Report

JSON: `stories[].activities[]` becomes `{id, name, paths}` with `name: null` when unnamed. Every
other activity reference — `scenarios[].activity_ids`, `steps[].activity_ids`,
`coverage[].activity_id` — keeps carrying the int id as today. Serde reads `name` back onto the
activity; nothing else changes shape.

HTML: the timeline bubble keeps the number; a named row shows its name as a small muted tag beside
the bubble, so a reviewer writing a pin can read the handle off the timeline. The `Activity 3: …`
filter chip, the `story:id` activity key, `highlightedActivities` and `app.js` are untouched.
Verified by Playwright only, no markup-pinning tests.

### Docs and skills

- `docs/site/guide/domain-storytelling.md`: the pin forms, the claim semantics.
- Authoring skill `references/stories.md`: the renumbering-trap paragraph now points at a name as
  the fix; `references/api.md` for the widened signatures and the retired `activity_id=N`.
- Reviewing skill `references/story-coverage.md`: a claiming scenario covers what it claims and
  nothing is matched for it.
- Navigating skill `references/report-json.md`: the activity's `id` / `name` pair.
- `GLOSSARY.md`: the *Coverage* and *Scenario↔activity binding* rows describe the cap; they get the
  claim, and the two pin forms.
- `examples/hotel-booking`: one activity named and pinned by name, so a rendered example shows it.

## Non-goals and forward notes

- **Multi-story claims.** `activities=[...]` reads as shorthand for `{story: [...]}` with the one
  story from `story=`. A later `dict[Story, list[int | str]]` form widens `Scenario.story_id` /
  `Scenario.activity_ids`; the coverage side (`coverage[]` rows, `story:id` keys in the HTML) is
  already story-qualified and would not move. Not built until a consumer needs it.
- **Story diagrams** (unmerged branch) take the arrow number from `int(activity.id)`, which keeps
  working: the id is the row number for every row.
