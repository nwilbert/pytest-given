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

## 1. Structural gate: run the lint first

```bash
pytest --given-lint
# plus the opt-in rule when the glossary is meant to be fully exercised:
pytest --given-lint -o "given_lint_rules=dead-term=warn"
```

Lint the whole suite, not just the tests a change touches. A `given_lint_ignore` entry for a test outside the selection fails the run as `stale-ignore`. `-o` replaces the project's `given_lint_rules` list instead of adding to it. If the project sets any rules, repeat them in the same value, one per line.

`warn` findings print in the summary, and an `error` finding fails the run. The rule catalog is in the authoring skill's [scenarios.md](../pytest-given-authoring/references/scenarios.md) under "Mechanical counterparts". Under "Phase structure", the same file has the test an ignored `missing-phase` must pass: two phases must be honest. A finding that is a deliberate exception belongs on the project's `given_lint_ignore` list; don't just let it pass in review. Entries that no longer suppress anything fail the run, so the list can't go stale.

## 2. Semantic audit: step text against step body

**Reviewing a change? Diff the Markdown report first.** Render `pytest <selection> --no-given-md-lines --given-md=<file>` at the base and at the head of the change, or use a committed report, and diff the two. For a saved JSON report, `pytest-given report <file> --format md --no-lines` does the same. The Markdown has no timestamps or commit SHAs, so the diff shows exactly how the described behavior changed, and it tells you what to audit. Read it in both directions. Changed narration means its body needs another check. Changed step *bodies* with no change in the narration are the typical sign of drift: the behavior changed, but the spec didn't.

**No base to compare with**, as on a branch that adopts pytest-given? Audit the whole suite. Start with the scenarios whose bodies the branch changed, then go through the rest file by file. `--given-md` needs no project setup, so run it yourself even when CI only writes other formats.

Judge each scenario's step texts against their bodies with the rubric below. [references/pairs.md](references/pairs.md) prints them side by side, one file per test file. The rubric is complete on its own, so a reviewer you hand it to needs nothing else.

**Step text may abstract, but it must never overstate.**

- **Values:** a quantity, date or amount in the text must match the body. `'three copies'` over `catalog={'Dune': 1}` is a lie, even when every assertion passes. A literal copied from a constant goes stale when the constant changes; ask for the interpolation (`{BATCH_SIZE}`) instead.
- **Quantifiers:** "each", "every", "both" or "all" in a `then` or a scenario name is a claim about every item it covers. Assertions on a sample overstate it, like "each slot becomes a term ref" backed by checks on two of three slots. Fix it by asserting the rest or by narrowing the text.
- **Outcomes:** everything a `then` claims must be asserted in it. "…and recorded in the ledger" without such an assertion describes behavior nobody checked. So does a `then` that sets the value it asserts, or asserts a constant. The lint doesn't catch these, because the step contains an `assert`. Nor does it catch "never called" backed by a stub that raises: if the code catches the error, nothing checks the claim. Ask for recorded calls asserted in the `then`.
- **Raises:** the `then` of an expected raise may restate the message that `match=` pins in domain terms, but it must not claim more than the pin checks. Say the `then` promises that the message names the offender, offers a hint or includes a file:line. If the regex also passes without that detail, the pin is too weak, and the claim is unchecked even if the code delivers it today. For example, `match='Gues'` matches the echoed bad input, not the did-you-mean suggestion. A pin with alternatives (`match=r'odd|dangling|ends'`) is only as strong as its weakest branch: sibling scenarios that narrate *different* refusals then all pass on one generic message. Pin what tells this refusal apart from the others.
- **Expected failures:** an `xfail` mark without `strict=True` (and without the `xfail_strict` ini) stays on a scenario quietly once the behavior works. A later regression then shows up as an expected failure. Ask for `strict=True`.
- **Actions:** what the `when` names must be what its body calls. A common drift: the `when` text reads like more arrangement, but its body also performs the action, so the action appears nowhere in the report. Move the setup into a `given`.
- **Vocabulary:** a term ref puts the ubiquitous language right next to the code it describes. So each referenced term should show up in the names inside the step: in the body, and in the names of the code it calls directly. `File glossary` over a `FileGlossary` call matches by design, since term names are natural language and the definition spells out the class. But `Reservation` over code that only knows `Booking` is language drift. A term ref must also *mean* its term. One chosen just for its word (`Kindless` in "not kindless inference") sends the reader to the wrong row. Flag drift once per term, not once per step, and don't prescribe which side should be renamed.

For a large suite, split the audit: one reviewer per test file, each returning findings. Use a subagent where the harness and the user allow it. A cheap, fast model is enough, because the rubric only needs the one file. Otherwise, audit file by file yourself. Check a sample of the subagents' findings yourself before you report them. Only layer 2 can be split by file. Title twins, rules narrated at the wrong layer, and reading the titles as a list all need the whole suite, so the coordinating reviewer does those.

## 3. Completeness audit: what the report doesn't say

Layers 1 and 2 start from the narration and ask whether it is true. Neither catches a report that is true line by line but still misrepresents the system by leaving things out. When the question is "does this capture the essentials?", for example on a branch adopting pytest-given or for a feature's first scenarios, reverse the direction. Start from the implementation and ask what the report fails to say. Limit the search to the code the change touches.

