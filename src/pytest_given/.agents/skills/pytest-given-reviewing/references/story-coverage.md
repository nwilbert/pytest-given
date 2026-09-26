# Story coverage from the JSON report

The Stories tab shows a coverage chip per sentence, but it is HTML, and `--given-md` has no Stories section at all. From a terminal, read coverage from the JSON sink — `pytest <selection> --given-json=report.json` — whose top-level `coverage[]` carries one record per sentence: `{story_id, sentence_id, tracked, scenario_ids}`. It is computed by the same code as the Stories tab; do not recompute it from `steps[]`, the matching rule below has more to it than a set comparison on term ids.

```bash
# uncovered sentences: tracked, and no scenario covers them
jq -r '.coverage[] | select(.tracked and .scenario_ids == [])
       | .story_id + "#" + (.sentence_id|tostring)' report.json

# untracked sentences: the report can say nothing about them
jq -r '.coverage[] | select(.tracked | not)
       | .story_id + "#" + (.sentence_id|tostring)' report.json
```

Before reporting an uncovered sentence, read its declaration site: a story maps the whole flow, so some sentences (elicitation, human review) are deliberate gaps, usually marked there. Report a marked one only if the marking has gone stale. An *untracked* sentence is a different finding — fewer than two glossary terms and no pin, so it is out of narration matching altogether; the fix is vocabulary or a pin, not a scenario.

## The matching rule

Knowing the rule is what lets you say *why* a sentence is uncovered, and what change would cover it.

A sentence is covered when **one single step's** term refs include **all** of the sentence's terms.

- Refs spread across several steps never add up — matching is per step, not against their union.
- Terms in the `@scenario` name don't count; only step narration does.
- A sentence with fewer than two distinct terms is out of narration matching, and renders as "not coverage-tracked" — unless a pin covers it.
- A pin replaces narration matching. A step pin (`pins=` on `given`/`when`/`then`) covers exactly the sentences it names, in any story — a pinned step is skipped by matching everywhere, so it cannot also cover a sentence its text happens to fit; `pins=[]` makes a step cover nothing. A pin is not subject to the two-term rule.
- A scenario pin (`@scenario(pins=...)`) covers its sentences plus its steps' pins, and none of its steps is matched; `pins=[]` keeps only the steps' pins. It is an assertion no narration backs, and it covers even when the test fails early or is skipped. **Check that the test body really exercises each scenario-pinned sentence**; report a pin whose sentence the body never touches.
- Only the term counts, not its surface form: `guest('Alice')`, `guest.low` and `guest` are one ref, as are an activity and its inflections. Two sentences differing only by instance are one to matching; only a pin tells them apart.
- Because the test is a subset test, **a sentence whose term set is a subset of another's is covered by every step that covers the other.** Two such sentences always light up together; when one of them shows as covered only by scenarios that were plainly written for the other, that is a story-shape finding (see "Two sentences cover together" in the authoring skill's `stories.md`), not test coverage.
