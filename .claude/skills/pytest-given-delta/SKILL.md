---
name: pytest-given-delta
description: Use when building a pytest-given delta report — which scenarios and glossary terms were added, removed or changed between two commits or releases — or when recording a renamed test, case or term in `given-renames.toml`
---

# Building a pytest-given delta report

A **delta report** lists the scenarios and glossary terms added, removed or changed between two JSON reports, *before* and *after*. `pytest-given delta BEFORE.json AFTER.json` writes `given-report/delta-data.json` and `given-report/delta.html`, or only what `--json PATH` and `--html PATH` name. Given one delta JSON, it re-renders its HTML. It exits 0 whether or not anything changed, and 2 when it can't build the delta.

A scenario pairs by its **scenario identity**, its node ID without the parametrize tail, and then by an equal scenario title. A rename the delta can't see reads as one scenario removed and one added. The **rename log**, `given-renames.toml` in the working directory (or `--renames PATH`), records those renames.

## Picking the range

- A project that keeps its deltas starts each one where the last kept one ended, at its *after* SHA (`.metadata.after.metadata.commit_sha` in its JSON).
- Keep a delta only when it lists a change. A release that changed no scenario adds none, and the next delta starts at the same commit.
- Without a kept delta, start at the previous release tag.
- For a release not tagged yet, pass `--after-label v<version>`.
- Pass `--title` naming the product and the release, in words its stakeholders know: `--title "Hotel booking changes for v2.4"`. It defaults to the after report's title.

## Getting the two reports

Both must come from full runs: a scenario that a partial run left out reads as removed. Use CI's JSON reports of both commits, if it kept them. Otherwise build each in a git worktree:

    git worktree add <scratch>/before/<project> <BEFORE_SHA>
    cd <scratch>/before/<project>
    env -u GITHUB_SHA -u CI_COMMIT_SHA -u BUILDKITE_COMMIT pytest -m pytest_given --given-json=<scratch>/before.json

- Name the worktree directory after the project: a report's `project` is its rootdir's name.
- Unset the CI commit variables, as above, or a report built inside CI carries the current commit's SHA.
- Run `pytest-given delta` from the current checkout, so it reads the current rename log.

**One pytest-given and one pytest version for both.** Another version can narrate a test or name its cases differently. On a schema version refusal or a version warning, regenerate the older report in its worktree, with the current versions installed in place of its lockfile's. When the older suite can't run under the current pytest-given, because the public API changed, no delta spans that change: say so.

## Triage

These are rename candidates:

- every suggested match, in the delta JSON's `.suggestions[]` (`of` is `scenario`, `case` or `term`)
- a removed scenario and an added one in the same module
- a removed term and an added one of the same kind, or one of them kindless
- a removed case and an added case of a paired scenario, whose generated case IDs differ

Resolve each from git: `git diff --find-renames BEFORE_SHA..AFTER_SHA`, and `git log --follow -- <test file>`. Find the commit with `git log -S '<function name>'` for a function, or `git log --diff-filter=R --stat` for a moved file. Then read both sides' steps and test bodies: a rename states the same rule, not a similar one or its opposite. Add an entry for each confirmed rename, and leave a genuine removal alone. Without a commit SHA in a report, git can't help: tell the human which pairs you couldn't resolve.

If Markdown documents cite the report, run `pytest-given citations check` after a rename. Fix its citation findings as the `pytest-given-citing` skill does: `citations update` for a renamed test whose title one scenario still has, its repair guide for a target not in the report.

Re-run the delta after adding entries, until each remaining removed and added pair is genuine.

## Writing rename log entries

```toml
[[scenario]]  # renamed, and one case's generated ID changed
old = "tests/test_pricing.py::test_pricing"
new = "tests/test_prices.py::test_price_list"
cases = { "1.5-True" = "2.0-True" }
rev = "3f2a9c1e5b7d40a8c6f2e19b4d7a0c3e8f5b6d21"

[[scenario]]  # only cases changed: leave `new` out
old = "tests/test_prices.py::test_price_list"
cases = { "happy-hour" = "happy-hour-weekdays" }

[[term]]
old = "room"
new = "suite"
rev = "8d41e07c2a9f4b6e1d3c5a7f9e0b2d4c6a8f1e35"
```

- `old` and `new` are node IDs without the `[…]` tail. For a per-case scenario (`group_parametrized=False`), that is the part all its cases share.
- `cases` maps old case IDs to new ones. A case it doesn't name keeps its case ID under the new identity, so list only the changed ones. One entry records one rename of a scenario together with its cases.
- `[[term]]` holds term IDs (`Late fee` is `late-fee`).
- Entries apply in file order, so chains work (`A → B`, later `B → C`). A swap goes through a name neither test has: `A → tmp`, `B → A`, `tmp → B`.

**`rev`** is the commit that made the rename. An entry without it applies to every comparison. An entry whose `rev` is the *before* commit or an ancestor of it is skipped, so a later test reusing the old ID isn't paired with it. So is one whose `rev` the *after* commit doesn't contain: that rename comes after the range. A `rev` that doesn't resolve, or a shallow clone, applies the entry with a warning.

Write that commit's full SHA on the default branch (`git log -1 --format=%H <commit>`), since a short one can turn ambiguous. When you can't find the commit, write the *after* commit's, if it is on the default branch. Never write a pull request run's SHA: a squash merge drops a branch commit, and on GitHub it names a temporary merge commit. In the renaming pull request, leave `rev` out. The project's release checklist may fill it in later.

## Values that differ on every run

A step or cell that reads as changed in every delta holds a per-run value, such as a timestamp or a default `str()` with a memory address. Fix it at its source, with a fixed clock or a stable `__str__`.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
