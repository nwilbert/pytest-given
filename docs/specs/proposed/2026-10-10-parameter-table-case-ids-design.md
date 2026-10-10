# Case Ids in Parameter Tables — Design Spec

## Goal

Name each row of a parameter table by its pytest case id when the author wrote ids for readers,
so a failure the terminal reports as `test_overlap[touching-edges]` can be found in the report at
a glance. The column appears only when some id was written by hand; generated ids restate the value
columns and stay hidden.

## Background

pytest ids are for people: `-v` output, the failure summary and `-k` selection all show them, and
`pytest.param(..., id=...)` and `parametrize(ids=...)` exist so an author can name a case instead
of having its values spelled out.

The report drops them everywhere. A grouped scenario keeps its representative case's node id, and
the Markdown anchor strips even that suffix; a `ParameterCase` carries its cells, status and error,
but nothing that says which pytest case it is. With generated ids that loss is harmless, since
`10-20-15-25-True` can be matched against the value columns. With hand-written ids it is not:
nothing in the report connects `touching-edges` to its row.

## Approach

### Capture

`ParamSpec` gains the case's id and whether any part of it was written by hand:

```python
class ParamSpec(NamedTuple):
    names: list[str]
    values: list[RawParamValue]
    group: bool = True
    case_id: str = ''
    explicit_id: bool = False
```

`case_id` is `callspec.id`. pytest records only the final id parts, not where they came from, so
`explicit_id` is read from the item's `parametrize` marks. For each mark, the case's position in
its `argvalues` is `callspec.indices[argnames[0]]`. The part is explicit when the mark has an
`ids=` argument (a list or a callable) or that argvalue is a `pytest.param` with an `id`. A case
is explicit when any of its parts is: stacked `parametrize` decorators each contribute a part, and
one named part is enough to make the id worth reading.

Parametrization that never becomes a mark (`metafunc.parametrize` in a `pytest_generate_tests`
hook, fixture `params=` with `ids=`) reads as generated. Those ids still reach the JSON (below);
they only don't switch the column on.

### Model

```python
@dataclass(frozen=True)
class ParameterCase:
    values: list[CellValue]
    status: Status = 'passed'
    error: ErrorInfo | None = None
    node_id: NodeId = NodeId('')


@dataclass(frozen=True)
class ParameterTable:
    columns: list[ParameterColumn]
    cases: list[ParameterCase] = field(default_factory=list)
    named_cases: bool = False
```

Every case carries its full `node_id`, whatever the id's origin, so a JSON consumer can rerun a
row (`pytest "$(jq -r … report.json)"`) without reconstructing the id. `named_cases` is true when
any case's `ParamSpec.explicit_id` is, and it is the only thing the renderers consult to show the
column.

The id is not a `ParameterColumn`. Columns are what slots point at, what row hover substitutes
into the scenario card, and what the column order rules sort; an id has no slot, nothing narrates
it, and it belongs to the row rather than to any input. It is the row's header.

### Rendering

Both renderers show the column first, headed `id`, with each row's id: the bracketed tail of
`node_id`, the text the terminal printed. When `named_cases` holds, every row shows its id, the
generated ones included, so the column is the same id the terminal shows for each row.

- **HTML:** a header cell left of the first column, in code style; it takes no part in row hover.
- **Markdown:** a leading `id` column in the table, the id in backticks.

````markdown
| id | existing booking | hours later | it clashes |
|---|---|---|---|
| `touching-edges` | 10–20 | 10 | True |
| `one-hour-apart` | 10–20 | 11 | False |
````

## Authoring and review

The id is a claim nothing checks, like a scenario title: the body never reads it, so it cannot be
turned back into data, but it can misname its row. Both skills treat it that way.

- **Authoring** (`references/scenarios.md`, "Parameter tables"): name rows with ids when a reader
  needs to talk about them, as in a boundary or a named edge case. An id names what the row is
  for (`touching-edges`); it never restates a value the columns already show (`start-10`). The
  "no label column sits next to the data it describes" rule gets a carve-out for ids, since that
  rule is about labels the body consumes.
- **Review** (reviewing `SKILL.md`, parameter-table legibility): an id that misnames its row, or
  one that only restates a column, is a legibility finding, judged like a title.

## Implementation touch points

- `model/runtime.py` — `ParamSpec.case_id`, `ParamSpec.explicit_id`.
- `model/schema.py` — `ParameterCase.node_id`, `ParameterTable.named_cases`; serde follows
  reflectively.
- `plugin/runtest.py` — fill both from `item.callspec` and the item's `parametrize` marks.
- `grouping/columns.py` — `ColumnBuilder.table` sets `node_id` per case and `named_cases`.
- `report/md_renderer.py` — the leading `id` column.
- `report/templates/` — the header cell; Playwright-verified per AGENTS.md.
- Navigating skill `references/report-json.md` — the two new fields.
- Authoring skill `references/scenarios.md`, reviewing `SKILL.md` — the guidance above, with
  `docs/site/` kept in step.
- Self-report: decorate the test that best states "a parameter table names its rows by their
  hand-written ids".
- `CHANGELOG.md` — Added: parameter tables show hand-written case ids; JSON cases carry their
  node id.
- Regenerate `examples/` (give one example table ids) and `examples/self-report/`.

## Test coverage

- Capture units over pytester-collected items: `pytest.param(id=)`, `ids=` list, `ids=` callable,
  generated ids, stacked marks with one explicit part, a hook-parametrized test reading as
  generated.
- Grouping: `node_id` per case in declaration order; `named_cases` false for generated ids, true
  when any case is explicit.
- Markdown renderer: the column present only under `named_cases`, generated ids filled in beside
  explicit ones.
- HTML: data-shaped only (the ids the renderer receives); the markup is Playwright's.

## Out of scope

- **Per-case scenarios** (`group_parametrized=False`): each is its own scenario with its own
  title, and the Markdown anchor strips the id suffix from all of them alike. Distinguishing their
  anchors is a separate decision about the anchor, not about tables.
- **Formatting value cells.** An id names the row; it does not replace a value cell that renders
  as a list or object repr.
- **Deep links to a row.** The id would make a natural URL fragment, but the report has no row
  links today.

## Open questions

1. Header text: `id` (pytest's word) or `case`?
2. Should the HTML show the id on hover of the row's status icon instead, when `named_cases` is
   false, so generated ids are reachable without a column?
