# Activity Pins — Design Spec

## Goal

Make a pin say which activity it means in a way that survives the story being edited, and let a
scenario bind to more than one story:

```python
book_a_room = story('Book a room', [
    activity(guest, 'searches for', room),
    activity(guest, 'cancels', booking, name='cancel'),
])

@scenario('Carol cancels', activities=book_a_room['cancel'])
def test_cancel(): ...

@scenario('Carol pays and gets a receipt', stories=[book_a_room, checkout])
def test_pay():
    with when(t'{guest} pays for the {booking}', activities=checkout['pay']):
        ...
```

- An activity may have a **name**, which stays stable when rows are inserted, unlike its number.
- A pin is written with an **activity handle**, `the_story['name']` or `the_story[3]`, which
  carries its story. Steps and scenarios both take it as `activities=`.
- A scenario pin replaces narration matching for its story instead of capping what matching finds.
  A scenario can bind to several stories, and the rule applies to each separately.

## Background

`ActivityId` is `NewType('ActivityId', int)`. `story()` numbers rows 1..N in list order, and
`activity(..., activity_id=12)` sets an explicit number (0 is the unset sentinel). The number is
both what the report displays (the timeline bubble, the `Activity 3: …` chip) and what everything
refers to an activity by (`given(..., activity=3)`, `@scenario(activities=[2, 3])`,
`coverage[].activity_id`, `steps[].activity_ids`).

The problems:

- **Pins drift.** Numbers are positional, so inserting a row silently re-targets every pin after
  it. The authoring skill documents this trap, with explicit numbering as the workaround.
- **Scenario `activities=` is hard to explain.** It is an intersection: narration matching still
  runs, and anything found outside the listed ids is dropped (`report/coverage.py`). It neither
  guarantees the listed ids are covered nor stops matching. The reviewing skill paraphrases it as
  "can cover no others", which is only half of it.
- **Grafted pins re-target.** A scenario binds to at most one story (`Scenario.story_id`), and a
  bare-int pin means "row N of the scenario's story". A wider-scoped `@given` fixture records once,
  while the first scenario that uses it is active; `_check_step_activity_scope` checks its pins
  against that scenario only. `graft_recording` then copies the steps into later scenarios
  unchecked, where `activity=3` points at row 3 of whatever story they bind.

## Design

### Number and name

- `id: ActivityId` stays an int but is always the row's 1-based position, assigned by `story()` and
  never settable. So it is always contiguous, which is how a Domain Storytelling diagram numbers its
  arrows.
- `name: ActivityName | None` is new, set by `activity(*parts, name=None)`.
  - `ActivityName` is a `NewType('ActivityName', str)` beside `ActivityId` in `model/schema.py`.
  - A name must be non-empty, free of leading and trailing whitespace, and unique within its story.
  - It is a lookup key only, never a report key, HTML id or hash parameter, so it needs no slug
    alphabet.
  - Messages and the timeline quote names (`'cancel'`) and leave numbers bare, so a row named `'3'`
    never reads as row 3.

`activity_id=` is removed, and with it the 0 sentinel, the skip-taken-numbers rule in
`_assign_sequence_numbers`, and `_check_unique_ids`, which can no longer fail. Its one job, keeping
pins stable across an inserted row, is what a name does better.

Why `name=`: a glossary term's name is also the string its author picks and lookups go through.
`g['Guest']` finds a term by name, and `book_a_room['cancel']` finds an activity by name.

### Activity handles

A story hands out **activity handles** to its rows, the way a glossary hands out term handles:

- `book_a_room['cancel']` looks a row up by name, `book_a_room[3]` by number. Both return an
  `ActivityHandle`.
- A miss raises `PytestGivenError` where the expression is evaluated: at import for `@scenario` and
  decorator-form steps, when the line runs for a `with` step. Either way the traceback points at
  the line that wrote the pin. The message lists the story's rows (`1`, `2 'search'`, …).
- A number is a row number, not a list index: `0`, a negative number and a `bool` raise.

Recording converts a handle into what the report stores, as it does for terms:

| author writes | recorded as | model type |
|---|---|---|
| term handle, in narration | term ref | `NarrationTermRef` |
| activity handle, in `activities=` | pin | `ActivityPin` |

- `ActivityPin` is a frozen `{story_id, activity_id}` in `model/schema.py`.
- `ActivityHandle` lives on the capture side. It holds its pin plus the live `Story`, so
  `@scenario` can register a story it reaches only through a pin, and `model/` stays the leaf.
- `__getitem__` lives on the capture-side story subclass that `story()` already returns, and
  `story()`'s return annotation names that subclass so type checkers see the lookup.

A step and `@scenario` both take `activities=`, as `ActivityHandle | Sequence[ActivityHandle]`: the
plural keyword accepts one handle or several, as `stories=` and `tags=` do. Step `activity=` goes.
Bare ints and strings are rejected with a message showing the handle form. Capture therefore never
resolves a number or name against "the scenario's story".

