# Domain Storytelling

[Domain Storytelling](https://domainstorytelling.org/quick-start-guide) is a technique in which domain experts and developers describe how a domain works as short stories: who does what, with what, and in which order. With pytest-given you write these stories in code. Your scenarios sit one level below them, each documenting one piece of domain logic in more detail, and the report shows which scenarios cover each sentence of a story.

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

Handles from a [Markdown glossary](glossary.md#markdown-glossary) work the same way: `sentence(g['Guest'], g['book'].s, g['Room'])`.

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

If a term has no declared [kind](glossary.md#kinds), pytest-given infers it from the term's position in story sentences:

- first position: **actor**
- an activity position (2nd, 4th, …): **activity**
- any other position (3rd, 5th, …): **work object**

An actor can also stand in a work-object position, for example when it receives something.

A term with a declared kind in a position that doesn't fit it raises `PytestGivenError`.

A term without a declared kind that appears both in an activity position and in another position raises an error too. Declare the term's kind (or add a `kind_column` to your Markdown glossary) to fix it.

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

A step covers a sentence when the step's text mentions every glossary term in that sentence. The form of the term ref doesn't matter: `{room}`, `{room.l.s}` and `room('Deluxe Suite')` all count as the term *Room*.

### Sentence handles

To refer to one sentence, get a **sentence handle** from the story, by name or by number:

```python
book_a_group_trip['select']  # by name, set with name='select' above
book_a_group_trip[2]         # by number
```

A number is the sentence's number in the story, starting at 1, as the Stories tab shows it. Numbers change when you insert a sentence before them. Names stay the same.

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

### Coverage in the report

The Stories tab shows each story as a timeline of its sentences. Each sentence has a coverage chip and lists the scenarios that cover it. Select a sentence and choose *Open in Scenarios* to see only those scenarios. Below the timeline, the story's scenarios open in place to show their steps, and selecting sentences shows only the scenarios covering one of them. Every story you declare appears in the tab, even if no scenario covers it.

`pytest-given coverage` prints the same data from a JSON report (see [Standalone CLI](../cli.md#coverage)).

Story coverage helps a reader find the scenarios behind a part of the flow, and see the flow behind a scenario. It is not a measure of how completely the suite tests the system: a covered sentence means a step talks about it, not that its behavior is tested. To ask what the scenarios exercise, measure the code coverage of [`-m pytest_given`](../configuration/pytest-options.md#selecting-scenarios).

## Story diagrams

`--given-diagrams` writes one more self-contained HTML page, which draws each story in Domain Storytelling notation. Actors and work objects are icons, and each sentence's activities are arrows labelled with their verb and its number. A work object is drawn again in each sentence that uses it, while an actor is drawn once per story.

- The sidebar switches between stories, and the story's id after `#` in the address opens it directly.
- The arrow buttons, or the left and right arrow keys, replay the story one sentence at a time.
- Hovering a sentence highlights all its arrows. Hovering a term shows its definition.
- The wheel zooms, dragging pans, and *Fit* fits the whole diagram into view.

The layout is computed when the page is written, and it keeps arrows from crossing wherever the story allows. An HTML report written in the same run links each story's header to its diagram. `pytest-given report --diagrams` draws the page from a saved JSON report (see [Standalone CLI](../cli.md#report)).

## Examples

The hotel-booking and table-glossary [examples](../examples.md) show stories and coverage in use. The hotel-booking example also has its [story diagrams](../examples/hotel-booking-diagrams.html){ target=_blank }.
