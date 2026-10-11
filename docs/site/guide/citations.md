# Citations

A design spec, a README or any other Markdown document can link to a scenario, a tag or a story in the HTML report. pytest-given checks these links against the JSON report of a test run, so they keep pointing at something that exists, and keeps their text in line with what that run found.

It reads two kinds of report link:

- A **citation** starts with a status glyph: `✅ [title](…)`. pytest-given owns everything in it — the glyph, the link text and, for a tag or story, a summary of its scenarios — and `pytest-given citations update` keeps all of it current.
- A **plain report link** has no glyph, so it can sit inside your own sentence: "rejecting [divergent cases](…#scenario=…) keeps the tree honest". pytest-given only checks that its target still exists and never touches its text.

```markdown
✅ [A renamed test keeps its citation](https://example.org/report.html#scenario=tests/test_x.py::test_y)
🔵 [Cancel a Booking](https://example.org/report.html#view=stories&story=cancel-a-booking) (3 ✅ · 1 🔵)
```

Live, against this site's example reports:

- 🔵 [Cancel a Booking](../examples/hotel-booking.html#view=stories&story=cancel-a-booking) (2 ✅ · 1 🔵)
- ✅ [spec/citations](../examples/self-report.html#tag=spec/citations) (3 ✅)

## How it fits together

Citations link to the HTML report you publish, but the `pytest-given citations` commands read a JSON report and run no tests. So a citation is only right if the two reports match: write both from the same run.

1. **Run** the scenarios, writing both reports:

    ```bash
    pytest --given-json=report.json --given-html=report.html
    ```

2. **Publish** `report.html` at the URL your citations link to, the `given_report_url` setting. How depends on your hosting; with a docs site, copy it in before the site build:

    ```bash
    cp report.html docs/report.html
    ```

3. **Cite** scenarios, tags and stories by [copying a citation from the report](#copying-it-from-the-report), or by [writing one by hand](#writing-it-by-hand).

4. **Update** your documents after the report changes. Pass the Markdown files that cite the report, or directories to search for them — here everything under `docs/` and the project's `README.md`:

    ```bash
    pytest-given citations update docs/ README.md --report report.json
    ```

5. **Check** in CI that the documents match the report:

    ```bash
    pytest-given citations check docs/ README.md --report report.json
    ```

The run must include every scenario a document cites, because the commands can't tell a scenario the run left out from one that was deleted. Add the flags to your usual test run, or pass `-m pytest_given` to run only the scenarios. If you kept only the JSON report, `pytest-given report report.json -o report.html` renders the matching HTML from it.

## Glyphs and summaries

| Glyph | Meaning |
|---|---|
| ✅ | passed |
| ❌ | failed |
| 🟠 | skipped — or, for a story, no scenario yet |
| 🔵 | expected failure |
| ❓ | not in the report |

A tag or story reads `❌` if any of its scenarios failed, else `🔵` if any is an expected failure, else `✅` if any passed, else `🟠`.

Its summary counts its scenarios per status, as in `(5 ✅ · 2 🔵)`, or reads `(no scenarios)` for a story nothing covers yet. A tag counts the scenarios below it too, as its link opens them: `spec` counts those tagged `spec/citations`. A scenario citation has no summary.

## Adding a citation

### Copying it from the report

Set `given_report_url` to the public URL your HTML report is served from, such as where CI publishes it:

```toml
[tool.pytest]
given_report_url = "https://docs.example.org/report.html"
```

Then write the HTML report as usual, for example with `pytest --given-html`. To set the URL for one run instead, pass `--given-report-url=URL`. The URL is also stored in the JSON report, so `pytest-given report` re-renders the buttons from it, and the `pytest-given citations` commands know which links point at the report.

The report now shows a **Copy Markdown citation** button on scenario cards, story headers and Tags sidebar rows. The copied link uses the configured URL rather than the address you opened the report at, so you can copy citations from a local report and still get links to the published one. Without the setting, there are no buttons.

### Writing it by hand

Write `?` as the glyph, leave the link text empty, and let `pytest-given citations update` fill in the rest:

```markdown
? [](https://docs.example.org/report.html#scenario=tests/test_x.py::test_y)
```

The part after `#` names the target:

| Target | Fragment |
|---|---|
| Scenario | `#scenario=<node id>` — for a parametrized scenario, without the `[case]` part |
| Tag | `#tag=<tag>` |
| Story | `#view=stories&story=<story id>` |

## Updating citations

Pass the documents or directories to update, and the JSON report from [the run that wrote your HTML report](#how-it-fits-together):

```bash
pytest-given citations update docs/ README.md --report report.json
```

It rewrites what the report now says:

- a citation's glyph, link text and summary;
- the fragment of any report link that uses a scenario's slug or a `[case]`, to its node id;
- the node id of a renamed test, when exactly one scenario still has the citation's title.

It can't fix everything. These stay as findings for you to resolve, and the command exits 1:

- **A target that is no longer in the report.** The citation's glyph becomes `❓`, its URL and text stay, and it recovers on its own once the target is back.
- **A cited target that fails.** The document claims something that doesn't hold right now: fix the code, or change what the document says.
- **A summary after a scenario citation**, which takes none.

The bundled [`pytest-given-citing` skill](../ai-agents.md#agent-skills) walks an agent through these.

## Checking in CI

`pytest-given citations check` takes the same arguments, writes nothing, and exits 1 on any finding, including what `pytest-given citations update` would rewrite:

```bash
pytest --given-json=report.json --given-html=report.html
pytest-given citations check docs/ README.md --report report.json
# then publish report.html at given_report_url
```

Make it a required CI check. A citation records the report as of its commit, and only a required check keeps the citations on your main branch current. Publish the HTML report from the run the check read, so a reader who follows a citation finds what it says.

If you commit the reports instead, write the JSON and HTML report together whenever you regenerate them, and let CI run only the check against the committed JSON. [Standalone CLI](../cli.md#citations) lists the flags and exit codes.

## Keeping the check accurate

These habits keep `pytest-given citations check` from failing on a document nothing is wrong with, or from skipping a citation it should check:

- **Run pytest from the same rootdir.** A node id is relative to pytest's rootdir, so a run from another one breaks every scenario citation at once.
- **Use a plain report link for a scenario whose title contains a per-run value**, such as a temporary path. Its citation's link text would be stale after every run.
- **Leave the glyph and link unformatted.** In `**✅** […](…)` or `✅ *[…](…)*` pytest-given doesn't see a citation, only a plain report link, so the glyph is never updated.
- **On a versioned docs site, link the report relatively**, as in `../examples/report.html#tag=…`, so each version of a page opens its own version's report. Pass `--report-path`, where your docs build puts the report, so the commands recognize these links.
