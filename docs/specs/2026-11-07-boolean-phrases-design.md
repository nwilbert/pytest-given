# Boolean Phrases in Narration — Design Spec

✅ [spec/boolean-phrases](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#tag=spec/boolean-phrases) (7 ✅)

## Goal

Let a Boolean column read as words in a step. The author writes both phrases in the interpolation's
format spec, true phrase first:

```python
@pytest.mark.parametrize(('pinned', 'untracked'), [(False, True), (True, False)])
def test_an_under_anchored_sentence_reads_as_untracked_until_pinned(pinned, untracked):
    with given(t'a scenario whose step {pinned:pins it|does not pin it}'):
        ...
    with then(t'it {untracked:reads as untracked|stays tracked}'):
        assert sentence_coverage.untracked == untracked
```

The report shows both phrases in the step and the Boolean in the table:

```
GIVEN a scenario whose step {pins it / does not pin it}
THEN it {reads as untracked / stays tracked}
```

| pinned | untracked |
|---|---|
| False | True |
| True | False |

Hovering the first row in the HTML report reads "a scenario whose step does not pin it" and "it
reads as untracked".

## Background

11 narrated steps in 10 of the 48 parametrized scenarios in the self-report interpolate a Boolean
column, almost all as a trailing `: {flag}`. The sentence stops being a sentence.

The forms available on `main` each break a rule of the authoring skill:

- **A local holding the phrase** (`pin = 'pins it' if pinned else 'does not pin it'`) adds a
  `derived` column beside `pinned`, a label next to the data it describes.
- **The phrases as parametrize values** make the body map a label back to data
  (`if pin == 'pins it'`).

A format spec has neither problem. The body keeps reading the real Boolean, and the column stays
one column.

## Approach

### The phrase spec

A **phrase spec** is a format spec with exactly one `|` and text on both sides of it, once each side
is stripped of surrounding whitespace. The text before the `|` is the true phrase and the text after
it the false phrase.

```python
def boolean_phrases(format_spec: str) -> tuple[str, str] | None: ...
```

It works in every position that takes a format spec: a t-string step, and a `Template` in
`@scenario(...)`, on a helper decorator or in `Annotated[..., given(...)]`. `Template` already
reads the spec with `string.Formatter`, and a t-string already hands it over as
`Interpolation.format_spec`, so neither form needs a parser change.

Like every interpolated value, a phrase is literal text: it holds no Markdown span and no term ref.
A phrase with an apostrophe needs a t-string in double quotes, since
`t'{pinned:doesn't pin it|pins it}'` is a Python syntax error.

These specs are not phrase specs and reach `format()` as they do on `main`:

- `|>5` has no text before the `|`. It stays a fill-and-align spec, so `format(True, '|>5')` is
  still `||||1`.
- `a|` has no text after the `|`. On a `bool` it raises Python's `ValueError`, which quotes the
  spec.
- `a|b|c` has two. It raises the same `ValueError`.

### Rendering a value

`render_interpolation` is the one definition of how an interpolation renders. It checks for a phrase
spec before it applies the conversion:

- A `bool` with no conversion renders as its phrase.
- Anything else raises `PytestGivenError`, quoting the spec and the value's type. A conversion
  counts, since it produces a string, so `{pinned!r:a|b}` is refused.

Truthiness is not enough. Given `None` or `1`, a reader can't tell which phrase the author meant
for that row.

This reserves the phrase shape for Booleans, because the token is chosen from the spec alone, with
no value in reach. So `{when:%H|%M}` on a `datetime`, which renders `14|30` on `main`, is refused.
The fix is to bind the text to a local (`clock = when.strftime('%H|%M')`) and narrate `{clock}`.

**Identical phrases** (`{flag:a|a}`, compared once stripped) are refused whatever the value, since
the step would say the same thing in every row. `boolean_phrases` raises `PytestGivenError`, so a
t-string step fails when it opens, and a `Template` raises when it is created.

### Where a refusal surfaces

This table is for a phrase spec on a value that isn't a Boolean.


| Position | Raised |
|---|---|
| t-string step | When the step opens, failing the test |
| `Template` on a helper decorator | When the helper is called, failing the test |
| `Template` in `@scenario(...)` or `Annotated[..., given(...)]` | In the grouping pass, failing the run, for a case that passed |
| Those two under `group_parametrized=False` | In the grouping pass, failing the run, for any case |

A `Template` in `@scenario(...)` or `Annotated[..., given(...)]` renders no value while the test
runs, so grouping holds it to the rule. This is **rule 7** of the rejected authoring forms: for each
passed case, a slot with a phrase spec must carry no conversion and its raw parameter must be a
`bool`. The error names the placeholder, the test, the case and the location, as the other rules'
errors do.

In a grouped scenario, a row that did not pass never fails the run. A `[True, False, None]` column whose `None` case fails
at its t-string step, or skips before it narrates anything, shows `None` in that row, and the rest
of the report is written. Under `group_parametrized=False` each case is a scenario of its own,
whose title and labels have to render, so rule 7 holds every case to it.

Rule 3's `_reformat` counts this refusal as evidence of a rebinding, as it does `ValueError` and
`TypeError`. So `pinned = pinned == 'yes'` over a column of strings, narrated with a phrase spec,
reports the rebinding.

### The token

`placeholder_token` returns both phrases in braces for a phrase spec, and `{name}` otherwise:

| Slot as written | Token |
|---|---|
| `{pinned}` | `{pinned}` |
| `{price:.2f}` | `{price}` |
| `{pinned:pins it\|does not pin it}` | `{pins it / does not pin it}` |

Both phrases show because a token stands for every row. One phrase would state one branch as fact,
and two such slots read together can state something no row does. The token is written from the
stripped phrases, so `{pinned:a | b}` and `{pinned:a|b}` show alike.

The token separates the phrases with ` / ` instead of the spec's `|`. Markdown escapes a `|` as `\|`,
which would show in raw `--given-md` output, and ` / ` needs no escape. Nothing parses a token back,
so a phrase that holds a `/` breaks nothing.

The HTML report, the Markdown report, citation link text and `narration_text` all call this
function, so they agree. A placeholder's `name` and `column_id` don't change, and the palette and
the hover highlight key on them.

The grouped `text` holds both phrases, so a `jq` query over step text finds either one, and so does
the report's search box in a scenario title.

### The table

A phrase spec doesn't format the column. The header stays the parametrize argument, and the cells
stay the raw Booleans, in the table and in the JSON. `True` and `False` are what the parametrize list
and the case ID show, and a table of them reads as a decision table.

`param_cell_formats` counts a phrase spec as leaving the cell plain. That slot always points at the
`param` column, whatever its neighbours do:

- **Two slots with different phrases** share the column.
- **A bare `{pinned}` beside a phrased slot** shares the column.
- **A slot with any other format** beside a phrased one gets a `derived` column if its text differs
  from the Boolean. `{pinned:>5}` does, and `{pinned!r}` doesn't.
- **A non-Boolean row** that did not pass keeps its plain value.

**A Boolean local that varies** (`t'{flag:on|off}'`, no column named `flag`) is promoted to a
`derived` column holding `True` and `False`, read from whether each case rendered the true phrase.
Slots with the same expression and the same Booleans share that column, whatever their phrases. One
that doesn't vary renders its phrase inline.

**The column's name says what `True` means, and the phrases word that.** A reader of the Markdown
report matches a slot to its column by those words, so they have to agree. If a slot's phrases don't
lead back to its column's name, the wording is wrong, and the reviewing skill reports it.

### Row hover

A slot with a phrase spec carries both phrases as `data-true-phrase` and `data-false-phrase`, and a
table cell holding a Boolean carries `data-boolean`. `setHoverRow` shows the true phrase on a `True`
cell and the false phrase on a `False` cell, and any other cell's text as it does for every slot,
including a string `'True'`. This is why two slots with different phrases can share a cell.

### What stays as it is

Each of these gets a test:

- **Rule 3** re-applies `render_interpolation` to the raw parameter, so a local holding the opposite
  Boolean is caught.
- **`unused-interpolation`** reads the bare name (`lint/ast_rules.py`), so a phrased slot lints as
  a plain one.
- **Generated case IDs** come from the raw values, so they still read `True-False`.
- **`group_parametrized=False`** renders each case's own phrase, with no table.

### Schema

The report JSON keeps its shape. `format_spec` is already on a placeholder part, and a Boolean cell
is already a JSON Boolean. A `derived` cell can now hold one too.

## Authoring and review

Nothing checks a phrase against the body. `{pinned:does not pin it|pins it}` over `if pinned` runs
green, and the report says the opposite of what the test did.

- **Authoring** (`references/parameter-tables.md`): word a Boolean as a phrase instead of a
  trailing `: {flag}`. The true phrase comes first, both phrases must complete the same sentence, and
  they word what the column's name says. The examples under "Never turn a label back into data" and
  "Outcomes are columns" (`same room: {same_room}`, `it clashes: {clashes}`) are reworded to match. A
  phrase doesn't change which rows belong in a table.
- **Review** (reviewing `SKILL.md`): swapped phrases are a semantic finding, checked by reading the
  step body. Two legibility findings: a pair that only restates the value (`{kept:True|False}`), and
  a pair whose words don't lead back to the column's name.

## Implementation touch points

- `model/narration.py`: `boolean_phrases`, `render_interpolation`, `placeholder_token`.
- `capture/template.py`: `Template.__init__` reads each format spec through `boolean_phrases`.
- `grouping/columns.py`: `leaves_cell_plain` counts a phrase spec, `derived` takes Boolean cells, and
  `shared_derived` gives slots with the same expression and Booleans one column.
- `grouping/templatize.py`: `_cell_of` reads the Boolean behind a phrase, so a phrased slot keeps
  pointing at its `param` column and `_templatize_value` promotes to Boolean cells.
- `grouping/checks.py`: rule 7, `_reformat` catching `PytestGivenError`, rule 2's advice keeping the
  slot's spec, and the module docstring's count of rejected forms.
- `report/html_renderer.py`: the two phrase attributes. `report/templates/report.html.j2`:
  `data-boolean`. `report/templates/app.js`: `setHoverRow`.
- `report/markdown_writer.py`, `report/link_text.py`: a phrase's line break folds to a space.
  Drive this in Playwright, per [Report testing](../../AGENTS.md#report-testing).
- `GLOSSARY.md`: a **Boolean phrase** row that defines the phrase spec too.
- Skills: authoring `references/parameter-tables.md` and `references/api.md`, reviewing `SKILL.md`,
  navigating `references/report-json.md` (a step's text holds both phrases for a phrase spec).
  Regenerate the `.claude/skills/` mirror with `uv run pytest-given skills install`.
- `docs/site/guide/step-text.md`: a section on Boolean phrases, linked from "Template placeholders".
  `docs/site/guide/parametrized.md`: the `{name}` placeholder line, and rule 7 in the rejected forms
  table.
- `CHANGELOG.md`: Added, the phrase spec. Changed, a **Breaking** line for `{when:%H|%M}` on a
  non-Boolean value with its migration.
- Self-report: reword the Boolean steps that read better as phrases. `examples/coffeeshop`:
  `then(t'the purchase {expect:is allowed|is refused}')`. Regenerate both.

## Test coverage

- **`boolean_phrases`:** a phrase spec, stripped phrases, and `None` for no spec, `.2f`, `|>5`, `a|`,
  `a|b|c` and a side holding only whitespace, and a refusal for `a|a` and `a | a`.
- **`Template`:** creating one with `{flag:a|a}` raises, with no value bound.
- **`render_interpolation`:** each phrase for `True` and `False`, `|>5` still a fill and align, `a|`
  and `a|b|c` raising `ValueError`, and a refusal for `1`, `None`, a string, `!r` and a `datetime`.
- **`placeholder_token`:** both phrases joined by ` / ` for a phrase spec, stripped, and `{name}` for
  no spec, `.2f` and `|>5`.
- **Grouping:**
  - Cells hold the raw Booleans, and rule 3 stays silent.
  - A local holding the opposite Boolean raises rule 3, and a Boolean local over a column of strings
    raises rule 3 too.
  - Two slots with different phrases and a bare slot beside a phrased one share the `param` column.
  - A varying local gets a `derived` column of Booleans, and one that doesn't vary stays inline.
  - Rule 7 raises for a non-Boolean value and for a conversion under a `Template` title and an
    `Annotated` label.
  - A failed or skipped `None` row shows `None` and raises nothing.
  - `group_parametrized=False` renders each case's phrase and refuses a non-Boolean value.
- **Integration, as scenarios tagged `spec/boolean-phrases`:** a Boolean column reads as phrases in
  the step and as Booleans in the parameter table of the Markdown report, and a phrase spec on a
  non-Boolean value is refused.
- **HTML:** data-shaped only, the two phrases per slot. The token, the colour link to the column and
  row hover are Playwright's.

## Out of scope

- **Phrases for values other than Booleans.** A column of more than two values already reads well
  as its own words, or as a relation column.
- **Phrases in the table.** Row hover puts a row's own phrases into the sentence, so the cells don't
  need to hold them.
- **A token that follows the row.** The grouped view marks which column varies, so its token stays
  the same whatever the row says.
- **Renaming the column.** The header stays the parametrize argument, which is what the code and
  the case ID show.
- **A lint rule for `: {flag}`.** A step can end in a Boolean and still read well, so the reviewing
  skill judges it.
- **Checking a phrase against the body.** Nothing in the report can tell which phrase is the true
  one, so this stays with the reviewing skill.
