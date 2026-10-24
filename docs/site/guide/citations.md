# Citations

A design spec, a README or any other Markdown document can link to a scenario, a tag or a story in the HTML report. pytest-given checks these links against the JSON report of a test run, so they keep pointing at something that exists, and keeps their text in line with what that run found.

Such a link is a **citation** when it starts with a status glyph. pytest-given owns everything in it — the glyph, the link text and, for a tag or story, a summary of its scenarios — and `pytest-given citations update` keeps all of it current.

```markdown
✅ [A renamed test keeps its citation](https://example.org/report.html#scenario=tests/test_x.py::test_y)
🔵 [Cancel a Booking](https://example.org/report.html#view=stories&story=cancel-a-booking) (3 ✅ · 1 🔵)
```

Live, against this site's example reports:

- 🔵 [Cancel a Booking](../examples/hotel-booking.html#view=stories&story=cancel-a-booking) (2 ✅ · 1 🔵)
- ✅ [spec/citations](../examples/self-report.html#tag=spec/citations) (10 ✅)

A [narrated citation](#narrated-citations) also folds in its scenario's narration:

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

1. **Configure** the public URL your HTML report will be served from, the `given_report_url` setting:

    ```toml
    [tool.pytest]
    given_report_url = "https://docs.example.org/report.html"
    ```

2. **Run** the scenarios, writing both reports under `given-report/`:

    ```bash
    pytest --given-json --given-html
    ```

3. **Publish** `given-report/report.html` at that URL. How depends on your hosting; with a docs site served from `https://docs.example.org/`, copy it in before the site build:

    ```bash
    cp given-report/report.html docs/report.html
    ```

4. **Cite** scenarios, tags and stories by [copying a citation from the report](#copying-from-the-report), or by [writing one by hand](#writing-it-by-hand).

5. **Update** your documents after the report changes. Pass the Markdown files that cite the report, or directories to search for them — here everything under `docs/` and the project's `README.md`:

    ```bash
    pytest-given citations update docs/ README.md
    ```

    It reads the JSON report at `given-report/report-data.json`, where a bare `--given-json` writes it. Pass `--report PATH` for one written elsewhere.

6. **Check** in CI that the documents match the report:

    ```bash
    pytest-given citations check docs/ README.md
    ```

The run must include every scenario a document cites, because the commands can't tell a scenario the run left out from one that was deleted. Add the flags to your usual test run, or pass `-m pytest_given` to run only the scenarios. If you kept only the JSON report, `pytest-given report` renders the matching HTML from it.

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

## Adding a report link

pytest-given reads four kinds of link into the report:

| Kind | Looks like | Kept current | From the report |
|---|---|---|---|
| Scenario citation | `✅ [title](…#scenario=…)` | glyph and link text | **Copy citation** on its scenario card |
| Tag or story citation | `✅ [spec/citations](…#tag=spec/citations) (10 ✅)` | glyph, link text and summary | **Copy citation** on a story header or a Tags sidebar row |
| [Narrated citation](#narrated-citations) | a `<details>` block around a scenario citation | glyph, link text and narration | **Copy narrated citation** on its scenario card |
| Plain report link | `[your words](…#scenario=…)` | its fragment | **Copy link** on the published report. On a local report, **Copy citation** and delete the glyph and any summary. |

A citation states what the report found, so `pytest-given citations check` fails when it is out of date or its target fails. A plain report link states only that its target exists, so its text is yours and it can sit inside your own sentence. You can also [write any of them by hand](#writing-it-by-hand).

### Copying from the report

The report offers the citation entries in the table only when `given_report_url` is set, as in [step 1](#how-it-fits-together) above. To set it for one run instead, pass `--given-report-url=URL`. The URL is also stored in the JSON report, so `pytest-given report` re-renders the entries from it, and the `pytest-given citations` commands know which links point at the report.

The copy button on a scenario card, story header or Tags sidebar row opens a menu with these entries. A citation links to `given_report_url`, not to the address you opened the report at, so you can copy it from a local report and still get a link to the published one. **Copy link** copies the address you opened the report at. Without the setting, it is all the copy button offers.

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

A plain report link takes the same URL, with no glyph and your own link text:

```markdown
Rejecting [divergent cases](https://docs.example.org/report.html#scenario=tests/test_grouping.py::test_divergent_cases) keeps the tree honest.
```

A link into the report can outlive what it names. When the report no longer has a scenario, tag, story or other filter a link selects, it warns that the link is out of date, names what is missing, and opens without it.

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

The citation is in the `<summary>`: the glyph, then an `<a href="…">` with the [report link](#writing-it-by-hand) as its only attribute and the title as its link text, written as HTML. Everything below it, down to `</details>` on a line of its own, is the body. The `<summary>` follows `<details>` with no blank line between, and the block needs a blank line above it: `check` reports a block that breaks either as mistyped, such as one that continues another narrated citation's `</details>`. Only a scenario can be narrated, not a tag or a story.

The body reads as the scenario's section of the Markdown report (`--given-md`), minus its heading, its subtitle line (source anchor, tags, skip or xfail reason) and any error block. Nested steps indent by four spaces.

To add one, choose **Copy narrated citation** in the report's copy menu on a scenario card, paste it into your document, and run `pytest-given citations update`, which fills the empty body. From then on `update` rewrites the body to match the report, and `pytest-given citations check` fails when it differs, or when the opening tag lacks `markdown="1"`, which `update` adds, keeping any other attributes such as `open`.

On a Python-Markdown site (MkDocs, Zensical), enable `md_in_html` and keep the block at the top level of the page, not inside a list item. GitHub renders it anywhere.

## Updating citations

Pass the documents or directories to update. The JSON report must come from [the run that wrote your HTML report](#how-it-fits-together):

```bash
pytest-given citations update docs/ README.md
```

It rewrites what the report now says:

- a citation's glyph, link text and summary;
- the fragment of any report link that uses a scenario's slug or a `[case]`, to its node ID;
- the node ID of a renamed test, when exactly one scenario still has the citation's title.

It can't fix everything. These stay as citation findings for you to resolve, and the command exits 1:

- **A target that is no longer in the report.** The citation's glyph becomes `❓`, its URL and text stay, and it recovers on its own once the target is back.
- **A cited target that fails.** The document claims something that doesn't hold right now: fix the code, or change what the document says.
- **A summary after a scenario citation**, which takes none.
- **A tag or story written as a narrated citation**, which has no single narration.

The bundled [`pytest-given-citing` skill](../ai-agents.md#agent-skills) walks an agent through these.

## Checking in CI

`pytest-given citations check` takes the same arguments, writes nothing, and exits 1 on any citation finding, including what `pytest-given citations update` would rewrite:

```bash
pytest --given-json --given-html
pytest-given citations check docs/ README.md
# then publish given-report/report.html at given_report_url
```

Make it a required CI check. A citation records the report as of its commit, and only a required check keeps the citations on your main branch current. When no document links the report, as with a mistyped `given_report_url`, the check exits 2 instead of passing. Publish the HTML report from the run the check read, so a reader who follows a citation finds what it says.

If you commit the reports instead, write the JSON and HTML report together whenever you regenerate them, and let CI run only the check against the committed JSON. [Standalone CLI](../cli.md#citations) lists the flags and exit codes.

## Keeping the check accurate

These habits keep `pytest-given citations check` from failing on a document nothing is wrong with, or from skipping a citation it should check:

- **Run pytest from the same rootdir.** A node ID is relative to pytest's rootdir, so a run from another one breaks every scenario citation at once.
- **Use a plain report link for a scenario whose title contains a per-run value**, such as a temporary path. Its citation's link text would be stale after every run, and so would a narrated citation's body when any step or attachment contains one.
- **Cite a tag that belongs to one piece of work**, like `spec/<slug>`. A broad area tag's summary changes with every new scenario, so link it with a plain report link.
- **Leave the glyph and link unformatted.** In `**✅** […](…)` or `✅ *[…](…)*` pytest-given doesn't see a citation, only a plain report link, so the glyph is never updated.
- **On a versioned docs site, link the report relatively**, as in `../examples/report.html#tag=…`, so each version of a page opens its own version's report. A copied citation links `given_report_url`, so replace its URL up to the `#` with the relative path. Pass `--report-path`, where your docs build puts the report, so the commands recognize these links and keep them relative.
- **Keep a Markdown formatter off narrated citations.** Prettier pads table columns and a two-space list-indent rule reindents nested steps, so `check` then reports the body stale. Wrap each block in ignore comments:

```markdown
<!-- prettier-ignore-start -->

<details markdown="1">
<summary>…</summary>

…

</details>

<!-- prettier-ignore-end -->
```

### Finding the citations of a scenario

To list the report links that may cite a scenario, pass its node ID to `--covering`:

```bash
pytest-given citations check docs/ README.md \
    --covering tests/test_checkout.py::test_pay_by_card
```

It prints each link's file, line, glyph and target:

```
docs/specs/checkout.md:3: ✅ tag spec/checkout
docs/specs/checkout.md:41: ✅ scenario tests/test_checkout.py::test_pay_by_card
citations: every report link is current
```

The list includes links to a tag or story whose summary counts the scenario. It also includes every link the check can't resolve, as one may cite the scenario under an old node ID. Run `citations update` first to repoint a renamed test, and the list is exact once the check is clean.
