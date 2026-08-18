# Report JSON shape

`pytest <selection> --given-json=report.json` writes one file with four top-level keys:

```
metadata      project, timestamp, commit_sha, duration_ms
scenarios[]   one entry per @scenario (parametrized cases grouped into one)
glossary      {terms: [...]} — every declared term, referenced or not
stories[]     one entry per story(...)
```

## Scenario

| Field | Meaning |
|---|---|
| `narration.text` | The scenario name (grouped template for parametrized scenarios) — for a *step* in a grouped parametrized scenario this is the template too (`the drink costs {price} euros`), not the first case's rendering |
| `module` | Python module the test lives in |
| `tags[]` | `tags=` from `@scenario` — report metadata, **not** pytest marks |
| `status` | `passed` / `failed` / `skipped` |
| `steps[]` | Recursive step tree (see below) |
| `parameters` | `null`, or `{columns: [{id, name, kind}], cases: [{values, status, error}]}` for parametrized scenarios. `kind` is `param` / `derived` / `attachment`; a case's `values` is positionally aligned with `columns`, and an `attachment` cell is an `{label, content, content_type}` object (or `null` for a case with no value) |
| `error` | `null`, or `{message, frames: [{path, lineno, func, code}]}` |
| `source` | `{relpath, line}` — the test function's definition site |
| `story_id` / `activity_ids` | Story binding from `@scenario(..., story=...)` |

## Step

`{phase, narration, status, children[], attachments[], error, activity_ids, fixture_name}` — `phase` is `given`/`when`/`then`; `children` nests sub-steps; `fixture_name` is set when the step came from a `@given`-decorated fixture. An entry in `attachments[]` is either `{label, content, content_type}` or, when the payload varies across parametrize cases, `{label, content_type, column_id}` — a content-less pointer at the column that holds every case's payload.

`narration.parts[]` is the structured step text; each part is one of:

- `{value: "literal text"}` — plain text or an interpolated non-term value
- `{term_id, display, expression, param_column}` — a glossary term reference
- `{name, column_id}` — a placeholder for the column `column_id` in a grouped parametrized scenario

Term ids and story ids are slugs: lowercased, non-alphanumeric runs → `-` (`Late fee` → `late-fee`).

## Glossary term

`{id, kind, canonical, definition, source}` — `kind` is `actor` / `verb` / `object`, or `null` for kindless terms.

## Story

`{id, title, activities: [{id, paths: [{parts: [{term_id, display}]}]}], source}` — activity ids are what `activity_ids` on scenarios and steps point at.

## Recipes

```bash
# All scenario names with status and location
jq -r '.scenarios[] | .status + "  " + .narration.text
       + " — " + .source.relpath + ":" + (.source.line|tostring)' report.json

# Failing scenarios with the failure message
jq -r '.scenarios[] | select(.status == "failed")
       | .narration.text + ": " + .error.message' report.json

# Scenarios whose narration references a term (any step depth: use recursion for nested steps)
jq -r '.scenarios[] | select([.. | .term_id? // empty] | index("waitlist"))
       | .narration.text' report.json

# Scenarios by tag
jq -r '.scenarios[] | select(.tags | index("validation")) | .narration.text' report.json

# Scenarios implementing a story
jq -r '.scenarios[] | select(.story_id == "lend-and-return-a-book") | .narration.text' report.json

# Every term with its definition
jq -r '.glossary.terms[] | .canonical + ": " + .definition' report.json

# Every derived/attachment column a parametrized scenario grew
jq -r '.scenarios[] | select(.parameters)
       | .narration.text + ": "
       + ([.parameters.columns[] | select(.kind != "param") | .name] | join(", "))' report.json

# One parametrize case's attachment payloads
jq -r '.scenarios[] | select(.parameters) | .parameters as $p
       | $p.cases[0].values | to_entries[]
       | select(.value | type == "object")
       | $p.columns[.key].name + ": " + .value.content' report.json
```
