# Case Ids in Parameter Tables — Design Spec

✅ [spec/parameter-table-case-ids](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html#tag=spec/parameter-table-case-ids) (1 ✅)

## Goal

Name each row of a parameter table by its pytest case id when the author wrote ids for readers,
so a failure the terminal reports as `test_overlap[touching-edges]` can be found in the report at
a glance. The column appears only when some id was written by hand; generated ids restate the value
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

`ParamSpec` gains `explicit_id: bool = False`: whether any part of the case's id was written by
hand. pytest records only the final id parts, so it is read from the item's `parametrize` marks
(`item.iter_markers('parametrize')`, class- and module-level ones included). For each mark, the
argnames are split and each argvalue unpacked the way pytest does it (a lone name in a bare string
takes each value whole), and the case's position in its `argvalues` is found by identity: pytest
passes each argvalue through unchanged into `callspec.params`. `callspec.indices` cannot say it,
since pytest renumbers a direct argument's index to the case's place among all cases. Each mark is
indexed once, by its argvalues' identities, for every case that shares it; where one object sits
at several positions, each of them is matched. The part is explicit when:

- the argvalue is a `pytest.param` with an `id` other than `pytest.HIDDEN_PARAM` (such an id wins
  over `ids=`, as in pytest), or, without one,
- the mark's `ids` (keyword or fourth positional argument) is a callable or an iterator, or a
  sequence whose entry at that position is neither `None` nor `HIDDEN_PARAM` — pytest generates
  the id for a `None` entry.

A callable counts even where it returns `None`: telling would mean calling it again. An iterator
counts too, as pytest has consumed it. One explicit part makes the case explicit, since one named
part makes the id worth reading, and so does one explicit position among several an object
matches: the table shows its ids for that position's own case anyway. Parametrization
that never becomes a mark (`metafunc.parametrize`, fixture `params=`) reads as generated.

### Model

```python
@dataclass(frozen=True)
class ParameterTable:
    columns: list[ParameterColumn]
    cases: list[ParameterCase] = field(default_factory=list)
    named_cases: bool = False


def case_id(node_id: str) -> str: ...
```

`named_cases` is true when any case is explicit, and it is the only thing the renderers consult
to show the column. `case_id` is `case_suffix(node_id)` unbracketed, the text the terminal
printed and the suffix a per-case scenario's title already carries, which takes it from the same
function.

The id is not a `ParameterColumn`: it has no slot, nothing narrates it, row hover has nothing to
substitute, and the column order rules don't sort it. It is the row's header.

### Rendering

When `named_cases` holds, both renderers lead the table with a column headed `id` (pytest's word,
the one `ids=` and `-k` use). Every row shows its id, generated ones included, so each row reads as
the terminal printed it; an all-`HIDDEN_PARAM` id leaves its cell empty.

- **HTML:** a `<th scope="row">` per row, in plain text and uncoloured, with no `data-param`: the
  id reads as a value reads in a table, as a per-case title's suffix reads as a value in prose. For
  phase hover it shares one `data-block` with the status column, so pointing at either outlines
  both. The two sit at opposite ends of the row, so `_outlinePhase` draws one box per run of
  adjacent columns and run of rows instead of one per run of rows.
- **Markdown:** a leading `id` column, the id escaped whole by the inline Markdown writer, like
  every text that is not a title or a step (`a*b*c` is written `a\*b\*c`). The notes below the
  table (a case's error, an attachment too long to inline) are keyed by the
  id instead of the joined values, falling back to the values for an empty id.

````markdown
| id | existing booking | hours later | it clashes |
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
- `plugin/case_ids.py` — `explicit_id`; `grouping/columns.py` — `named_cases`.
- `report/md_renderer.py` — the column; `_case_key` prefers the id.
- `report/templates/` — the row header, the shared block, per-run outline boxes;
  Playwright-verified per AGENTS.md.
- Skills: navigating `references/report-json.md` (`named_cases`), authoring
  `references/parameter-tables.md`, reviewing `SKILL.md`; `docs/site/` in step.
- Self-report: decorate the test that best states "a parameter table names its rows by their
  hand-written ids".
- `CHANGELOG.md` — Added: parameter tables lead with the case ids when any was written by hand.
- Regenerate `examples/` (one example table with ids and mixed statuses) and
  `examples/self-report/`.

## Test coverage

- Capture, over pytester-collected items: each explicit and generated form above, `HIDDEN_PARAM`,
  and stacked marks with one explicit part.
- Grouping and model: `named_cases` false for generated ids, true for any explicit case; `case_id`
  for a plain, stacked and hidden id.
- Markdown renderer: the leading column only under `named_cases`, generated ids beside explicit
  ones, notes keyed by id, an id holding `*` and `|` escaped.
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
