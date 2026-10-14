# Writing scenarios

When you decorate a test with `@scenario`, the goal is a report that reads as a truthful behavioral spec. The narration lint checks the structural part of these rules: [lint.md](lint.md) has its rules and what to do about a finding.

## What to decorate

- **Convert behavior, not plumbing.** Decorate tests that assert a rule, such as a calculation, a validation or a dispatch decision. Leave trivial getters, constructors and dataclass round-trips as plain tests. They add noise to the report, not behavior.
- **One scenario per rule, not per branch.** Write the title the way the report's readers know the rule: as a call they make, as an outcome they see (even when code deep inside decides it), or as a part the glossary names. Then decorate a test that proves that title. An outcome needs a test that runs the system, with one exception in the next bullet. A call or a named part needs its own test. If several tests prove the rule, pick the one whose `when` calls the deciding code most directly, so a reader who opens the test finds the implementation quickly. Leave the edge cases as plain tests. A user-visible rule you add or change needs its scenario, or the report never shows it.
- **Each layer narrates what it decides.** A caller's scenario states only what the caller decides: the inputs it passes, how it handles a failure, what it writes, its exit status. Callers of a shared function don't each repeat its rule. A rule decided deep inside the code may still be narrated in a unit test of that code, as one scenario or a parameter table, because running the whole system for every case is slow. In that case, another scenario must run the system through the same code and show its effect for at least one input.
- **Sibling scenarios of one rule are one table.** Merge sibling scenarios into one parametrized scenario (see [parameter-tables.md](parameter-tables.md)) when they share their steps and vary one arrangement, or when their names negate each other ("the reviewer confirms, so it is rejected" and "the reviewer declines, so it is accepted"). Plain tests of the rule that fit its steps become rows. Before you merge or delete a scenario, account for everything only it had:
  - An assertion: keep it, or name the scenario that still makes it.
  - An input the table holds fixed: a booking in another building is not just another "no clash" row.
  - A step that covers a story sentence or holds a term's last term ref: re-run the coverage check from [stories.md](stories.md).

## Scenario titles

Readers scan titles first, often without the steps: in the report's list, in Markdown headings, in a diff.

