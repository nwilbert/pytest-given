# `pytest_given` Marker — Design Spec

## Goal

Give every `@scenario` test a registered pytest marker, `pytest_given`, so pytest's own selection
can run the scenarios alone or leave them out:

```bash
pytest -m pytest_given --given-html          # a report without running the plain tests
pytest -m pytest_given --cov=mypkg           # code coverage of the scenarios alone
pytest -m "not pytest_given"                 # the plain tests alone
```

And say plainly what story coverage is for: discovering scenarios and their context, not checking
that the suite is complete. Code coverage of the scenarios is the tool for the second question.

## Background

`@scenario` sets a `_scenario` attribute on the test function; nothing makes it visible to pytest's
selection. A report, which holds only scenarios, therefore costs a run of the whole suite, and
there is no way to ask which code the scenarios exercise.

Story coverage gets read as that missing measurement. It isn't one: a sentence counts as covered
when one step's term refs include all of its terms, so a chip says a scenario *talks about* the
sentence, and nothing about how much behavior lies behind it. The reviewing skill calls an
uncovered sentence "a gap worth noting", which invites reading the chips as test coverage.

## Marker

- **Name: `pytest_given`.** The marker sits only on scenarios, so naming them in it is redundant;
  the import name is what a reader recognizes. An identifier, unlike `pytest-given`, so
  `pytest.mark.pytest_given` and `item.iter_markers('pytest_given')` work as for any other marker.
  (`-m` parses both forms.)
- **Registered** in `pytest_configure` with `config.addinivalue_line('markers', …)`, so
  `--strict-markers` accepts it and `pytest --markers` lists it.
- **Applied by the plugin**, from `pytest_itemcollected`, to every item whose function carries
  `@scenario` — every case of a parametrized one included. That hook runs before
  `pytest_collection_modifyitems`, where pytest deselects by `-m`. `capture/` stays free of pytest:
  the decorator keeps setting its attribute, and the plugin translates it into the marker.
- **Applied by the plugin only.** A hand-written `@pytest.mark.pytest_given` on a plain test makes
  it selectable as if it were a scenario but records nothing; the docs say the marker is applied
  for you, and nothing checks against the hand-written one.

## Uses

- **Scenario-only report runs.** `pytest -m pytest_given --given-json/--given-html/--given-md`
  writes the same report as a full run, since the report holds only scenarios. The lint is
  unaffected: its findings and `given_lint_ignore` entries concern scenarios, so leaving the plain
  tests out cannot make an entry stale.
- **Code coverage of the scenarios.** `pytest -m pytest_given --cov=mypkg`, or
  `coverage run -m pytest -m pytest_given`. It measures lines *run*, not lines a step *describes*:
  code a scenario's arrangement runs counts as covered though no step names it. So it is an upper
  bound on what the report documents. The useful reading is the difference against a full run:
  lines the suite covers but the scenarios don't are behavior only plain tests reach, which is
  invisible in the report.
- **The plain tests alone**, with `-m "not pytest_given"`.

## Story coverage is for discovery

One note, in each place that presents story coverage:

> Story coverage helps a reader find the scenarios behind a part of the flow, and see the flow
> behind a scenario. It is not a measure of how completely the suite tests the system: a covered
> sentence means a step talks about it, not that its behavior is tested. To ask what the scenarios
> exercise, measure code coverage of `-m pytest_given`.

- The site's `guide/domain-storytelling.md`, under "Coverage in the report".
- The authoring skill's `references/stories.md`, beside "An uncovered sentence is a signal, not an
  error".
- The reviewing skill's layer 4, whose "uncovered story sentence" bullet then reads as a pointer
  to a gap in the story's telling, not in the tests. Layer 3 gains the coverage difference above as
  a mechanical starting point for "Behavior without a scenario", next to the undecorated-tests
  query.

## Implementation touch points

- `plugin/collection.py` — `pytest_itemcollected` adds the marker; `plugin/options.py` (or the
  existing `pytest_configure`) registers it. `plugin/__init__.py` re-exports the new hook.
- `docs/site/configuration/pytest-options.md` — a "Selecting scenarios" section: the marker and
  the three uses.
- `docs/site/getting-started.md` — the scenario-only report run.
- The authoring skill's `references/api.md` — the marker; the navigating skill's `SKILL.md` —
  render the spec with `-m pytest_given` when a full run is slow.
- The story-coverage note in the three places above.
- `noxfile.py` — `self_report` runs `pytest tests -m pytest_given`.
- Self-report: decorate the test that states "every scenario carries the `pytest_given` marker".
- `CHANGELOG.md` — Added: the `pytest_given` marker on every scenario test.
- Regenerate `examples/self-report/`; its content should not change apart from the new scenario.

## Test coverage

- Integration (pytester): `-m pytest_given` runs the scenario and deselects a plain test;
  `-m "not pytest_given"` the reverse; every case of a parametrized scenario carries the marker;
  `--strict-markers` accepts it; a scenario-only run writes the same JSON scenarios as a full run.
