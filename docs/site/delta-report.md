# Delta report

A **delta report** shows what a release changed about what the system does. It lists the scenarios and glossary terms added, removed or changed between two JSON reports, the *before* and the *after*. A changed scenario shows what changed inside it, down to the word.

The [example delta](examples/delta.html){ target=_blank } compares two versions of a small hotel suite.

```bash
pytest-given delta before.json after.json
```

The command writes `given-report/delta-data.json` and `given-report/delta.html`. The HTML looks and works like the [HTML report](html-report.md), with added, removed and changed shown in green, red and amber. It has a Scenarios tab and, when a term changed, a Glossary tab.

The command takes its flags from the command line only. See [Standalone CLI](cli.md#delta) for each flag and its default. The [`pytest-given-delta` agent skill](ai-agents.md#agent-skills) teaches an agent the whole loop. It builds the two reports in git worktrees, finds renames with `git`, and records them in the rename log.

## Getting the two reports

Both reports come from `--given-json`, from full runs of the whole suite. A scenario that a partial run left out reads as removed.

Build both with the same pytest-given and the same pytest. Another version can narrate a test or name its cases differently, and the delta cannot tell that from a change to the suite. When the two versions differ, the delta warns.

Both reports must have the report format (the schema version) of the pytest-given that compares them. Otherwise the delta exits 2, and the older report needs regenerating.

Each report carries the commit SHA it ran at. The delta header shows the SHAs and a version label for each side. The label is the git tag on that commit, or what `--before-label` and `--after-label` name. For a release not tagged yet, pass `--after-label v<version>`.

### Picking the range

A project that keeps its deltas starts each one where the last kept one ended. That is the *after* SHA in `.metadata.after.metadata.commit_sha` of its JSON. Without a kept delta, start at the previous release tag.

Keep a delta only when it lists a change.

## What counts as a change

A scenario found on both sides is *changed* when any of these differ:

- its title
- its steps, with their phase, narration and nesting
- its tags
- its status, or its skip or xfail reason
- its parameter table, meaning its columns, cases, cell values and case statuses

A case ID that pytest generates from the values does not count on its own, only the values do. A custom case ID counts.

Steps compare by how they read: their text and their values as shown. A term ref compares by its term, so renaming a term alone does not make a scenario changed.

Nothing else counts. That includes the node ID, the module, the source location, the duration, the error, the fixtures, the stories and the attachments.

A term is *changed* when its name or definition differs.

A value that differs on every run reads as changed in every delta. An example is a timestamp, or an object's default `str()` with its memory address. Fix it at its source, with a fixed clock or a stable `__str__`.

## How scenarios pair

A scenario pairs by its **scenario identity**. That is its node ID without the parametrize tail, so a case added to a parametrized scenario does not change it. With `group_parametrized=False`, each case is a *per-case scenario*, and its identity is the full node ID.

A scenario still unpaired then pairs by title, if exactly one unpaired scenario on each side has it. That covers a test moved to another file.

Whatever stays unpaired is removed on the before side and added on the after side. A test renamed with a new title therefore reads as one scenario removed and one added.

Inside a paired parametrized scenario, columns pair by name first. Cases then pair by custom case ID, then by their values, then by generated case ID. A case whose value changed under a generated ID, such as `2-True` to `3-True`, reads as one removed and one added.

Glossary terms pair by term ID. A term whose kind changed reads as removed under its old kind and added under its new one.

The delta JSON lists a `suggestions` entry for each removed and added pair that looks like one rename. A suggestion is never applied. To accept one, add it to the rename log.

## The rename log

The **rename log** records the renames the delta cannot see. It is `given-renames.toml` in the working directory, or the file `--renames` names. Commit it and review it like source. It grows over the project's life.

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
- When two before identities would end at the same one, the delta pairs neither and warns.

### When an entry applies

`rev` is the commit that made the rename. It is optional, and an entry without it applies to every comparison.

An entry applies only when its `rev` lies in the compared range, after the before commit and up to the after commit. A rename before the range is skipped, so a later test that reuses the old name is not paired with it. A rename after the range is skipped too.

When git cannot tell, the delta warns and does not skip the entry for that reason. That happens when the `rev` does not resolve, when the clone is shallow, or when a report has no commit SHA.

Write the renaming commit's full SHA from the default branch. A short one can turn ambiguous as the repository grows. A comment can name the release that shipped it, as in the example above. An entry written in the renaming pull request leaves `rev` out, since a squash merge drops the branch's commits. Fill it in once the commit is on the default branch, for example as a release step.

Any other git revision works too, but less precisely. A release tag places the rename at the release, so a delta that ends before the tag skips the entry.

### Errors

A malformed log exits 2 and names the entry. Malformed means:

- bad TOML
- an entry without `old`, or with neither `new` nor `cases`
- an `old` or `new` with a parametrize tail
- a `rev` that starts with `-`
- an unknown key or table

An entry that is well formed but does not apply is not an error.

A working directory without `given-renames.toml` is no error. `--renames` naming a file that does not exist is.
