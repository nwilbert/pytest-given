---
name: pytest-given-reviewing
description: Use when reviewing pytest-given artifacts — checking @scenario narration against the implementation, or auditing a glossary, tags, or stories for hygiene, e.g. before merging changes to narrated tests
---

# Reviewing pytest-given artifacts

Narration can be **audited, but nothing verifies it**. No tool compares a step's text to its body, so a passing suite says nothing about whether the narration is true. Review in four layers:

1. The lint settles what a tool can decide.
2. A semantic audit judges what the lint can't.
3. A completeness audit asks what the report leaves out.
4. A last pass checks the glossary, tags and stories.

Don't skip layer 1. It is cheaper and stricter than finding the same problems by reading.

Run the `pytest` commands below through the project's own runner, such as `uv run pytest` or tox.

## 1. Structural gate: run the lint first

```bash
pytest --given-lint
# plus the opt-in rule when the glossary is meant to be fully exercised:
pytest --given-lint -o "given_lint_rules=dead-term=warn"
```

Lint the whole suite, not just the tests a change touches. A `given_lint_ignore` entry for a test outside the selection fails the run as `stale-ignore`. `-o` replaces the project's `given_lint_rules` list instead of adding to it. If the project sets any rules, repeat them in the same value, one per line.

`warn` lint findings print in the summary, an `error` lint finding fails the run, and a clean run prints `narration lint (no findings)`. The rule catalog, and when an ignored `missing-phase` is justified, are in the authoring skill's [lint.md](../pytest-given-authoring/references/lint.md). A lint finding that is a deliberate exception belongs on the project's `given_lint_ignore` list; don't just let it pass in review.

If Markdown documents cite the report, run `pytest-given citations check` and hand its citation findings to the `pytest-given-citing` skill. Where a cited scenario's title or behavior changed, run `citations update`, then reread each sentence that `citations check --covering <node ID>` lists, unresolved links included: the claim may no longer hold. Read each citing passage against the rules under "Writing citations" in the [citing skill](../pytest-given-citing/SKILL.md#writing-citations). A narrated citation's body is the behavior its document claims, so a contradiction is a false claim. A document without citations is no finding.

## 2. Semantic audit: step text against step body

**Reviewing a change? Diff the Markdown report first.** Render `pytest <selection> --no-given-md-lines --given-md=<file>` at the base and at the head of the change, or use a committed report, and diff the two. For a saved JSON report, `pytest-given report <file> --format md --no-lines` does the same. The Markdown has no timestamps or commit SHAs, so the diff shows exactly how the described behavior changed, and it tells you what to audit. Compare it with the code diff in both directions. Changed narration means its body needs another check. A changed step *body* under unchanged narration is the typical sign of drift: the behavior changed, but the spec didn't. If the merge target has moved since the branch left it, judge vocabulary and actions against the code under test as it will be after the merge.

**No base to compare with**, as on a branch that adopts pytest-given? Audit the whole suite. Start with the scenarios whose bodies the branch changed, then go through the rest file by file. `--given-md` needs no project setup, so run it yourself even when CI only writes other formats.

Judge each scenario's step texts against their bodies with the rubric below. `pytest <test file> --given-md=<file> --given-md-source` prints them side by side: each scenario's narration ends with its test function, decorators included, under its line numbers, so you cite `file:line` straight from it. Only the test function is shown. A step with no `with` in the function was recorded by a step fixture or a decorated step helper the body calls, and a constant or helper the body uses is elsewhere in the file, so open the file before you judge a value.

**Step text may abstract, but it must never overstate.**

