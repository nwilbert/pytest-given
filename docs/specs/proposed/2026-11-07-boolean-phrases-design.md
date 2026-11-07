# Boolean Phrases in Narration — Design Spec

## Goal

Let a Boolean column read as words in a step and in its parameter table. The author writes both
phrases in the interpolation's format spec, true phrase first:

```python
@pytest.mark.parametrize(('pinned', 'untracked'), [(False, True), (True, False)])
def test_an_under_anchored_sentence_reads_as_untracked_until_pinned(pinned, untracked):
    with given(t'a scenario whose step {pinned:pins it|does not pin it}'):
        ...
    with then(t'it {untracked:reads as untracked|stays tracked}'):
        assert sentence_coverage.untracked == untracked
```

The report shows:

```
GIVEN a scenario whose step {pins it}
THEN it {reads as untracked}
```

| pinned | untracked |
|---|---|
| does not pin it | reads as untracked |
| pins it | stays tracked |

## Background

10 narrated steps in 9 of the 47 parametrized scenarios in the self-report interpolate a Boolean
column, almost all as a trailing `: {flag}`. The sentence stops being a sentence, and the table
shows `True` and `False` under a column name the reader has to carry back to the step.

The forms available on `main` each break a rule of the authoring skill:

- **A local holding the phrase** (`pin = 'pins it' if pinned else 'does not pin it'`) adds a
  `derived` column beside `pinned`, a label next to the data it describes.
- **The phrases as parametrize values** make the body map a label back to data
  (`if pin == 'pins it'`).

A format spec has neither problem. The body keeps reading the real Boolean, and the column stays
one column. `param_cell_formats` already renders a cell through the format spec its slots share,
and row hover already substitutes that cell into the slot.

## Approach

### The phrase spec

A **phrase spec** is a format spec with exactly one `|` and text on both sides of it. The text
before the `|` is the true phrase and the text after it the false phrase.

```python
def boolean_phrases(format_spec: str) -> tuple[str, str] | None: ...
```

It works in every position that takes a format spec: a t-string step, and a `Template` in
`@scenario(...)`, on a helper decorator or in `Annotated[..., given(...)]`. `Template` already
reads the spec with `string.Formatter`, and a t-string already hands it over as
`Interpolation.format_spec`, so neither form needs a parser change.

Phrases are used verbatim. Like every interpolated value, a phrase is literal text: it holds no
Markdown span and no term ref.

These specs are not phrase specs and reach `format()` as they do on `main`:

- `|>5` has no text before the `|`. It stays a fill-and-align spec, so `format(True, '|>5')` is
  still `||||1`.
- `a|b|c` has two. On a `bool` it raises Python's `ValueError`, which quotes the spec.

### Rendering a value

`render_interpolation` is the one definition of how an interpolation renders. It applies the
conversion, then checks for a phrase spec:

- A `bool` renders as its phrase.
- Any other value raises `PytestGivenError`, naming the placeholder and the value's type.

Truthiness is not enough. Given `None` or `1`, a reader can't tell which phrase the author meant
for that row. A conversion produces a string, so `{pinned!r:a|b}` is refused too.

This reserves the phrase shape for Booleans, because the token is chosen from the spec alone, with
no value in reach. So `{when:%H|%M}` on a `datetime`, which renders `14|30` on `main`, is refused.
The fix is to bind the text to a local (`clock = when.strftime('%H|%M')`) and narrate `{clock}`.

Where the refusal surfaces follows from where the value is first rendered:

| Position | Raised |
|---|---|
| t-string step | When the step opens, failing the test |
| `Template` on a helper decorator | When the helper is called, failing the test |
| `Template` in `@scenario(...)` or `Annotated[..., given(...)]` | In the grouping pass, failing the run |

`param_cell` catches every exception from a value's own rendering and falls back to the plain
value. It lets `PytestGivenError` through, since that one is an authoring mistake and not a broken
`__format__`.

### The token

`placeholder_token` returns the true phrase in braces for a phrase spec, and `{name}` otherwise:

| Slot as written | Token |
|---|---|
| `{pinned}` | `{pinned}` |
| `{price:.2f}` | `{price}` |
| `{pinned:pins it\|does not pin it}` | `{pins it}` |

The HTML report, the Markdown report, citation link text and `narration_text` all call this
function, so they agree. A placeholder's `name` and `column_id` don't change, and the palette, the
hover highlight and `data-subst` key on them.

The grouped `text` holds the true phrase only. The false phrase is in the column's cells, so a
`jq` search for it has to read `parameters.cases[].values` as well.

