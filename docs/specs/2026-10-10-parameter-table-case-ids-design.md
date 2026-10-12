# Case Ids in Parameter Tables — Design Spec

✅ [spec/parameter-table-case-ids](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#tag=spec/parameter-table-case-ids) (1 ✅)

## Goal

Name each row of a parameter table by its pytest case id when the author wrote ids for readers,
so a failure the terminal reports as `test_overlap[touching-edges]` can be found in the report at
a glance. The column appears only when some id is custom, written by hand; generated ids restate the value
columns and stay hidden.

## Background

pytest ids are for people: `-v` output, the failure summary and `-k` selection all show them, and
`pytest.param(..., id=...)` and `parametrize(ids=...)` let an author name a case instead of having
its values spelled out. Each `ParameterCase` carries its node id, so the JSON has the ids, but
neither renderer prints them. Generated ids like `10-20-15-25-True` can be matched against the
value columns; nothing a reader sees connects `touching-edges` to its row.

This spec is implemented after [Inline Markdown in Titles, Steps and
Definitions](2026-10-11-inline-markdown-design.md) and uses its Markdown writer for the id column.

## Approach

### Capture

`ParamSpec` gains `custom_id: bool = False`: whether the case's id is custom, written by hand. pytest
records only the finished id, and its parametrization reaches it from marks, fixture `params=` and
`metafunc.parametrize` alike, so the id is read off its form rather than its source. A generated id
is the case's values' tokens joined by `-`, in the order of `callspec.params`, which is the order
pytest parametrized in. The id is custom unless it is such a join, where each token follows
pytest's `IdMaker`:

- a `pytest_make_parametrize_id` hook's answer, if any;
- otherwise from the value: a string or bytes ASCII-escaped (unless the ini option that disables
  escaping is set), a number, bool or `None` by `str`, a regex by its pattern, an enum member by
  `str`, anything with a `__name__` by that name;
- or `argname` and a number, pytest's fallback for any other value, allowed for every value since
  the number is the case's position in its parametrize call, which is not known;
- each optionally followed by a counter, which pytest appends to tell duplicate ids apart, after a
  `_` where the token ends in a digit (`1_0`, `a1`).

Any token may be missing, as `HIDDEN_PARAM` drops a part from the id, and an empty id is not
written. The rules are copied, as pytest exports none of them; the unit tests pin each, and
`nox -s compat` runs them against the oldest and newest supported pytest. A drift in pytest's rules
reads its generated ids as written, which shows the column where it adds nothing. An id written by
hand that matches its values' tokens (`ids=['1']` for `1`) reads as generated, which is the point:
it says nothing the value columns don't.

### Model

```python
@dataclass(frozen=True)
class ParameterCase:
    ...
    custom_id: bool = False


@dataclass(frozen=True)
class ParameterTable:
    ...

    @property
    def has_custom_ids(self) -> bool: ...


def case_id(node_id: str) -> str: ...
```

`custom_id` is copied from the case's `ParamSpec`, so the JSON says which ids are custom.
`has_custom_ids` is true when any case's is, and it is the only thing the renderers consult to show
the column. `case_id` is `case_suffix(node_id)` unbracketed, the tail starting at the first `[` past the
path (a directory may hold one, a class or function name cannot), the text the terminal
printed and the suffix a per-case scenario's title already carries, which takes it from the same
function.

The id is not a `ParameterColumn`: it has no slot, nothing narrates it, row hover has nothing to
substitute, and the column order rules don't sort it. It is the row's header.

### Rendering

When `has_custom_ids` holds, both renderers lead the table with a column headed `case id`, the
glossary's word; a bare `id` would clash with a parametrize argument of that name. Every row shows its id, generated ones included, so each row reads as
the terminal printed it; an all-`HIDDEN_PARAM` id leaves its cell empty.

- **HTML:** a `<th scope="row">` per row, in plain text and uncoloured, with no `data-param`: the
  id reads as a value reads in a table, as a per-case title's suffix reads as a value in prose. For
  phase hover it shares one `data-block` with the status column, so pointing at either outlines
  both. The two sit at opposite ends of the row, so `_outlinePhase` draws one box per run of
  adjacent columns and run of rows instead of one per run of rows.
- **Markdown:** a leading `case id` column, the id escaped whole by the inline Markdown writer,
  like every text that is not a title or a step (`a*b*c` is written `a\*b\*c`). A generated id too
  long to inline leaves its cell empty, by the rule that keeps a long value out of a note's key:
  it only repeats a value the row already shows. A custom one shows whole. The notes below the table (a case's error, an
  attachment too long to inline) are keyed by the id instead of the joined values, falling back to
  the values for an empty cell; notes that would share a key add their row number.

````markdown
| case id | existing booking | hours later | it clashes |
|---|---|---|---|
| touching-edges | 10–20 | 10 | True |
| one-hour-apart | 10–20 | 11 | False |
````

## Authoring and review

The id is a claim nothing checks, like a scenario title: the body never reads it, but it can
misname its row.

- **Authoring** (`references/parameter-tables.md`): name rows with ids when a reader needs to talk
  about them, as in a boundary or a named edge case. An id names what the row is for
  (`touching-edges`), never a value the columns already show (`start-10`). The "no label column
  sits next to the data it describes" rule gets a carve-out for ids, since it is about labels the
  body consumes.
- **Review** (reviewing `SKILL.md`, the parameter-table list): an id that misnames its row or only
  restates a column is a legibility finding.

## Implementation touch points

- `model/runtime.py`, `model/schema.py` — the fields and `case_id` above; serde follows.
- `plugin/case_ids.py` — `is_custom_id`, worked out for a grouped case only; `grouping/columns.py`
  copies it onto the table's cases.
- `report/md_renderer.py` — the column; `_case_key` prefers the id.
- `report/templates/` — the row header, the shared block, per-run outline boxes;
  Playwright-verified per AGENTS.md.
- Skills: navigating `references/report-json.md` (`custom_id`), authoring
  `references/parameter-tables.md`, reviewing `SKILL.md`; `docs/site/` in step.
- Self-report: decorate the test that best states "a parameter table names its rows by their
  custom ids".
- `CHANGELOG.md` — Added: parameter tables lead with the case ids when any is custom.
- Regenerate `examples/` (one example table with ids and mixed statuses) and
  `examples/self-report/`.

## Test coverage

- Capture, over pytester-collected items: each token rule above, a duplicate, `HIDDEN_PARAM`,
  stacked marks, and custom ids from a mark, a fixture and `metafunc.parametrize`.
- Grouping and model: each case's `custom_id` carried to the table, `has_custom_ids` true for any; `case_id`
  for a plain, stacked and hidden id.
- Markdown renderer: the leading column only under `has_custom_ids`, generated ids beside custom
  ones, notes keyed by id, an id holding `*` and `|` escaped, an id too long to inline left out.
- HTML: data-shaped only; the markup, the shared block and the outline are Playwright's.

## Out of scope

- **Per-case scenarios** (`group_parametrized=False`): each title already ends in its case id,
  generated or not.
- **Deep links to a row, and citing one.** The id would make a natural URL fragment, but the
  report has no row links, and a cited case's node id resolves to its whole scenario.
- **A frozen id column.** Keeping the id in view while a wide table scrolls sideways needs an
  opaque sticky cell that repeats every row tint the `tr` paints; few tables are that wide.
- **A lint rule for an id that restates a value.** Short values (`True`, `1`) would make it noisy;
  review catches it.
- **Generated ids without the column**, e.g. on hover of the status dot: they restate the values,
  and the JSON has them.
