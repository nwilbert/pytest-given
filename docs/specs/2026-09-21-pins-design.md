# Pins — Design Spec

## Goal

Make a pin say which sentence it means in a way that survives the story being edited, and let a
scenario bind to more than one story:

```python
book_a_room = story('Book a room', [
    sentence(guest, 'searches for', room),
    sentence(guest, 'cancels', booking, name='cancel'),
])

@scenario('Carol cancels', pins=book_a_room['cancel'])
def test_cancel(): ...

@scenario('Carol pays and gets a receipt', stories=[book_a_room, checkout])
def test_pay():
    with when(t'{guest} pays for the {booking}', pins=checkout['pay']):
        ...
```

- A sentence may have a **name**, which stays stable when sentences are inserted, unlike its number.
- A pin is written with a **sentence handle**, `the_story['name']` or `the_story[3]`, which
  carries its story. Steps and scenarios both take it as `pins=`.
- `stories=` says where narration matching looks. A pin, on a step or a scenario, replaces
  narration matching there; `pins=[]` opts out of it without pinning anything.
- Every story a run declares reaches the report, whether or not a scenario covers it.

This spec is written against the vocabulary of the
[sentences and clauses spec](2026-09-26-sentences-and-clauses-design.md), which lands first. That
spec leaves the pin arguments under their old names for this one to replace.

## Background

`SentenceId` is `NewType('SentenceId', int)`. `story()` numbers sentences 1..N in list order, and
`sentence(..., activity_id=12)` sets an explicit number (0 is the unset sentinel). The number is
both what the report displays (the timeline bubble, the `Sentence 3: …` chip) and what everything
refers to a sentence by (`given(..., activity=3)`, `@scenario(activities=[2, 3])`,
`coverage[].sentence_id`, `steps[].activity_ids`).

The problems:

- **Pins drift.** Numbers are positional, so inserting a sentence silently re-targets every pin
  after it. The authoring skill documents this trap, with explicit numbering as the workaround.
- **Scenario `activities=` is hard to explain.** It is an intersection: narration matching still
  runs, and anything found outside the listed ids is dropped (`report/coverage.py`). It neither
  guarantees the listed ids are covered nor stops matching. The reviewing skill paraphrases it as
  "can cover no others", which is only half of it.
- **Grafted pins re-target.** A scenario binds to at most one story (`Scenario.story_id`), and a
  bare-int pin means "sentence N of the scenario's story". A wider-scoped `@given` fixture records
  once, while the first scenario that uses it is active; `_check_step_activity_scope` checks its
  pins against that scenario only. `graft_recording` then copies the steps into later scenarios
  unchecked, where `activity=3` points at sentence 3 of whatever story they bind.

## Design

### Number and name

- `id: SentenceId` stays an int but is always the sentence's 1-based position, assigned by
  `story()` and never settable. So it is always contiguous, which is how a Domain Storytelling
  diagram numbers its sentences.
- `name: SentenceName | None` is new, set by `sentence(*parts, name=None)`.
  - `SentenceName` is a `NewType('SentenceName', str)` beside `SentenceId` in `model/schema.py`.
  - A name must be non-empty, free of leading and trailing whitespace, and unique within its story.
  - It is a lookup key only, never a report key, HTML id or hash parameter, so it needs no slug
    alphabet.
  - Messages quote names (`'cancel'`) and leave numbers bare, so a sentence named `'3'` never
    reads as sentence 3.

`activity_id=` is removed, and with it the 0 sentinel, the skip-taken-numbers rule in
`_assign_sequence_numbers`, and `_check_unique_ids`, which can no longer fail. Its one job, keeping
pins stable across an inserted sentence, is what a name does better.

Why `name=`: a glossary term's name is also the string its author picks and lookups go through.
`g['Guest']` finds a term by name, and `book_a_room['cancel']` finds a sentence by name.

### Sentence handles

A story hands out **sentence handles** to its sentences, the way a glossary hands out term handles:

- `book_a_room['cancel']` looks a sentence up by name, `book_a_room[3]` by number. Both return a
  `SentenceHandle`.
- A miss raises `PytestGivenError` where the expression is evaluated: at import for `@scenario` and
  decorator-form steps, when the line runs for a `with` step. Either way the traceback points at
  the line that wrote the pin. The message lists the story's sentences (`1`, `2 'search'`, …).
