---
name: pytest-given-citing
description: Use when `pytest-given citations check` reports a finding, or when citing pytest-given scenarios, tags or stories from a Markdown document such as a design spec
---

# Citing pytest-given scenarios

A **citation** is a Markdown link into the HTML report, led by a status glyph — `✅` passed, `❌` failed, `🟠` skipped, `🔵` xfailed, `❓` not in the report — and, for a tag or story, followed by a summary:

    ✅ [A renamed test keeps its citation](https://example.org/report.html#scenario=tests/test_x.py::test_y)
    🔵 [spec/checkout](https://example.org/report.html#tag=spec/checkout) (5 ✅ · 2 🔵)

A **report link** without a glyph is a plain one: it keeps its own wording and claims only that its target exists.

`pytest-given citations check DOCS… --report report.json` verifies every report link; `citations update` (same arguments) rewrites glyphs, link text, summaries and fragments to match. Both read the JSON report of a run of **every** scenario — `pytest -m pytest_given --given-json=report.json` — since a partial run reads every target outside it as gone.

## Triage

| Finding | What to do |
|---|---|
| Stale glyph, text or summary; slug or `[case]` in a fragment; a renamed test whose title survived | Run `citations update`. |
| Failed target | Nothing in the document: the test fails, and that is the problem to fix or report. |
| Summary after a scenario citation | Delete it, unless the author wrote it as prose — then reword it so it no longer reads as a summary. |
| Mistyped citation | Fix the fragment to `#scenario=<node id>`, `#tag=<tag>` or `#view=stories&story=<id>`, or drop the glyph if a plain link is meant. |
| Target not in the report | Check the report comes from a run of every scenario, then follow [references/repair.md](references/repair.md). |

## Writing citations

You cannot click a copy button. Write a placeholder — a typed `?` glyph and empty text — and let `update` fill it:

    ? [](https://example.org/report.html#scenario=tests/test_x.py::test_y)

Choose the target as in a repair: read its steps and body against the prose that cites it; a matching title is not enough.

- Write the glyph and link bare: `**✅**` or `*[…](…)*` no longer reads as a citation.
- On a versioned docs site, link the report relatively (`../examples/report.html#tag=…`), so each version's page opens its own report.
- Give a piece of work one tag (`spec/<slug>`) and cite that, not a broad area tag, whose summary every later scenario changes; link an area tag with a plain report link.
- Link a scenario whose title interpolates a per-run value (a temporary path) with a plain report link: its citation would be stale on every run.
