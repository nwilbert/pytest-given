# Markdown report

The Markdown report is a run's scenarios as plain Markdown: one section per scenario, with its steps, attachments, parameter table and error. It reads well in a terminal, shows up as a readable diff in a pull request, and costs an AI agent a fraction of the tokens of the test code it narrates. The [full example](#example) at the end of this page shows one.

## Writing it

```bash
pytest --given-md              # print it to stdout
pytest --given-md=report.md    # write it to a file
```

Printed to stdout, the report sits between `<!-- pytest-given:md:start -->` and `<!-- pytest-given:md:end -->` markers, which separate it from pytest's own output. The report covers whatever the run selected, so pytest's `-k`, `--lf` and node IDs narrow it as usual.

To render it from a saved JSON report instead, without running the tests, use the [standalone CLI](cli.md): `pytest-given report report-data.json --format md`.

## Reading it

- **The heading** is the scenario title, led by its status: ✓ passed, ✗ failed, ○ skipped, ⊗ expected failure. A [parametrized scenario](guide/parametrized.md) adds its number of cases.
- **The line below it** points at the test as `file.py:line::test_name`, then lists the scenario's tags and any skip or xfail reason. The examples are rendered with `given_md_lines = false`, so their anchors carry no line (see [Diffs](#diffs)).
- **Steps** are a list, each led by its phase in bold. Steps recorded inside another step, like those of a helper function, are nested under it. A [term ref](guide/glossary.md) shows in guillemets, like `«room»`.
- **Attachments** follow their step after a 📎. A short one sits on the same line, and a longer one goes in a code block below it.
- **A parametrized scenario** narrates its cases once, with `{placeholders}` where they differ, and then a parameter table. The table leads with a case ID column only when some case has a custom ID. It ends with a status column only when the cases differ in status. A failed case's error and any attachment too long for its cell follow the table, keyed by the row.
- **An error** is a quote: the first line of the message, then the innermost frame of your code.

The Markdown report holds only scenarios. The glossary and the domain stories appear in the HTML report and the JSON, along with source links and full tracebacks.

## Diffs

Commit the Markdown report, and a pull request shows what changed in the narration next to the code that changed it. This project commits its own [self-report](https://github.com/nwilbert/pytest-given/blob/main/examples/self-report/self-report.md) for that reason.

By default, every anchor carries a line, so inserting one test changes the anchor of every scenario below it in the file. Set `given_md_lines = false` (or pass `--no-given-md-lines`) to leave the lines out. When diffing two reports rendered by the CLI, pass `--no-lines` to both.

## Reviewing narration

Add `--given-md-source` to end each scenario with its test function, each line under its number in the file. Step text and step body then sit side by side, which makes it quick to check that the narration says what the code does. Only the test function is shown, not the step fixtures or helpers it uses.

All Markdown flags are listed under [pytest options](configuration/pytest-options.md#flags).

## Example

The Coffeeshop example's report, as committed in [`examples/coffeeshop/coffeeshop.md`](https://github.com/nwilbert/pytest-given/blob/main/examples/coffeeshop/coffeeshop.md), where GitHub also shows it rendered. The [Examples](examples.md) page links every example's Markdown report.

````markdown
--8<-- "examples/coffeeshop/coffeeshop.md"
````
