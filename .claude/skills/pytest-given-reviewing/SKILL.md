---
name: pytest-given-reviewing
description: Use when reviewing pytest-given artifacts — checking @scenario narration against the implementation, or auditing a glossary, tags, or stories for hygiene, e.g. before merging changes to narrated tests
---

# Reviewing pytest-given artifacts

Narration is **auditable, not verified**: nothing mechanical compares a step's text to its body, so a passing suite says nothing about the narration being true. Review in two layers — the lint decides what is mechanically decidable, then a semantic audit judges what it can't. Don't skip layer 1: it is cheaper and stricter than re-deriving the same findings by reading.

## 1. Structural gate — run the lint first

```bash
pytest <selection> --given-lint=true
# plus the opt-in rule when the glossary is meant to be fully exercised:
pytest <selection> --given-lint=true -o "given_lint_rules=dead-term=warn"
```

`warn` findings print in the summary; an `error` finding fails the run. The rule catalog and the honest-two-phase ignore convention live in the authoring skill's [scenarios.md](../pytest-given-authoring/references/scenarios.md) under "Mechanical counterparts". A finding that is a deliberate exception belongs on the project's `given_lint_ignore` list, never silently waved through in review — stale entries fail the run, so the list cannot rot.

## 2. Semantic audit — step text vs step body

**Reviewing a change rather than a whole suite? Diff the Markdown report first.** Render `pytest <selection> --given-md=<file>` at base and head and diff the two files (or diff the committed report, if the project checks one in). The Markdown sink is deterministic — no timestamps or commit SHAs, unlike the JSON/HTML sinks — so the diff *is* the behavioural delta in prose, and it scopes the audit to the scenarios whose narration actually changed. Read it in both directions: narration that changed needs its body re-checked, and a change to step *bodies* that leaves the narration diff empty is the drift signature — behaviour may have moved while the spec stood still.

For each scenario under review, read the step texts against their bodies (jump via the ``file.py:line`` anchor under each `--given-md` heading, or `.source` in the JSON report) and judge with one rubric:

**Step text may abstract; it must never overstate.**

- **Values** — a quantity, date, or amount in the text must match the body: `'three copies'` over `catalog={'Dune': 1}` is a lie, even when every assertion passes.
- **Quantifiers** — "each", "every", "both", "all" in a `then` is a claim about every item it ranges over; assertions on a representative subset ("each slot becomes a term ref" backed by two of three slots) overstate. The fix is asserting the rest or narrowing the text.
- **Outcomes** — everything a `then` claims must be asserted in it: "…and recorded in the ledger" with no such assertion is fabricated behaviour.
- **Raises** — the `then` of an expected raise may translate the `match=`-pinned message into domain terms, but must not add claims the message doesn't carry. Judge against the pin, not the implementation: a `then` promising the message names the offender, a hint, or a file:line is under-pinned when the regex would also pass on a message without that detail (e.g. `match='Gues'` matching the echoed bad input rather than the did-you-mean suggestion) — even if the implementation currently includes it, the narrated claim is unverified and can regress silently.
- **Actions** — what the `when` names must be what the body calls.
- **Vocabulary** — a term ref puts the ubiquitous language directly next to the code it describes: each referenced term should be reflected in the naming within the step — the body and the SUT names it directly calls. `File glossary` over a `FileGlossary` call matches by design (term names are natural language; the definition spells the class), but `Reservation` over code that only knows `Booking` is language drift. Flag once per term, not per step, and report the drift without prescribing which side renames.

For a large suite, fan the audit out: one reviewer per test file — a subagent where the harness has them (a cheap, fast model suffices; the rubric is local to each file) — each returning findings; otherwise audit inline, file by file. Verify a sample of any fan-out findings yourself before reporting them.

## 3. Glossary, tags, stories

- A **dead term** (layer 1, opt-in rule) that describes unimplemented behaviour is misleading domain documentation — flag it. The fix is as often deleting the term as adding a reference; don't accept references manufactured to appease the rule.
- **Dilution** is the inverse finding: a row nothing would miss — a generic verb minted to fill a story slot (a bare word belongs there), a concept duplicated under a second name, a term added only to render as a pill. A sharp, lean glossary outranks an impressive-looking one.
- An **oversized glossary** is a structural finding: a glossary only works read whole, so one grown past a single comfortable reading likely spans more than one bounded context. Recommend splitting it per context; don't fix size by trimming healthy terms.
- `tag-shadows-term` is linted; the fix is dropping the tag, **not spreading tags wider**. Tags stay orthogonal to the glossary (behaviour, mechanism), so sparse tagging is usually correct — don't report it as a finding.
- A story activity no scenario covers is a gap worth noting: check scenarios' `story_id` bindings and term coverage (the HTML report's Stories tab shows a coverage chip per activity).

## Findings are advisory review comments

For each finding: file:line, what the narration claims, what the body actually does, why it matters. Rate truthfulness findings highest — a false spec misleads every future reader; language drift rates below that, because a drifted vocabulary erodes slowly rather than lying outright. Style preferences the authoring rules don't state are not findings.