### The table

The column keeps the parametrize argument as its header. Its cells hold the phrases through the
existing `param_cell_formats` rule, and row hover then reads as a whole sentence: "a scenario whose
step does not pin it".

What follows from the existing rules needs no new code, and each gets a test:

- **Two slots with one phrase spec** share the column.
- **Two slots that differ**, including one bare `{pinned}` beside a phrased one, leave the `param`
  column with plain `True` and `False`, and each disagreeing slot gets a `derived` column.
- **A Boolean local that varies** (`t'{flag:on|off}'`, no column named `flag`) is promoted to a
  `derived` column holding the phrases. One that doesn't vary renders its phrase inline.
- **Rule 3** re-applies `render_interpolation` to the raw parameter, so a local rebinding the name
  is still caught.
- **`unused-interpolation`** reads the bare name (`lint/ast_rules.py`), so a phrased slot lints as
  a plain one.
- **Generated case IDs** come from the raw values, so they still read `True-False`.

### Schema

The report JSON keeps its shape. `format_spec` is already on a placeholder part, and a cell is
already a string where its slots carry a format spec.

## Authoring and review

Nothing checks a phrase against the body. `{pinned:does not pin it|pins it}` over `if pinned` runs
green, and the report says the opposite of what the test did.

- **Authoring** (`references/parameter-tables.md`): word a Boolean as a phrase instead of a
  trailing `: {flag}`. The true phrase comes first, and both phrases must complete the same
  sentence. The examples under "Never turn a label back into data" and "Outcomes are columns"
  (`same room: {same_room}`, `it clashes: {clashes}`) are reworded to match. A phrase doesn't change
  which rows belong in a table.
- **Review** (reviewing `SKILL.md`): swapped phrases are a semantic finding, checked by reading the
  step body. A pair that only restates the value (`{kept:True|False}`) is a legibility finding.

## Implementation touch points

- `model/narration.py`: `boolean_phrases`, `render_interpolation`, `placeholder_token`.
- `grouping/columns.py`: `param_cell` lets `PytestGivenError` through.
- `GLOSSARY.md`: a **Boolean phrase** row.
- Skills: authoring `references/parameter-tables.md` and `references/api.md`, reviewing `SKILL.md`,
  navigating `references/report-json.md` (a step's text holds the true phrase for a phrase spec).
  Regenerate the `.claude/skills/` mirror with `uv run pytest-given skills install`.
- `docs/site/guide/step-text.md`: a section on Boolean phrases, linked from "Template
  placeholders".
- `CHANGELOG.md`: Added, the phrase spec. Changed, a **Breaking** line for `{when:%H|%M}` on a
  non-Boolean value with its migration.
- Self-report: reword the Boolean steps that read better as phrases. `examples/`: one example table
  that uses a phrase. Regenerate both.
- No template or `app.js` change. Hover substitution is what makes the phrase read as a sentence,
  so drive it in Playwright all the same, per [Report testing](../../../AGENTS.md#report-testing).

## Test coverage

- **`render_interpolation`:** each phrase verbatim for `True` and `False`, `|>5` still a fill and
  align, `a|b|c` raising `ValueError`, and a refusal for `1`, `None`, a string, `!r` and a
  `datetime`.
- **`placeholder_token`:** the true phrase for a phrase spec, `{name}` for no spec, `.2f` and `|>5`.
- **Grouping:** cells hold the phrases and rule 3 stays silent, a rebinding local still raises, and
  the slot cases under [The table](#the-table). A non-Boolean value under a `Template` title or an
  `Annotated` label raises instead of falling back. A failed case's row shows its phrase.
- **Integration, as scenarios tagged `spec/boolean-phrases`:** a Boolean column reads as a phrase in
  the step and in the parameter table of the Markdown report, and a phrase spec on a non-Boolean
  value is refused.
- **HTML:** data-shaped only. The token, the colour link to the column and row hover are
  Playwright's.

## Out of scope

- **Phrases for values other than Booleans.** A column of more than two values already reads well
  as its own words, or as a relation column.
- **A token that follows the row.** The grouped view marks which column varies, so its token stays
  the true phrase whatever the row says. Row hover shows the row's own phrase.
- **Renaming the column.** The header stays the parametrize argument, which is what the code and
  the case ID show.
- **A lint rule for `: {flag}`.** A step can end in a Boolean and still read well, so the reviewing
  skill judges it.
- **Checking a phrase against the body.** Nothing in the report can tell which phrase is the true
  one, so this stays with the reviewing skill.
