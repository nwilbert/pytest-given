---
name: pytest-given-reviewing
description: Use when reviewing pytest-given artifacts — checking @scenario narration against the implementation, or auditing a glossary, tags, or stories for hygiene, e.g. before merging changes to narrated tests
---

# Reviewing pytest-given artifacts

Narration is **auditable, not verified**: nothing mechanical compares a step's text to its body, so a passing suite says nothing about the narration being true. Review in layers — the lint decides what is mechanically decidable, a semantic audit judges what it can't, a completeness audit asks what the report leaves out entirely, and a last pass checks the glossary, tags and stories for hygiene. Don't skip layer 1: it is cheaper and stricter than re-deriving the same findings by reading.

## 1. Structural gate — run the lint first

```bash
pytest <selection> --given-lint
# plus the opt-in rule when the glossary is meant to be fully exercised:
pytest <selection> --given-lint -o "given_lint_rules=dead-term=warn"
```

`warn` findings print in the summary; an `error` finding fails the run. The rule catalog and the honest-two-phase ignore convention live in the authoring skill's [scenarios.md](../pytest-given-authoring/references/scenarios.md) under "Mechanical counterparts". A finding that is a deliberate exception belongs on the project's `given_lint_ignore` list, never silently waved through in review — stale entries fail the run, so the list cannot rot.

## 2. Semantic audit — step text vs step body

**Reviewing a change rather than a whole suite? Diff the Markdown report first.** Render `pytest <selection> --given-md=<file>` at base and head and diff the two files (or diff the committed report, if the project checks one in). The Markdown sink is deterministic — no timestamps or commit SHAs, unlike the JSON/HTML sinks — so the diff *is* the behavioral delta in prose, and it scopes the audit to the scenarios whose narration actually changed. Read it in both directions: narration that changed needs its body re-checked, and a change to step *bodies* that leaves the narration diff empty is the drift signature — behavior may have moved while the spec stood still.

**No base report to diff against?** On an adoption branch the base has no scenarios, so the diff *is* the whole report — not a reason to skip the layer. Audit the full suite ordered by risk: scenarios whose bodies the branch touched first, then the rest file by file (fan out as below). `--given-md` is a plain pytest flag needing no project wiring, so run it yourself even when CI only configures the HTML/JSON sinks.

For each scenario under review, read the step texts against their bodies and judge with one rubric — restated here rather than linked, because the fan-out below hands one file to one reviewer who has to carry it without loading a second skill. Its authoring-time counterpart is the authoring skill's [scenarios.md](../pytest-given-authoring/references/scenarios.md) ("Keeping it truthful", "Expected raises", "Vocabulary and tags") — change one, change both.

Don't collect the bodies by hand: [references/pairs.md](references/pairs.md) dumps each scenario's narration beside the source of its test, one file per test file — also the fan-out unit below.

**Step text may abstract; it must never overstate.**

- **Values** — a quantity, date, or amount in the text must match the body: `'three copies'` over `catalog={'Dune': 1}` is a lie, even when every assertion passes.
- **Quantifiers** — "each", "every", "both", "all" in a `then` is a claim about every item it ranges over; assertions on a representative subset ("each slot becomes a term ref" backed by two of three slots) overstate. The fix is asserting the rest or narrowing the text.
- **Outcomes** — everything a `then` claims must be asserted in it: "…and recorded in the ledger" with no such assertion is fabricated behavior.
- **Raises** — the `then` of an expected raise may translate the `match=`-pinned message into domain terms, but must not add claims the message doesn't carry. Judge against the pin, not the implementation: a `then` promising the message names the offender, a hint, or a file:line is under-pinned when the regex would also pass on a message without that detail (e.g. `match='Gues'` matching the echoed bad input rather than the did-you-mean suggestion) — even if the implementation currently includes it, the narrated claim is unverified and can regress silently. An alternation pin (`match=r'odd|dangling|ends'`) holds only its weakest branch, so siblings narrating *different* refusals all pass on one generic message — pin what tells this refusal from its neighbours.
- **Actions** — what the `when` names must be what the body calls. The usual drift: a `when` reading as more arrangement while its body also performs the action, which then appears nowhere in the report. Move the setup into a `given`.
- **Vocabulary** — a term ref puts the ubiquitous language directly next to the code it describes: each referenced term should be reflected in the naming within the step — the body and the SUT names it directly calls. `File glossary` over a `FileGlossary` call matches by design (term names are natural language; the definition spells the class), but `Reservation` over code that only knows `Booking` is language drift. Flag once per term, not per step, and report the drift without prescribing which side renames.

