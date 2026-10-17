# Completeness audit: what the report doesn't say

Start from what the project promises, then from the implementation, and ask what the report fails to say. Limit the search to the code the change touches. For a review of the whole suite, the promises limit the scope the way a diff does for a change.

- **Promises without a scenario.** A project states its behavior in its own words wherever it keeps them: release notes or a changelog, the user documentation, a glossary row that makes a claim ("X takes precedence over Y", "must be unique"), a design spec that cites the report. A spec's rules each need a scenario under the tag it cites, and its findings or decision tables list the rules row by row. Check that a scenario demonstrates each claim, the newest first, such as a changelog's unreleased entries. These gaps matter most, because readers trust the promise. A claim narrated only in part, such as the fix without the way to opt out, is a finding too. Prefer adding a scenario to weakening the claim. When a scenario contradicts a glossary row, the row is a false claim.
- **Behavior without a scenario.** Go through the branches of the code under review that carry behavior: a scoping rule, a precedence decision, a fallback path. Check that each has a scenario that names it. A branch that only an undecorated test covers is invisible in the report. A branch with no test at all rates higher, because the spec looks complete while hiding it. A rule narrated at the wrong layer is also a finding. There are two cases. In one, several callers each repeat a rule that a shared function decides. In the other, a unit scenario's title claims what the system does, but its body only calls internal code, and no other scenario shows a run reaching that code. The second case is a false claim: decorate a test that proves the title instead. Look among the undecorated tests first; the right one often exists already.

  List the undecorated tests in test files that hold a scenario, and the test files that hold none:

  ```bash
  pytest <selection> -m pytest_given --given-json=report.json
  pytest <selection> -m "not pytest_given" --collect-only -q > plain.txt
  # undecorated tests next to narrated ones
  jq -r --rawfile plain plain.txt '
    [.scenarios[].id | split("::")[0]] as $files
    | $plain | split("\n") | map(select(contains("::")) | sub("[[].*"; "")) | unique[]
    | select(split("::")[0] | IN($files[]))' report.json
  # test files without a single scenario
  jq -r --rawfile plain plain.txt '
    [.scenarios[].id | split("::")[0]] as $files
    | $plain | split("\n") | map(select(contains("::")) | split("::")[0]) | unique[]
    | select(IN($files[]) | not)' report.json
  ```

  In a large suite the first list is long: read the test names for rules a user would recognize, and skip the edge cases. In the second, a file that drives a user-facing surface end to end, such as a command line or a configuration option, is the likelier gap.

  For the code itself, compare the code coverage of `pytest -m pytest_given` with a full run's. Lines only the full run covers are behavior only plain tests reach.
- **Parameter tables that can't show what decides.** For each input that decides a parametrized scenario's outcome, some row should change only that input and flip the outcome. Without such a row, the table only lists examples, and the rule that decides between them stays unnarrated. Ask for the contrast row, at the boundary if there is one, instead of splitting the table into one scenario per row. A refusal can be a contrast row too, and a sibling scenario with the flipped outcome doesn't make up for a missing row.
