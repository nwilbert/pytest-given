# Parametrized scenarios

## Grouping

pytest-given groups all cases of a parametrized test into one scenario with a parameter table. The report shows the steps once, taken from the first case that passed (the **baseline case**). Anything that differs between cases becomes a column in the parameter table:

- a parametrize argument
- a t-string value that differs between cases. The step shows a `{name}` placeholder that points to the column.
- an attachment whose content differs between cases. The step shows a badge that points to the column, instead of the content.

The columns appear in the order the narration first shows them: the scenario name, then the steps from top to bottom. Inputs narrated in a `given` come before outcomes narrated in a `then`. A parametrize argument that no step narrates stays next to the argument before it.

```python
@scenario('Pricing')
@pytest.mark.parametrize('euros,expect', [(1, False), (2, True), (3, True)])
def test_pricing(machine, euros, expect):
    with when(t'I insert ${euros}'):
        can_buy = euros >= machine['price']
    with then(t'can_buy is {expect}'):
        assert can_buy == expect
```

## Scenario names

To put parameter values into the scenario name, use `pytest_given.Template`. Its placeholders are filled in from the parametrize arguments:

```python
from pytest_given import Template, scenario

@scenario(Template('Brew {cup_size} ml'))
@pytest.mark.parametrize('cup_size', [200, 300])
def test_brew(cup_size):
    ...
```

A name can't contain both a parameter value and a glossary term ref. A `Template` name has no term refs, and a t-string name (see [Step text](step-text.md)) can only contain glossary handles.

## Declining the merge

Grouping only works when all cases have the same steps, with different values. If the steps really differ from case to case, add `group_parametrized=False` to `@scenario`.

Each case then becomes its own scenario, without a parameter table. Its name ends with the parametrize id, like `Brew 200 ml [200]` for the example above. A `Template` name gets its placeholders filled in first; a plain string name gets the id added the same way. Every case gets the id, even if its name already shows its values.

`group_parametrized=False` on a test that isn't parametrized raises an error at collection.

## Rejected authoring forms

Some ways of writing steps would make the grouped scenario show the wrong text. pytest-given rejects them: the run fails, no report is written, and the error message tells you how to fix it.

| # | Rejected | Fix |
|---|---|---|
| 1 | A plain string (usually an f-string) whose text differs between cases | Use a t-string, so the changing part becomes a placeholder instead of showing the first case's text |
| 2 | A changing t-string value that isn't a plain variable name, like `t'{cup_size * 0.01}'` or `t'{m.balance}'` | Assign it to a local variable and use that in the t-string |
| 3 | A t-string value named after a parametrize argument, when the variable no longer holds that argument's value | If you reassigned the variable, give the new value a new name. If the test changed the value in place, assign the result to a new variable and use that |
| 4 | A term ref that names a different term or reads differently between cases, including one that takes its text from a parametrize argument | Keep the term ref and the value apart: `given(t"{pg['Customer']} {name} places an order")` |
| 5 | A step whose `attach` labels differ between cases | Keep the labels the same and let only the content differ; the parameter table gets a column for it |
| 6 | Passed cases whose steps differ in any other way: different steps, different wording, a different t-string expression, or different pins | Add `group_parametrized=False` to `@scenario` so each case becomes its own scenario. For pins that differ, pin the step to one sentence instead |
