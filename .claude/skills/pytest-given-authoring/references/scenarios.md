# Writing scenarios

When you decorate a test with `@scenario`, the goal is a report that reads as a truthful behavioral spec.

## What to decorate

- **Convert behavior, not plumbing.** Decorate tests that assert a rule, such as a calculation, a validation or a dispatch decision. Leave trivial getters, constructors and dataclass round-trips as plain tests. They add noise to the report, not behavior.
- **One scenario per rule, not per branch.** Write the title the way the report's readers know the rule: as a call they make, as an outcome they see (even when code deep inside decides it), or as a part the glossary names. Then decorate a test that proves that title. An outcome needs a test that runs the system, with one exception in the next bullet. A call or a named part needs its own test. If several tests prove the rule, pick the one whose `when` calls the deciding code most directly, so a reader who opens the test finds the implementation quickly. Leave the edge cases as plain tests. A user-visible rule you add or change needs its scenario, or the report never shows it.
- **Each layer narrates what it decides.** A caller's scenario states only what the caller decides: the inputs it passes, how it handles a failure, what it writes, its exit status. Callers of a shared function don't each repeat its rule. A rule decided deep inside the code may still be narrated in a unit test of that code, as one scenario or a parameter table, because running the whole system for every case is slow. In that case, another scenario must run the system through the same code and show its effect for at least one input.
- **Sibling scenarios of one rule are one table.** Merge sibling scenarios into one parametrized scenario (see [Parameter tables](#parameter-tables)) when they share their steps and vary one arrangement, or when their names negate each other ("the reviewer confirms, so it is rejected" and "the reviewer declines, so it is accepted"). Plain tests of the rule that fit its steps become rows. Before you merge or delete a scenario, account for everything only it had:
  - An assertion: keep it, or name the scenario that still makes it.
  - An input the table holds fixed: a booking in another building is not just another "no clash" row.
  - A step that covers a story sentence or holds a term's last term ref: re-run the coverage check from [stories.md](stories.md).

## Scenario titles

Readers scan titles first, often without the steps: in the report's list, in Markdown headings, in a diff.

- **A title states the rule** in plain words and the present tense: subject, verb, outcome. Avoid compressed phrasing ("a finding its own class settled is never offered another") and metaphors ("sits out"). A story example with personas still states its rule: "A paid booking is confirmed to every guest", not "Carol completes the booking". A reader must understand the title without its steps. Aim for 60 to 70 characters and move detail into the steps.
- **A title is a heading.** Use sentence case and no trailing period. A code identifier at the start keeps its case. When the title starts with a term ref, use the bare handle, not `.l`. Steps stay lowercase, because each one continues its keyword's sentence. Leave status out of the title ("planned feature", "failing"); use a mark, which the report shows.
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

A parametrized scenario renders as one narrated tree above a parameter table. A reader uses that table as a decision table: one row per input combination, with its outcomes.

- **Step structure must not depend on parameter values.** Every row is shown against the step structure of the first case, so a `with given/when/then(...)` inside an `if` on a parametrize value fails the run. When the steps really differ per case, decline the merge with `@scenario(..., group_parametrized=False)`. When the cases are different behaviors, not one behavior narrated two ways, split them into separate scenarios.
- **Narrate what varies with a t-string that interpolates a bare name.** `when(t'the drink costs {price} euros')` puts a `{price}` token in the step and adds a column with each case's value. Keep everything else the same across cases: the sentence, the `attach` labels, the term refs. To narrate a value derived from a column, bind it to its own local first (`price = cup_size * 0.01`, then `{price}`).
- **A column must make sense on its own.** Sometimes the outcome depends on how a varied input relates to a fixed one. Then the column holds the relation (`hours_later`, `same_room`), not the varied input's raw value. `existing_start=50` or `existing_room='B'` only make sense next to a new booking that another step fixes in room A at hours 10 to 20. Merged tables fall into this too: parametrizing the value an old step text happened to name produces such columns. Arrange the fixed side first, so the relation has something to refer to. Whole objects as columns fail the same way, because a reader can't compare two `Booking(...)` reprs at a glance.
- **Never turn a label back into data.** The body may unpack a relation column the way its narration says (`'A' if same_room else 'B'` under "same room: {same_room}"). It never maps a descriptive label to the input (`{'40 hours later': 40}[shift]`), and no label column sits next to the data it describes. In both cases, the report shows a claim that nothing checks against the input. A document is the exception, because it can't be shown as a column: parametrize a label, look the document up, and `attach` it, so the row shows both.
- **Contrast rows show what decides.** For each input that decides the outcome, include a row that changes only that input and flips the outcome. Put it at the boundary if there is one: moved 10 hours later, a booking still shares an hour; 11 hours later, it doesn't. A table whose rows all have the same outcome can't show which column matters, even when another scenario has the flipped case. Two exceptions need no flip: a column that lists forms the rule treats alike, and a flip that would need other steps, which stays in its own scenario.
- **A refusal is a row too.** `when_then` can't narrate a raise per row. When accepted and refused inputs share the steps, catch the refusal in the `when` and assert it like any other outcome:
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
  Keep `when_then` for a scenario where every row is refused.
- **Outcomes are columns, and the `then` asserts against them.** An outcome that varies gets a column. A `then` names it and holds for every row (`assert (0 in result.clashes) == clashes` under "it clashes: {clashes}"); don't put an `if` on the column inside the step. The main outcome gets its own column even when another column implies it: `settled_by=None` implies "no clash", but a reader looks for the clash. Columns follow the order in which the narration first shows them, so an input narrated in a `given` comes before an outcome in a `then`.

## Arrangement

- **Show the arrangement as a `given`. Don't hide it in the `when` or the assertion.** When the action uses a module constant or a value built on the fly (a document string, a path, a list of rows), bind it in a `with given(...)` block. Don't pass it as a literal into the `when`, the `then` or the `pytest.raises` call.
  - Setup calls that change state (inserting credit, seeding a database) are arrangement too. A scenario with two `when` steps usually hides an arrangement in the first one.
- **Decide a fixture's `given` by what it holds.** Ask: would you write a `given` for this value if you built it inline? A domain value the scenario is about, such as an actor, a document or an entity it acts on, is arrangement: decorate the fixture with `@given('…')` under `@pytest.fixture`. Infrastructure (a `Glossary()`, `tmp_path`, a connection) stays a bare `@pytest.fixture`. Either way, the arrangement reads the same whether the scenario builds it inline or gets it from a fixture.
- **A parametrized value can be a `given` too.** Its column already shows in the parameter table. When the reader should see it named up front as an arrangement, show it with `Annotated[..., given(Template('… {col} …'))]` on that parameter. For a pure function with one argument, both readings are honest.
- **Attach the concrete artifact a step can only describe.** When a step handles a multi-line value that its text can only summarize, such as a source document, a config snippet or a rendered result, `attach('label', text)` it to that step.
  - **An input document goes on the `given` that arranges it. An output document goes on the `then` that checks it.** Output is the case people miss most. The assertions only sample the result, so the attachment is the only place where a reader sees all of it.
  - **Attach documents, not object dumps.** Skip the attachment when the step text or the parameter table already shows the value, or when the artifact is too big to read inline, like a full HTML page. The exception is a real before and after: when a step reduces a rich input to a small output, attaching the input lets a reader check a claim like "only the first line survives".
  - Across parametrize cases, an attachment whose content varies becomes a column, headed by its label.

## Expected raises

- **Keep pytest-given narration and real assertions separate.** Nest the plain `pytest.raises` inside the narration, never inside a helper named after the narration. Exempt tests from lint rules that forbid nested `with` statements (ruff `SIM117`).
- **Narrate an expected raise with `when_then`.** `with when_then('the action', 'an `InsufficientCredit` error is raised'), pytest.raises(Exc, match=…): sut(x)` records a `when` around the call and a sibling `then`. The `then` is recorded once `pytest.raises` catches the error.
  - **Write the `then` as a real outcome.** Name the exception type. When `match=` pins a specific message, say what it reports in domain terms (`'the shortfall amount is reported'`). Never write a bare `'it raises'`.
  - **Check a message with several details in its own `then`.** Use `pytest.raises(E) as excinfo` under the `when_then`, then `with then('the error names …'): assert '…' in str(excinfo.value)`.
  - **The pin must be as specific as the `then`.** A `then` that promises details in the message (the offender, a suggestion, a file:line) needs a `match=` that only a message with that detail passes. With `match='column'` under "names the missing column", the detail can break unnoticed. An alternation (`match=r'odd|dangling|ends'`) is only as strong as its weakest branch, so pin the detail that tells sibling refusals apart.

## Vocabulary and tags

- **Narrate in glossary vocabulary.** Reference terms through handles in t-string step text, like `t'a {g["Room"].l} is booked'` (see [glossaries.md](glossaries.md)). They then render as kind-colored words and feed the Glossary tab's per-term filter. Use `.l` in the middle of a sentence and the bare handle at its start. Use `.s` for a regular plural or verb -s (`.l.s` in the middle of a sentence). Pick a term for its meaning, not its word: a term ref whose definition isn't what the sentence means sends the reader to the wrong row. (Skip this rule if the project has no glossary yet.)
- **The code speaks the language too.** Each referenced term should show up in the names inside the step: in the body, and in the names of the code it calls directly. `File glossary` over a `FileGlossary` call matches by design, since term names are natural language. But `{g["Reservation"]}` over code that only knows `Booking` is language drift, so rename one side.
- **Keep tags separate from the glossary.** A tag that repeats a term is redundant; filter by the term instead. `tag-shadows-term` catches exact collisions. It doesn't catch a tag that names a feature area the glossary covers under another word (`markdown` on scenarios that reference `File glossary`).
- **Expect few tags.** Tags carry only what the glossary can't: behavior (`validation`) and mechanism (`parametrization`). A tag must cut across modules, because a tag used in only one test file repeats the module grouping. It must also stay on a minority of the suite: `happy-path` on most scenarios filters nothing. Once you use a tag, put it on every scenario it describes, or filtering by it will miss some.
- **A `/` nests a tag.** The Tags sidebar files `ticket/ABC-123` under a `ticket` heading, which filters like a package, so a family of tags takes one row. Ticket tags are the family worth having: each one shows exactly one ticket's work in the report.
- **Keep step text short.** A t-string with two or three term refs reaches your line-length limit fast. Move detail into nested steps instead of one long sentence.

## Keeping it truthful

Step text may abstract, but it must never overstate.

- **A value in the text must match the body.** A quantity, date or amount you narrate is a claim about the data the step actually holds. `'three copies'` over `catalog={'Dune': 1}` is a lie, even when every assertion passes.
- **Everything a `then` claims must be asserted in it.** A `then` that says "…and recorded in the ledger" without such an assertion describes behavior nobody checked. Assert it, or drop the clause. A `then` that sets the value it asserts, or asserts a constant, checks nothing. The asserted value must come from the code under test.
- **What the `when` names must be what the body calls.** Narrate the action the step performs, not the one the scenario is loosely about. A common mistake: the `when` text reads like more arrangement, but its body arranges *and* makes the call the `then` reports. The action then appears nowhere in the report. Move the setup into a `given`.
- **"Each", "every", "both" and "all" are claims about every item.** A `then` or scenario name with one of these words must assert every item it covers. "Each slot becomes a term ref", backed by assertions on two of three slots, overstates. Assert them all, or narrow the text to what is checked.
- **Mark a scenario written before its implementation `xfail(strict=True)`** (or set `xfail_strict`). It reports as an expected failure, with its reason, steps and error. Once it passes, it fails the run, so you remember to remove the mark. A non-strict mark stays on working behavior and turns a later regression into an expected failure. An `xfail` on one `pytest.param` row is fine too.
- **Stale narration is a stale assertion.** When a change touches a step's *body*, re-read the step's *text* (and the scenario name) in the same edit, and update it if the behavior changed.
- **When narration and body disagree, the narration isn't automatically wrong.** The name may state the intended behavior while the body checks something weaker, or passes for a different reason. Then you have found a broken test: fix the body and keep the words. Weakening the narration to match turns a bad test into a spec that only looks truthful. Ask whether the body would fail if the name's promise were broken.

## Mechanical counterparts

The narration lint enforces the structural part of these rules. Turn it on with `pytest --given-lint` or `given_lint = true` in `[tool.pytest]`; `--no-given-lint` turns an ini-enabled lint off for one run. A *warn* finding prints in the terminal summary. Only an *error* finding fails the run.

| Rule | Default | Catches |
|---|---|---|
| `empty-step` | error | A step whose body does nothing: only constants or `pass`, or, for `when`/`then`, only an `attach(...)` call. |
| `then-without-check` | error | A `then` with no `assert` statement and no checking call. A checking call is one whose name starts with `assert` (`assert_totals(order)`, `result.assert_outcomes(...)`), or `pytest.raises` / `pytest.warns` / `pytest.fail`. Nothing else counts, not even `pytest.approx`. |
| `missing-phase` | warn | A passed scenario that doesn't cover all three phases. Fixture `@given`s and `Annotated[..., given(...)]` parameters count. |
| `check-outside-then` | warn | An `assert` inside a `given` or `when`. The `when` half of a `when_then` pair is exempt. |
| `action-in-then` | warn | No `when` performs an action, and a `then` folds the action into its assertion. |
| `unused-interpolation` | warn | A `with` step whose narration interpolates a `{name}` that its body never uses: a t-string interpolation, or a parametrize placeholder in a grouped scenario. |
| `tag-shadows-term` | warn | A scenario tag whose slug duplicates a glossary term. |
| `dead-term` | off | A glossary term that no scenario name, no step and no story sentence references. Off by default, because an unreferenced term is normal. Turn it on where every glossary term is meant to be used. |

You can override each rule's severity with the `given_lint_rules` ini. That and the rest of the setup are in the project documentation at <https://nwilbert.github.io/pytest-given/latest/configuration/narration-lint/>.

**A `then-without-check` finding on a step that does check is usually a naming problem.** The rule only recognizes an assertion helper by its `assert` prefix. So rename `check_totals` to `assert_totals` before you reach for the ignore list. A third-party matcher with another name (`result.stdout.fnmatch_lines(...)`) needs a real `assert` next to it, or an ignore entry.

**Treat a `missing-phase` warning as a prompt to restructure, not to suppress.** It nearly always marks a hidden `when`. Apply the constructor rule above, or show a parametrized input as `Annotated[..., given(Template('…'))]` so the inline block can narrate the action. A `given_lint_ignore` entry (`missing-phase: <node-id glob>`) is a last resort, and it costs more than it seems. An entry that suppresses nothing is a `stale-ignore` error, which can't be downgraded or ignored. So `pytest tests/one_file.py --given-lint` fails whenever the selection skips the suppressed test.
