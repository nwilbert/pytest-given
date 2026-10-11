# Completeness audit: what the report doesn't say

Start from the implementation and ask what the report fails to say. Limit the search to the code the change touches.

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
