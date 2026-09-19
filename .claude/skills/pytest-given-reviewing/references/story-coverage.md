# Story coverage from the JSON report

The Stories tab shows a coverage chip per activity, but it is HTML, and `--given-md` has no Stories section at all. From a terminal, read coverage from the JSON sink — `pytest <selection> --given-json=report.json` — whose top-level `coverage[]` carries one record per activity: `{story_id, activity_id, tracked, scenario_ids}`. It is computed by the same code as the Stories tab; do not recompute it from `steps[]`, the matching rule below has more to it than a set comparison on term ids.

```bash
# uncovered activities: tracked, and no scenario covers them
jq -r '.coverage[] | select(.tracked and .scenario_ids == [])
       | .story_id + "#" + (.activity_id|tostring)' report.json

# untracked activities: the report can say nothing about them
jq -r '.coverage[] | select(.tracked | not)
       | .story_id + "#" + (.activity_id|tostring)' report.json
```

Before reporting an uncovered activity, read its declaration site: a story maps the whole flow, so some activities (elicitation, human review) are deliberate gaps, usually marked there. Report a marked one only if the marking has gone stale. An *untracked* activity is a different finding — fewer than two glossary terms and no `activity=` pin, so it is out of narration matching altogether; the fix is vocabulary or a pin, not a scenario.

## The matching rule

Knowing the rule is what lets you say *why* an activity is uncovered, and what change would cover it.

An activity is covered when **one single step's** term refs include **all** of the activity's terms.

- Refs spread across several steps never add up — matching is per step, not against their union.
- Terms in the `@scenario` name don't count; only step narration does.
- An activity with fewer than two distinct terms is out of narration matching, and renders as "not coverage-tracked" — unless a pin covers it.
- A step pinned with `activity=` covers exactly the activities it names, regardless of what the narration references — and *only* those: a pinned step is skipped by narration matching entirely, so it cannot also cover a different activity its text happens to fit. A pin is not subject to the two-term rule.
- A scenario carrying `activity_ids` is scoped to those activities and can cover no others.
- Only the term counts, not its surface form: `guest('Alice')`, `guest.low` and `guest` are one ref, as are a verb and its inflections. Two activities differing only by instance are one to matching; only a pin tells them apart.
- Because the test is a subset test, **an activity whose term set is a subset of another's is covered by every step that covers the other.** Two such activities always light up together; when one of them shows as covered only by scenarios that were plainly written for the other, that is a story-shape finding (see "Two activities cover together" in the authoring skill's `stories.md`), not test coverage.
