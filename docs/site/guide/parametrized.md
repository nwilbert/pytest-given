# Parametrized scenarios

Parametrized tests are automatically grouped into a single scenario with a parameter table. The grouped step tree comes from a **baseline case** — the first that passed — and anything varying across cases is promoted into a column of the table: a parametrize argument, a t-string interpolation whose value differs per case (the step keeps a `{name}` placeholder pointing at the column), and an attachment whose payload differs (the step keeps a content-less badge).

```python
@scenario('Pricing')
@pytest.mark.parametrize('euros,expect', [(1, False), (2, True), (3, True)])
def test_pricing(machine, euros, expect):
    with when(t'I insert ${euros}'):
        can_buy = euros >= machine['price']
    with then(t'can_buy is {expect}'):
        assert can_buy == expect
```

For a parametrized **scenario name**, use `pytest_given.Template` — deferred substitution against the parametrize columns:

```python
from pytest_given import Template, scenario

@scenario(Template('Brew {cup_size} ml'))
@pytest.mark.parametrize('cup_size', [200, 300])
def test_brew(cup_size):
    ...
```

The `Template` name and the glossary-handle t-string name from the [step-text table](step-text.md) don't combine: a title needing both a term ref and a per-case value isn't expressible today.

What a column cannot carry is a case that narrates a *different sentence*. When the narration genuinely branches per case, add `group_parametrized=False` to the `@scenario` above to decline the merge. Each case then becomes its own scenario with no parameter table, titled by its parametrize id — `Brew 200 ml [200]` for the `Template` above, whose placeholders are substituted per case first (a plain-string name is suffixed the same way). Every case carries the id, including one whose name already renders its values. On a test that isn't parametrized the argument raises at collection.

**Six authoring forms are rejected outright** in a parametrized scenario, because each would make the grouped tree lie. Every one fails the run and writes no report — the message names the fix:

| # | Rejected | Fix |
|---|---|---|
| 1 | A plain `str` (usually an f-string) whose text differs per case | Narrate with a t-string so the varying part is a placeholder, not case 1's text |
| 2 | A varying interpolation that isn't a bare name — `t'{cup_size * 0.01}'`, `t'{m.balance}'` | Bind it to a local and narrate that local |
| 3 | An interpolation naming a parametrize column that no longer holds the case's value | Rename the local that rebound the name — or, if the body mutated the value in place before narrating it, bind the result to its own name and narrate that |
| 4 | A term ref that names a different term or reads differently between cases — including one bound to a parametrize column | Split the term ref from the value: `given(t"{pg['Customer']} {name} places an order")` |
| 5 | A step whose set of `attach` labels differs between cases | Keep the label constant and let the content vary — that's what the attachment column is for |
| 6 | Passed cases that narrate different templates — a different step structure, a differently shaped narration, different wording, a different interpolated expression, or a step pinned to different activities | Decline the merge with `@scenario(..., group_parametrized=False)` and let each case be its own scenario (for a varying `activity=` pin, give the step one activity instead) |

