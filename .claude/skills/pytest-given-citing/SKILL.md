---
name: pytest-given-citing
description: Use when `pytest-given citations check` reports a finding, or when citing pytest-given scenarios, tags or stories from a Markdown document such as a design spec
---

# Citing pytest-given scenarios

A **citation** is a Markdown link into the HTML report, led by a status glyph — `✅` passed, `❌` failed, `🟠` skipped (for a story: no scenario yet), `🔵` xfailed, `❓` not in the report — and, for a tag or story, followed by a summary:

    ✅ [A renamed test keeps its citation](https://example.org/report.html#scenario=tests/test_x.py::test_y)
    🔵 [spec/checkout](https://example.org/report.html#tag=spec/checkout) (5 ✅ · 2 🔵)

A **plain report link** has no glyph: it keeps its own wording and claims only that its target exists.

`pytest-given citations check DOCS… --report report.json` verifies every report link; `citations update` (same arguments) fixes what the first triage row lists, and exits 1 while any other finding remains. Both read the JSON report of a run of **every** scenario — `pytest -m pytest_given --given-json=report.json` — and take a target the run left out as gone. A link is a report link when its URL is the one the JSON stores (`given_report_url`) or `--report-url` names; a relative link counts only with `--report-path`, where the HTML report sits in the repository.

## Triage

| Finding | What to do |
|---|---|
| Stale glyph or text; stale or missing summary; slug or `[case]` in a fragment; a renamed test whose title one scenario still has | Run `citations update`. |
| Cited target fails | The document claims what doesn't hold now. Fix the code, or, if the claim itself is outdated, tell the human: the prose is theirs. |
| Summary after a scenario citation | Delete it, unless the author wrote it as prose — then reword it so it no longer reads as a summary. |
| Mistyped citation | Fix the fragment to `#scenario=<node id>`, `#tag=<tag>` or `#view=stories&story=<id>`, or drop the glyph if a plain link is meant. |
| Target not in the report | Rule out the report first: a partial run, or one from another rootdir (node ids are relative to it), loses many targets at once. Then follow [references/repair.md](references/repair.md). |

## Writing citations

You cannot click a copy button. Write a placeholder — a typed `?` glyph and empty text — and let `update` fill it:

    ? [](https://example.org/report.html#scenario=tests/test_x.py::test_y)

Choose the target as in a repair: read its steps and body against the prose that cites it; a matching title is not enough.

- Write the glyph and link bare: `**✅**` or `*[…](…)*` no longer reads as a citation.
- On a versioned docs site, link the report relatively (`../examples/report.html#tag=…`), so each version's page opens its own report.
- Give a piece of work one tag (`spec/<slug>`) and cite that, not a broad area tag, whose summary every later scenario changes; link an area tag with a plain report link.
- Link a scenario whose title interpolates a per-run value (a temporary path) with a plain report link: its citation would be stale on every run.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
