---
name: pytest-given-navigating
description: Use when exploring or onboarding to a codebase whose tests use pytest-given (@scenario tests, a glossary, domain stories) — to learn what the system does, find which scenarios cover a behavior, tag, or glossary term, or see what currently fails
---

# Navigating a codebase through its pytest-given artifacts

The test suite narrates itself: rendered scenarios are a behavioral spec, the glossary is the domain map, stories are the interaction map. Render the narration instead of reverse-engineering test bodies, and answer every "which scenarios …?" question from the structured report instead of grepping — term references flow through glossary handles (often variables imported from a vocab module), so text search misses or double-counts them.

## Orientation — first contact

1. **Glossary first.** Read `GLOSSARY.md` (or the `Glossary()` / `FileGlossary` declaration reachable from a `conftest.py`): the domain vocabulary, with definitions.
2. **Render the spec.** `pytest <selection> --given-md` runs the selected tests and prints a Markdown spec of every scenario to stdout between `<!-- pytest-given:md:start -->` / `:end` fences — narration with `«term»` markers, a ``file.py:line::test_name`` anchor under each heading with the scenario's tags after it, and a ✓ / ✗ / ⤼ status glyph per scenario (a skipped one also carries ` · skipped` and its reason). A grouped parametrized scenario reads ` · N cases` and renders its parameter table below the steps, one row per case with its own glyph. Select with pytest's own args (`-k`, node ids, `--lf`); the renderer narrates whatever ran.
3. **Stories.** Read the `story(...)` definitions — actor-level flows the scenarios implement; `story=` on a `@scenario` links them.

## Structured questions — JSON + jq

For "which scenarios are tagged X / reference term Y / fail / implement story Z", write the data file and query it (shape and more recipes in [references/report-json.md](references/report-json.md)):

```bash
pytest <selection> --given-json=report.json
jq -r '.scenarios[] | select(.tags | index("validation"))
       | .narration.text + " — " + .source.relpath + ":" + (.source.line|tostring)' report.json
```

- By status: `select(.status == "failed")`; the failure message and frames are in `.error`.
- By term: `select([.. | .term_id? // empty] | index("waitlist"))` — recursive, because steps nest and a term ref at any depth counts. Term ids are slugs (lowercased, non-alphanumeric → `-`, so `Late fee` → `late-fee`).
- By story: `select(.story_id == "lend-and-return-a-book")` (story ids are slugs too).

## Traps

- **Scenario tags are report metadata, not pytest marks.** `pytest -m <tag>` selects nothing — that is expected, not a broken suite. Filter tags via the JSON report or read them in the Markdown output.
- **Put a bare `--given-md` / `--given-json` last on the command line** (or use the `=PATH` form): a path-like token right after the bare flag is parsed as its output path, changing what runs. A path whose suffix does not match the sink is refused up front, so the common mistake fails loudly instead of overwriting a test file.
- **The Markdown report contains scenarios only.** Glossary and stories render in the HTML report (`--given-html`) and live in the JSON (`.glossary.terms[]`, `.stories[]`).
- A ✗ scenario in the Markdown carries the failure's first message line and its innermost non-internal frame as a blockquote (a grouped one, per failing case under the table) — usually enough to place the failure. Drop to `.error` in the JSON, or rerun the node id with plain pytest, when you need the full frame list.
- Re-render a saved run without rerunning tests: `pytest-given report <data.json> --format md`.

## When to drop to the code

To change behavior, or to verify one scenario's narration against its body. Jump straight to the scenario's `source.relpath` + `source.line` from the JSON (or the ``file.py:line::test_name`` line under each Markdown heading) rather than searching for it.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