"Pin" becomes a glossary term, so the internal glossary carrier in `capture/story.py` (`_Pinned`,
`pinned_glossaries`) is renamed, e.g. to `_GlossaryCarrier` / `carried_glossaries`.

### The stories a scenario binds to

`@scenario(story=)` becomes `stories=`, taking `Story | Sequence[Story]`. The two arguments bind in
opposite ways:

- `stories=` lists the stories the scenario is **narration-matched** against. Step pins may point
  only into these.
- `activities=` lists the rows the scenario **pins**. Each pin binds its story, and no matching
  runs against that story.

A story named by both raises at decoration time: the two arguments ask for opposite things. A
scenario's stories are the `stories=` list followed by the pinned stories, in order of first
appearance.

`Scenario.story_id` becomes `story_ids: tuple[StoryId, ...]`. `Scenario.activity_ids` and
`Step.activity_ids` become `pins: tuple[ActivityPin, ...]`. `start_scenario` registers every story
the scenario binds, since stories still reach the report only through a scenario.

### Pins and coverage

A pin replaces narration matching **for the story it names**: a step pin for its step, a scenario
pin for the whole scenario. For each story S the scenario binds:

| scenario pins into S | step pins into S | coverage in S |
|---|---|---|
| none | none | narration matching on every step |
| none | some | pinned steps contribute their pins; the rest are matched |
| some | none | exactly the scenario's pins into S |
| some | some | error |

"The rest" includes steps pinned into another story, since a pin into T says nothing about S. As
today, a pin reaches under-anchored activities.

