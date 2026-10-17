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
- ✅ [spec/citations](../examples/self-report.html#tag=spec/citations) (7 ✅)

And a [narrated citation](#narrated-citations) of a scenario:

<details markdown="1">
<summary>✅ <a href="../examples/self-report.html#scenario=tests/unit/citations/test_check.py::test_update_writes_a_narrated_citations_body"><code>citations update</code> writes a narrated citation's body from the report</a></summary>

- **given** a «report» whose «scenario» has two steps
- **given** a document holding a «narrated citation» of it, copied with an empty body
    - 📎 document:
        ```
        Paying:

        <details markdown="1">
        <summary>✅ <a href="https://example.org/report.html#scenario=t.py::test_pay">Pay by card</a></summary>

        </details>
        ```
- **when** the document is updated
- **then** its body holds the scenario's narration between blank lines
    - 📎 updated document:
        ```
        Paying:

        <details markdown="1">
        <summary>✅ <a href="https://example.org/report.html#scenario=t.py::test_pay">Pay by card</a></summary>

        - **given** a card
        - **then** it is paid

        </details>
        ```
- **then** no finding remains

</details>

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

The copy button on a scenario card or story header then opens a menu: **Copy link**, **Copy citation** and, on a scenario card, **Copy narrated citation**, for a [narrated citation](#narrated-citations). On a Tags sidebar row, the button copies the tag's citation directly. A citation links to the configured URL rather than the address you opened the report at, so you can copy citations from a local report and still get links to the published one. Without the setting, the copy button copies a link, as **Copy link** does, and Tags sidebar rows have none.

### Writing it by hand

Write `?` as the glyph, leave the link text empty, and let `pytest-given citations update` fill in the rest:

```markdown
? [](https://docs.example.org/report.html#scenario=tests/test_x.py::test_y)
```

The part after `#` names the target:

| Target | Fragment |
|---|---|
| Scenario | `#scenario=<node ID>` — for a parametrized scenario, any case's node ID |
| Tag | `#tag=<tag>` |
| Story | `#view=stories&story=<story id>` |

## Narrated citations

A scenario citation written as a `<details>` block carries the scenario's narration, folded under it. A reader sees what the scenario does where it is cited, and your pull request's diff shows the behavior change. A **narrated citation** looks like this:

```markdown
<details markdown="1">
<summary>✅ <a href="https://example.org/report.html#scenario=tests/test_x.py::test_y">A renamed <code>test</code> keeps its citation</a></summary>

- **given** a «citation» of `test_y`
- **when** the test is renamed
- **then** `citations update` repoints it

</details>
```

The citation is in the `<summary>`: the glyph, then an `<a href>` with the [report link](#writing-it-by-hand) as its only attribute and the title as its link text, written as HTML. Everything below it, down to `</details>` on a line of its own, is the body. The block needs a blank line above it: `check` reports one that continues the HTML above it, such as another narrated citation's `</details>`, as mistyped. Only a scenario can be narrated, not a tag or a story.

The body reads as the scenario's section of the Markdown report (`--given-md`), minus its heading, its subtitle line (source anchor, tags, skip or xfail reason) and any error block. Nested steps indent by four spaces.

To add one, choose **Copy narrated citation** in the report's copy menu on a scenario card, paste it into your document, and run `pytest-given citations update`, which fills the empty body. From then on `update` rewrites the body to match the report, and `pytest-given citations check` fails when it differs, or when the opening tag lacks `markdown="1"`, which `update` adds, keeping any other attributes such as `open`.

On a Python-Markdown site (MkDocs, Zensical), enable `md_in_html` and keep the block at the top level of the page, not inside a list item. GitHub renders it anywhere.

## Updating citations

Pass the documents or directories to update, and the JSON report from [the run that wrote your HTML report](#how-it-fits-together):

```bash
pytest-given citations update docs/ README.md --report report.json
```

It rewrites what the report now says:

- a citation's glyph, link text and summary;
- the fragment of any report link that uses a scenario's slug or a `[case]`, to its node ID;
- the node ID of a renamed test, when exactly one scenario still has the citation's title.

It can't fix everything. These stay as findings for you to resolve, and the command exits 1:

- **A target that is no longer in the report.** The citation's glyph becomes `❓`, its URL and text stay, and it recovers on its own once the target is back.
- **A cited target that fails.** The document claims something that doesn't hold right now: fix the code, or change what the document says.
- **A summary after a scenario citation**, which takes none.
- **A tag or story written as a narrated citation**, which has no single narration.

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

- **Run pytest from the same rootdir.** A node ID is relative to pytest's rootdir, so a run from another one breaks every scenario citation at once.
- **Use a plain report link for a scenario whose title contains a per-run value**, such as a temporary path. Its citation's link text would be stale after every run.
- **Cite a tag that belongs to one piece of work**, like `spec/<slug>`. A broad area tag's summary changes with every new scenario, so link it with a plain report link.
- **Leave the glyph and link unformatted.** In `**✅** […](…)` or `✅ *[…](…)*` pytest-given doesn't see a citation, only a plain report link, so the glyph is never updated.
- **On a versioned docs site, link the report relatively**, as in `../examples/report.html#tag=…`, so each version of a page opens its own version's report. Pass `--report-path`, where your docs build puts the report, so the commands recognize these links.
- **Keep a Markdown formatter off narrated citations.** Prettier pads table columns and a two-space list-indent rule reindents nested steps, so `check` then reports the body stale. Wrap each block in ignore comments:

```markdown
<!-- prettier-ignore-start -->

<details markdown="1">
<summary>…</summary>

…

</details>

<!-- prettier-ignore-end -->
```

### Finding the citations of a changed scenario

A citation states a scenario's title and status, not what it does. When a test's behavior changes while its title and status stay, every citation of it still reads ✅ and the check stays silent, though the sentence citing it may no longer hold. List the report links that may cite it, and reread each sentence:

```bash
pytest-given citations update docs/ README.md --report report.json
pytest-given citations check docs/ README.md --report report.json \
    --covering tests/test_checkout.py::test_pay_by_card
```

```
docs/specs/checkout.md:3: ✅ tag spec/checkout
docs/specs/checkout.md:41: ✅ scenario tests/test_checkout.py::test_pay_by_card
citations: every report link is current
```

`--covering` keeps a report link to the scenario, and one to a tag or story whose summary counts it, a tag through its prefixes too. It also keeps every link it cannot resolve: one whose target is not in the report may be the scenario under a node ID it no longer has, and a mistyped citation may cite anything. Running `citations update` first repoints a renamed test whose title one scenario still has, so once the check is clean the list is exact. `--list` alone lists every report link, each with its findings under it.
