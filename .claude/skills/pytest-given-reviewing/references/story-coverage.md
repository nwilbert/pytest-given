# Story coverage from the JSON report

`--given-md` has no Stories section, and the Stories tab is HTML. So read coverage from the top-level `coverage[]` of the JSON report, and don't recompute it from `steps[]`. Its shape and the query for uncovered sentences are in the navigating skill's [report-json.md](../../pytest-given-navigating/references/report-json.md). Review adds two queries:

```bash
pytest <selection> --given-json=report.json

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

- **A pin is a claim that no narration backs.** A scenario pin even covers its sentence when the test fails early or is skipped. Check that the test body really exercises each pinned sentence, for scenario pins and step pins alike. Report a pin whose sentence the body never touches. If a sentence is covered mostly by scenarios pinned to it for lack of a better sentence, it has become a catch-all: the story is missing the sentence those scenarios demonstrate. Coverage is mainly a way to navigate from a sentence to its scenarios, and a catch-all sends the reader to scenarios about something else. To spot one, list each sentence's scenarios with how they cover it, and read the pinned titles against the sentence:

  ```bash
  jq -r '
    .scenarios as $all
    | .coverage[] | . as $c
    | .scenario_ids[] as $id
    | ($all[] | select(.id == $id)) as $s
    | ([($s.pins // [])[], ($s.steps | .. | objects | .pins? // empty | .[])]
       | any(.story_id == $c.story_id and .sentence_id == $c.sentence_id)) as $pinned
    | "\($c.story_id)#\($c.sentence_id)\t\(if $pinned then "pin" else "narration" end)\t\($s.narration.text)"' report.json
  ```
- **Nested sentences are covered together.** If a sentence's terms are a subset of another sentence's terms, every step that covers the other one covers it too. When a sentence shows as covered only by scenarios clearly written for the other sentence, that is a finding about the story's shape (see "Two sentences are covered together" in `stories.md`), not about test coverage.