- A number is a sentence number, not a list index: `0`, a negative number and a `bool` raise.
- Iterating a story yields its sentence handles in order, so `list(the_story)` and
  `for handle in the_story` work instead of falling back to `__getitem__(0)`.

Recording converts a handle into what the report stores, as it does for terms:

| author writes | recorded as | model type |
|---|---|---|
| term handle, in narration | term ref | `NarrationTermRef` |
| sentence handle, in `pins=` | pin | `Pin` |

- `Pin` is a frozen `{story_id, sentence_id}` in `model/schema.py`.
- `SentenceHandle` lives on the capture side and holds its pin; `model/` stays the leaf.
- `__getitem__` and `__iter__` live on the capture-side story subclass that `story()` already
  returns, and `story()`'s return annotation names that subclass so type checkers see the lookup.

A step and `@scenario` both take `pins=`, as `SentenceHandle | Sequence[SentenceHandle] | None`:
the plural keyword accepts one handle or several, as `stories=` and `tags=` do. Step `activity=`
and scenario `activities=` go. Bare ints and strings are rejected with a message showing the handle
form. Capture therefore never resolves a number or name against "the scenario's story".

Why `pins=`:

- The keyword, the glossary term, the model fields and the JSON field are one word.
- It names the mechanism. Coverage is the result, and narration matching produces it too, so a
  pin keyword should say how the scenario binds, not what the report shows.
- It carries the override. Pinning a dependency version means choosing it instead of letting a
  resolver pick; pinning a sentence means choosing it instead of letting narration matching find
  it.

"Pin" becomes a glossary term, so the internal glossary carrier in `capture/story.py` (`_Pinned`,
`pinned_glossaries`) is renamed to `_GlossaryCarrier` / `carried_glossaries`.

### Stories in the report

`story()` registers the story it builds, after its checks pass, in the process-wide story
registry, which keeps the `Story` itself rather than only its declaration site. The report's
`stories` are every registered story, in declaration order, so a story no scenario covers still
shows, with no coverage on any sentence. The registry is swapped around a nested in-process run as
it is today.

`resolve_glossary` reads its glossaries off every registered story, so the one-glossary rule holds
across the suite rather than across the bound stories. The `dead-term` lint rule reads the same
list, so a term that only an uncovered story uses is not reported as dead.

### Binding and coverage

`@scenario(story=)` becomes `stories=`, taking `Story | Sequence[Story] | None`. There are three
levels, each more specific than the one before: `stories=`, the scenario's `pins=`, a step's
`pins=`.

- `stories=` lists the stories the scenario is **narration-matched** against. `[]` and `None` mean
  the same: no story.
- A `pins=` of `None` (or omitted) leaves the level above in charge. Any list, `[]` included, means
  "exactly these, and no narration matching":
  - a **step** pin: the step covers exactly its pins, in whatever stories they name, and is not
    matched against any story;
  - a **scenario** pin: the scenario covers its pins, and none of its steps is narration-matched
    against any story. `stories=` then only lists the scenario under those stories.

| scenario `pins=` | step `pins=` | the step contributes |
|---|---|---|
| `None` | `None` | its narration matches, in the `stories=` stories |
| `None` | a list | exactly its pins |
| a list | `None` | nothing |
| a list | a list | exactly its pins |

A scenario covers its own pins plus what its steps contribute. As today, a pin reaches
under-anchored sentences, and a pin into any registered story counts, whether or not the scenario
names that story in `stories=`.

