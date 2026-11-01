# Delta report

A **delta report** shows what a release changed about what the system does. It lists the scenarios and glossary terms added, removed or changed between two JSON reports, the *before* and the *after*. A changed scenario shows what changed inside it, down to the word.

The [example delta](examples/delta.html){ target=_blank } compares two versions of a small hotel suite.

```bash
pytest-given delta before.json after.json
```

The command writes `given-report/delta-data.json` and `given-report/delta.html`. The HTML looks and works like the [HTML report](html-report.md), with added, removed and changed shown in green, red and amber. It has a Scenarios tab and, when a term changed, a Glossary tab.

## Getting the two reports

Both reports come from `--given-json`, from full runs of the whole suite. A scenario that a partial run left out reads as removed.

Build both with the same pytest-given and the same pytest. Another version can narrate a test differently or name its cases differently, and the delta cannot tell that from a change to the suite. When the two versions differ, the delta warns.

Both reports must carry the schema version of the pytest-given that compares them, or the delta exits 2. A report from a pytest-given that predates the schema version has none, so regenerate it.

Each report carries the commit SHA it ran at. The delta header shows the SHAs and a version label for each side. The label is the git tag on that commit, or what `--before-label` and `--after-label` name.

## What counts as a change

A scenario found on both sides is *changed* when any of these differ:

- its title
- its steps, with their phase, narration and nesting
- its tags
- its status, or its skip or xfail reason
- its parameter table, meaning its columns, cases, cell values and case statuses

A generated case ID is made from the case's values, so it counts only through those values. A custom case ID counts.

Narration compares as it reads. Its text and its values as rendered count. A term ref counts by its term and its form. A display that changed only because its term was renamed does not make a scenario changed.

Nothing else counts. That includes the node ID, the module, the source location, the duration, the error, the fixtures, the stories and the attachments.

A term is *changed* when its name or definition differs.

A value that differs on every run reads as changed in every delta. An example is a timestamp, or an object's default `str()` with its memory address. Fix it at its source, with a fixed clock or a stable `__str__`.

## How scenarios pair

A scenario pairs by its **scenario identity**. That is its node ID without the parametrize tail, so a case added to a parametrized scenario does not change it. With `group_parametrized=False`, each case is a *per-case scenario*. Its identity is the full node ID, and it never pairs by values.

What the identity does not pair is paired by an equal scenario title, when exactly one unpaired scenario on each side has it. That covers a test moved to another file.

Whatever stays unpaired is removed on the before side and added on the after side. A test renamed with a new title therefore reads as one scenario removed and one added.

Inside a paired parametrized scenario, columns pair by name first. Cases then pair by custom case ID, then by their values, then by generated case ID. A case whose value changed under a generated ID, such as `2-True` to `3-True`, reads as one removed and one added.

Glossary terms pair by term ID. A term whose kind changed reads as removed under its old kind and added under its new one.

The delta JSON lists a `suggestions` entry for each removed and added pair that looks like one rename. A suggestion is never applied. Confirm it in the rename log.

## The rename log

The **rename log** records the renames the delta cannot see. It is `given-renames.toml` in the working directory, or the file `--renames` names. Commit it and review it like source. It grows over the project's life.

```toml
[[scenario]]  # renamed, and one case's generated ID changed
old = "tests/test_pricing.py::test_pricing"
new = "tests/test_prices.py::test_price_list"
cases = { "1.5-True" = "2.0-True" }
rev = "v0.6.0"

[[scenario]]  # only cases changed: leave `new` out
old = "tests/test_prices.py::test_price_list"
cases = { "happy-hour" = "happy-hour-weekdays" }

[[term]]
old = "room"
new = "suite"
rev = "v0.6.0"
```

- `[[scenario]]` holds scenario identities. `old` and `new` are node IDs without the `[…]` tail. For a `group_parametrized=False` scenario, that is the part all its cases share.
- `cases` maps old case IDs to new ones. A case it does not name keeps its case ID. One entry records a scenario's rename together with its cases.
- `new` may be left out when `cases` is given. The identity then stays.
- `[[term]]` holds term IDs. `Late fee` is `late-fee`.
- Entries apply in file order, so chains work. `A` to `B` and a later `B` to `C` take `A` to `C` when comparing across both. Comparing only up to the version with `B`, `A` pairs with `B`.
- A swap goes through a name neither test has: `A` to `tmp`, `B` to `A`, `tmp` to `B`.
- An entry whose old identity is nowhere in the range is skipped silently. One log serves every comparison.

When two before identities would end at the same one, the delta pairs neither and warns.

### rev

`rev` is a git revision, a tag or a SHA, at which the rename had already happened. It is optional.

An entry whose `rev` is the before commit or an ancestor of it is skipped. The rename predates the range, so a later test that reuses the old ID is not paired with it by mistake.

The delta asks git once per distinct `rev`. It applies the entry and warns when the `rev` does not resolve, when the clone is shallow, when the before report has no SHA, or when git cannot answer.

Write the tightest lasting `rev`. That is the earliest release tag containing the commit that made the rename. Otherwise it is that commit's SHA, when it is on the default branch. Never write the SHA of a pull request run, because a squash merge drops it. An entry written in the renaming pull request may leave `rev` out.

### Malformed logs

A malformed log exits 2 and names the entry. Malformed means bad TOML, an entry missing `old`, an entry with neither `new` nor `cases`, or an `old` or `new` with a parametrize tail. A `rev` that starts with `-` and an unknown key or table are malformed too. An entry that is well formed but does not apply is not an error.

A working directory without `given-renames.toml` is no error. `--renames` naming a file that does not exist is.

## Keeping deltas

A project that keeps its deltas starts each one where the last kept one ended. That is the *after* SHA in `.metadata.after.metadata.commit_sha` of its JSON. Without a kept delta, start at the previous release tag.

Keep a delta only when it lists a change. For a release not tagged yet, pass `--after-label v<version>`.

## The command line

`pytest-given delta` takes its flags from the command line only. See [Standalone CLI](cli.md#delta) for each flag and its default.

The [`pytest-given-delta` agent skill](ai-agents.md#agent-skills) teaches an agent the whole loop. It builds the two reports in git worktrees, finds renames with `git`, and records them in the rename log.
