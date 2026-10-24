---
name: pytest-given-navigating
description: Use when exploring or onboarding to a codebase whose tests use pytest-given (@scenario tests, a glossary, domain stories) — to learn what the system does, find which scenarios cover a behavior, tag, or glossary term, or see what currently fails
---

# Navigating a codebase through its pytest-given artifacts

The test suite describes itself. The rendered scenarios are a behavioral spec, the glossary maps the domain, and the stories map how actors interact. Read the narration instead of working backwards from test bodies. Answer every "which scenarios …?" question from the structured report, not with grep: term refs go through glossary handles, so a text search misses some or counts them twice.

## Orientation: first contact

1. **Look for an existing report.** A `*.md` or `*.json` report that is committed or published by CI (often under `given-report/`) is the spec of the last run. Reading it costs nothing: no test environment, no suite run. To re-render a saved JSON report as Markdown, run `pytest-given report <data.json> --format md`. Render a fresh one only when there is none, or when the question is about *this* checkout. A report covers only what its run selected, so a local one may be partial: compare the test files it lists (`[.scenarios[].source.relpath] | unique`) with the suite's, and its `metadata.commit_sha` with HEAD, before treating it as the whole spec.
2. **Read the glossary first.** Read `GLOSSARY.md`, or the `Glossary()` or `FileGlossary` declaration the tests import. It holds the domain vocabulary, with definitions.
3. **Render the spec.** `pytest <selection> --given-md` runs the selected tests and prints a Markdown spec of every scenario to stdout, between `<!-- pytest-given:md:start -->` and `:end`. The ``file.py:line::test_name`` line under each heading leads back to the code. Select tests with pytest's own arguments (`-k`, node IDs, `--lf`); the report covers whatever ran. When a full run is slow, add `-m pytest_given`: the report holds only scenarios, so leaving the plain tests out changes nothing in it.
4. **Read the stories.** The `story(...)` definitions are the flows between actors that the scenarios implement. `stories=` on a `@scenario`, or a pin on a scenario or a step, links a scenario to them.

## Structured questions: JSON and jq

For questions like "which scenarios are tagged X, reference term Y, fail, or implement story Z", write the data file and query it. The full shape and more recipes are in [references/report-json.md](references/report-json.md).

"Is this area covered?" usually spans several glossary terms, a tag and a directory. Match any of them:

```bash
pytest <selection> --given-json=report.json
jq -r '.scenarios[] | select(([.. | .term_id? // empty] | any(IN("late-fee", "waitlist")))
         or (.tags | any(startswith("billing")))
         or (.source.relpath | startswith("tests/billing/")))
       | .narration.text + " — " + .source.relpath + ":" + (.source.line|tostring)' report.json
```

The reference has recipes by status, words, term, tag and story. Use them rather than writing your own: a parametrized scenario keeps its failures per case, term refs nest at any depth, and `.story_ids` misses a scenario that only pins a story. Without jq, load the JSON with Python's `json` module. The recipes' logic carries over.

These queries find only what exists. For where an area has no scenario, the reviewing skill's [completeness.md](../pytest-given-reviewing/references/completeness.md) lists the undecorated tests and the test files without a single scenario.

## Traps

- **Scenario tags are report metadata, not pytest marks.** `pytest -m <tag>` selects nothing. That is expected; the suite isn't broken. Filter tags through the JSON report, or read them in the Markdown output.
- **Put a bare `--given-md` or `--given-json` last on the command line**, or use the `=PATH` form. Otherwise, a path-like argument right after the bare flag is taken as its output path, and that changes what runs.
- **The Markdown report contains only scenarios.** The glossary and stories appear in the HTML report (`--given-html`) and in the JSON (`.glossary.terms[]`, `.stories[]`).
- **Don't hand-edit a citation** (`✅ [title](…#scenario=…)` in a Markdown document): `pytest-given citations update` rewrites its glyph, link text, summary and narrated body from the report. Writing or repairing one is the `pytest-given-citing` skill's job. To learn why a scenario exists, `citations check --covering <node ID>` lists the documents that may cite it, and `--list` every document's report links.

## When to go to the code

Go to the code to change behavior, or to check one scenario's narration against its body. Jump straight to the scenario's `source.relpath` and `source.line` from the JSON, or to the ``file.py:line::test_name`` line under each Markdown heading, instead of searching for it. A project that sets `given_md_lines = false` shows only ``file.py::test_name``; add `--given-md-lines` for the line. To read a scenario's narration beside its body, add `--given-md-source`: each scenario then ends with its test function.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