A scenario pin is an assertion that no narration backs. It covers its sentences even when the test
fails early or is skipped (the rollup shows the scenario's status beside the chip). The docs say
so, and the reviewing skill checks that the body exercises each pinned sentence.

`Scenario.story_id` becomes `story_ids: tuple[StoryId, ...]`, the `stories=` list in order, without
duplicates.
`Scenario.activity_ids` and `Step.activity_ids` become `pins: tuple[Pin, ...] | None`, `None` when
`pins=` was not given.

A scenario is listed under each story in `stories=`, even where nothing matched, and under every
story it covers a sentence of. `CoverageMap` becomes
`dict[NodeId, dict[StoryId, set[SentenceId]]]`, holding exactly those stories.

Every pin is intersected with its story's ids: a report replayed through `pytest-given report` is
deserialized unvalidated, and a stale pin must not put a `Covers:` chip on a sentence that no
longer exists.

### Grafting and Annotated labels

A handle is checked where it is written, and a pin names its story, which is always in the report.
So nothing is left to check where a pin lands. `_check_step_activity_scope` goes without a
replacement, and so does its error for a pin recorded outside any scenario: a wider-scoped fixture
first set up by an unannotated test records its pins, and they count in each scenario it is
grafted into. A graft cannot re-target, because the pin says which story it means. Grafted steps
are ordinary steps of the scenario they land in, so an unpinned one is narration-matched against
that scenario's own `stories=`.

`Annotated[..., given('label', activity=...)]` is accepted today, and the pin is silently dropped:
`_graft_annotated_leaves` passes only the narration on. Both graft paths now pass the label's pins
on too:

- `graft_leaf_given` puts them on the leaf step.
- `graft_recording` treats the label as retelling the fixture's root step. A label with
  `pins=None` keeps the root's pins; any list, `[]` included, replaces them, the way the label's
  narration replaces the root's. Steps inside the fixture body keep their own pins.

Parametrize grouping compares pins where it compared ids (`StepSignature`), `None` and `[]` as
different values; rule 6 is unchanged.

### Report

JSON:

- `stories[]` lists every registered story; `stories[].sentences[]` gains `name`, `null` when
  unnamed.
- `scenarios[].story_id` becomes `story_ids`.
- `activity_ids` on scenarios and steps becomes `pins: [{story_id, sentence_id}]`, `null` when
  `pins=` was not given.
- `coverage[]` keeps its shape, since it was already story-qualified.

Serde reads the new fields back. Reports written by older versions are not supported.

HTML:

- The timeline bubble keeps the number. A named sentence shows its name as an outlined
  monospace tag beside its coverage chip, so an author can read the name off the timeline
  without it competing with the sentence's prose.
- A scenario listed under several stories shows, under each, the `Covers:` chips for that story.
- In the app data, `scenario_sentences` becomes `{node_id: {story_id: [ids]}}`, and the sentence
  filter reads the ids under the selected story.
- The sentence filter chip names the sentence's story when the report has several, since a number
  alone is ambiguous there. The sentence highlights and the `story:id` sentence key are unchanged,
  because they already live inside one selected story.

Verified by Playwright only.

### Changelog

Each break gets a `**Breaking.**` entry with its migration:

- `sentence(..., activity_id=N)` is removed: sentences are numbered by position, so name the
  sentence (`name=`) and pin it by name.
- Pins take sentence handles under `pins=`: `given(..., activity=3)` becomes
  `given(..., pins=the_story[3])`, and `@scenario(activities=[2, 3])` becomes
  `pins=[the_story[2], the_story[3]]`, or `the_story['name']` for a named sentence.
- `@scenario(story=)` is now `stories=` and takes one story or several.
- `@scenario(pins=)` covers exactly the pinned sentences plus its steps' pins, with no narration
  matching in any story; `pins=[]` on a step or scenario opts out of narration matching without
  pinning anything.
- In the JSON report, `scenarios[].story_id` is now `story_ids`, and `activity_ids` on scenarios
  and steps is now `pins`, `null` when not given.

Under **Added**: sentence names shown on the timeline, and scenarios that bind several stories.
Under **Changed**: the report lists every story the run declares, not only those a scenario binds.
Under **Fixed**: an `Annotated` `given(...)` label carrying a pin records it instead of dropping it.

### Docs, skills and glossary

- `GLOSSARY.md`:
  - *Handle* covers both term handles (`g['Guest']`) and sentence handles
    (`book_a_room['cancel']`).
  - A new **Pin** row: what a sentence handle in `pins=` is recorded as, as a term handle is
    recorded as a term ref. A pin binds explicitly and replaces narration matching for its step or
    scenario.
  - The *Sentence* row gains number and name. *Scenario↔sentence binding* becomes `stories=` plus
    pins. *Coverage* refers to *Pin*.
- Site guide:
  - `domain-storytelling.md`: handles, names, multi-story binding, the three levels and their
    table, `pins=[]`, unbacked scenario pins, and every declared story appearing.
  - `scenarios.md`: the signature, and an Annotated label's `pins=`. Its "never a string" remark
    goes.
  - `parametrized.md`: rule 6's `activity=` becomes `pins=`.
- Authoring skill:
  - `api.md`: the signatures, the retired `activity_id=`, and an Annotated label's `pins=`.
  - `stories.md`: stories reach the report by being declared, the step pin example becomes a
    handle, `pins=[]`, and the renumbering-trap paragraph points at names.
  - `domain-storytelling.md`: its `story=` binding becomes `stories=`.
- Reviewing skill:
  - `story-coverage.md`: the three levels, and the check that each scenario pin is exercised.
  - `pairs.md`: its Python block moves from `story_id` to `story_ids` (`test_skills_scripts.py` runs
    it).
- Navigating skill:
  - `SKILL.md`: `story=` becomes `stories=`, and the by-story `jq` recipe reads a story's scenarios
    off `coverage[]`, since `story_ids` only says where narration matching looked.
  - `report-json.md`: the changed fields, `pins: null`, and their `jq` examples.
- Regenerate the `.claude/skills/` mirror with `uv run pytest-given skills install`, since the sync
  test compares it against the source skills.

### Self-report and examples

- **Dogfood story.** `tests/ubiquitous_language.py` names every sentence of `adopt_pytest_given`,
  and its ~30 `activity=N` pins become `pins=adopt_pytest_given['…']`, behind a short alias if
  needed. This story has the most pins an inserted sentence would re-target, so it shows the fix
  best.
- **New scenarios, one per rule:**
  - a handle resolves a name and a number, and a miss raises at its line;
  - iterating a story yields its handles;
  - a duplicate, empty or padded name is rejected;
  - a scenario pin covers exactly its sentences, including an under-anchored one, and stops
    narration matching in the stories `stories=` names;
  - a pinned scenario still counts its steps' pins;
  - `pins=[]` on a step covers nothing, and on a scenario leaves only its steps' pins;
  - a step pin into a story the scenario does not name covers it and lists the scenario there;
  - a declared story no scenario covers appears in the report;
  - a wider-scoped fixture's pin keeps its story when grafted into later scenarios;
  - a scenario matched against two stories;
  - an Annotated label's pin reaches its step, `[]` clears the fixture's pins, and `None` keeps
    them.
- **Changed scenarios:**
  - the `activity_id=0` scenario in `test_story.py` goes;
  - "A string `activities=` argument is refused" (`test_step_descriptor.py`) becomes the refusal of
    bare ints and strings under `pins=`;
  - the scope tests in `test_plugin.py` (scenario `activities=` combined with step pins) become the
    level combinations above.
- **Examples.** `hotel-booking` and `file-glossary-booking` move to `stories=`. `hotel-booking`
  gains a named, pinned sentence and a scenario bound to two stories.

## Considered and rejected

- **Bare `int` / `str` pins beside handles.** They need "the scenario's story" to resolve against,
  which a multi-story scenario lacks. They also keep resolution at capture, where the graft went
  wrong.
- **Pinning by the `Sentence` object.** `story()` rebuilds sentences to number them, so a sentence
  bound to a variable before `story()` is not the sentence in the story. It would also force every
  pinned sentence out of the story's inline list.
- **Scenario pins per story.** A scenario pin would replace narration matching only in the story it
  names, so `stories=A, pins=B[2]` would still match A. An empty list names no story, so the
  scenario level would have no way to opt out of matching, and the mix would need three errors: a
  step pin into a story outside `stories=`, a story in both `stories=` and `pins=`, and a step pin
  into a pinned story.
- **Omitting `stories=` to mean "match against every declared story".** Matching would be on by
  default, and stories sharing terms would pick up each other's steps. Binding for matching stays
  explicit; only the report's story list is suite-wide.
- **"Claim" for the scenario form.** A second term would suggest the two forms do different
  things. Both do one thing at two scopes, so one term, *Pin*, covers them.
- **"Sentence ref" instead of "pin".**
  - The glossary row would stay, since it still has to say that the binding replaces matching.
  - Matching is itself a step's term refs reaching a sentence, so "ref" would blur the difference
    between pinned and matched coverage.
- **`sentences=` as the keyword.** It names only what is passed, not the override, and reads less
  naturally on a scenario than the old `activities=`.
- **`covers=` as the keyword.** It matches the `Covers:` chips but names the result (see "Why
  `pins=`"), and invites the reading "these as well as whatever matching finds".

## Forward notes

- **A lint rule for unbacked scenario pins**: a pinned sentence whose terms no step mentions. It
  would be the mechanical counterpart of the reviewing check. Only worth building if that check
  keeps finding such pins.
- **Story diagrams** (unmerged branch) take the arrow number from `int(sentence.id)`, which keeps
  working.