- **Values:** a quantity, date or amount in the text must match the body's data, even when every assertion passes. Ask for an interpolation (`{BATCH_SIZE}`) over a literal copied from a constant.
- **Quantifiers:** "each", "every", "both" or "all" in a `then` or a scenario title claims every item it covers. Assertions on a sample overstate it: ask for the rest to be asserted, or for the text to be narrowed.
- **Outcomes:** everything a `then` claims must be asserted in it, on a value the code under test produced. The lint can't tell, because the step contains an `assert`. A "never called" claim needs recorded calls asserted in the `then`, not a stub that raises, whose error the code may catch. In a parameter table, the claim must hold for every row: "the scenario errors, saying {error}" over a row that passes is false for that row. A conditional claim ("a coffee is brewed when the machine has beans") still holds on a contrast row where its condition fails, such as an empty machine that brews nothing.
- **Strength:** an assertion must fail when its claim is false. `relpath.endswith('.py')` under "keeps its rootdir-relative source" passes on an absolute path too. Data that keeps two parts in separate fields can't show their order.
- **Raises:** the `then` of an expected raise must not claim more than `match=` checks. When it promises that the message names the offender, offers a hint or includes a file:line, the regex must fail without that detail: `match='Gues'` matches the echoed bad input, not the did-you-mean suggestion. An alternation is only as strong as its weakest branch, so sibling scenarios that narrate *different* refusals may all pass on one generic message. Pin what tells this refusal apart from the others.
- **Expected failures:** an `xfail` without `strict=True` (or the `xfail_strict` ini) stays quietly on working behavior and turns a later regression into an expected failure. Ask for `strict=True`.
- **Actions:** what the `when` names must be what its body calls. Watch for a `when` whose text reads like arrangement while its body also performs the action, which then appears nowhere in the report.
- **Vocabulary:** each referenced term should show up in the names inside the step: in the body, and in the names of the code it calls directly. A natural-language term over its class (`File glossary` over `FileGlossary`) is no drift. A term ref must also *mean* its term. One chosen just for its word (`Kindless` in "not kindless inference") sends the reader to the wrong row. Flag drift once per term, not once per step, and don't prescribe which side should be renamed.

For a large suite, split layer 2 by test file. One run's Markdown splits at its scenario headings, each followed by its `file::test` line. Hand each reviewer one test file's Markdown, the rubric, and the paths of the test file, the glossary and the code under test, and have it return findings. Where the harness and the user allow subagents, a cheap, fast model is enough, because the rubric needs only that one file's context. Check a sample of their findings before you report them. Title twins, rules narrated at the wrong layer and the list of titles need the whole suite, so the coordinating reviewer does those.

## 3. Completeness audit: what the report doesn't say

Layers 1 and 2 ask whether the narration is true. Neither catches a report that is true line by line but leaves out what matters. When the question is "does this capture the essentials?", for example on a branch adopting pytest-given or for a feature's first scenarios, start from the project's promises and its implementation instead, and follow [references/completeness.md](references/completeness.md).

## 4. Glossary, tags, stories

When the change touches the glossary, tags or stories, or the review audits them, follow [references/hygiene.md](references/hygiene.md).

## Findings are advisory review comments

For each finding, give the file:line, what the narration claims, what the body actually does, and why it matters. Rank findings in this order, most serious first:

1. **False claims:** overstatement found in layer 2, a glossary row stating behavior that no scenario demonstrates or that a scenario contradicts, a pin whose sentence the body never exercises, a citation that contradicts its prose. A false spec misleads every future reader.
2. **Language drift:** a drifting vocabulary does damage slowly instead of lying outright.
3. **Behavior without a scenario:** silence understates, which misleads less than a false claim.
4. **Glossary, tag and story hygiene** (layer 4).
5. **Report legibility** (below).

**Report legibility can be reviewed; taste can't.** The report is documentation, so how it *reads* is in scope. Flag inconsistent casing or wording of the same concept across step texts. Read the scenario titles alone, as a list, by test file:

```bash
jq -r '.scenarios | group_by(.source.relpath)[]
       | .[0].source.relpath, (map(.narration.text) | unique[] | "  " + .)' report.json
```

Flag a title that:

- can't be understood without its steps,
- is a question or a phrase, not a statement of the rule,
- breaks sentence case (a code identifier at the start keeps its case), ends in a period, carries a status note, or uses bold or italic nobody asked for.

Also flag twins: two titles that don't tell their scenarios apart. Twins are often worded differently, so group the titles that state the same rule and compare their test files. The usual pair is a unit test and an integration test. Say which one keeps the scenario: the one whose body proves the title. The authoring skill's [scenarios.md](../pytest-given-authoring/references/scenarios.md) has the rules under "Scenario titles".

Parameter tables are part of the document too. Flag these:

- A column that only makes sense next to a value another step fixes.
- A column that no step narrates.
- A column of Python reprs, such as objects or lists.
- A label column that the body turns back into data, with no attachment showing the data.
- A case ID that misnames its row, or only repeats a column's value.
- An outcome that varies but has no column of its own, or that the body derives from an input column.
- Sibling scenarios that should be one table: the same steps with one arrangement varied, or titles that negate each other.

The fixes are in the authoring skill's [parameter-tables.md](../pytest-given-authoring/references/parameter-tables.md). Report all legibility problems as one combined finding, not one per instance. A wording you would simply have chosen differently is out of scope.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
