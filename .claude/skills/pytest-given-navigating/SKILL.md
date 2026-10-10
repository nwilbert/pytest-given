---
name: pytest-given-navigating
description: Use when exploring or onboarding to a codebase whose tests use pytest-given (@scenario tests, a glossary, domain stories) — to learn what the system does, find which scenarios cover a behavior, tag, or glossary term, or see what currently fails
---

# Navigating a codebase through its pytest-given artifacts

The test suite describes itself. The rendered scenarios are a behavioral spec, the glossary maps the domain, and the stories map how actors interact. Read the narration instead of working backwards from test bodies. Answer every "which scenarios …?" question from the structured report, not with grep: term refs go through glossary handles, so a text search misses some or counts them twice.

## Orientation: first contact

1. **Look for an existing report.** A `*.md` or `*.json` report that is committed or published by CI (often under `given-report/`) is the spec of the last run. Reading it costs nothing: no test environment, no suite run. To re-render a saved JSON report as Markdown, run `pytest-given report <data.json> --format md`. Render a fresh one only when there is none, or when the question is about *this* checkout.
2. **Read the glossary first.** Read `GLOSSARY.md`, or the `Glossary()` or `FileGlossary` declaration the tests import. It holds the domain vocabulary, with definitions.
3. **Render the spec.** `pytest <selection> --given-md` runs the selected tests and prints a Markdown spec of every scenario to stdout, between `<!-- pytest-given:md:start -->` and `:end`. The ``file.py:line::test_name`` line under each heading leads back to the code. Select tests with pytest's own arguments (`-k`, node ids, `--lf`); the report covers whatever ran. When a full run is slow, add `-m pytest_given`: the report holds only scenarios, so leaving the plain tests out changes nothing in it.
4. **Read the stories.** The `story(...)` definitions are the flows between actors that the scenarios implement. `stories=` on a `@scenario`, or a pin on a scenario or a step, links a scenario to them.

## Structured questions: JSON and jq

For questions like "which scenarios are tagged X, reference term Y, fail, or implement story Z", write the data file and query it. The full shape and more recipes are in [references/report-json.md](references/report-json.md).

```bash
pytest <selection> --given-json=report.json
jq -r '.scenarios[] | select(.tags | index("validation"))
       | .narration.text + " — " + .source.relpath + ":" + (.source.line|tostring)' report.json
```

- By status: `select(.status == "failed")`. The message and frames are in `.error`. But a **parametrized scenario's `.error` is `null`**: its failures are in each case's `.parameters.cases[].error`. The reference's recipe reads both.
- By term: `select([.. | .term_id? // empty] | index("waitlist"))`. The search is recursive, because steps nest and a term ref at any depth counts. Term ids are slugs: the name in lowercase, with every non-alphanumeric character replaced by `-` (`Late fee` becomes `late-fee`).
- By story: read the story's `scenario_ids` in `.coverage[]`. Don't use `.story_ids`, which misses a scenario that only pins the story. Story ids are slugs too.

## Traps

- **Scenario tags are report metadata, not pytest marks.** `pytest -m <tag>` selects nothing. That is expected; the suite isn't broken. Filter tags through the JSON report, or read them in the Markdown output.
- **Put a bare `--given-md` or `--given-json` last on the command line**, or use the `=PATH` form. Otherwise, a path-like argument right after the bare flag is taken as its output path, and that changes what runs.
- **The Markdown report contains only scenarios.** The glossary and stories appear in the HTML report (`--given-html`) and in the JSON (`.glossary.terms[]`, `.stories[]`).

## When to go to the code

Go to the code to change behavior, or to check one scenario's narration against its body. Jump straight to the scenario's `source.relpath` and `source.line` from the JSON, or to the ``file.py:line::test_name`` line under each Markdown heading, instead of searching for it.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
