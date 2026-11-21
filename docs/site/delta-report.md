# Delta report

A **delta report** shows what a release changed about what the system does. It lists the scenarios and glossary terms added, removed or changed between two JSON reports, the *before* and the *after*. A changed scenario shows what changed inside it, down to the word.

The [example delta](examples/delta.html){ target=_blank } compares two versions of a small hotel suite.

```bash
pytest-given delta before.json after.json
```

The command writes `given-report/delta-data.json` and `given-report/delta.html`. The HTML looks and works like the [HTML report](html-report.md), with added, removed and changed shown in green, red and amber. It has a Scenarios tab and, when a term changed, a Glossary tab. Warnings go to stderr, as `Warning: …` lines, and do not stop the command.

The command takes its flags from the command line only. See [Standalone CLI](cli.md#delta) for each flag and its default. The [`pytest-given-delta` agent skill](ai-agents.md#agent-skills) guides an agent through a delta. The agent builds the two reports in git worktrees, finds renames with `git`, and records them in the rename log.

## Getting the two reports

Both reports come from `--given-json`, from full runs of the whole suite. A scenario that a partial run left out is listed as removed.

Build both with the same pytest-given and the same pytest. Another version can narrate a test or name its cases differently, and the delta cannot tell that from a change to the suite. When the two versions differ, the command prints a warning.

Both reports must have the report format (the schema version) of the pytest-given that compares them. Otherwise the delta exits 2, and the older report needs regenerating.

Each report carries the commit SHA it ran at. The delta header names each side by its version label. The label is the git tag on that commit, or what `--before-label` and `--after-label` name. For a release not tagged yet, pass `--after-label v<version>`. Hover a side for its commit, run time, report file, and pytest and pytest-given versions.

The delta's title is the after report's title. Pass `--title` to name what the delta covers in words its readers know, such as `--title "Hotel booking changes for v2.4"`.

### Choosing the two commits

The command compares the two reports you give it. Which commits they come from is up to you. To publish a delta with each release:

- Start the first delta at the previous release tag.
- Start each later delta at the commit the last published one ended at, its *after* commit, so together they cover every commit once. Its SHA is in `.metadata.after.metadata.commit_sha` of that delta's JSON.
- Skip a release whose delta lists no change. The next delta then starts at the last published one and covers the skipped release too.

### For a pull request

A delta on a pull request shows reviewers what merging it changes about the system's behavior. A GitHub `pull_request` run checks out a merge commit of the pull request into its base branch. Compare that commit, the *after*, with its first parent `HEAD^1`, the *before*. A comparison of the pull request's head with the base branch's tip would also list the base branch's newer changes, in reverse.

Neither commit has a tag, so label the sides with `--before-label` and `--after-label`. Record a rename in the rename log in the pull request itself, without `rev`. See [When an entry applies](#when-an-entry-applies).

This workflow builds both reports and keeps the delta's HTML as a workflow artifact. A second job posts the delta's summary as a comment on the pull request and edits that comment on later runs. It runs none of the pull request's code, because it holds a token that can write. A pull request from a fork gets no such token, so the second job skips it. `--edit-last` edits the newest comment by `github-actions`, so no other workflow should comment on pull requests as `github-actions`. Replace `uv run` with your project's runner.

```yaml
name: Delta

on:
  pull_request:

permissions:
  contents: read

jobs:
  delta:
    runs-on: ubuntu-latest
    outputs:
      summary: ${{ steps.delta.outputs.summary }}
      url: ${{ steps.artifact.outputs.artifact-url }}
    steps:
      - uses: actions/checkout@v5
        with:
          persist-credentials: false
          fetch-depth: 0  # HEAD^1 and the rename log's rev checks need history
      - uses: astral-sh/setup-uv@v7
      - name: After report
        run: uv run pytest -m pytest_given --given-json="$RUNNER_TEMP/after.json"
      - name: Before report
        run: |
          # A report's project is its rootdir's name, so keep the repository's.
          before="$RUNNER_TEMP/before/${GITHUB_REPOSITORY#*/}"
          git worktree add "$before" HEAD^1
          cd "$before"
          # GITHUB_SHA names the merge commit, not this one.
          env -u GITHUB_SHA uv run pytest -m pytest_given \
            --given-json="$RUNNER_TEMP/before.json"
      - name: Delta
        id: delta
        env:
          BASE_REF: ${{ github.base_ref }}
          PR_NUMBER: ${{ github.event.number }}
        run: |
          uv run pytest-given delta "$RUNNER_TEMP/before.json" "$RUNNER_TEMP/after.json" \
            --before-label "$BASE_REF" --after-label "#$PR_NUMBER" \
            > "$RUNNER_TEMP/delta.txt"
          cat "$RUNNER_TEMP/delta.txt" >> "$GITHUB_STEP_SUMMARY"
          echo "summary=$(grep -m1 '^delta: ' "$RUNNER_TEMP/delta.txt")" >> "$GITHUB_OUTPUT"
      - id: artifact
        uses: actions/upload-artifact@v7
        with:
          name: delta
          path: given-report/delta.html

  comment:
    needs: delta
    if: github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - env:
          GH_TOKEN: ${{ github.token }}
          GH_REPO: ${{ github.repository }}
          PR_NUMBER: ${{ github.event.number }}
          SUMMARY: ${{ needs.delta.outputs.summary }}
          ARTIFACT_URL: ${{ needs.delta.outputs.url }}
        run: |
          body=$(printf '`%s`\n\nDownload [delta.html](%s) and open it locally.\n' \
            "$SUMMARY" "$ARTIFACT_URL")
          gh pr comment "$PR_NUMBER" --edit-last --create-if-none --body "$body"
```

## What counts as a change

A scenario found on both sides is *changed* when one of these parts differs. The delta JSON lists them in `changed_in`.

- **Title**
- **Steps**: their phase, narration and nesting.
- **Tags**
- **Status**, including a skip or xfail reason.
- **Parameters**: the parameter table's columns, cases, cell values and case statuses.
- **Attachments**: an attachment's content or content type, or an `attachment` column or cell.

Steps compare by their text, with each value as the report shows it. A term ref compares by its term, so renaming a term does not change the scenarios that use it. A case ID that pytest generates from the values does not count, only the values do. A custom case ID counts. Nothing else counts, such as the node ID, the source location, the duration, the error or the stories.

A term is *changed* when its name or definition differs.

A value that differs on every run makes its scenario changed in every delta. Examples are a timestamp, a generated ID, or a default `str()` with a memory address. Fix it at its source, with a fixed clock, a seeded ID generator or a stable `__str__`, or replace it with a fixed placeholder before attaching. Until then, the HTML's *Changed in* filter can hide the scenarios that changed only in their attachments.

## How scenarios pair

A scenario pairs by its **scenario identity**: its node ID without the parametrize tail, so adding a case does not change it. With `group_parametrized=False`, each case is a *per-case scenario* and pairs by its full node ID. A scenario still unpaired then pairs by title, if exactly one unpaired scenario on each side has it. That covers a test moved to another file.

Anything still unpaired is listed as removed and added, such as a test renamed along with its title. Record such a rename in the [rename log](#the-rename-log). The delta JSON's `suggestions` lists the removed and added pairs that look like one rename, but never applies them.

Inside a paired scenario, a case whose values changed under a generated case ID, such as `2-True` to `3-True`, is likewise one case removed and one added. So is an attachment whose label changed.

Glossary terms pair by term ID. A term whose kind changed is listed as removed and added. A term that only gains or loses a kind still pairs.

## The rename log

The **rename log** records the renames the delta cannot detect: a test renamed together with its title, a case whose generated ID changed with its value, a renamed term. It is `given-renames.toml` in the working directory, or the file `--renames` names. Commit it and review it like source.

```toml
[[scenario]]  # renamed, and one case's generated ID changed
old = "tests/test_pricing.py::test_pricing"
new = "tests/test_prices.py::test_price_list"
cases = { "1.5-True" = "2.0-True" }
rev = "3f2a9c1e5b7d40a8c6f2e19b4d7a0c3e8f5b6d21"  # v0.6.0

[[scenario]]  # only cases changed: leave `new` out
old = "tests/test_prices.py::test_price_list"
cases = { "happy-hour" = "happy-hour-weekdays" }

[[term]]
old = "room"
new = "suite"
rev = "8d41e07c2a9f4b6e1d3c5a7f9e0b2d4c6a8f1e35"  # v0.6.0
```

- `[[scenario]]` holds scenario identities. `old` and `new` are node IDs without the `[…]` tail. For a `group_parametrized=False` scenario, that is the part all its cases share.
- `cases` maps old case IDs to new ones. A case it does not name keeps its case ID. One entry records a scenario's rename together with its cases.
- `new` may be left out when `cases` is given. The identity then stays.
- `[[term]]` holds term IDs. `Late fee` is `late-fee`.
- Entries apply in file order, so renames chain. `A` to `B`, then later `B` to `C`, pairs `A` with `C`. A delta that ends before the second rename pairs `A` with `B`.
- A swap goes through a name neither test has: `A` to `tmp`, `B` to `A`, `tmp` to `B`.
- An entry that matches nothing in the compared reports is skipped silently, so one log serves every comparison.
- When two before identities would end at the same one, the delta pairs neither and prints a warning. So does a `cases` map that takes two cases to the same case ID.

### When an entry applies

`rev` is the commit that made the rename. It is optional, and an entry without it applies to every comparison.

An entry applies only when its `rev` lies in the compared range, after the before commit and up to the after commit. A rename before the range is skipped, so a later test that reuses the old name is not paired with it. A rename after the range is skipped too.

Where git cannot answer, the `rev` counts as inside the range, and the command prints a warning. That happens when the `rev` does not resolve, when the clone is shallow, or when a report has no commit SHA.

Write the renaming commit's full SHA from the default branch. A short one can turn ambiguous as the repository grows. A comment can name the release that shipped it, as in the example above. An entry written in the renaming pull request leaves `rev` out, since a squash merge drops the branch's commits. Fill it in once the commit is on the default branch, for example as a release step.

Any other git revision works too, but less precisely. A release tag places the rename at the release, so a delta that ends before the tag skips the entry.

### Errors

A malformed log exits 2 and names the entry. Malformed means:

- bad TOML
- an entry without `old`, or with neither `new` nor `cases`
- an `old` or `new` with a parametrize tail
- an unknown key or table

An entry that is well formed but does not apply is not an error.

A working directory without `given-renames.toml` is no error. `--renames` naming a file that does not exist is.

## JSON schema

The delta JSON follows a published [JSON Schema](schemas/delta-v1.schema.json) and names it under a top-level `$schema` key. `metadata.schema_version` holds the delta's version. `pytest-given delta` re-renders only a delta of its own version. It refuses another with one line saying to build it again from its two reports.
