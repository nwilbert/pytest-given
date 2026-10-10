# Report JSON shape

`pytest <selection> --given-json=report.json` writes one file with five top-level keys:

```
metadata      project, title, timestamp, pytest_version, plugin_version, commit_sha
scenarios[]   one entry per @scenario (parametrized cases grouped into one)
glossary      {terms: [...]} — every declared term, referenced or not; null on a suite with no glossary
stories[]     one entry per story(...)
coverage[]    one entry per story sentence — which scenarios cover it
```

## Scenario

| Field | Meaning |
|---|---|
| `id` | The pytest node id. A grouped parametrized scenario **keeps the suffix of its first collected case** (`tests/test_x.py::test_y[1-False]`). The suffix is not removed, so match on a prefix, not on equality. |
| `narration.text` | The scenario name. For a parametrized scenario it is the grouped template. A *step* in a grouped parametrized scenario also holds the template (`the drink costs {price} euros`), not the text of the first case. |
| `module` | The Python module the test lives in. |
| `tags[]` | `tags=` from `@scenario`. These are report metadata, **not** pytest marks. |
| `status` | `passed`, `failed`, `skipped` or `xfailed`. `xfailed` means it failed as expected, through an `xfail` mark or `pytest.xfail()`. |
| `skip_reason` | `null`, or the reason a skipped scenario shows instead of a traceback. |
| `xfail_reason` | `null`, or the reason an xfailed scenario was expected to fail. Such a scenario keeps its steps and error too. |
| `duration_ms` | The wall-clock time of the test. |
| `steps[]` | The tree of steps (see below). |
| `parameters` | `null`, or `{columns: [{id, name, kind}], cases: [{values, status, error}]}` for a parametrized scenario. `kind` is `param`, `derived` or `attachment`. A case's `values` are in the same order as `columns`. An `attachment` cell is a `{label, content, content_type}` object, or `null` for a case without a value. A scenario that declines grouping with `group_parametrized=False` has `parameters: null`, like any scenario that isn't parametrized. |
| `error` | `null`, or `{message, error_tail, frames: [{path, lineno, func, code, is_internal}]}`. `is_internal` marks a frame from `pluggy`, `_pytest` or pytest-given; such frames are kept only with `--given-all-frames`. **On a parametrized scenario, `error` is always `null`**, even when it failed. Its errors are in each case's `parameters.cases[].error`, with the same shape. |
| `source` | `{relpath, line}`: where the test function is defined. |
| `story_ids` / `pins` | `story_ids` lists the stories `@scenario(stories=...)` matches against. `pins` lists the scenario's pins as `[{story_id, sentence_id}]`: `null` when the scenario isn't pinned, `[]` when it turned matching off. A step's `pins` works the same way. |

In a grouped scenario, `id`, `module`, `tags` and `source` come from the first
*collected* case, while `steps` are built from the first case that *passed*.
So when the first case was skipped, the `id` and the step tree come from two
different cases. Neither identifies a case: read `parameters.cases[]` for the
status of each case.

## Step

A step is `{phase, narration, children[], attachments[], pins, fixture_name}`. `phase` is `given`, `when` or `then`. `children` holds nested steps. `fixture_name` is set when the step came from a fixture decorated with `@given`. A step has no status or error of its own: a failure is recorded on the scenario, and for each case in `parameters.cases[]`. An entry in `attachments[]` is either `{label, content, content_type}` or, when the content varies between parametrize cases, `{label, content_type, column_id}`. The second form has no content; it points at the column that holds each case's content.

`narration.parts[]` holds the step text in structured form. Each part is one of:

- `{value: "literal text"}`: plain text.
- `{rendered, expression, format_spec, conversion}`: a t-string interpolation whose value is the same in every case. `rendered` is the text shown, and `expression` the source code it came from.
- `{term_id, display, expression}`: a term ref.
- `{name, column_id, format_spec, conversion}`: a placeholder for the column `column_id` in a grouped parametrized scenario.

Match parts by their keys, not by position. A step's text is `value`, `rendered`, `display` or `{name}` of each part, joined in order.

Term ids and story ids are slugs: the name in lowercase, with each run of non-alphanumeric characters replaced by `-` (`Late fee` becomes `late-fee`).

## Glossary term

A term is `{id, kind, canonical, definition, source}`. `kind` is `actor`, `activity` or `object`, or `null` for a kindless term.

## Story

A story is `{id, title, sentences: [{id, name, clauses: [{parts: [...]}]}], source}`. The sentence ids are what `pins[].sentence_id` on scenarios and steps refers to. `name` is `null` for a sentence without a name. A clause part is either `{term_id, display}`, a glossary term, or `{text}`, a bare connective word. A bare word has no id and never counts for coverage, so filter parts on `term_id` instead of assuming every part has one.

## Coverage

A coverage record is `{story_id, sentence_id, tracked, scenario_ids: [...]}`. It is the same coverage per sentence that the Stories tab shows, with one record for every sentence of every story, ordered by story and then by sentence. `scenario_ids` are the node ids of the scenarios that cover the sentence. `tracked: false` marks a sentence the report can't say anything about: it has fewer than two glossary terms, and no pin covers it. That is the Stories tab's "not coverage-tracked", and it points to a gap in the vocabulary, not in the tests. **Read coverage from here instead of recomputing it from `steps[]`.** The rule works step by step, needs at least two terms per sentence, and lets pins replace narration matching. Reimplementing it gives wrong answers.

## Recipes

```bash
# All scenario names with status and location
jq -r '.scenarios[] | .status + "  " + .narration.text
       + " — " + .source.relpath + ":" + (.source.line|tostring)' report.json

# Failing scenarios with the failure message — a parametrized scenario's
# `.error` is null; its failures live per case, so read both
jq -r '.scenarios[] | select(.status == "failed")
       | .narration.text + ": "
       + (.error.message
          // ([.parameters.cases[] | select(.status == "failed")
              | "[" + (.values | map(tostring) | join(", ")) + "] " + .error.message]
             | join("; ")))' report.json

# Expected failures with their reasons — planned behavior not yet working
jq -r '.scenarios[] | select(.status == "xfailed")
       | .narration.text + (if .xfail_reason then " — " + .xfail_reason else "" end)' report.json

# Scenarios whose narration references a term (any step depth: use recursion for nested steps)
jq -r '.scenarios[] | select([.. | .term_id? // empty] | index("waitlist"))
       | .narration.text' report.json

# Scenarios by tag, or by a tag prefix (`ticket/ABC-123` nests under `ticket`)
jq -r '.scenarios[] | select(.tags | index("validation")) | .narration.text' report.json
jq -r '.scenarios[] | select(.tags | any(startswith("ticket/"))) | .narration.text' report.json

# Scenarios covering a story (node ids) — `story_ids` misses one that only pins it
jq -r '[.coverage[] | select(.story_id == "lend-and-return-a-book") | .scenario_ids[]]
       | unique[]' report.json

# Uncovered sentences (tracked ones no scenario covers), as story#sentence
jq -r '.coverage[] | select(.tracked and .scenario_ids == [])
       | .story_id + "#" + (.sentence_id|tostring)' report.json

# Which scenarios cover one sentence
jq -r '.coverage[] | select(.story_id == "lend-and-return-a-book" and .sentence_id == 3)
       | .scenario_ids[]' report.json

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
