# Expected-Failure Status — Design Spec

## Goal

Give a scenario that fails as expected (`@pytest.mark.xfail`, `pytest.param(..., marks=pytest.mark.xfail)`, or an in-body `pytest.xfail()`) its own status, `xfailed`, instead of filing it under `skipped` or `failed`.

An xfailed scenario is neither of those:

- **It ran.** Unlike a skipped one, it recorded steps up to where it broke and carries the error that broke it. Both are what a reader opens it for: the steps document the intended behavior, and the error shows how far the implementation is from it. `xfail(run=False)` is the exception: it never runs, so it has neither, only its reason.
- **It does not fail the run.** Unlike a failed one, the team has already declared it known-broken. Rendering it red, or counting it as failing story coverage, would raise an alarm pytest itself does not raise.

pytest draws the same line: its summary counts `xfailed` apart from both `failed` and `skipped`.

## Scope

- In: a new `Status` value `xfailed`, with an `xfail_reason`, recorded for every way pytest reports an expected failure — a marked test failing, an imperative `pytest.xfail()`, and `xfail(run=False)`.
- In: every place that branches on status — serde, grouping, both renderers, the HTML filters, story coverage, the lint — and the docs and skills that list the statuses.
- Out: an `xpassed` status. A non-strict unexpected pass stays `passed`, and a strict one stays `failed`, now carrying pytest's `[XPASS(strict)]` message as its error — the right answer for both.
- Out: per-case reasons in the parameter table, as for skip reasons.

## How pytest reports an expected failure

`_pytest/skipping.py` rewrites the report in its `pytest_runtest_makereport` hookwrapper:

| Case | `report.when` | `report.outcome` | `report.wasxfail` |
|---|---|---|---|
| marked test fails (and `raises=` matches, if given) | `call`, or `setup` / `teardown` when a fixture raises | `skipped` | the mark's `reason` (may be `''`) |
| `pytest.xfail('msg')` in the body or a fixture | `call` / `setup` | `skipped` | `'msg'` |
| `xfail(run=False)` | `setup` | `skipped` | `'[NOTRUN] ' + reason` |
| marked test passes, non-strict | `call` | `passed` | the mark's `reason` |
| marked test passes, `strict=True` | `call` | `failed` | absent |
| marked test fails with an exception `raises=` excludes | `call` | `failed` | absent |

So `wasxfail` on a *skipped* report is the whole signal. A `passed` report carrying `wasxfail` is an xpass and stays `passed`; nothing else changes. Under `--runxfail` pytest leaves every report alone, and so does this.

## Data model

`model/schema.py`:

```python
type Status = Literal['passed', 'failed', 'skipped', 'xfailed']

STATUSES: tuple[Status, ...] = ('passed', 'failed', 'skipped', 'xfailed')

@dataclass
class Scenario:
    ...
    skip_reason: str | None = None
    xfail_reason: str | None = None
```

`xfail_reason` sits beside `skip_reason` rather than replacing it with a shared `reason`: the two read differently ("skipped because" against "expected to fail because") and the JSON already carries `skip_reason`. Serde reads it with `.get`, so the field is optional in a report. `_literal` validates the widened `STATUSES` with no change of its own.

## Capture

`plugin/runtest.py`:

- `pytest_runtest_logreport` treats a skipped report carrying `wasxfail` as `xfailed`, at setup or call — the setup-skip branch already reaches `finish_scenario`, which covers `run=False` and a fixture calling `pytest.xfail()`. `xfail_reason` is `wasxfail` with pytest's `[NOTRUN] ` prefix removed and stripped, or None when that leaves it empty: the prefix is pytest's terminal jargon, and a card with no steps already says the test never ran.
- `pytest_runtest_makereport` already attaches the error of a marked test that fails as expected, which is the error the reader wants. It skips the error for `pytest.xfail.Exception`, exactly as it does for `pytest.skip.Exception`: the imperative call's traceback is the xfail machinery, not the failure. A strict xpass raised nothing, so its error is pytest's `[XPASS(strict)] <reason>` message, read off the failed call report.
- `Collector.finish_scenario` takes `xfail_reason` alongside `skip_reason`, and closes the scenario `makereport` already marked xfailed.

A teardown error follows pytest's verdict on the teardown report, which differs by how the test was declared to fail:

- **Under an `xfail` mark**, pytest rewrites a teardown error to an expected failure too (skipped, carrying `wasxfail`) and the run stays green — even after a non-strict xpass, which pytest then counts as both `xpassed` and `xfailed`. The scenario ends `xfailed`, keeping the first error.
- **After an imperative `pytest.xfail()`** with no mark, the teardown error is a plain error that fails the run, and the scenario ends `failed`.

`pytest_runtest_makereport` becomes a `wrapper=True, tryfirst=True` hook, so it wraps `_pytest/skipping.py`'s. Before its `yield` it captures the error, so the frame filter still runs before pytest renders its own longrepr; after it, it reads the report `_pytest/skipping.py` has rewritten. A report carrying `wasxfail`, in any phase, marks the scenario — open, or finished by the time of teardown — through `Collector.fail_as_expected`: `xfailed` with the first error and the reason, unless it already failed, which stays `failed` without one. Any other error goes through `Collector.fail`, and only a failed call report starting `[XPASS(strict)]` counts as a strict xpass. `pytest_runtest_logreport` cannot take this over: `pytest_runtest_teardown` has unpublished the collector before the teardown report is logged.

A reason goes only with its status: a scenario or group carries `xfail_reason` only when `xfailed`, and `skip_reason` only when `skipped`.

## Grouping

`grouping/group.py`'s `_grouped_status` gains one rung:

