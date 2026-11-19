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

Each report carries the commit SHA it ran at. The delta header shows the SHAs and a version label for each side. The label is the git tag on that commit, or what `--before-label` and `--after-label` name. For a release not tagged yet, pass `--after-label v<version>`.

The delta's title is the after report's title. Pass `--title` to name what the delta covers in words its readers know, such as `--title "Hotel booking changes for v2.4"`.

### Choosing the two commits

The command compares the two reports you give it. Which commits they come from is up to you. To publish a delta with each release:

- Start the first delta at the previous release tag.
- Start each later delta at the commit the last published one ended at, its *after* commit, so together they cover every commit once. Its SHA is in `.metadata.after.metadata.commit_sha` of that delta's JSON.
- Skip a release whose delta lists no change. The next delta then starts at the last published one and covers the skipped release too.

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
