# `unused-story` Lint Rule — Design Spec

## Goal

Flag a scenario that names a story in `stories=` while none of its steps matches or pins any of
that story's sentences. The authoring skill already states the rule ("name a story only when a
step can match or pin one of its sentences"); the lint makes it mechanical, the way the other rules
in "Mechanical counterparts" back theirs.

## Background

Today the only check is a jq query in the reviewing skill's `references/story-coverage.md`, run by
a reviewer who thinks to run it. It prints a grouped scenario's `id`, which is its first case's
node id (`test_overlap[10-20-15-25-True]`), so the finding reads as if only that row fails to
cover. And it offers no remedy, although each of the four fits a different case.

A scenario's coverage depends only on its own steps and the story, so the rule gives the same
answer for any selection — unlike `stale-ignore`, it can't fail a run that lints one file.

## Rule

| Rule | Default | Catches |
|---|---|---|
| `unused-story` | warn | A passed scenario whose `stories=` names a story that none of its steps matches or pins a sentence of. |

- **Passed scenarios only.** A skipped scenario records no steps, and a failed one may stop before
  its covering step; both would be false findings. `missing-phase` skips them for the same reason.
- **One finding per scenario and story.** Subject: the scenario's node id, so a deliberate
  exception is an ordinary `given_lint_ignore` entry (`unused-story: <node-id glob>`). Location:
  the scenario's source. Message, with the test name stripped of its parametrize suffix:

  ```text
  test_overlap names story 'Book a Group Trip', but no step matches or pins any of its sentences
  ```

- **Coverage is the Stories tab's.** The rule reads the same matching the report renders, so a
  finding and an uncovered chip can never disagree. A scenario-level pin counts like a step pin.

The catalog entry lists the remedies, since each fits a different case:

- **Unbind** — the scenario was named in `stories=` without a step that can reach the story.
- **Reword a step** — a step demonstrates a sentence but lacks one of its term refs.
- **Add a sentence** — the scenario demonstrates a part of the flow the story doesn't tell.
- **Pin** — the sentence is phrased above the step's vocabulary.

## Coverage moves into `model/`

`lint/` may import only `model/`, and the matching lives in `report/coverage.py`. That module
imports nothing but `model/` already, so it moves to `model/coverage.py` unchanged and `report/`
imports it from there. `build_story_index` and `compute_coverage(scenario, index)` are what the
rule needs; `build_coverage_map` stays the report's entry point over `ReportData`.

## Implementation touch points

- `model/coverage.py` (moved from `report/coverage.py`), re-exported from `model/__init__.py`;
  `report/html_renderer.py` and `report/story_view.py` import it from `model`.
- `lint/base.py` — `UNUSED_STORY`, default `warn`.
- `lint/runtime_rules.py` — `_unused_story_findings`, registered in `_RUNTIME_RULES`.
- Authoring skill `references/scenarios.md` — the catalog row; `references/stories.md` — the
  "Binding scenarios to a story" rule points at it, with the remedies.
- Reviewing skill `references/story-coverage.md` — the "names a story yet covers none" query
  goes; layer 1 already runs the rule.
- `docs/site/configuration/narration-lint.md` — the rule table.
- Self-report: the existing `dead-term` / `tag-shadows-term` scenarios show the pattern; decorate
  the test that states the rule.
- `CHANGELOG.md` — Added: the `unused-story` lint rule.
- Regenerate `examples/` and `examples/self-report/`, and fix or ignore what the rule finds there.

## Test coverage

- Rule units: a bound scenario with a matching step (clean), with a step pin (clean), with a
  scenario pin (clean), with neither (finding); a skipped and a failed scenario (no finding); a
  grouped scenario (one finding, message without the suffix); a scenario bound to two stories,
  covering one (one finding).
- Integration: the finding prints under `--given-lint`; an ignore entry suppresses it.
