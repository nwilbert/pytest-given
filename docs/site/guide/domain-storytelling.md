# Domain Storytelling

[Domain Storytelling](https://domainstorytelling.org/quick-start-guide) describes how a domain works as short stories. With pytest-given you write these stories in code, and the report shows which scenarios cover each sentence of a story.

!!! info "About Domain Storytelling"

    [Domain Storytelling](https://domainstorytelling.org) is a technique for building a shared understanding between domain experts and developers. Together they describe the domain as stories: who does what, with what, and in which order. These stories give your tests context. Your scenarios sit one level below them, and each one documents a specific piece of domain logic in much more detail.

In Domain Storytelling, **actors** do **activities** with **work objects**. "Carol selects a room" has an actor (Carol), an activity (selects), and a work object (room). A story is a numbered list of such **sentences**. In a Domain Storytelling diagram, each activity is an arrow labelled with a verb.

When the parts of a sentence are [glossary](glossary.md) terms, the report can match the sentence against your tests. The HTML report shows stories in a **Stories** tab.

## Writing stories

Create a story with `story(...)`, passing a name and a list of `sentence(...)` calls:

```python
from pytest_given import sentence, story

book_a_group_trip = story('Book a Group Trip', [
    sentence(organizer('Carol'), 'searches for', room),
    sentence(organizer('Carol'), 'selects', room('Deluxe Suite'), name='select'),
])
```

Here `organizer` and `room` are glossary handles.

### Sentences

A sentence reads left to right: actor, activity, work object. Connecting words like `'to'` can go in between.

Each part can be a glossary handle or a plain string. Use plain strings for generic verbs like *searches for*. Only words with a specific meaning in your domain need a glossary entry.

Handles from a [file glossary](glossary.md#file-glossary) work the same way: `sentence(g['Guest'], g['book']('books'), g['Room'])`.

To be matched against your tests, a sentence needs at least two different glossary terms. The report marks a sentence with fewer as "not coverage-tracked". You can still cover it with a [pin](#pins).

### Clauses

Sometimes one sentence has more than one arrow: an actor hands a work object to two people, or two actors do something at the same time. Write one `clause(...)` per arrow chain:

```python
sentence(
    clause(organizer('Carol'), 'adds', guest('Alice'), 'to', trip),
    clause(organizer('Carol'), 'adds', guest('Bob'), 'to', trip),
)
```

A clause starts with its actor. After that, its parts alternate: an activity or connecting word, then an actor or work object, and so on. A clause ends with an actor or work object, so it always has an odd number of parts, at least three.

To cover a sentence with several clauses, one step must mention every glossary term from all of its clauses.

### Kind inference

If a term has no declared [kind](glossary.md#kinds), pytest-given infers it from the term's position in story sentences when the test session finishes:

- first position: **actor**
- an activity position (2nd, 4th, …): **activity**
- any other position (3rd, 5th, …): **work object**

If a term's kind is declared, pytest-given checks the kind against the term's position when the sentence is created. A term in the wrong position raises `PytestGivenError`, naming the term and its kind.

If a term without a declared kind appears both in an activity position and in another position, inference fails with an error at the end of the session. Declare the term's kind (or add a `kind_column` to your file glossary) to fix it.

## Linking scenarios to stories

Tell pytest-given which story a scenario belongs to with `stories=`:

```python
@scenario('Carol selects a suite', stories=book_a_group_trip)
def test_select_suite(carol):
    with when(t'{organizer("Carol")} selects the {room("Deluxe Suite")}'):
        ...
```

For several stories, pass a list: `stories=[book_a_group_trip, check_in]`, where `check_in` is another story. The scenario then appears under each of them.

pytest-given works out which sentences of these stories the scenario covers. By default, it matches the text of the scenario's steps against the sentences. With pins, you state the covered sentences yourself.

### Narration matching

A step covers a sentence when the step's text mentions every glossary term in that sentence. The form of the term ref doesn't matter: `{room}`, `{room.low}` and `room('Deluxe Suite')` all count as the term *Room*.

### Coverage in the report

The Stories tab shows each story as a timeline of its sentences. Each sentence has a coverage chip and lists the scenarios that cover it. Select a sentence and choose *Open in Scenarios* to see only those scenarios. Below the timeline, the story's scenarios open in place to show their steps, and selecting sentences shows only the scenarios covering one of them. Every story you declare appears in the tab, even if no scenario covers it.

The JSON report contains the same data under the top-level `coverage` key.

### Sentence handles

To refer to one sentence, get a **sentence handle** from the story, by name or by number:

```python
book_a_group_trip['select']  # by name, set with name='select' above
book_a_group_trip[2]         # by number
```

Numbers are positions in the list, so they change when you insert a sentence before them. Names stay the same.

### Pins

A **pin** states which sentences a step or scenario covers, instead of relying on narration matching. Pass sentence handles to `pins=`:

- **On a step**, like `given(text, pins=book_a_group_trip['select'])`: the step covers exactly these sentences, from any story. Its text is not matched.
- **On a scenario**, like `@scenario(..., pins=book_a_group_trip['select'])`: the scenario covers these sentences, plus whatever its steps pin. The text of its steps is not matched.

`pins=[]` turns off narration matching without pinning anything. On a step, it affects only that step. On a scenario, it affects all its steps, but steps with their own pins still count.

A pin can point into a story that isn't in the scenario's `stories=`. The scenario then also appears under that story.

The default, `pins=None`, means "no pins at this level". So narration matching only happens where no level sets pins. This table shows what a step contributes:

| scenario `pins=` | step `pins=` | the step contributes |
|---|---|---|
| `None` | `None` | its narration matches, in the `stories=` stories |
| `None` | a list | exactly its pins |
| a list, `[]` included | `None` | nothing |
| a list, `[]` included | a list | exactly its pins |

Use scenario pins with care: no step text backs them up. A pinned sentence counts as covered even if the test fails early or is skipped (its chip then shows the scenario's status). Only pin a sentence if the test really exercises it.

Pins also work for sentences with fewer than two glossary terms, which narration matching can't cover.

## Examples

The hotel-booking and file-glossary-booking [examples](../examples.md) show stories and coverage in use.
