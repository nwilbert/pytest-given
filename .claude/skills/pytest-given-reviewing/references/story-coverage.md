# Story coverage from the JSON report

`--given-md` has no Stories section, and the Stories tab is HTML. So read coverage from the top-level `coverage[]` of the JSON report. It has one `{story_id, sentence_id, tracked, scenario_ids}` record per sentence, computed by the same code as the Stories tab. Don't recompute it from `steps[]`.

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

Before you report an uncovered sentence, read where it is declared. A story maps the whole flow, so some sentences (gathering requirements, a human review) are deliberate gaps, and they are usually marked as such there. Report a marked one only if the mark is out of date. An *untracked* sentence is a different finding. It has fewer than two glossary terms and no pin, so narration matching never reaches it. The fix is vocabulary or a pin, not a scenario.

## Saying why a sentence is uncovered

The matching rule is in the authoring skill's [stories.md](../../pytest-given-authoring/references/stories.md), under "Binding scenarios to a story": one step's term refs must include all of the sentence's terms, and a pin replaces narration matching. Review adds two checks on top:

- **A pin is a claim that no narration backs.** A scenario pin even covers its sentence when the test fails early or is skipped. Check that the test body really exercises each pinned sentence, for scenario pins and step pins alike. Report a pin whose sentence the body never touches. If a sentence is covered mostly by scenarios pinned to it for lack of a better sentence, it has become a catch-all: the story is missing the sentence those scenarios demonstrate.
- **Nested sentences are covered together.** If a sentence's terms are a subset of another sentence's terms, every step that covers the other one covers it too. When a sentence shows as covered only by scenarios clearly written for the other sentence, that is a finding about the story's shape (see "Two sentences are covered together" in `stories.md`), not about test coverage.
