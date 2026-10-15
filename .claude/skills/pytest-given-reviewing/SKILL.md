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

`warn` findings print in the summary, an `error` finding fails the run, and a clean run prints `narration lint (no findings)`. The rule catalog, and when an ignored `missing-phase` is justified, are in the authoring skill's [lint.md](../pytest-given-authoring/references/lint.md). A finding that is a deliberate exception belongs on the project's `given_lint_ignore` list; don't just let it pass in review.

If Markdown documents cite the report, run `pytest-given citations check` too, and hand its findings to the `pytest-given-citing` skill. Where a cited scenario's title changed, read the sentence that cites it: the new title may no longer fit.

## 2. Semantic audit: step text against step body

**Reviewing a change? Diff the Markdown report first.** Render `pytest <selection> --no-given-md-lines --given-md=<file>` at the base and at the head of the change, or use a committed report, and diff the two. For a saved JSON report, `pytest-given report <file> --format md --no-lines` does the same. The Markdown has no timestamps or commit SHAs, so the diff shows exactly how the described behavior changed, and it tells you what to audit. Read it in both directions. Changed narration means its body needs another check. Changed step *bodies* with no change in the narration are the typical sign of drift: the behavior changed, but the spec didn't.

**No base to compare with**, as on a branch that adopts pytest-given? Audit the whole suite. Start with the scenarios whose bodies the branch changed, then go through the rest file by file. `--given-md` needs no project setup, so run it yourself even when CI only writes other formats.

Judge each scenario's step texts against their bodies with the rubric below. [references/pairs.md](references/pairs.md) prints them side by side, one file per test file. The rubric is complete on its own, so a reviewer you hand it to needs nothing else.

**Step text may abstract, but it must never overstate.**

- **Values:** a quantity, date or amount in the text must match the body. `'three copies'` over `catalog={'Dune': 1}` is a lie, even when every assertion passes. A literal copied from a constant goes stale when the constant changes; ask for the interpolation (`{BATCH_SIZE}`) instead.
- **Quantifiers:** "each", "every", "both" or "all" in a `then` or a scenario title is a claim about every item it covers. Assertions on a sample overstate it, like "each slot becomes a term ref" backed by checks on two of three slots. Fix it by asserting the rest or by narrowing the text.
- **Outcomes:** everything a `then` claims must be asserted in it. "…and recorded in the ledger" without such an assertion describes behavior nobody checked. So does a `then` that sets the value it asserts, or asserts a constant. The lint doesn't catch these, because the step contains an `assert`. Nor does it catch "never called" backed by a stub that raises: if the code catches the error, nothing checks the claim. Ask for recorded calls asserted in the `then`. In a parameter table, the claim must hold for every row: "the scenario errors, saying {error}" over a row that passes is false for that row.
- **Raises:** the `then` of an expected raise may restate the message that `match=` pins in domain terms, but it must not claim more than the pin checks. Say the `then` promises that the message names the offender, offers a hint or includes a file:line. If the regex also passes without that detail, the pin is too weak, and the claim is unchecked even if the code delivers it today. For example, `match='Gues'` matches the echoed bad input, not the did-you-mean suggestion. A pin with alternatives (`match=r'odd|dangling|ends'`) is only as strong as its weakest branch: sibling scenarios that narrate *different* refusals then all pass on one generic message. Pin what tells this refusal apart from the others.
- **Expected failures:** an `xfail` mark without `strict=True` (and without the `xfail_strict` ini) stays on a scenario quietly once the behavior works. A later regression then shows up as an expected failure. Ask for `strict=True`.
- **Actions:** what the `when` names must be what its body calls. A common drift: the `when` text reads like more arrangement, but its body also performs the action, so the action appears nowhere in the report. Move the setup into a `given`.
- **Vocabulary:** a term ref puts the ubiquitous language right next to the code it describes. So each referenced term should show up in the names inside the step: in the body, and in the names of the code it calls directly. `File glossary` over a `FileGlossary` call matches by design, since term names are natural language and the definition spells out the class. But `Reservation` over code that only knows `Booking` is language drift. A term ref must also *mean* its term. One chosen just for its word (`Kindless` in "not kindless inference") sends the reader to the wrong row. Flag drift once per term, not once per step, and don't prescribe which side should be renamed.

For a large suite, split the audit: one reviewer per test file, each returning findings. Use a subagent where the harness and the user allow it. A cheap, fast model is enough, because the rubric only needs the one file. Otherwise, audit file by file yourself. Check a sample of the subagents' findings yourself before you report them. Only layer 2 can be split by file. Title twins, rules narrated at the wrong layer, and reading the titles as a list all need the whole suite, so the coordinating reviewer does those.

## 3. Completeness audit: what the report doesn't say

Layers 1 and 2 ask whether the narration is true. Neither catches a report that is true line by line but leaves out what matters. When the question is "does this capture the essentials?", for example on a branch adopting pytest-given or for a feature's first scenarios, start from the implementation instead and follow [references/completeness.md](references/completeness.md).

## 4. Glossary, tags, stories

When the change touches the glossary, tags or stories, or the review audits them, follow [references/hygiene.md](references/hygiene.md).

## Findings are advisory review comments

For each finding, give the file:line, what the narration claims, what the body actually does, and why it matters. Rank findings in this order, most serious first:

1. **False claims:** overstatement found in layer 2, a glossary row stating behavior that no scenario demonstrates or that a scenario contradicts, a pin whose sentence the body never exercises. A false spec misleads every future reader.
2. **Language drift:** a drifting vocabulary does damage slowly instead of lying outright.
3. **Behavior without a scenario:** silence understates, which misleads less than a false claim.
4. **Glossary, tag and story hygiene** (layer 4).
5. **Report legibility** (below).

**Report legibility can be reviewed; taste can't.** The report is documentation, so how it *reads* is in scope. Flag inconsistent casing or wording of the same concept across step texts. Read the scenario titles alone, as a list. Flag a title that can't be understood without its steps, that is a question or a phrase instead of a statement of the rule, that breaks sentence case (a code identifier at the start keeps its case), that ends in a period, that carries a status note, or that uses bold or italic nobody asked for. Also flag two titles that don't tell their scenarios apart. Such twins are often worded differently, so group the titles that state the same rule and compare their test files. The usual pair is a unit test and an integration test. Say which of the two should keep the scenario: the one whose body proves the title. The authoring skill's [scenarios.md](../pytest-given-authoring/references/scenarios.md) has the rules under "Scenario titles".

Parameter tables are part of the document too. Flag these:

- A column that only makes sense next to a value another step fixes, like `existing_start=50` next to a new booking that another step fixes at hours 10 to 20.
- A column that no step narrates.
- A label column that the body turns back into data, with no attachment showing the data.
- A case ID that misnames its row, or only repeats a column's value.
- An outcome that varies but has no column of its own, or that the body derives from an input column (`[1, 2] if enabled else []`).
- Sibling scenarios that should be one table: the same steps with one arrangement varied, or titles that negate each other.

The fixes are in the authoring skill's [parameter-tables.md](../pytest-given-authoring/references/parameter-tables.md). Report all legibility problems as one combined finding, not one per instance. A wording you would simply have chosen differently is out of scope.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