1. any case `failed` → `failed`
2. any case `xfailed` → `xfailed`
3. every case `skipped` → `skipped`
4. otherwise → `passed`

A single xfailed case is the common shape — `pytest.param(..., marks=pytest.mark.xfail)` on one row of a decision table — and a group that reads `passed` would hide the one row the table exists to flag. The per-case status column, shown once the cases differ, says which row it is.

`comparable` stays the passed cases only: an xfailed case may stop mid-tree like a failed one. `_baseline` already prefers a case that recorded a tree over a skipped one, and an xfailed case records one.

A grouped scenario's `xfail_reason` is the reason its xfailed cases share, or None when they differ. It cannot be the anchor's, as `skip_reason` is: a group is `skipped` only when every case is, so the anchor's skip reason is everyone's, but the one xfailed row of a decision table is seldom the anchor, so the anchor's `xfail_reason` would usually be None.

## Rendering

The glyph is `⊗` — a cross held in a circle: a failure, but a contained one. `report/text.py`'s `STATUS_GLYPH` carries it, so both renderers pick it up.

**HTML.**

- A scenario card takes the `xfailed` class, styled from new `--color-xfailed` and `--color-xfailed-tint` tokens in both themes: a muted steel blue. The other hues are taken — red failed, amber skipped, green passed, aubergine the accent and activity terms, teal object terms — and blue reads as calmer than any of them.
- Every surface that paints a status in the skipped token gets an xfailed counterpart: the card's status bar and its multi-case bar, the status badge, the parameter table's status dot, and the Stories tab's coverage count.
- The status badge reads `⊗ expected failure`, not the raw `xfailed` the badge macro would print today, so badge, filter pill and Markdown use one wording.
- Its body renders steps, error and reason. The reason sits where a skip reason does, in a box styled like `.skip-reason` but in the xfailed token, labelled "Expected to fail:". The error block takes the xfailed ink on a neutral ground instead of failed red — on an xfailed card, and on an xfailed case's error row in a group where another case failed — since the dark theme's traceback ground is the failed tint.
- The status filter gains an `⊗ Expected failure` pill, shown only when the report has one, like `Skipped`. `#status=` accepts `xfailed`, and the "All Scenarios" / "no statuses" summary counts it like the other three.
- The status pills wrap instead of overflowing the sidebar. Four need about 330px, more than the 238px the default sidebar width gives them, so at that width the expected-failure pill takes a second row; the sidebar's minimum width already clips three pills today, which the wrap fixes too. The wrapped layout and the new pill are designed with the `frontend-design` skill, not just made to fit.
- A parameter-table row whose case is xfailed takes an `xfailed-row` class, tinted like `failed-row` but in the xfailed token.

**Markdown.** The heading suffix reads `· expected failure` where a skipped one reads `· skipped`, and the subtitle carries `— expected to fail: <reason>` where a skipped one carries `— reason: <reason>`. Steps and error render as for a failed scenario.

## Story coverage

`report/story_view.py`'s `SentenceCoverage` gains an `xfailed` count, and `failed` becomes `total - passed - skipped - xfailed`. The Stories tab shows it as "N expected to fail" beside "failing" and "skipped". A sentence covered only by xfailed scenarios therefore reads as documented but not yet working, rather than as broken. The JSON `coverage` records list scenario ids only and are unchanged.

## Lint

No rule changes. `missing-phase` already considers only `passed` scenarios, and an xfailed one may stop before its `then` for the same reason a failed one does.

## Documentation

- The navigating skill's `references/report-json.md` lists `xfailed` among the statuses and `xfail_reason` among the scenario fields, with a `jq` filter for it.
- No docs site page lists the statuses today. `guide/scenarios.md` gains an "Expected failures" section — the status, its reason, and the planned-feature use with `strict=True` — and `guide/parametrized.md` notes that a group with an xfailed row reads `xfailed`. The authoring skill notes that `xfail` marks are fine on scenarios and on individual parametrize rows, and that a scenario written ahead of its implementation is the main use: an xfailed scenario is an executable statement of planned behavior. It recommends `strict=True` (or the `xfail_strict` ini), so a scenario that starts passing fails the run until its mark comes off. A non-strict mark passes quietly and stays, so a later regression would report as an expected failure.
- A self-report scenario demonstrates an expected failure.
- The coffeeshop example gains two, so its report shows both shapes:
  - a planned-feature scenario — a loyalty card earning a free coffee — marked `xfail(strict=True, reason='not implemented yet')`, whose body runs into the missing feature. It shows the card, the steps up to the break, the error and the reason.
  - one xfailed row in the parametrized pricing scenario, through `pytest.param(..., marks=pytest.mark.xfail(strict=True, reason=...))`. It shows the grouped status rule and the `xfailed-row` styling.
- The hotel-booking example, which has stories where coffeeshop has none, gains a planned-feature scenario that pins a story sentence, so its Stories tab shows the "expected to fail" count.
- CHANGELOG, under Added: scenarios that fail as expected get their own `xfailed` status, with their reason, steps and error, in every report format.

## Testing

- Unit: `_grouped_status` precedence; serde round-trip of `xfailed` and `xfail_reason`; `SentenceCoverage` counts.
- Integration, through `pytester`: a marked failure, `pytest.xfail()` in the body and in a fixture, `run=False`, a non-strict xpass (stays `passed`), a strict xpass (`failed`), a `raises=` mismatch (`failed`), a teardown error under a mark (`xfailed`) and after an imperative `pytest.xfail()` (`failed`), and a parametrized group with one xfailed row.
- Frontend: Playwright, in both themes, on the regenerated coffeeshop report — the card, the filter pill and its `#status=` round-trip, all four pills unclipped at the minimum, default and maximum sidebar widths, the table row — and on the hotel-booking report for the Stories count.
