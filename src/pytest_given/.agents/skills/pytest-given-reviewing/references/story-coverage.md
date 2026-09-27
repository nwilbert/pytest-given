# Story coverage from the JSON report

`--given-md` has no Stories section and the Stories tab is HTML, so read coverage from the JSON sink's top-level `coverage[]`: one `{story_id, sentence_id, tracked, scenario_ids}` record per sentence, computed by the same code as the Stories tab. Don't recompute it from `steps[]`.

```bash
pytest <selection> --given-json=report.json

# uncovered sentences: tracked, and no scenario covers them
jq -r '.coverage[] | select(.tracked and .scenario_ids == [])
       | .story_id + "#" + (.sentence_id|tostring)' report.json

# untracked sentences: the report can say nothing about them
jq -r '.coverage[] | select(.tracked | not)
       | .story_id + "#" + (.sentence_id|tostring)' report.json

# scenarios that name a story yet cover none of its sentences
jq -r '[.coverage[].scenario_ids[]] as $covering
       | .scenarios[] | select(.story_ids != [] and (.id | IN($covering[]) | not))
       | .id' report.json
```

Before reporting an uncovered sentence, read its declaration site: a story maps the whole flow, so some sentences (elicitation, human review) are deliberate gaps, usually marked there. Report a marked one only if the marking has gone stale. An *untracked* sentence is a different finding — fewer than two glossary terms and no pin, so it is out of narration matching altogether; the fix is vocabulary or a pin, not a scenario.

## Saying why a sentence is uncovered

The matching rule is in the authoring skill's [stories.md](../../pytest-given-authoring/references/stories.md) under "Binding scenarios to a story": one step's term refs must include all of the sentence's terms, and a pin replaces narration matching. Two checks on top of it are review's own:

- **A pin is an assertion no narration backs**, and a scenario pin covers even when the test fails early or is skipped. Check that the test body really exercises each pinned sentence, scenario and step pins alike; report a pin whose sentence the body never touches. A sentence covered mostly by scenarios pinned there for want of a better one is a catch-all: the story is missing the sentence they demonstrate.
- **Nested sentences light up together.** A sentence whose terms are a subset of another's is covered by every step that covers the other. When one shows as covered only by scenarios plainly written for the other, that is a story-shape finding (see "Two sentences cover together" in `stories.md`), not test coverage.
