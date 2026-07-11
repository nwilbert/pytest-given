# Report JSON shape

`pytest <selection> --given-json=report.json` writes one file with four top-level keys:

```
metadata      project, timestamp, commit_sha, duration_ms
scenarios[]   one entry per @scenario (parametrized cases merged into one)
glossary      {terms: [...]} — every declared term, referenced or not
stories[]     one entry per story(...)
```

## Scenario

| Field | Meaning |
|---|---|
| `narration.text` | The scenario name (merged template for parametrized scenarios) |
| `module` | Python module the test lives in |
| `tags[]` | `tags=` from `@scenario` — report metadata, **not** pytest marks |
| `status` | `passed` / `failed` / `skipped` |
| `steps[]` | Recursive step tree (see below) |
| `parameters` | `null`, or `{names: [...], cases: [{values, status, error}]}` for parametrized scenarios |
| `error` | `null`, or `{message, frames: [{path, lineno, func, code}]}` |
| `source` | `{relpath, line}` — the test function's definition site |
| `story_id` / `activity_ids` | Story binding from `@scenario(..., story=...)` |

## Step

`{phase, narration, status, children[], attachments[], error, activity_ids, fixture_name}` — `phase` is `given`/`when`/`then`; `children` nests sub-steps; `fixture_name` is set when the step came from a `@given`-decorated fixture.

`narration.parts[]` is the structured step text; each part is one of:

- `{value: "literal text"}` — plain text or an interpolated non-term value
- `{term_id, display, expression, param_column}` — a glossary term reference
- `{name}` — a parametrize placeholder in a merged parametrized scenario

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
```