For a large suite, fan the audit out: one reviewer per test file — a subagent where the harness has them (a cheap, fast model suffices; the rubric is local to each file) — each returning findings; otherwise audit inline, file by file. Verify a sample of any fan-out findings yourself before reporting them.

## 3. Completeness audit — what the report doesn't say

Layers 1 and 2 start from the narration and ask whether it is true; neither catches a report that is truthful line by line and still misrepresents the system by omission. When the question is "does this capture the gist?" — an adoption branch, a feature's first scenarios — invert the direction: start from the implementation and ask what the report fails to say. Bound the sweep to the code the change touches.

- **Unnarrated behavior branches.** Walk the behavior-bearing branches of the code under review — a scoping rule, a precedence decision, a fallback path — and check each has a scenario naming it. A branch covered only by an undecorated test is invisible in the report; one with no test at all rates higher, because an otherwise complete-looking spec now hides it.
- **Glossary rows that assert behavior.** A definition making a claim ("X takes precedence over Y", "must be unique") is a spec sentence in its own right. When no scenario demonstrates that claim, the glossary is unbacked documentation — flag the pair and prefer pinning the behavior in a scenario over softening the definition.
- **Rules the release notes announce.** Check that a scenario names each rule the CHANGELOG's unreleased entries state — the project promising a behavior in its own words, and what bounds a whole-suite review the way a diff bounds a change review. A rule narrated half (the fix named, the escape hatch not) counts.

Rate an unnarrated branch below overstatement: silence understates, which misleads less than a false claim. A glossary row asserting untested behavior is not silence — it rates with layer 2.

## 4. Glossary, tags, stories

The first four mirror the authoring skill's [glossaries.md](../pytest-given-authoring/references/glossaries.md) ("Keeping the glossary honest"); the fifth mirrors [stories.md](../pytest-given-authoring/references/stories.md). Same reason as the layer-2 rubric — change one, change both.

- A **dead term** (layer 1, opt-in rule) that describes unimplemented behavior is misleading domain documentation — flag it. Deleting the term is as often the answer as adding a reference; don't accept references manufactured to appease the rule. Check first whether an undecorated test already covers the row's behavior: then the fix is decorating it, not deleting the term. A term that is simply real vocabulary no scenario happens to narrate is **not** a finding — the glossary documents the domain, not the suite's coverage.
- **Dilution** is the inverse finding: a row nothing would miss — a generic verb minted to fill a story slot (a bare word belongs there), a concept duplicated under a second name, a term added only to render as a term ref. A sharp, lean glossary outranks an impressive-looking one.
- An **oversized glossary** is a structural finding: a glossary only works read whole, so one grown past a single comfortable reading likely spans more than one bounded context. Raise it as a design question — a suite supports only one glossary, so splitting per context means splitting the suite. Don't fix size by trimming healthy terms.
- `tag-shadows-term` is linted; the fix is dropping the tag, **not spreading tags wider**. Tags stay orthogonal to the glossary (behavior, mechanism), so sparse tagging is usually correct — don't report it as a finding.
- An **uncovered story activity** is a gap worth noting — unless the declaration site marks it deliberate (a story maps the whole flow, human activities included). Coverage is matched per step: one step's term refs must include all of an activity's terms. The Stories tab shows it, but that is HTML and `--given-md` has no Stories section — the full rule and a ready-to-run query over the JSON report are in [references/story-coverage.md](references/story-coverage.md).

## Findings are advisory review comments

For each finding: file:line, what the narration claims, what the body actually does, why it matters. Rate truthfulness findings highest — a false spec misleads every future reader; language drift rates below that, because a drifted vocabulary erodes slowly rather than lying outright.

**Report legibility is reviewable; taste is not.** The premise of the whole exercise is that the report is documentation, so how the document *reads* is in scope: inconsistent casing or phrasing of the same concept across step texts, a scenario name that doesn't parse as a sentence, two scenarios whose titles don't distinguish them. Rate these lowest and report them as one batched finding, not one per instance. Out of scope is what legibility doesn't reach — a wording you would simply have chosen differently.

*These files are installed by `pytest-given skills install` and overwritten on reinstall — don't edit them in place.*
