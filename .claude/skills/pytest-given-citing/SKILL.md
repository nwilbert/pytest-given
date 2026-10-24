---
name: pytest-given-citing
description: Use when `pytest-given citations check` reports a citation finding, or when citing pytest-given scenarios, tags or stories from a Markdown document such as a design spec
---

# Citing pytest-given scenarios

A **citation** is a Markdown link into the HTML report, led by a status glyph — `✅` passed, `❌` failed, `🟠` skipped (for a story: no scenario yet), `🔵` xfailed, `❓` not in the report — and, for a tag or story, followed by a summary:

    ✅ [A renamed test keeps its citation](https://example.org/report.html#scenario=tests/test_x.py::test_y)
    🔵 [spec/checkout](https://example.org/report.html#tag=spec/checkout) (5 ✅ · 2 🔵)

A **narrated citation** is a scenario citation written as a `<details>` block, its `<summary>` holding the glyph and link and its body the scenario's narration.

A **plain report link** has no glyph: it keeps its own wording and claims only that its target exists.

`pytest-given citations check DOCS… --report report.json` verifies every report link. `citations update` (same arguments) fixes what the first triage row lists, and exits 1 while other citation findings remain. Both read the JSON report of a run of **every** scenario (`pytest -m pytest_given --given-json=report.json`, without xdist's `-n`); a target the run left out counts as gone. A link is a report link when its URL is the one the JSON stores (`given_report_url`) or the one `--report-url` names. A relative link counts only with `--report-path`, the HTML report's place in the repository. Both commands exit 2 when they have neither a URL nor a path, or when no document links the report: check the URL and path first.

## Triage

| Citation finding | What to do |
|---|---|
| Stale glyph, text or narration; stale or missing summary; an opening tag without `markdown="1"`; slug or `[case]` in a fragment; a renamed test whose title one scenario still has | Run `citations update`. |
| Cited target fails | The document claims what doesn't hold now. Fix the code, or, if the claim itself is outdated, tell the human: the prose is theirs. |
| Summary after a scenario citation | Delete it, unless the author wrote it as prose — then reword it so it no longer reads as a summary. |
| A tag or story citation "takes no narration" | Rewrite it as a one-line citation: only a scenario has a narration. |
| Mistyped citation | Fix the fragment to `#scenario=<node ID>`, `#tag=<tag>` or `#view=stories&story=<id>`, or drop the glyph if a plain link is meant. For a `<details>` block: a blank line above it, `<summary>` on the next line in the summary shape under Writing citations, and a `</details>` closing it on its own line. |
| Target not in the report | Rule out the report first: a partial run, or one from another rootdir (node IDs are relative to it), loses many targets at once. Then follow [references/repair.md](references/repair.md). |

## Finding what cites a scenario

`citations check --list` prints every report link, `path:line: glyph kind key`, its citation findings indented under it. `--covering <node ID>` (repeatable) keeps the links that may cite that scenario: its own citations, those of a tag or story that counts it, and every link it can't resolve. An unresolved link may be the scenario under an old node ID, or a mistyped citation of anything. Run `update` first; once `check` is clean, the list is exact. A node ID the report lacks, such as a renamed test's old one, exits 2.

## Writing citations

Citations are optional. A document such as a spec uses them to tie its prose to the code and to show the rules it describes at work. Cite only where the user asks. Where a passage cites:

- The cited scenario must not contradict the prose that cites it.
- The citations cover all the logic the passage describes: every case, not just one. A claim no test can show, such as an instruction in an agent prompt, stays uncited. Tell the user, rather than citing a scenario that only looks related.
- If the project has a glossary, the passage uses its terms consistently, as the cited scenarios do.

You cannot click a copy button. Write a placeholder — a typed `?` glyph and empty text — and let `update` fill it:

    ? [](https://example.org/report.html#scenario=tests/test_x.py::test_y)

Choose the target as in a repair: read its steps and body against the prose that cites it; a matching title is not enough.

- Narrate a scenario where the document states the behavior it demonstrates: a reader sees its steps, and a diff shows them change. A one-line citation only points at it.
- To narrate, write a `<details markdown="1">` block: a `<summary>` of the glyph and an `<a href="…#scenario=…">` with no other attribute, `</summary>` ending its line, a blank line, an empty body, `</details>` on its own line. `update` fills the body with the scenario's `--given-md` narration and rewrites it whole from then on, so write your own prose outside the block. On a Python-Markdown site, keep the block at the top level. Keep formatters off it (Prettier: `<!-- prettier-ignore-start -->` … `<!-- prettier-ignore-end -->`).
- Write the glyph and link bare: `**✅**` or `*[…](…)*` no longer reads as a citation.
- On a versioned docs site, link the report relatively (`../examples/report.html#tag=…`), so each version's page opens its own report. A copied citation links `given_report_url`: replace its URL up to the `#`.
- To cite a piece of work as a whole, give it one tag (`spec/<slug>`) and cite that. Don't cite a broad area tag, whose summary every later scenario changes: link it with a plain report link.
- Link a scenario whose title interpolates a per-run value (a temporary path) with a plain report link: its citation would be stale on every run. Narrate one only if no step or attachment holds such a value either.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