- **A title states the rule** in plain words and the present tense: subject, verb, outcome. Avoid compressed phrasing ("a finding its own class settled is never offered another") and metaphors ("sits out"). A story example with personas still states its rule: "A paid booking is confirmed to every guest", not "Carol completes the booking". A reader must understand the title without its steps. Aim for 60 to 70 characters and move detail into the steps.
- **A title is a heading.** Use sentence case and no trailing period. A code identifier at the start keeps its case. When the title starts with a term ref, use the bare handle, not `.l`. Steps stay lowercase, because each one continues its keyword's sentence. Leave status out of the title ("planned feature", "failing"); use a mark, which the report shows.
- **Don't format unless asked.** Put a code identifier in a code span (`` `--given-md` ``); leave bold and italic to the user. Titles and steps render `**bold**`, `*italic*` and `` `code` ``; underscores never format, and a marker whose partner sits across a term ref or a value shows as written.
- **Statements only.** No questions, and no phrases like "how much detail is recorded" next to statements. A table's title states the rule its rows decide: "Open alerts of any tool suppress, dismissed ones only of the same tool", not "Which alert may suppress". It doesn't list the rows, because the table shows them.
- **No implementation words.** Exception names, function arguments and internal flags belong in the steps. Name a domain concept with its glossary term. If the glossary doesn't have your word, check whether it has the same concept under another name. If it doesn't, the glossary may be missing a term.
- **Two titles never state the same rule.** This usually happens when a unit test and an integration test cover one rule. Keep the scenario on the test that proves the title (see [one scenario per rule](#what-to-decorate)). Give the other test a title that names what its own layer decides, or remove its decoration and its steps; a step outside a scenario triggers a warning.

## Phase structure

- **Every step maps to code that matters.** `given` arranges, `when` performs the one call under test, and `then` asserts its result. Never write a placeholder step like `with given(...): pass`. A step with no code is a lie in the report, so delete it.
- **Put the call under test in `when`, not inside the `then` assertion.** Write `with when(...): result = sut(x)` and then `with then(...): assert result == …`, not `with then(...): assert sut(x) == …`.
- **One outcome per `then`.** When an action has two independent outcomes, such as a return value *and* a state change, give each its own sibling `then` step. A `then` text that needs an "and" is two steps written as one.
- **When building the object *is* the action under test, `when` builds it and `given` shows only the input.** This applies when a scenario asserts a property of a freshly loaded, parsed or built object (`Order(lines)` computes its total, `parse(doc)` yields all rows). The `given` holds the raw input and, when useful, `attach`es it. The `when` runs the constructor, and the `then` asserts on the result. A `given` that both arranges the input *and* builds the object under test is the most common missed `when`.
- **Two phases are fine when honest, but rarer than they look.** If the assertion inspects a *static property of the arranged state*, not the return value of an action, then `given` + `then` is truthful. Don't invent a `when` for it. Likewise, a pure "constructing X raises" check needs no `given`.

## Parameter tables

A parametrized scenario renders as one narrated tree above a parameter table. Before you decorate a parametrized test or merge sibling scenarios into one, read [parameter-tables.md](parameter-tables.md).

## Arrangement

- **Show the arrangement as a `given`. Don't hide it in the `when` or the assertion.** When the action uses a module constant or a value built on the fly (a document string, a path, a list of rows), bind it in a `with given(...)` block. Don't pass it as a literal into the `when`, the `then` or the `pytest.raises` call.
  - Setup calls that change state (inserting credit, seeding a database) are arrangement too. A scenario with two `when` steps usually hides an arrangement in the first one.
- **Decide a fixture's `given` by what it holds.** Ask: would you write a `given` for this value if you built it inline? A domain value the scenario is about, such as an actor or a work object it acts on, like a document, is arrangement: decorate the fixture with `@given('…')` under `@pytest.fixture`. Infrastructure (a `Glossary()`, `tmp_path`, a connection) stays a bare `@pytest.fixture`. Either way, the arrangement reads the same whether the scenario builds it inline or gets it from a fixture.
- **A parametrized value can be a `given` too.** Its column already shows in the parameter table. When the reader should see it named up front as an arrangement, show it with `Annotated[..., given(Template('… {col} …'))]` on that parameter. For a pure function with one argument, both readings are honest.
- **Attach the concrete artifact a step can only describe.** When a step handles a multi-line value that its text can only summarize, such as a source document, a config snippet or a rendered result, `attach('label', text)` it to that step.
  - **An input document goes on the `given` that arranges it. An output document goes on the `then` that checks it.** Output is the case people miss most. The assertions only sample the result, so the attachment is the only place where a reader sees all of it.
  - **Attach documents, not object dumps.** Skip the attachment when the step text or the parameter table already shows the value, or when the artifact is too big to read inline, like a full HTML page. The exception is a real before and after: when a step reduces a rich input to a small output, attaching the input lets a reader check a claim like "only the first line survives".
  - Across parametrize cases, an attachment whose content varies becomes a column, headed by its label.

## Expected raises

- **Keep pytest-given narration and real assertions separate.** Nest the plain `pytest.raises` inside the narration, never inside a helper named after the narration. Exempt tests from lint rules that forbid nested `with` statements (ruff `SIM117`).
- **Narrate an expected raise with `when_then`.** `` with when_then('the action', 'an `InsufficientCredit` error is raised'), pytest.raises(Exc, match=…): sut(x) `` records a `when` around the call and a sibling `then`. The `then` is recorded once `pytest.raises` catches the error.
  - **Write the `then` as a real outcome.** Name the exception type. When `match=` pins a specific message, say what it reports in domain terms (`'the shortfall amount is reported'`). Never write a bare `'it raises'`.
  - **Check a message with several details in its own `then`.** Use `pytest.raises(E) as excinfo` under the `when_then`, then `with then('the error names …'): assert '…' in str(excinfo.value)`.
  - **The pin must be as specific as the `then`.** A `then` that promises details in the message (the offender, a suggestion, a file:line) needs a `match=` that only a message with that detail passes. With `match='column'` under "names the missing column", the detail can break unnoticed. An alternation (`match=r'odd|dangling|ends'`) is only as strong as its weakest branch, so pin the detail that tells sibling refusals apart.
- **When whether it raises is the outcome, catch the error in the `when`.** This covers a table whose rows are partly refused (`when_then` can't narrate a raise per row) and a scenario showing that a call returns normally. Assert the caught error like any other outcome:
  ```python
  with when(t'the {g["Guest"].l} books {nights} nights'):
      try:
          booking, refusal = book(room, nights), ''
      except BookingRefused as error:
          booking, refusal = None, str(error)
  with then(t'the booking is accepted: {accepted}'):
      assert (booking is not None) == accepted
  with then('a refusal names the minimum stay'):
      assert ('minimum stay' in refusal) == (not accepted)
  ```
  Keep `when_then` for a scenario where every row is refused. "It returns normally" is usually the weak half of a rule: when the code does something instead, such as logging a warning or writing an empty output, assert that.

## Vocabulary and tags

- **Narrate in glossary vocabulary.** Reference terms through handles in t-string step text, like `t'a {g["Room"].l} is booked'` (see [glossaries.md](glossaries.md)). They then render as kind-colored words and feed the Glossary tab's per-term filter. Use `.l` in the middle of a sentence and the bare handle at its start. Use `.s` for a regular plural or verb -s (`.l.s` in the middle of a sentence). Pick a term for its meaning, not its word: a term ref whose definition isn't what the sentence means sends the reader to the wrong row. (Skip this rule if the project has no glossary yet.)
- **The code speaks the language too.** Each referenced term should show up in the names inside the step: in the body, and in the names of the code it calls directly. `File glossary` over a `FileGlossary` call matches by design, since term names are natural language. But `{g["Reservation"]}` over code that only knows `Booking` is language drift, so rename one side.
- **Keep tags separate from the glossary.** A tag that repeats a term is redundant; filter by the term instead. `tag-shadows-term` catches exact collisions. It doesn't catch a tag that names a feature area the glossary covers under another word (`markdown` on scenarios that reference `File glossary`).
- **Expect few tags.** Tags carry only what the glossary can't: behavior (`validation`) and mechanism (`parametrization`). A tag must cut across modules, because a tag used in only one test file repeats the module grouping. It must also stay on a minority of the suite: `happy-path` on most scenarios filters nothing. Once you use a tag, put it on every scenario it describes, or filtering by it will miss some.
- **A `/` nests a tag.** The Tags sidebar files `ticket/ABC-123` under a `ticket` heading, which filters like a package, so a family of tags takes one row. Ticket tags are the family worth having: each one shows exactly one ticket's work in the report.
- **A work-item tag marks one piece of work.** `ticket/ABC-123` or `spec/<slug>` means "added by this piece of work", not "describes this behavior": it need not cut across modules, and other scenarios of the same behavior need not carry it.
- **Keep step text short.** A t-string with two or three term refs reaches your line-length limit fast. Move detail into nested steps instead of one long sentence.

## Keeping it truthful

Step text may abstract, but it must never overstate.

- **A value in the text must match the body.** A quantity, date or amount you narrate is a claim about the data the step actually holds. `'three copies'` over `catalog={'Dune': 1}` is a lie, even when every assertion passes. Interpolate a value the body takes from a constant (`t'a batch of {BATCH_SIZE} rows'`), so the text can't go stale when the constant changes.
- **Everything a `then` claims must be asserted in it.** A `then` that says "…and recorded in the ledger" without such an assertion describes behavior nobody checked. Assert it, or drop the clause. A `then` that sets the value it asserts, or asserts a constant, checks nothing. The asserted value must come from the code under test.
- **A stub that raises when called checks nothing in the `then`.** The code under test may catch its `AssertionError` and fall back to the very outcome the `then` expects. To show a collaborator is never called, record its calls and assert `calls == []` (or `mock.assert_not_called()`) in the `then`.
- **What the `when` names must be what the body calls.** Narrate the action the step performs, not the one the scenario is loosely about. A common mistake: the `when` text reads like more arrangement, but its body arranges *and* makes the call the `then` reports. The action then appears nowhere in the report. Move the setup into a `given`.
- **"Each", "every", "both" and "all" are claims about every item.** A `then` or scenario title with one of these words must assert every item it covers. "Each slot becomes a term ref", backed by assertions on two of three slots, overstates. Assert them all, or narrow the text to what is checked.
- **Mark a scenario written before its implementation `xfail(strict=True)`** (or set `xfail_strict`). It reports as an expected failure, with its reason, steps and error. Once it passes, it fails the run, so you remember to remove the mark. A non-strict mark stays on working behavior and turns a later regression into an expected failure. An `xfail` on one `pytest.param` row is fine too.
- **Stale narration is a stale assertion.** When a change touches a step's *body*, re-read the step's *text* (and the scenario title) in the same edit, and update it if the behavior changed.
- **When narration and body disagree, the narration isn't automatically wrong.** The text may state the intended behavior while the body checks something weaker, or passes for a different reason. Then you have found a broken test: fix the body and keep the words. Weakening the narration to match turns a bad test into a spec that only looks truthful. Ask whether the body would fail if the name's promise were broken.
