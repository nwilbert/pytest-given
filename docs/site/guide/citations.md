# Citations

A design spec, a README or any other Markdown document can cite a scenario, a tag or a story of the HTML report by a link that stays true. A **citation** leads with its target's status glyph and, for a tag or story, ends with a summary:

```markdown
✅ [A renamed test keeps its citation](https://example.org/report.html#scenario=tests/test_x.py::test_y)
🔵 [Cancel a Booking](https://example.org/report.html#view=stories&story=cancel-a-booking) (3 ✅ · 1 🔵)
```

Live, against this site's example reports:

- 🔵 [Cancel a Booking](../examples/hotel-booking.html#view=stories&story=cancel-a-booking) (2 ✅ · 1 🔵)
- ✅ [spec/citations](../examples/self-report.html#tag=spec/citations) (3 ✅)

`pytest-given citations check` holds every such link to a JSON report, and `pytest-given citations update` rewrites a citation to what the report now says.

## Glyphs and summaries

| Glyph | Meaning |
|---|---|
| ✅ | passed |
| ❌ | failed |
| 🟠 | skipped — or, for a story, no scenario yet |
| 🔵 | expected failure |
| ❓ | not in the report |

A tag or story reads `❌` if any of its scenarios failed, else `🔵` if any is an expected failure, else `✅` if any passed, else `🟠`. Its summary counts its scenarios per status, `(5 ✅ · 2 🔵)`; a story no scenario belongs to yet reads `(no scenarios)`. A tag citation counts the scenarios carrying the tag or one below it (`spec` counts `spec/citations`), as its link opens them.

A link without a glyph is a plain **report link** — the form for a sentence in its own words ("rejecting [divergent cases](…#scenario=…) keeps the tree honest"). It claims only that its target exists, and the check owns none of its text.

## Copying a citation

Give the report the public URL it will be served from:

```toml
[tool.pytest]
given_report_url = "https://docs.example.org/report.html"
```

Its scenario cards, story headers and Tags sidebar rows then show a **Copy Markdown citation** button beside the copy-link one. The button links the configured URL rather than the page's own address, since the report you draft a document against is seldom the hosted one. A report without the setting shows no buttons.

## Writing one by hand

Type a `?` as the glyph and leave the text empty, then run `citations update`:

```markdown
? [](https://docs.example.org/report.html#scenario=tests/test_x.py::test_y)
```

The fragment is `#scenario=<node id>`, `#tag=<tag>` or `#view=stories&story=<story id>`. A grouped parametrized scenario is cited by its node id without the `[case]` part.

## Checking in CI

```bash
pytest -m pytest_given --given-json=report.json
pytest-given citations check docs/ README.md --report report.json
```

Put the check in a required CI gate: a citation is a snapshot of the report at its commit, and only a gate keeps the snapshot on your main branch current. Feed it a run of **every** scenario — the check cannot tell a test the run never collected from a deleted one. See [Standalone CLI](../cli.md#citations) for the flags and exit codes.

`citations update` rewrites stale glyphs, link texts and summaries, a slug or `[case]` in a fragment, and the node id of a renamed test whose scenario title survived. It marks a citation whose target is gone `❓`, keeping its URL and text, and the citation recovers once the target is back. What it cannot fix stays a finding: a cited failure, a target no longer in the report, a summary after a scenario citation. The bundled [`pytest-given-citing` skill](../ai-agents.md#agent-skills) walks an agent through those.

## Keeping citations quiet

- **Link a versioned site's reports relatively** (`../examples/report.html#tag=…`), so each version of a page opens its own version's report, and pass `--report-path` (where the docs build puts the report) to the check.
- **Cite a tag that belongs to one piece of work**, like `spec/<slug>`; a broad area tag's summary changes with every new scenario, so link that with a plain report link.
- **Write the glyph and link bare.** `**✅** […](…)` or `✅ *[…](…)*` no longer reads as a citation.
- **Keep the rootdir fixed.** A node id is relative to pytest's rootdir, so running the suite from another one shifts every scenario citation.
- **Link a scenario whose title interpolates a per-run value** (a temporary path) with a plain report link; its citation would be stale on every run.