- **Behavior without a scenario.** Go through the branches of the code under review that carry behavior: a scoping rule, a precedence decision, a fallback path. Check that each has a scenario that names it. A branch that only an undecorated test covers is invisible in the report. A branch with no test at all rates higher, because the spec looks complete while hiding it. A rule narrated at the wrong layer is also a finding. There are two cases. In one, several callers each repeat a rule that a shared function decides. In the other, a unit scenario's title claims what the system does, but its body only calls internal code, and no other scenario shows a run reaching that code. The second case is a false claim: decorate a test that proves the title instead. Look among the undecorated tests first; the right one often exists already.

  Start with the undecorated tests in test files that hold a scenario. They are where most gaps sit, next to the narrated tests of the same code:

  ```bash
  pytest <selection> -m pytest_given --given-json=report.json
  pytest <selection> -m "not pytest_given" --collect-only -q > plain.txt
  jq -r --rawfile plain plain.txt '
    [.scenarios[].id | split("::")[0]] as $files
    | $plain | split("\n") | map(select(contains("::")) | sub("[[].*"; "")) | unique[]
    | select(split("::")[0] | IN($files[]))' report.json
  ```

  For the code itself, compare the code coverage of `pytest -m pytest_given` with a full run's. Lines only the full run covers are behavior only plain tests reach.
- **Parameter tables that can't show what decides.** For each input that decides a parametrized scenario's outcome, some row should change only that input and flip the outcome. Without such a row, the table only lists examples, and the rule that decides between them stays unnarrated. Ask for the contrast row, at the boundary if there is one, instead of splitting the table into one scenario per row. A refusal can be a contrast row too, and a sibling scenario with the flipped outcome doesn't make up for a missing row.
- **Glossary rows that state behavior.** A definition that makes a claim ("X takes precedence over Y", "must be unique") is part of the spec. When no scenario demonstrates the claim, the glossary documents something nothing checks. Flag the row and the missing scenario, and prefer adding a scenario to weakening the definition. When a scenario contradicts the row, the row is a false claim.
- **Rules the release notes announce.** If the project keeps a changelog, check that a scenario names each rule its unreleased entries state. That is the project promising a behavior in its own words. For a review of the whole suite, the changelog limits the scope the way a diff does for a change. A rule narrated only in part, such as the fix without the way to opt out, is a finding too.

## 4. Glossary, tags, stories

- A **dead term** (layer 1, opt-in rule) that describes behavior nobody implemented is misleading domain documentation, so flag it. Deleting the term is as often the fix as adding a reference. Don't accept references invented just to satisfy the rule. First check whether an undecorated test already covers the row's behavior, or a step already uses the term as plain text. Then the fix is to decorate the test or add the term ref, not to delete the term. A term that is real vocabulary, but that no scenario happens to narrate, is **not** a finding. The glossary documents the domain, not the suite's coverage.
- **Dilution** is the opposite finding: a row nobody would miss. Examples are a generic verb added to fill a story slot (a bare word belongs there), a concept listed twice under two names, or a term added only to render as a term ref. A small, precise glossary is better than one that just looks impressive.
- An **oversized glossary** is a structural finding. A glossary only works when it is read as a whole, so one too long to read comfortably in one sitting probably covers more than one bounded context. Raise it as a design question: a suite supports only one glossary, so splitting by context means splitting the suite. Don't reduce the size by removing good terms.
- The lint checks `tag-shadows-term`. The fix is to remove the tag, **not to add more tags**. Tags stay separate from the glossary (behavior, mechanism), so having few tags is usually right; don't report it as a finding. A tag missing from some of the scenarios it describes is a finding, because filtering by it then misses those scenarios.
- An **uncovered story sentence** is a gap in the story's telling, not in the tests (untested behavior is layer 3). Note it, unless the place that declares it marks it as deliberate; a story maps the whole flow, including human work. Read coverage from the JSON report. The queries, including one for scenarios that name a story but cover none of it, and how to explain *why* a sentence is uncovered, are in [references/story-coverage.md](references/story-coverage.md).

## Findings are advisory review comments

For each finding, give the file:line, what the narration claims, what the body actually does, and why it matters. Rank findings in this order, most serious first:

1. **False claims:** overstatement found in layer 2, a glossary row stating behavior that no scenario demonstrates or that a scenario contradicts, a pin whose sentence the body never exercises. A false spec misleads every future reader.
2. **Language drift:** a drifting vocabulary does damage slowly instead of lying outright.
3. **Behavior without a scenario:** silence understates, which misleads less than a false claim.
4. **Glossary, tag and story hygiene** (layer 4).
5. **Report legibility** (below).

**Report legibility can be reviewed; taste can't.** The whole point is that the report is documentation, so how it *reads* is in scope. Flag inconsistent casing or wording of the same concept across step texts. Read the scenario titles alone, as a list. Flag a title that can't be understood without its steps, that is a question or a phrase instead of a statement of the rule, that breaks sentence case (a code identifier at the start keeps its case), that ends in a period, or that carries a status note. Also flag two titles that don't tell their scenarios apart. Such twins are often worded differently, so group the titles that state the same rule and compare their test files. The usual pair is a unit test and an integration test. Say which of the two should keep the scenario: the one whose body proves the title. The authoring skill's [scenarios.md](../pytest-given-authoring/references/scenarios.md) has the rules under "Scenario titles".

Parameter tables are part of the document too. Flag these:

- A column that only makes sense next to a value another step fixes, like `existing_start=50` next to a new booking that another step fixes at hours 10 to 20.
- A column that no step narrates.
- A label column that the body turns back into data, with no attachment showing the data.
- An outcome that varies but has no column of its own.
- Sibling scenarios that should be one table: the same steps with one arrangement varied, or names that negate each other.

The fixes are in the authoring skill's [scenarios.md](../pytest-given-authoring/references/scenarios.md) under "Parameter tables". Report all legibility problems as one combined finding, not one per instance. A wording you would simply have chosen differently is out of scope.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
