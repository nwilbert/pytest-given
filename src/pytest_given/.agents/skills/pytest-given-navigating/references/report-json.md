# Report JSON shape

`pytest <selection> --given-json=report.json` writes one file with five top-level keys: `$schema`, `metadata`, `scenarios[]` (one entry per `@scenario`, parametrized cases grouped into one), `glossary` (`null` on a suite with no glossary) and `stories[]`. The JSON Schema at the `$schema` URL lists every field and its type. This page holds what the field names don't say.

`metadata.schema_version` changes with every change to this shape, and `pytest-given report` refuses a report of another one. A delta JSON (`metadata.kind` is `"delta"`) is not a report: `pytest-given delta <file>` renders it.

## Scenarios and steps

- **A scenario's `id` identifies no case.** A grouped parametrized scenario keeps the suffix of its first collected case (`tests/test_x.py::test_y[1-False]`), so match on a prefix, not on equality. Its `module`, `tags` and `source` come from that case too, but its `steps` from the first case that *passed*. Each case's node ID and status are in `parameters.cases[]`.
- **On a parametrized scenario, `error` is always `null`**, even when it failed. Its errors are in each case's `parameters.cases[].error`. A step has no status or error of its own.
- **`narration.text` keeps its `**`, `*` and `` ` `` markers as written**, in titles and steps alike, so strip them before you search for words. In a grouped scenario, the title and the steps hold the template (`the drink costs {price} euros`), not the first case's text.
- **`tags[]` are report metadata, not pytest marks.**
- **`story_ids` lists only the stories of `stories=`.** A scenario that pins a sentence of a story it doesn't name is missing from it. `pins` is `null` when nothing pins and `[]` when pinning turned matching off, on a scenario and a step alike.
- **A parameter cell depends on its column's `kind`.** A case's `values` follow the order of `parameters.columns`. A `param` cell is the parametrize value. A `derived` cell is the string the case rendered, or a JSON Boolean for a local worded with a Boolean phrase. An `attachment` cell is a `{label, content, content_type}` object. Either is `null` for a case without a value. An attachment whose content varies between cases has no `content` in its step: its `column_id` names the column that holds it. `group_parametrized=False` gives one scenario per case, each with `parameters: null`.

`narration.parts[]` holds a text in structured form. Match a part by its keys, not by position:

- `{value}`: plain text.
- `{rendered, expression, format_spec, conversion}`: a t-string interpolation with the same value in every case. In a `group_parametrized=False` title, the case ID in the trailing brackets is one too, with an empty `expression`.
- `{term_id, display, expression}`: a term ref.
- `{name, column_id, format_spec, conversion}`: a placeholder for a parameter column. One whose `format_spec` holds Boolean phrases (`a|b`) reads `{a / b}`, and its column holds the Booleans.

Term ids and story ids are slugs: the name in lowercase, with each run of non-alphanumeric characters replaced by `-` (`Late fee` becomes `late-fee`).

## Glossary and stories

- A term's `kind` is `actor`, `activity`, `object` or `null`.
- A term's `definition` is `null` or `{text, parts}`. `parts` split the text into `{value}` literals and a `{term_id, display, expression}` term ref for each definition ref.
- A story sentence's clause part is `{term_id, display}` or `{text}`, a bare word that has no id and never counts for coverage: filter parts on `term_id`.

## Story coverage

Which scenarios cover each story sentence is not in the file. `pytest-given coverage report.json` prints a JSON array of `{story_id, sentence_id, tracked, scenario_ids}`, one per sentence of every story, and exits 1 when a tracked sentence has no scenario. `tracked: false` marks a sentence with fewer than two glossary terms that no pin covers: a gap in the vocabulary, not in the tests. **Read coverage from here instead of recomputing it from `steps[]`.** The rule works step by step, needs two terms per sentence, and lets pins replace narration matching.

## Recipes

```bash
# All scenario titles with status and location
jq -r '.scenarios[] | .status + "  " + .narration.text
       + " — " + .source.relpath + ":" + (.source.line|tostring)' report.json

# Failing scenarios with the failure message — a parametrized scenario's
# `.error` is null; its failures live per case, so read both
jq -r '.scenarios[] | select(.status == "failed")
       | .narration.text + ": "
       + (.error.message
          // ([.parameters.cases[] | select(.status == "failed")
              | .id[(.id | index("[")):] + " " + .error.message]
             | join("; ")))' report.json

# Expected failures with their reasons — planned behavior not yet working
jq -r '.scenarios[] | select(.status == "xfailed")
       | .narration.text + (if .xfail_reason then " — " + .xfail_reason else "" end)' report.json

# Scenarios whose title or step text has some words, Markdown markers stripped
jq -r '.scenarios[] | select([.. | .narration?.text? // empty | gsub("[*`]"; "") | ascii_downcase]
       | any(contains("late fee")))
       | .narration.text' report.json

# Scenarios whose narration references a term (any step depth: use recursion for nested steps)
jq -r '.scenarios[] | select([.. | .term_id? // empty] | index("waitlist"))
       | .narration.text' report.json

# Scenarios by tag, or by a tag prefix (`ticket/ABC-123` nests under `ticket`)
jq -r '.scenarios[] | select(.tags | index("validation")) | .narration.text' report.json
jq -r '.scenarios[] | select(.tags | any(startswith("ticket/"))) | .narration.text' report.json

# Scenarios covering a story (node IDs) — `story_ids` misses one that only pins it
pytest-given coverage report.json |
  jq -r '[.[] | select(.story_id == "lend-and-return-a-book") | .scenario_ids[]] | unique[]'

# Uncovered sentences (tracked ones no scenario covers), as story#sentence
pytest-given coverage report.json |
  jq -r '.[] | select(.tracked and .scenario_ids == []) | .story_id + "#" + (.sentence_id|tostring)'

# Which scenarios cover one sentence
pytest-given coverage report.json |
  jq -r '.[] | select(.story_id == "lend-and-return-a-book" and .sentence_id == 3) | .scenario_ids[]'

# A story's sentences as text, one clause after another
jq -r '.stories[] | select(.id == "cancel-a-booking") | .sentences[]
       | (.id|tostring) + ". " + ([.clauses[] | [.parts[] | .display // .text] | join(" ")] | join(" / "))' report.json

# Every term with its definition
jq -r '.glossary.terms[] | select(.definition) | .canonical + ": " + .definition.text' report.json

# The terms one term's definition names
jq -r '.glossary.terms[] | select(.id == "booking") | .definition.parts[]
       | select(.term_id) | .term_id' report.json

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
