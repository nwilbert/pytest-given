---
name: pytest-given-navigating
description: Use when exploring or onboarding to a codebase whose tests use pytest-given (@scenario tests, a glossary, domain stories) — to learn what the system does, find which scenarios cover a behavior, tag, or glossary term, or see what currently fails
---

# Navigating a codebase through its pytest-given artifacts

The test suite narrates itself: rendered scenarios are a behavioral spec, the glossary is the domain map, stories are the interaction map. Read the narration instead of reverse-engineering test bodies, and answer every "which scenarios …?" question from the structured report instead of grepping — term references flow through glossary handles, so text search misses or double-counts them.

## Orientation — first contact

1. **Look for an existing report.** A committed or CI-published `*.md` / `*.json` report (often under `given-report/`) is the spec of the last run and costs nothing: no test environment, no suite run. Re-render a saved JSON as Markdown with `pytest-given report <data.json> --format md`. Render fresh only when there is none, or the question is about *this* checkout.
2. **Glossary first.** Read `GLOSSARY.md` (or the `Glossary()` / `FileGlossary` declaration the tests import): the domain vocabulary, with definitions.
3. **Render the spec.** `pytest <selection> --given-md` runs the selected tests and prints a Markdown spec of every scenario to stdout, fenced between `<!-- pytest-given:md:start -->` and `:end`. The output explains itself; the ``file.py:line::test_name`` line under each heading is the way back to the code. Select with pytest's own args (`-k`, node ids, `--lf`); the renderer narrates whatever ran.
4. **Stories.** Read the `story(...)` definitions — actor-level flows the scenarios implement; `story=` on a `@scenario` links them.

## Structured questions — JSON + jq

For "which scenarios are tagged X / reference term Y / fail / implement story Z", write the data file and query it (shape and more recipes in [references/report-json.md](references/report-json.md)):

```bash
pytest <selection> --given-json=report.json
jq -r '.scenarios[] | select(.tags | index("validation"))
       | .narration.text + " — " + .source.relpath + ":" + (.source.line|tostring)' report.json
```

- By status: `select(.status == "failed")`. Message and frames are in `.error` — but a **parametrized scenario's `.error` is `null`**; its failures sit per case in `.parameters.cases[].error`. The reference's recipe reads both.
- By term: `select([.. | .term_id? // empty] | index("waitlist"))` — recursive, because steps nest and a term ref at any depth counts. Term ids are slugs (lowercased, non-alphanumeric → `-`, so `Late fee` → `late-fee`).
- By story: `select(.story_id == "lend-and-return-a-book")` (story ids are slugs too).

## Traps

- **Scenario tags are report metadata, not pytest marks.** `pytest -m <tag>` selects nothing — that is expected, not a broken suite. Filter tags via the JSON report or read them in the Markdown output.
- **Put a bare `--given-md` / `--given-json` last on the command line** (or use the `=PATH` form): a path-like token right after the bare flag is parsed as its output path, changing what runs.
- **The Markdown report contains scenarios only.** Glossary and stories render in the HTML report (`--given-html`) and live in the JSON (`.glossary.terms[]`, `.stories[]`).

## When to drop to the code

To change behavior, or to verify one scenario's narration against its body. Jump straight to the scenario's `source.relpath` + `source.line` from the JSON (or the ``file.py:line::test_name`` line under each Markdown heading) rather than searching for it.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