A scenario pin is an assertion that no narration backs. It covers its activities even when the test
fails early or is skipped (the rollup shows the scenario's status beside the chip). The docs say
so, and the reviewing skill checks that the body exercises each pinned activity.

`compute_coverage` returns a scenario's pins into S early, without matching. Pins of both forms are
intersected with the story's ids, the one part of today's `scope` intersection that survives: a
report replayed through `pytest-given report` is deserialized unvalidated, and a stale pin must not
put a `Covers:` chip on a row that no longer exists. `CoverageMap` becomes
`dict[NodeId, dict[StoryId, set[ActivityId]]]`. `build_coverage_map` and `build_story_rollups`
iterate over every story a scenario binds.

### Where pins are checked

A handle is checked where it is written. What remains is whether a pin fits the scenario it lands
in: the pin's story must be one the scenario binds, and not one it pins. That check runs everywhere
a step enters a scenario:

- `push_step`, replacing `_check_step_activity_scope`. Its error for a pin recorded outside any
  scenario stays.
- `graft_recording`, over the whole grafted subtree, so a wider-scoped fixture's recording fails
  loudly in a scenario it doesn't fit instead of re-targeting.

The error for a step pin into an unbound story names the story and suggests `stories=`.

`Annotated[..., given('label', activity=...)]` is accepted today, and the pin is silently dropped:
`_graft_annotated_leaves` passes only the narration on. `annotated_given_descriptors` now rejects a
descriptor that carries `activities=`.

Parametrize grouping compares pins where it compared ids (`StepSignature`); rule 6 is unchanged.

### Report

JSON:

- `stories[].activities[]` becomes `{id, name, paths}`, with `name: null` when unnamed.
- `scenarios[].story_id` becomes `story_ids`.
- `activity_ids` on scenarios and steps becomes `pins: [{story_id, activity_id}]`.
- `coverage[]` keeps its shape, since it was already story-qualified.

Serde reads the new fields back, `name` with `.get` like its optional neighbours. It does not read
the old field names, so a report saved before this change replays without its story bindings.

HTML:

- The timeline bubble keeps the number. A named row shows its name as a small muted tag beside it,
  so an author can read the name off the timeline.
- A scenario that binds several stories is listed under each of them, with the `Covers:` chips for
  that story.
- In the app data, `scenarios[].story_id` becomes `story_ids`, and `scenario_activities` becomes
  `{node_id: {story_id: [ids]}}`.
- The template reads `scn_covers[scn.id][story.id]`. The `app.js` activity filter checks
  `s.story_ids.includes(storyId)` and reads the ids under that story.
- `highlightedActivities`, the `story:id` activity key and the activity chip are unchanged, because
  they already live inside one selected story.

Verified by Playwright only.

### Changelog

Each break gets a `**Breaking.**` entry with its migration:

- `activity(..., activity_id=N)` is removed: rows are numbered by position, so name the row
  (`name=`) and pin it by name.
- Pins take activity handles under `activities=` on steps too: `given(..., activity=3)` becomes
  `given(..., activities=the_story[3])`, and `@scenario(activities=[2, 3])` becomes
  `activities=[the_story[2], the_story[3]]`, or `the_story['name']` for a named row.
- `@scenario(story=)` is now `stories=` and takes one story or several; a scenario pin binds its
  story without it.
- `@scenario(activities=)` covers exactly the pinned activities, with no narration matching
  against their story; a step pin into such a story raises.
- In the JSON report, `scenarios[].story_id` is now `story_ids`, and `activity_ids` on scenarios
  and steps is now `pins`.

Under **Added**: activity names shown on the timeline, and scenarios that bind several stories.
Under **Fixed**: an `Annotated` `given(...)` label carrying a pin raises instead of dropping it.

### Docs, skills and glossary

- `GLOSSARY.md`:
  - *Handle* covers both term handles (`g['Guest']`) and activity handles
    (`book_a_room['cancel']`).
  - A new **Pin** row: what an activity handle in `activities=` is recorded as, as a term handle is
    recorded as a term ref. A pin binds explicitly and replaces narration matching for its story.
  - The *Activity* row gains number and name. *Scenario↔activity binding* becomes `stories=` plus
    pins. *Coverage* refers to *Pin*.
- Site guide:
  - `domain-storytelling.md`: handles, names, multi-story binding, the pin table, and unbacked
    scenario pins.
  - `scenarios.md`: the signature. Its "never a string" remark goes.
  - `parametrized.md`: rule 6's `activity=` becomes `activities=`.
- Authoring skill:
  - `api.md`: the signatures, and the retired `activity_id=`.
  - `stories.md`: stories reach the report through `stories=` or a pin, the step pin example
    becomes a handle, and the renumbering-trap paragraph points at names.
  - `domain-storytelling.md`: its `story=` binding becomes `stories=`.
- Reviewing skill:
  - `story-coverage.md`: the per-story rule, and the check that each scenario pin is exercised.
  - `pairs.md`: its Python block moves from `story_id` to `story_ids` (`test_skills_scripts.py` runs
    it).
- Navigating skill:
  - `SKILL.md`: `story=` becomes `stories=`, and the by-story `jq` selector becomes
    `select(.story_ids | index("…"))`.
  - `report-json.md`: the changed fields and their `jq` examples.
- Regenerate the `.claude/skills/` mirror with `uv run pytest-given skills install`, since the sync
  test compares it against the source skills.

### Self-report and examples

- **Dogfood story.** `tests/ubiquitous_language.py` names every row of `adopt_pytest_given`, and its
  ~30 `activity=N` pins become `activities=adopt_pytest_given['…']`, behind a short alias if needed.
  This story has the most pins an inserted row would re-target, so it shows the fix best.
- **New scenarios, one per rule:**
  - a handle resolves a name and a number, and a miss raises at its line;
  - a duplicate, empty or padded name is rejected;
  - a scenario pin covers exactly its activities, including an under-anchored one;
  - a story in both `stories=` and `activities=` raises;
  - a step pin into a pinned story raises;
  - a step pin into an unbound story raises;
  - a wider-scoped fixture's pin raises when grafted into a scenario it doesn't fit;
  - a scenario matched against two stories;
  - an Annotated label with a pin is rejected.
- **Changed scenarios:**
  - the `activity_id=0` scenario in `test_story.py` goes;
  - "A string `activities=` argument is refused" (`test_step_descriptor.py`) becomes the refusal of
    bare ints and strings;
  - the scope tests in `test_plugin.py` (scenario `activities=` combined with step pins) become the
    new error cases.
- **Examples.** `hotel-booking` and `file-glossary-booking` move to `stories=`. `hotel-booking` gains a named, pinned
  activity and a scenario bound to two stories.

## Considered and rejected

- **Bare `int` / `str` pins beside handles.** They need "the scenario's story" to resolve against,
  which a multi-story scenario lacks. They also keep resolution at capture, where the graft went
  wrong.
- **Pinning by the `Activity` object.** `story()` rebuilds rows to number them, so a row bound to a
  variable before `story()` is not the row in the story. It would also force every pinned row out
  of the story's inline list.
- **Inferring a step pin's story into the scenario's binding.** A scenario's stories would then
  depend on which steps ran.
- **"Claim" for the scenario form.** It only contrasted with the old cap. Now both forms do one
  thing at two scopes, so one term, *Pin*, covers them.
- **"Activity ref" instead of "pin".**
  - The glossary row would stay, since it still has to say that the binding replaces matching.
  - `ActivityRef` would sit next to `ActivityTermRef` with the opposite meaning.
  - Matching is itself a step's term refs reaching an activity, so "ref" would blur the difference
    between pinned and matched coverage.
- **`pins=` as the keyword.** `activities=` names what is passed, so a newcomer needs no glossary to
  read it.

## Forward notes

- **A lint rule for unbacked scenario pins**: a pinned activity whose terms no step mentions. It
  would be the mechanical counterpart of the reviewing check. Only worth building if that check
  keeps finding such pins.
- **Story diagrams** (unmerged branch) take the arrow number from `int(activity.id)`, which keeps
  working.
