# Writing scenarios

When decorating a test with `@scenario`, the goal is a report that reads as a truthful behavioral spec.

## What to decorate

- **Convert behavior, not plumbing.** Decorate tests that assert a rule (a calculation, a validation, a dispatch decision). Leave trivial getters, constructors, and dataclass round-trips as plain tests — they add report noise, not behavior.
- **One scenario per rule, not per branch.** Decorate the test that best states the rule — the one whose body shows what its name claims, so the end-to-end test when a unit test covers the same rule — and leave its edge cases plain. A user-visible rule you add or change needs its scenario, or the report never shows it.
- **Sibling scenarios of one rule are one table.** Merge scenarios that share a step skeleton and vary one arrangement, or whose names negate each other ("the reviewer confirms, so it is rejected" / "the reviewer declines, so it is accepted"), into one parametrized scenario (see [Parameter tables](#parameter-tables)); plain tests of the rule that fit its steps become rows. Before you merge or delete a scenario, account for everything only it had:
  - an assertion: keep it, or name the scenario that still makes it;
  - an input the table holds fixed: a booking in another building is not just another "no clash" row;
  - a step that covers a story sentence or holds a term's last term ref: re-run the coverage check from [stories.md](stories.md).

## Phase structure

- **Every step maps to load-bearing code.** `given` arranges, `when` performs the one call under test, `then` asserts its result. Never write a placeholder step like `with given(...): pass` — a step with no code is a lie in the report. Delete it.
- **Put the system-under-test call in `when`, not folded into the `then` assertion.** Prefer `with when(...): result = sut(x)` then `with then(...): assert result == …` over `with then(...): assert sut(x) == …`.
- **One outcome per `then`.** When an action has two independent outcomes (a return value *and* a state change), give each its own sibling `then` step. A `then` narration that needs an "and" is two steps written as one.
- **When the construction *is* the action under test, `when` builds it and `given` shows only the input.** If a scenario asserts a property of a freshly loaded, parsed, or built object (`Order(lines)` computes its total, `parse(doc)` yields all rows), `given` holds and, when useful, `attach`es the raw input; `when` runs the constructor; `then` asserts on the result. A `given` that both arranges the input *and* constructs the object under test is the most common missed `when`.
- **Two phases is fine when honest — but rarer than it looks.** If the assertion inspects a *static property of the arranged state* (not a return value of an action), `given` + `then` is truthful and you shouldn't invent a `when`. Likewise a pure "constructing X raises" check needs no `given`.

## Parameter tables

A parametrized scenario renders as one narrated tree over a parameter table, and a reader uses that table as a decision table: one row per input combination, with its outcomes.

- **Step structure must not depend on parameter values.** Every row renders against the baseline case's step structure, so a conditional `with given/when/then(...)` on a parametrize value fails the run. When the steps genuinely differ per case, decline the merge with `@scenario(..., group_parametrized=False)`; when the cases are different behaviors rather than one behavior narrated two ways, split them into separate scenarios.
- **Narrate what varies with a t-string interpolating a bare name.** `when(t'the drink costs {price} euros')` leaves a `{price}` token in the step and a column holding each case's value. Keep everything else identical across cases — the sentence, the `attach` labels, the term refs — and bind a value you derive from a column to its own local before narrating it (`price = cup_size * 0.01`, then `{price}`).
- **A column must read on its own.** When the outcome depends on how a varied input relates to a fixed one, the column holds the relation (`hours_later`, `same_room`), not the varied input's own value (`existing_start=50` or `existing_room='B'` beside a new booking fixed in room A at hours 10 to 20 in another step). This applies to a merged table too: parametrizing the value an old step text happened to name is how such columns arise. Arrange the fixed side first, so the relation has something to refer to. Whole objects as columns fail the same way: a reader can't compare two `Booking(...)` reprs at a glance.
- **Never turn a label back into data.** The body may unpack a relation column the way its narration says (`'A' if same_room else 'B'` under "same room: {same_room}"). It never maps a descriptive label to the input (`{'40 hours later': 40}[shift]`), and no label column sits beside the data it describes. Either way, the report shows a claim that nothing checks against the input. A document is the exception, since it can't read as a column: parametrize a label, look the document up, and `attach` it, so the row shows both.
- **Contrast rows show what decides.** For each input that decides the outcome, include a row that changes only that input and flips the outcome, at the boundary where there is one (moved 10 hours later still shares an hour, 11 hours later does not). A table whose rows all share one outcome can't show which column matters, even when another scenario holds the flipped case. Only a column listing forms the rule treats alike needs no flip, and a flip that needs other steps stays in its own scenario.
- **A refusal is a row too.** `when_then` can't narrate a raise per row, so when accepted and refused inputs share the steps, catch the refusal in the `when` and assert it like any outcome:
  ```python
  with when(t'the {g["Guest"].low} books {nights} nights'):
      try:
          booking, refusal = book(room, nights), ''
      except BookingRefused as error:
          booking, refusal = None, str(error)
  with then(t'the booking is accepted: {accepted}'):
      assert (booking is not None) == accepted
  with then('a refusal names the minimum stay'):
      assert ('minimum stay' in refusal) == (not accepted)
  ```
  Keep `when_then` for a scenario whose every row refuses.
- **Outcomes are columns, asserted against.** An outcome that varies gets a column, named in a `then` that holds for every row (`assert (0 in result.clashes) == clashes` under "it clashes: {clashes}"), not an `if` on the column inside the step. The headline outcome gets its own column even when another column implies it (`settled_by=None` implies "no clash", but a reader looks for the clash). Columns follow the order the narration first shows them, so an input narrated in a `given` precedes an outcome in a `then`.

## Arrangement

- **Surface the arrangement as a `given`, don't hide it in the `when` or the assertion.** A module constant or a value built on the fly (a document string, a path, a list of rows) that the action consumes is bound in a `with given(...)` block, not passed as a literal into the `when`/`then`/`pytest.raises` call.
  - State-mutating setup calls (inserting credit, seeding a database) are arrangement too: a scenario with two `when` steps usually hides an arrangement in the first one.
- **Decide a fixture's `given` by what it holds.** Would you write a `given` for this value if you constructed it inline? A domain value the scenario is about (an actor, a document, an entity it acts on) is arrangement: decorate the fixture `@given('…')` under `@pytest.fixture`. Infrastructure (a `Glossary()`, `tmp_path`, a connection) stays a bare `@pytest.fixture`. Either way, an arrangement reads the same whether a scenario builds it inline or pulls a fixture.
- **A parametrized value can be a `given` too.** Its column already shows in the parameter table. When it reads as an arrangement the reader should see named up front, surface it via `Annotated[..., given(Template('… {col} …'))]` on that parameter; for a one-arg pure function either reading is honest.
- **Attach the concrete artifact a step can only describe.** When a step handles a multi-line value its text can only abstract — a source document, a config snippet, a rendered result — `attach('label', text)` it onto that step.
  - **An input document goes on the arranging `given`; an output document goes on the `then` that checks it.** Output is the case most often missed: the assertions only sample the result, so the attachment is the only place a reader sees all of it.
  - **Attach documents, not object dumps**, and skip it when the step text or the parameter table already carries the value, or the artifact is too big to read inline (a full HTML page). The exception is a genuine before/after: where a step digests a rich input to a small output, the input makes "only the first line survives" checkable.
  - Across parametrize cases, an attachment whose content varies becomes a column headed by its label.

## Expected raises

- **Keep pytest-given narration and real assertions separate.** Nest the vanilla `pytest.raises` inside the narration, never inside a narration-named helper, and exempt tests from lint rules that forbid nested `with` statements (ruff `SIM117`).
- **Narrate an expected raise as `when_then`.** `with when_then('the action', 'an `InsufficientCredit` error is raised'), pytest.raises(Exc, match=…): sut(x)` emits a `when` wrapping the call and a sibling `then`, recorded once `pytest.raises` swallows the error.
  - **Write the `then` as a real outcome.** Name the exception type and, when `match=` pins a specific message, say what it reports in domain terms (`'the shortfall amount is reported'`) — never a bare `'it raises'`.
  - **Check a message with several details in its own `then`**: `pytest.raises(E) as excinfo` under the `when_then`, then `with then('the error names …'): assert '…' in str(excinfo.value)`.
  - **The pin must be as specific as the `then`.** A `then` promising message details (the offender, a suggestion, a file:line) needs a `match=` that only a message with that detail passes; `match='column'` under "names the missing column" lets the detail regress unnoticed. An alternation (`match=r'odd|dangling|ends'`) is only as strong as its weakest branch: pin the detail that tells sibling refusals apart.

## Vocabulary and tags

- **Narrate in glossary vocabulary.** Reference terms through handles in t-string step text — `t'a {g["Room"].low} is booked'` ([glossaries.md](glossaries.md)) — so they render as kind-colored words and feed the Glossary tab's per-term filter. Use `.low` mid-sentence and the bare handle to start a sentence. Pick a term for its meaning, not its word: a ref whose definition isn't what the sentence means links the reader to the wrong row. (Skip this rule if the project has no glossary yet.)
- **The code speaks the language too.** Each referenced term should be reflected in the naming within the step: the body and the SUT names it directly calls. `File glossary` over a `FileGlossary` call matches by design (term names are natural language), but `{g["Reservation"]}` over code that only knows `Booking` is language drift — rename one side.
- **Tag orthogonally to the glossary.** A tag that restates a term is redundant — filter by the term instead. `tag-shadows-term` catches literal collisions, not a tag naming a feature area the glossary covers under a different word (`markdown` over scenarios referencing `File glossary`).
- **Expect tagging to be sparse.** Tags carry only what the glossary can't: behavior (`validation`) and mechanism (`parametrization`). A tag must cut across modules (one confined to a test file repeats the module grouping) and stay a minority of the suite — `happy-path` on most scenarios filters nothing. Once used, a tag goes on every scenario it describes, or filtering by it under-reports.
- **A `/` nests a tag.** The Tags sidebar files `ticket/ABC-123` under a `ticket` heading that filters like a package, so a family of tags costs one row. Ticket tags are the family worth having: they open exactly one ticket's work in the report.
- **Keep step text short.** A t-string with two or three term refs reaches your line-length limit fast; move detail into the node structure rather than one long sentence.

## Keeping it truthful

Step text may abstract; it must never overstate.

- **A value in the text must match the body.** A quantity, date, or amount you narrate is a claim about the data the step actually holds: `'three copies'` over `catalog={'Dune': 1}` is a lie even when every assertion passes.
- **Everything a `then` claims must be asserted in it.** A `then` reading "…and recorded in the ledger" with no such assertion is fabricated behavior — assert it, or drop the clause.
- **What the `when` names must be what the body calls.** Narrate the action the step performs, not the one the scenario is loosely about. The frequent slip: a `when` reading as more arrangement over a body that arranges *and* makes the call the `then` reports, so the action reaches the report nowhere. Move the setup into a `given`.
- **A universal quantifier is a claim about every item.** A `then` or scenario name saying "each", "every", "both", or "all" must assert every item it ranges over — "each slot becomes a term ref" backed by assertions on two of three slots overstates. Assert them all, or narrow the text to what is checked.
- **Mark a scenario written ahead of its implementation `xfail(strict=True)`** (or set `xfail_strict`). It reports as an expected failure, with its reason, steps and error, and fails the run once it passes, so the mark comes off. A non-strict mark stays on working behavior and turns a later regression into an expected failure. An `xfail` on one `pytest.param` row is fine too.
- **Stale narration is a stale assertion.** When a change touches a step *body*, re-read that step's *text* (and the scenario name) in the same edit and update it if the behavior shifted.
- **When narration and body disagree, the narration is not automatically the mistake.** A name stating the intended behavior over a body that checks something weaker, or passes for a different reason, has found a broken test: fix the body, keep the words. Editing the narration down launders a bad test into a truthful-looking spec. Ask whether the body would fail if the name's promise were broken.

## Mechanical counterparts

The narration lint (`pytest --given-lint`, or `given_lint = true` in `[tool.pytest]`; `--no-given-lint` turns an ini-enabled lint off for one run) enforces the structural subset of these rules. A *warn* finding prints in the terminal summary; only an *error* finding fails the run.

| Rule | Default | Catches |
|---|---|---|
| `empty-step` | error | A step whose body does nothing — only constants/`pass`, or, for `when`/`then`, only an `attach(...)` call. |
| `then-without-check` | error | A `then` with no `assert` statement and no checking call — a call whose name starts with `assert` (`assert_totals(order)`, `result.assert_outcomes(...)`), or `pytest.raises` / `pytest.warns` / `pytest.fail`. Nothing else counts, `pytest.approx` included. |
| `missing-phase` | warn | A passed scenario that doesn't cover all three phases. Fixture `@given`s and `Annotated[..., given(...)]` parameters count. |
| `check-outside-then` | warn | An `assert` inside a `given` or `when` (the `when` half of a `when_then` pair is exempt). |
| `action-in-then` | warn | No `when` performs an action and a `then` folds the action into its assertion. |
| `unused-interpolation` | warn | A `with`-anchored step whose narration interpolates `{name}` that the step body never uses — a t-string interpolation, or a parametrize placeholder in a grouped scenario. |
| `tag-shadows-term` | warn | A scenario tag whose slug duplicates a glossary term. |
| `dead-term` | off | A glossary term referenced by no scenario narration, no step narration and no story sentence. Off by default because an unreferenced term is normal; opt in where the glossary is meant to be fully exercised. |

Severities are overridable per rule via the `given_lint_rules` ini; that and the rest of the setup are in the project documentation at <https://nwilbert.github.io/pytest-given/latest/configuration/narration-lint/>.

**A `then-without-check` finding on a step that does check is usually a naming problem.** The rule knows an assertion helper only by its `assert` prefix, so rename `check_totals` to `assert_totals` before reaching for the ignore list. A third-party matcher under another name (`result.stdout.fnmatch_lines(...)`) needs a real `assert` beside it, or an ignore entry.

**Treat a `missing-phase` warning as a prompt to restructure, not to suppress.** It nearly always marks a hidden `when`: apply the constructor rule above, or surface a parametrized input as `Annotated[..., given(Template('…'))]` so the inline block can narrate the action. A `given_lint_ignore` entry (`missing-phase: <node-id glob>`) is a last resort, and costs more than it looks: an entry that suppresses nothing is a `stale-ignore` error that can't be downgraded or ignored, so `pytest tests/one_file.py --given-lint` fails whenever the selection skips the suppressed test.
